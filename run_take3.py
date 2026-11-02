"""Launch epoch-take3: nucleic-acid quantification on a Take3 plate.

    python3 run_take3.py           against the instrument
    python3 run_take3.py --sim     simulated numbers, for looking at the screen

For colorimetric assays in an ordinary plate -- IAA, Bradford, ELISA -- use
run_multispectral.py instead. The Take3 plate must not be used for those: the
reagents are acidic and the micro-spots are quartz.
"""

import sys

from epoch_open.launch import start

if __name__ == "__main__":
    sys.exit(start("epoch_open.gui"))
