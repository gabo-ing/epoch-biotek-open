"""Launch epoch-multispectral: colorimetric assays against a standard curve.

    python3 run_multispectral.py         against the instrument
    python3 run_multispectral.py --sim   simulated numbers, to see the screen

Reads an ordinary transparent 96-well plate at whatever wavelength the assay
needs -- 530 nm for Salkowski/IAA, 595 for Bradford, 405 or 450 for an ELISA --
and interpolates concentrations from standards measured on the same plate.

Do NOT use the Take3 plate with these assays. For nucleic acids on a Take3,
use run_take3.py.
"""

import sys

from epoch_open.launch import start

if __name__ == "__main__":
    sys.exit(start("epoch_open.gui_curve"))
