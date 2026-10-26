# Credits and provenance

## PyLabRobot (MIT)

The BioTek serial command vocabulary — the single-character commands, the
ACK/ETX framing, the `z` capability queries and the shape of the plate-geometry
and assay records — was learned from PyLabRobot's BioTek plate reader backend
and from its pull request #1505 on RDOP22 framing.

<https://github.com/PyLabRobot/pylabrobot> — MIT licensed.

That work made this project days shorter. Where this repository goes further is
in confirming the behaviour on an **Epoch with firmware 1.12**, which PyLabRobot's
own notes describe as unverified: the read commands fail there unless the
extended-optics field is omitted, which capability query 2064 reports.

## What was reverse engineered, and how

Nothing here was obtained by inspecting, patching or decompiling the vendor
software. The protocol was recovered by:

1. Reading the instrument's own replies over its serial port.
2. Capturing USB traffic between the vendor software and the instrument, on a
   machine and an instrument owned by this lab.
3. Comparing results against the lab's own exported data files.

This is interoperability work on hardware the lab owns.

## Not included in this repository

- The vendor software, its installer, licence keys or help files.
- Any vendor binary or any part of one.

## Instrument

Developed against an Agilent/BioTek Epoch (P/N 7200201), firmware 1.12, serial
254717, with a Take3 micro-volume plate, serial 243819. The certified pathlengths
for that plate are compiled in; other plates fall back to the 0.5 mm nominal, and
their own values can be added in `epoch_open/take3.py`.
