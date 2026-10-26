# Using this with a different Epoch and a different Take3

Nothing needs recompiling, and you do not have to edit any file by hand.

The header shows which Take3 is loaded and whether its calibration sheet is in:

    Placa Take3  243819  calibrada          <- values from the plate's data sheet
    Placa Take3  999999  SIN CALIBRAR       <- falling back to 0.5 mm nominal

Press **Cambiar placa...** to register a plate. The dialog is laid out like the
Take3 Pathlength Data Sheet, rows A-H against columns 2 and 3, so the numbers can
be copied straight across. It is saved to `epoch_open.json` beside the program and
used from then on.

If you have no sheet, **Usar 0,5 mm nominal** registers the plate without one. The
header then says SIN CALIBRAR, because concentrations can be off by around 2%.

The file can also be written by hand; copy `epoch_open.example.json` to
`epoch_open.json` and edit it.

## 1. Your reader

Leave `reader_serial` as `null` and the software takes whichever Epoch answers.
Set it to your reader's serial number only if more than one is attached and the
right one has to be chosen.

## 2. Your Take3 plate — the one that matters

Each Take3 ships with a **Take3 Pathlength Data Sheet** listing the measured
pathlength of all 16 micro-spots, around 0.5 mm each. The vendor software asks for
these when a plate is added, and divides by them. Copy them into `pathlengths_mm`.

If you leave the defaults at 0.5000, results are computed against the nominal
pathlength, which is what the vendor software does for a plate whose sheet was
never entered. On the plate this was developed with, that costs up to 2.4% on the
worst well.

Set `plate_serial` to your plate's number so the output records which plate
produced the numbers.

## 3. Nothing else should need changing

- **Baud rate** is negotiated. The reader here answered at 9600 one day and 38400
  the next, after the vendor software had driven it.
- **Capabilities** are queried, not assumed. That is what makes firmware 1.12 work:
  it reports capability 2064 as 0, and the read fails with status `2D06` if the
  extended-optics field is sent anyway.
- **Serial port** is found from the FTDI descriptors, which carry the instrument's
  own serial number. No COM port to configure.

## 4. Things you may actually want to change

- **Language.** The interface is Spanish. Every string is in the `TEXT` dictionary
  at the top of `epoch_open/gui.py`, and the warning messages are in `MESSAGES` in
  `epoch_open/quant.py`. Translating means editing two blocks and rebuilding.
- **Plate layout.** `epoch_open/take3.py` assumes the 16-spot Take3: rows A-H,
  columns 2 and 3. A Take3 Trio has three such sets and would need that file
  extended.

## 5. What was never tested here

- Any reader other than an Epoch, or any firmware other than 1.12.
- Any Take3 other than the 16-spot plate.
- Absolute accuracy against certified material. This software agrees with the
  vendor software to about 0.5% on the same drops; whether both are right in
  absolute terms is untested.
