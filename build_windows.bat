@echo off
REM Build EpochTake3.exe on Windows. Run this from the project folder.
REM
REM Needs Python 3.11+ from python.org, with "Add python.exe to PATH" ticked.
REM Do NOT use the Microsoft Store build: it has shipped without tkinter, and
REM the interface will not start.

echo.
echo === Checking Python ===
python --version || goto :nopython

echo.
echo === Checking tkinter (the interface needs it) ===
python -c "import tkinter; print('tkinter OK', tkinter.TkVersion)" || goto :notk

echo.
echo === Installing dependencies ===
python -m pip install --upgrade pip
python -m pip install pyserial pyinstaller || goto :fail

echo.
echo === Building EpochTake3.exe ===
python -m PyInstaller --onefile --windowed --name EpochTake3 ^
    --hidden-import serial --hidden-import serial.tools.list_ports ^
    run_gui.py || goto :fail

echo.
echo === Done ===
echo The program is at:  dist\EpochTake3.exe
echo.
echo Before giving it to anyone, run it once with the reader unplugged: it must
echo open and show the red SIMULATION banner. Then plug the reader in and check
echo the banner turns green with serial 254717.
goto :eof

:nopython
echo.
echo Python was not found. Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup.
exit /b 1

:notk
echo.
echo Python is installed but tkinter is missing. This usually means the
echo Microsoft Store build. Install Python from python.org instead.
exit /b 1

:fail
echo.
echo The build failed. The message above says why.
exit /b 1
