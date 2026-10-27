# epoch-open

Free replacement software for a BioTek Epoch microplate spectrophotometer with a Take3
micro-volume plate, for RNA/DNA quantification.

The lab owns the instrument. The vendor software's licence activations are exhausted, so
the instrument was unusable. This project writes a new program that talks to the reader directly. 

It does not modify, patch, bypass or inspect the vendor software, and nothing here depends on it at runtime.

## Who uses this

The daily user is a lab technician who is not a computer person. That constrains the
design more than anything technical does:

- Ships as a **single `.exe`** on Windows. Double-click. No Python, no install, no
  console window, no config files to edit.
- Main screen is a **Take3 plate layout**. Click to mark loaded spots, copying the
  Gen5 picker already known.
- Three buttons: **Read blank**, **Read samples**, **Save results**.
- Results export to **xlsx**, the same format Gen5 produces, so everything done with
  the file afterwards is unchanged.
- Sample type (dsDNA / ssDNA / RNA) is a dropdown, defaulted to whatever the lab uses most.
- Problems are reported in plain language next to the affected well, never as an error
  code or a traceback.

## Status

| Piece | State |
|---|---|
| Quantification math (`epoch_open/quant.py`) | Done, reproduces this lab's Gen5 numbers |
| xlsx export (`epoch_open/xlsx.py`) | Done, no dependencies, verified opens in LibreOffice |
| Take3 layout (`epoch_open/take3.py`) | Done, confirmed from the factory sheet (A2-H3) |
| Reader interface + simulator (`epoch_open/reader.py`) | Done |
| Technician GUI (`epoch_open/gui.py`) | Working against the real instrument |
| Test suite | 155 tests passing |
| Protocol capture procedure (`docs/CAPTURE.md`) | No longer needed |
| Serial protocol decode | **Done** — reads confirmed on the instrument |
| USB transport | **Solved** — reader is FTDI virtual COM, pyserial talks to it (`docs/FINDINGS.md`) |
| Instrument driver | Connect, carriage, capabilities, batched multi-wavelength reads |
| Validated against Gen5 | **Yes** — 0.5% on neat ladder, same drops (`docs/VALIDATION.md`) |
| Windows .exe | **Built and working** on the lab laptop: simulation fallback, reader detection, read, export |
| Excel compatibility | Verified — exports open in Excel without a repair prompt |

The software is finished and working end to end on the lab laptop. What remains is not
engineering: let the technician use it, and measure blank drift over a long session
(see the open questions at the end of `docs/VALIDATION.md`).

## The approach

1. **Capture** the serial conversation between Gen5 and the reader during one real Take3
   read, while the Gen5 trial still runs. See `docs/CAPTURE.md`. **Time-critical.**
2. **Decode** the captured bytes into a command set: move carriage, select wavelength,
   read, return values. [PyLabRobot](https://github.com/PyLabRobot/pylabrobot) already has
   a `BioTekPlateReaderBackend` whose version/serial/door commands reportedly work on an
   original Epoch; its read commands do not, apparently because the command set varies by
   firmware. The capture closes exactly that gap, and the result is worth contributing
   back upstream.
3. **Driver** — a small Python module over the reader's USB virtual COM port. The
   original disks confirm the Epoch is an FTDI USB-to-serial device, so this is
   plain pyserial over a COM port; see `docs/FINDINGS.md`.
4. **GUI** — Tkinter, bundled with PyInstaller into one `.exe`.
5. **Validate** — run the same plate through the captured Gen5 reference numbers and this
   software, and confirm they agree well by well before it is used for real samples.

## Quantification

Recovered from this lab's own Gen5 exports and verified against them: subtract the
320 nm reference from each measurement wavelength, subtract the per-well blank, scale
from the 0.5 mm Take3 path to 1 cm, multiply by the extinction factor. For dsDNA that
reduces to `ng/uL = A260 x 1000`.

The derivation, and two assumptions this project got wrong before the real exports
arrived, are in `docs/QUANTIFICATION.md`.

## Using it with a different instrument

Nothing is compiled in: copy `epoch_open.example.json` to
`epoch_open.json` beside the program and edit it. See `docs/FOR_OTHER_LABS.md`.
The one setting that genuinely matters is the pathlength table from your own
Take3's data sheet.

## Running it today

    python3 run_gui.py

Needs tkinter (bundled with Python on Windows; on Debian/Ubuntu
`apt install python3-tk`).

**Without an instrument it will not produce numbers.** The window opens, the plate
can be laid out and a saved file can be reopened, but the read buttons are greyed
out and an amber badge says to switch the reader on. It used to fall back to a
built-in simulator, which meant an Epoch that was merely switched off gave a screen
full of invented values behind a warning banner — one misread banner away from
simulated figures in a lab notebook.

The simulator is still there for development and for reviewing the screen without
hardware, but it has to be asked for, and anything it produces is labelled
simulated on screen and inside any file it saves:

    python3 run_gui.py --sim

The order you switch things on does not matter. If the reader is not there at
startup the program keeps looking for it every few seconds, turns the badge green
by itself once it answers and enables the read buttons, so there is no need to
restart it. If the reader stops answering mid-session the badge says so and
reading is disabled again, rather than quietly reverting to simulated numbers.

## Running the tests

    python3 tests/run_tests.py     # no dependencies
    python3 -m pytest tests/ -q    # if pytest is installed

## Layout

    epoch_open/quant.py    quantification, pathlength correction, purity ratios
    tests/                 test suite and a dependency-free runner
    docs/CAPTURE.md        how to capture the protocol from the running Gen5
    docs/FINDINGS.md       what the original instrument disks established
    captures/             (empty) .pcapng files and Gen5 reference numbers go here
