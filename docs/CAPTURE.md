# Capturing the Epoch protocol while Gen5 still runs

**Do this before the Gen5 trial lapses.** Once it does, we lose the only ground truth we
have for the read commands, and the project drops back to blind probing.

The goal is a recording of the bytes Gen5 sends to the reader, and the bytes the reader
sends back, during one complete Take3 nucleic-acid read. Nothing here modifies, patches or
inspects the Gen5 program itself — we only watch the conversation on a cable between two
pieces of hardware the lab owns.

This step needs a computer-literate person (you, not the technician) and happens once.

## What you need

- The Windows box with the working Gen5 trial, Epoch connected and reading.
- Wireshark (free, open source): https://www.wireshark.org/download.html
  During install, tick **USBPcap** — an optional component in the installer.
- A reboot after installing USBPcap. It installs a driver; capture will not see the
  device until you restart.
- A Take3 plate and any sample. A blank-only run is still useful; one real sample is
  much better.

## Procedure

1. Install Wireshark with USBPcap, reboot.
2. Plug in the Epoch. Open Gen5 once, confirm it still reads normally. Close Gen5.
3. Open Wireshark **as Administrator**. The interface list shows `USBPcap1`, `USBPcap2`,
   ... one per USB root hub. Pick the one whose device tree lists the BioTek reader.
   - If you cannot tell which: start a capture on one, unplug and replug the Epoch, and
     watch for a burst of traffic. That is the right one.
4. Start the capture.
5. In Gen5, run **one** complete Take3 nucleic-acid read, start to finish, exactly as the
   technician normally would. Let it finish and display results.
6. Stop the capture. **Write down the numbers Gen5 reported** — every well's A260, A280,
   the pathlength if shown, and the final ng/uL. Screenshot the results screen.
7. Save as `take3_read_01.pcapng`.

## Three more captures, if you have time

Each isolates a different part of the protocol and makes decoding far easier:

- **`carrier_only.pcapng`** — open Gen5, eject and re-insert the plate carrier, close
  Gen5. No read. Isolates door/carriage commands from everything else.
- **`blank_only.pcapng`** — a read of the Take3 with water in all the wells you use.
- **`endpoint_single.pcapng`** — a plain 260 nm endpoint read of a normal 96-well plate,
  no Take3. The simplest possible read, and the easiest to decode first.

## What to send back

The `.pcapng` files plus the written-down Gen5 numbers, dropped into `captures/`. Those
reported numbers are the Rosetta stone: they let us confirm the values we decode out of
the byte stream are the ones Gen5 computed, and they are the acceptance test for the
finished software.

## Also worth doing while the machine works

- Note the reader's **firmware version** — Gen5 shows it under instrument/system info.
  The PyLabRobot thread indicates the command set varies between firmware revisions, so
  this determines which prior work applies.
- Note the **serial number** and exact model (Epoch vs Epoch 2 — different instruments,
  different electronics).
- Record **how the technician actually runs a sample today**: which Gen5 protocol she
  opens, how many samples at a time, whether she blanks every run, and what she does with
  the numbers afterwards (Excel? notebook?). The replacement should match that workflow
  step for step so she has as little to relearn as possible.
- Check the original disks for an FTDI (`CDM`) or Silicon Labs USB driver and for any
  utility that is not Gen5 itself. Copy the whole disk contents to a folder — that driver
  is what the replacement software sits on top of, and it may be hard to find elsewhere.
