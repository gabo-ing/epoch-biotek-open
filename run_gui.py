"""Launch the quantification window.

    python3 run_gui.py

Needs tkinter, which ships with Python on Windows and macOS. On Debian/Ubuntu it is
a separate package: apt install python3-tk
"""

import sys

from epoch_open.gui import main

if __name__ == "__main__":
    sys.exit(main())
