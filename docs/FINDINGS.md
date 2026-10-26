# What the original disks tell us

Source: `/media/gabo/Ventoy/Epoch` (Gabo's backup of the disks that shipped with the
instrument). Three folders: `GEN5`, `Take3`, `USB driver`.

Only the hardware interface matters here. The Gen5 installer itself is not part of this
project and nothing we build depends on it.

## The reader is an FTDI USB-to-serial device  — the single most useful finding

`USB driver/CDM20600.exe` is FTDI's own **CDM 2.06.00** driver package (it contains
`ftdibus.sys`, `ftdibus.inf`, `ftdiport.inf` for i386 and amd64). BioTek did not write a
custom USB driver; they shipped the stock FTDI installer under its stock filename.

Consequences, all good:

- The Epoch enumerates as an ordinary **virtual COM port**. No proprietary USB protocol,
  no custom kernel driver, no libusb work.
- **pyserial talks to it directly.** The driver layer of this project is solved before it
  was started.
- On Windows, `CDM20600.exe` from the disk is the driver to install, so we are not
  dependent on a vendor download that may no longer exist. Note it is a 2009-era package;
  a current FTDI VCP driver from ftdichip.com will also work and is better on modern
  Windows.
- On Linux the kernel's `ftdi_sio` module handles it with no install at all. Worth
  remembering if the Windows box ever becomes a problem.

Because BioTek shipped the **unmodified** FTDI installer, the reader almost certainly
uses FTDI's **default VID 0x0403 / PID 0x6001** — a custom PID would have required a
modified INF, and there isn't one. *Confirm this* rather than trusting it: on Windows,
Device Manager -> the reader -> Properties -> Details -> Hardware Ids. With the real
VID/PID the software can find the reader by itself and the technician never sees a COM
port number.

## The instrument

| | |
|---|---|
| Reader | Epoch (original, not Epoch 2) |
| Reader serial | 254717 |
| Take3 plate serial | 243819 |
| Gen5 | 1.11.5, from the original disks |

Confirmed by Gabo: **Gen5 1.11.5 from the original disks installs and reads correctly on
a modern Windows 10 machine.** So the capture does not need the old lab PC — it can be
done on current hardware, and the Windows box that will eventually run the replacement
software is also able to run Gen5 for the capture.

The licence key is held by Gabo and is deliberately not recorded here.

### On the Take3 plate serial

Gen5 asks for the Take3 plate serial. Whether it keys any per-plate calibration to it is
unknown and worth watching for in the capture. Either way our arithmetic does not depend
on it: the 977/900 water peak measures the pathlength of each drop at read time, so the
correction is self-calibrating per well and needs no stored per-plate constant. If the
capture shows Gen5 applying a plate-specific factor on top of that, we will see it as a
systematic offset when comparing against the reference numbers.

## Versions

- Gen5 **1.11.5**, December 2010.
- The readme's minimum-basecode table lists the Epoch as basecode **Rev A**. So the
  instrument is from the era this Gen5 supports, consistent with the original (not
  Epoch 2) hardware, and plausibly the FW 1.12 generation discussed in the PyLabRobot
  thread. Confirm the actual firmware from the instrument's info screen.

## Other items noted

- `USB driver/USB Driver Installation Instructions.pdf` — vendor instructions for
  installing the FTDI driver. Useful as-is for the Windows setup step.
- `USB driver/Utilities/usbview.exe` — Microsoft's USBView. Shows the device descriptor,
  and will confirm the VID/PID without Device Manager.
- `GEN5/.../OLE Automation/Gen5 Automation Programmer Guide.pdf` — documents Gen5's OLE
  automation interface. **Not a route for us**: it drives Gen5, so it needs a licensed
  Gen5 running. It does confirm that pathlength arrives as "auxiliary data" alongside the
  absorbances, which matches the 977/900 correction implemented in `quant.py`.

## A parallel track worth pursuing

The Gen5 readme points users to BioTek TAC (now Agilent support) for software matters.
The lab owns the instrument, the disks and the licence; the obstacle is an exhausted
activation count, which is routine for support to reset. That request costs an email and
could restore the instrument in days.

