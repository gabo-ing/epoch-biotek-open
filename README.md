# Epoch Multispectral + TAKE3 - open software

Free MultiOS replacement software for a BioTek Epoch microplate spectrophotometer:
RNA/DNA quantification on a Take3 micro-volume plate, and colorimetric assays
against a standard curve in ordinary transparent 96-well plates.

Inspiration: Our lab owns the instrument but vendor software's licence activations were exhausted. As the instrument was not usable without the software, a new program was written. This program talks to the reader directly AND can be used on Linux/Windows

It does not modify, patch, bypass or inspect the vendor software, and nothing here depends on it at runtime.

There are two programs here, sharing one driver:

| Program | For | Plate |
|---|---|---|
| **epoch-take3** (`run_take3.py`) | RNA/DNA/protein quantification at 260/280 nm | Take3 micro-volume, 16 spots |
| **epoch-multispectral** (`run_multispectral.py`) | Colorimetric assays against a standard curve -- IAA/Salkowski at 530 nm, Bradford, MTT, ELISA | Ordinary transparent 96-well |

They share the serial driver, the plate geometries, the Excel writer and the
whole look (`epoch_open/ui.py`). What differs is the arithmetic: epoch-take3
computes concentration from physics, epoch-multispectral interpolates it from
standards measured in the same run. See `docs/MULTISPECTRAL.md`.

## Who uses this

This is focused for lab technicians/students/PostDocs/etc. That's why:

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

## epoch-take3 MUST be used with a TAKE3 plate, with its provided pathlenght table sheet (should have come with the TAKE3 plate). If not available, it can be used with standard 0.5 correction.

**epoch-multispectral is the opposite: never put a Take3 plate in it.** Those
assays use acidic reagents that would damage the plate irreversibly. Use a
plain transparent 96-well plate -- see `docs/MULTISPECTRAL.md`.

## Status

| Piece | State |
|---|---|
| Quantification math (`epoch_open/quant.py`) | Done, reproduces this lab's Gen5 numbers |
| xlsx export (`epoch_open/xlsx.py`) | Done, no dependencies, verified opens in LibreOffice |
| Take3 layout (`epoch_open/take3.py`) | Done, confirmed from the factory sheet (A2-H3) |
| Reader interface + simulator (`epoch_open/reader.py`) | Done |
| Take3 GUI (`epoch_open/gui.py`) | Working against the real instrument |
| Shared chrome + window fitting (`epoch_open/ui.py`) | Done -- palette, drawn buttons, screen fitting, ttk theme |
| Curve math (`epoch_open/curve.py`) | Done -- least squares, r2, residuals, range warnings |
| Multispectral GUI (`epoch_open/gui_curve.py`) | Reads a flat 96-well plate on the real instrument; agrees with Gen5 to 0.001 AU, addressing verified with a loaded pattern |
| Colorimetric assay itself | **Unverified** -- no standard curve has been measured on real reagents |
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

Uses the same method as Gen5 (verified on the same samples): subtract the
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

## What it needs

| | |
|---|---|
| Python | 3.10 or newer (it uses `X \| None` annotations). Run here on 3.13 |
| `pyserial` | the only third-party library, and only to talk to the instrument |
| tkinter | for the window. Bundled with Python on Windows and macOS; a separate package on Linux |
| `pyinstaller` | only to build the Windows `.exe` or the macOS `.app` |

Everything else — the Excel writer, the config file, the test runner — is written
against the standard library on purpose, so there is as little as possible to
break or to reinstall in five years.

Reading a plate also needs the **FTDI VCP driver** on Windows. Linux needs nothing:
`ftdi_sio` is in the kernel.

## Installing

### Windows (what the lab actually uses)

1. **Python** from <https://www.python.org/downloads/>, ticking
   **"Add python.exe to PATH"** during setup. Do not use the Microsoft Store
   build: it has shipped without tkinter, and the window will not open.
2. **FTDI VCP driver** from <https://ftdichip.com/drivers/vcp-drivers/>, installed
   **before** the reader is plugged in. 
