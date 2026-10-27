#!/bin/bash
# Build EpochTake3.app on macOS. Run this from the project folder:
#
#     bash build_macos.sh
#
# UNTESTED. Nobody has run this yet -- the project was developed on Linux and
# is used on Windows. It mirrors build_windows.bat, which is known to work, but
# treat a failure here as a bug in this script rather than in the program.
#
# PyInstaller cannot cross-compile: a .app has to be built on a Mac.
#
# Needs Python 3.10 or newer from python.org. The system python3 that ships
# with macOS has shipped with a Tk that is too old to draw this correctly.

set -e

echo
echo "=== Checking Python ==="
python3 --version

echo
echo "=== Checking tkinter (the interface needs it) ==="
python3 -c "import tkinter; print('tkinter OK, Tk', tkinter.TkVersion)" || {
    echo
    echo "tkinter is missing or broken. This usually means Apple's system"
    echo "python3. Install Python from https://www.python.org/downloads/ ,"
    echo "which bundles a current Tk."
    exit 1
}

python3 - <<'PY'
import tkinter, sys
if tkinter.TkVersion < 8.6:
    sys.exit("Tk 8.6 or newer is needed; this is %s" % tkinter.TkVersion)
PY

echo
echo "=== Installing dependencies ==="
python3 -m pip install --upgrade pip
python3 -m pip install pyserial pyinstaller

echo
echo "=== Building EpochTake3.app ==="
python3 -m PyInstaller --windowed --name EpochTake3 \
    --osx-bundle-identifier cl.utalca.epochopen \
    --hidden-import serial --hidden-import serial.tools.list_ports \
    --exclude-module unittest --exclude-module pydoc --exclude-module doctest \
    --exclude-module pdb --exclude-module sqlite3 --exclude-module lib2to3 \
    --exclude-module test --exclude-module distutils \
    run_gui.py

echo
echo "=== Done ==="
echo "The program is at:  dist/EpochTake3.app"
echo
echo "It is not signed, so the first launch is refused with 'cannot be opened"
echo "because the developer cannot be verified'. Right-click the app and choose"
echo "Open, then Open again: that is remembered and it starts normally after."
echo "Signing it properly needs an Apple Developer ID."
echo
echo "The Epoch appears on macOS as /dev/cu.usbserial-*; the FTDI driver has"
echo "been part of macOS since 10.9, so nothing has to be installed for it."
echo
echo "Before giving it to anyone, run it with the reader unplugged: the read"
echo "buttons must be greyed out and the badge must say to switch the reader on."
