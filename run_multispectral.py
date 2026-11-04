"""Launch epoch-multispectral: colorimetric assays, with or without a curve.

    python3 run_multispectral.py         against the instrument
    python3 run_multispectral.py --sim   simulated numbers, to see the screen

Reads an ordinary transparent 96-well plate at whatever wavelength the assay
needs -- 530 nm for Salkowski/IAA, 595 for Bradford, 405 or 450 for an ELISA.
Mark wells and read for plain absorbance; add standards to get concentrations.

Do NOT use the Take3 plate with these assays. For nucleic acids on a Take3,
use run_take3.py.
"""

import sys

from epoch_open.launch import no_tkinter

try:
    # Imported by name, not through importlib: see run_take3.py.
    from epoch_open.gui_curve import main
except ModuleNotFoundError as exc:
    raise SystemExit(no_tkinter(exc))


if __name__ == "__main__":
    sys.exit(main())
