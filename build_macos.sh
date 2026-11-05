#!/bin/bash
# Build the two apps on macOS. Run this from the project folder:
#
#     bash build_macos.sh
#
# PyInstaller cannot cross-compile: a .app has to be built on a Mac.
#
# Known to work: macOS 26.6 (arm64), Homebrew Python 3.15.2, Tk 9.1,
# PyInstaller 6.22.3, on 5 November 2026. Tk 9 was the part expected to fail
# and did not.
#
# Needs Python 3.10 or newer with a working tkinter. Apple's own /usr/bin/python3
# has shipped with a Tk too old to draw this correctly; python.org's build
# bundles a current one, and Homebrew's needs `brew install python-tk`.
#
# Everything is installed into a virtual environment inside this folder, never
# system-wide. Homebrew's Python refuses a system-wide pip install outright
# (PEP 668, "externally-managed-environment"), and on any Python it is the
# wrong thing to do to someone's machine for the sake of one build.

set -e

VENV=".venv-build"

echo
echo "=== Checking Python ==="
python3 --version

echo
echo "=== Checking tkinter (the interface needs it) ==="
python3 -c "import tkinter; print('tkinter OK, Tk', tkinter.TkVersion)" || {
    echo
    echo "tkinter is missing or broken. On Apple's system python3, install"
    echo "Python from https://www.python.org/downloads/ instead. On Homebrew's,"
    echo "run: brew install python-tk"
    exit 1
}

python3 - <<'PY'
import sys, tkinter
if tkinter.TkVersion < 8.6:
    sys.exit("Tk 8.6 or newer is needed; this is %s" % tkinter.TkVersion)
if tkinter.TkVersion >= 9.0:
    print("Note: Tk %s is very new. If PyInstaller fails below, that is the"
          % tkinter.TkVersion)
    print("      most likely reason -- the program itself runs fine from")
    print("      source. See 'Running without building' in README.md.")
PY

echo
echo "=== Virtual environment ($VENV) ==="
if [ -d "$VENV" ]; then
    echo "Reusing the existing one."
else
    python3 -m venv "$VENV"
    echo "Created."
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

echo
echo "=== Installing dependencies into $VENV ==="
python3 -m pip install --upgrade pip
python3 -m pip install pyserial pyinstaller

# A venv built on Homebrew's Python inherits its tkinter, but check rather than
# assume: a build that gets this far and produces an app that cannot open a
# window wastes far more time than one that stops here.
python3 -c "import tkinter" || {
    echo
    echo "The virtual environment has no tkinter, although the system Python"
    echo "did. On Homebrew that means python-tk is missing: brew install python-tk"
    exit 1
}

build () {
    local name="$1" entry="$2" window="$3"
    echo
    echo "=== Building $name.app ==="
    # --hidden-import for the window module: PyInstaller bundles what it can
    # see in an import statement, and the launchers import theirs directly for
    # exactly that reason. This is a second line of defence, not the fix --
    # see epoch_open/launch.py.
    python3 -m PyInstaller --windowed --name "$name" \
        --osx-bundle-identifier "cl.utalca.${name}" \
        --hidden-import serial --hidden-import serial.tools.list_ports \
        --hidden-import "$window" \
        --exclude-module unittest --exclude-module pydoc --exclude-module doctest \
        --exclude-module pdb --exclude-module sqlite3 --exclude-module lib2to3 \
        --exclude-module test --exclude-module distutils \
        "$entry"
}

build EpochTake3        run_take3.py         epoch_open.gui
build EpochMultispectral run_multispectral.py epoch_open.gui_curve

echo
echo "=== Done ==="
echo "The programs are at:"
echo "    dist/EpochTake3.app          nucleic acids, Take3 plate"
echo "    dist/EpochMultispectral.app  colorimetric assays, 96-well plate"
echo
echo "Neither is signed, so the first launch is refused with 'cannot be opened"
echo "because the developer cannot be verified'. Right-click the app and choose"
echo "Open, then Open again: that is remembered and it starts normally after."
echo "Signing properly needs an Apple Developer ID."
echo
echo "The Epoch appears on macOS as /dev/cu.usbserial-*; the FTDI driver has"
echo "been part of macOS since 10.9, so nothing has to be installed for it."
echo
echo "Before giving either to anyone, run it with the reader unplugged: it must"
echo "open, and the badge must say to switch the reader on. An app that dies on"
echo "launch is a packaging problem, not a program one."