It is worth doing **in parallel** with this project, not instead of it: if support says
yes, the lab is unblocked immediately; if they say no, or want a paid upgrade to a
current Gen5, this software is the answer and the lab is no longer dependent on a single
vendor activation for a machine it owns.

## Confirmed on the instrument (2026-10-22, plugged into colonial-one)

The reader was brought to colonial-one and powered on. Linux bound it with no driver
install of any kind -- `ftdi_sio` claimed it on sight and it appeared as `/dev/ttyUSB0`.

    lsusb:  Bus 008 Device 003: ID 0403:6001 Future Technology Devices International,
            Ltd FT232 Serial (UART) IC

    ID_VENDOR        BioTek
    ID_MODEL         Epoch
    ID_SERIAL_SHORT  254717          <- the instrument's own serial number
    ID_USB_DRIVER    ftdi_sio

So the FTDI inference from the disks was right, and the device gives us more than the
ids: the FTDI serial descriptor is programmed with the reader's real serial number, and
the manufacturer and product strings are meaningful. `EpochReader.find_port()` now
matches on serial number first, then the product string, and only falls back to the bare
FTDI ids. These descriptors are visible on Windows too, via pyserial's `list_ports`, so
the same detection works for the technician's machine.

`ID_USB_REVISION=0400` is the FTDI chip revision, not the instrument firmware. The
reader's own firmware version still has to come from the instrument.

### Still needed before the port can be opened

    sudo apt install python3-serial      # no pyserial, and no pip on this box
    sudo usermod -aG dialout gabo        # /dev/ttyUSB0 is root:dialout; needs re-login

## The reader answers (2026-10-22)

Handshake succeeded on the first attempt at 9600 8-N-2 with RTS/CTS. It returned its
serial number (254717) and firmware (**Version 1.12**, part 7200201). Firmware 1.12 is
exactly the revision discussed in the PyLabRobot thread, so that backend's command set
applies to this instrument. Details in `docs/PROTOCOL.md`.

## The factory paperwork (photos in /home/gabo/epoch)

### Take3 Pathlength Data Sheet — plate 243819, 25 Jan 2011

Settles the layout and hands us ground truth.

The micro-volume area is **16 spots, rows A-H, columns 2 and 3**, addressed as ordinary
positions on the 96-well grid. An earlier guess in this project had them as a 4x4 block;
that was wrong and is corrected. Reading the wrong spot would have produced a confident
number from the wrong sample.

Certified pathlengths are recorded in `epoch_open/take3.CERTIFIED_PATHLENGTHS_MM`
(0.4973 - 0.5125 mm, mean 0.5023 mm). They are a cross-check, not an input: the software
measures each drop at read time from the 977/900 water peak, because what matters is the
thickness of *this* drop. Agreement between measured and certified is the acceptance test
that replaces the Gen5 capture we never got.

It also lets `WATER_ABS_1CM` (the provisional 0.18 in `quant.py`) be **solved for** rather
than assumed: read water in a known spot, and the certified pathlength plus the measured
A977-A900 give the constant directly for this instrument.

### Absorbance Test Plate Results — reader 254717, 18 Feb 2011

Confirms what the reader told us over the wire: Epoch, serial 254717, P/N 7200201,
firmware v1.12.

**Worth knowing:** the Peak Absorbance check on that sheet *failed* — well C6, reference
505 nm, tolerance 3, read 500, `FAIL`. Everything else (alignment, accuracy and
repeatability at 405 and 450 nm) passed, and the accompanying Gen5 System Test Report
says `SYSTEM TEST PASS`. The sheet is marked "rev inicial", so it may be a pre-service
test rather than the final state, and it is fifteen years old either way.

It still deserves a check, because a wavelength offset of a few nm shifts A260 and A280
unequally and would bias the 260/280 ratio rather than cancel out. The test is cheap:
read a sample of known concentration and compare. Flagging it now so a systematic bias is
not mistaken for a bug in this software later.

### Gen5 System Test Report

Autocal corner coordinates and monochromator coefficients (A=0, B=+0.002064,
C=-0.404639). Internal calibration, nothing this software needs to send or know.