3. **The source**: on GitHub use *Code -> Download ZIP*, and unpack it somewhere
   stable such as `C:\EpochTake3\` — not Downloads, where it will be tidied away.
4. **Build**: double-click `build_windows.bat`. It checks Python and tkinter,
   installs `pyserial` and `pyinstaller`, and

## After installation, the binaries are left as `dist\EpochTake3.exe` and `dist\EpochMultispectral.exe`.

The exe is self-contained: the technician needs no Python and no console. Put it
somewhere stable and make a Desktop shortcut. `docs/WINDOWS.md` has the checks to
run before handing it to anyone.

### Linux

    sudo apt install python3-tk python3-serial      # Debian/Ubuntu
    sudo usermod -aG dialout $USER                  # then log out and back in

The `dialout` group is what grants access to the serial port. Without it the
program will find the reader and still be unable to open it.

### macOS

Install Python from <https://www.python.org/downloads/> rather than using the
`python3` that ships with macOS, which has come with a Tk too old to draw this
correctly. Homebrew's Python does not include Tk at all — it is packaged
separately as `brew install python-tk@3.13`, and
without it the program stops with `ModuleNotFoundError: _tkinter`.

#### Running without building

Homebrew's Python refuses a system-wide `pip install` outright — PEP 668,
`error: externally-managed-environment` — so install into a virtual
environment. This is also the fastest way to a working program, since it
skips PyInstaller entirely:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install pyserial
    python3 run_take3.py

The `source` line is needed once per terminal; after that the program starts
with the last line alone.

#### Building the apps

`bash build_macos.sh` produces `dist/EpochTake3.app` and
`dist/EpochMultispectral.app`. It makes its own virtual environment
(`.venv-build`) and installs nothing system-wide. PyInstaller cannot
cross-compile, so it has to run on a Mac. The result is unsigned, so the first
launch is refused with "cannot be opened because the developer cannot be
verified" — right-click the app, choose Open, then Open again, which is
remembered. Signing it properly needs an Apple Developer ID.

No driver is needed: the FTDI driver has been part of macOS since 10.9, and the
reader is found by its USB serial number rather than by any device path, so
`/dev/cu.usbserial-*` works without changes.

The interface runs on macOS and draws correctly: sharp on a Retina screen, the
layout tightening by itself for the shorter usable height
(`docs/img/gui-macos.png`).

**The build works.** Both apps were built on 5 November 2026 on macOS 26.6
(arm64) with Homebrew Python 3.15.2, Tk 9.1 and PyInstaller 6.22.3 — the
newest of everything, which was the combination most likely to break.

What has **not** been tried is a Mac talking to an actual Epoch. One warning
in the build is worth knowing about before that is attempted:

    WARNING: Ignoring .../IOKit.framework/IOKit imported from
             serial/tools/list_ports_osx.py
    WARNING: Ignoring .../CoreFoundation.framework/CoreFoundation

`list_ports_osx.py` is how pyserial enumerates serial ports on macOS, so it
is exactly how the reader gets found. PyInstaller did not bundle those two
frameworks. That is almost certainly fine — they are system frameworks at
absolute paths present on every Mac, loaded by ctypes at runtime — but it is
the one warning that lands on the one path that matters.

So test it deliberately: with the reader plugged in, if the `.app` shows no
instrument, run `python3 run_take3.py` from source in the same state. Source
finding it while the app does not would place the fault in the packaging, and
those two frameworks are where to look. (The `Cfgmgr32`, `Advapi32` and
`setupapi` warnings in the same build are pyserial's Windows backend and mean
nothing here.)

## Running it today

    python3 run_take3.py            nucleic acids on a Take3 plate
    python3 run_multispectral.py    colorimetric assays in a 96-well plate

**Without an instrument it will not produce numbers.** The window opens, the plate
can be laid out and a saved file can be reopened, but the read buttons are greyed
out and an amber badge says to switch the reader on. 

There's a built-in simulator for development and for reviewing the screen without
hardware, but it has to be asked for, and anything it produces is labelled
simulated on screen and inside any file it saves:

    python3 run_take3.py --sim
    python3 run_multispectral.py --sim

The order you switch things on does not matter. If the reader is not there at
startup the program keeps looking for it every few seconds, turns the badge green
by itself once it answers and enables the read buttons, so there is no need to
restart it. If the reader stops answering mid-session the badge says so and
reading is disabled again, rather than quietly reverting to simulated numbers.

## Running the tests

    python3 tests/run_tests.py     # no dependencies
    python3 -m pytest tests/ -q    # if pytest is installed

## Layout

    epoch_open/reader.py   serial driver, plate reads, both simulators
    epoch_open/plates.py   Take3 and standard 96-well geometries
    epoch_open/ui.py       the look both programs share, and window fitting
    epoch_open/launch.py   starting a program, and the missing-tkinter message

    epoch_open/quant.py    Take3: quantification, pathlength, purity ratios
    epoch_open/gui.py      Take3: the screen

    epoch_open/curve.py    multispectral: standard curves and their warnings
    epoch_open/gui_curve.py  multispectral: the screen

    epoch_open/xlsx.py     both workbooks, no dependencies
    tests/                 test suite and a dependency-free runner
    docs/MULTISPECTRAL.md  how the curve program works and what it refuses
    docs/CAPTURE.md        how to capture the protocol from the running Gen5
    docs/FINDINGS.md       what the original instrument disks established
