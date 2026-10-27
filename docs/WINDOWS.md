# Putting this on the lab's Windows laptop

The end product is one `.exe` the technician double-clicks. No Python, no console, no
settings file. This describes building it; it has not been run yet, because the build
has to happen on Windows.

## 1. The USB driver (once per machine)

The Epoch is an FTDI serial device. Windows needs the FTDI VCP driver:

- From the original disks: `USB driver/CDM20600.exe`. It works, but it is from 2009.
- Better: the current VCP driver from <https://ftdichip.com/drivers/vcp-drivers/>.
  Same driver family, properly signed for current Windows.

Install it **before** plugging the reader in. Afterwards, Device Manager should show a
"USB Serial Port (COMn)" under Ports. The software finds the port by itself using the
instrument's serial number, so the COM number never has to be typed anywhere.

Linux needs nothing: `ftdi_sio` is in the kernel.

## 2. Getting the source onto the machine

Git is not needed. On GitHub, use **Code -> Download ZIP** and unpack it somewhere
that is not the Downloads folder. Check which branch you are downloading: the ZIP
button gives you whichever branch the page is showing.

## 3. Build the exe (on the Windows machine, once)

Install Python 3.11 or newer from python.org, ticking **"Add python.exe to PATH"**.
The python.org build includes tkinter; the Microsoft Store build has been known not
to, so avoid it.

    pip install pyserial pyinstaller
    pyinstaller --onefile --windowed --name EpochTake3 --icon NONE run_gui.py

- `--onefile` produces a single `dist\EpochTake3.exe`.
- `--windowed` suppresses the console window, so no black box appears behind the app.

The only third-party dependency is **pyserial**. The xlsx writer is deliberately
hand-rolled against the standard library, so nothing else has to be bundled.

## 4. Check before handing it over

1. Run the exe with **no reader attached**. It must open, show the amber "enciende
   el lector" badge, and have the read buttons greyed out. If it offers to read, or
   produces any number at all in this state, stop: that build is the old one that
   fell back to the simulator.
2. Open a saved file in the lab's own Excel — not just LibreOffice. To produce one
   for this check without an instrument, run the exe from a command prompt with
   `EpochTake3.exe --sim`; everything it saves that way is labelled simulated.
3. With the exe still running, switch the reader on. Within a few seconds the badge
   must turn green by itself and report serial 254717 and firmware 1.12, with no
   restart. This is the check that matters most, because it is the order the
   technician will actually do things in.
4. Switch the reader off again while the program is open and take a read. It must
   say the reader is not answering and grey the read buttons out again. If it
   silently produces numbers instead, stop and do not hand it over: those numbers
   are simulated.
5. Run the paired validation in `docs/WISHLIST.md` before it is used for real results.

## 5. Where it lives

Put the exe somewhere stable (`C:\EpochTake3\`) and make a Desktop shortcut. Do not
run it from a USB stick or the Downloads folder, where it will eventually be deleted
by someone tidying up.

## Status: built and working

Built and run on the lab's Dell with Windows 11 on 26 October 2026. Confirmed:
started with no reader attached and showed the red simulation banner; closed,
attached the reader, restarted and the reader was detected; read a plate; exported
an xlsx that Excel opened with no repair prompt.

That build is now out of date. It predates the config file, the plate dialog, the
version stamping and the automatic reader detection, so it still needs the restart
described above. Rebuild from current source rather than copying that exe.

`build_windows.bat` in the project root does the whole build.

## Display scaling

The program declares itself DPI-aware, so Windows draws it at the screen's real
pixel size instead of rendering it at 96 dpi and stretching the result. Without
that the text is visibly blurry on any laptop running at 125% or 150%, which is
the default on most current machines.

The layout scales itself to match, and tightens as the usable space shrinks. It
fits a 1920x1080 screen at 100%, 125% and 150%. It does not fit a 1366x768 screen
above 100%: at 150% the layout needs about 760 pixels of height on a 768-pixel
screen, which no amount of tightening will fix. On such a machine set Windows
display scaling to 100%.

## Known gaps
- Windows may warn about an unsigned executable on first run ("Windows protected your
  PC" -> More info -> Run anyway). Expected for an unsigned binary; it does not
  recur once the file is trusted.
- Antivirus sometimes dislikes PyInstaller one-file builds, because they unpack
  themselves at startup. If that happens, build without `--onefile` and ship the
  folder instead.
