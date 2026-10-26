# Firmware captures — BioTek Epoch, firmware 1.12

USB traffic between the vendor software (Gen5 1.11.5) and an Agilent/BioTek Epoch
(P/N 7200201, **firmware 1.12**, serial 254717) with a Take3 micro-volume plate
(serial 243819). Captured with USBPcap on Windows 11, 26 October 2026, on an
instrument and a computer owned by the lab that publishes them.

These exist because PyLabRobot's BioTek work lists firmware 1.12 as unverified,
and the responses in its RDOP22 pull request are synthetic. These are real.

## Reading them

No Wireshark or tshark needed:

    python tools/usbpcap_read.py captures/blanks.pcap
    python tools/usbpcap_read.py captures/blanks.pcap --transcript --device 4

The reader is an FTDI device, so its traffic is USB **bulk**. The tool strips the
two modem-status bytes FTDI puts in front of every inbound packet, without which
every reply looks like it has two bytes of junk at the start.

## The files

| File | What it holds |
|---|---|
| `lecturas.pcap` | Startup, `z` capability sweep, and two 450 nm alignment scans (A2 and H2) |
| `calibracion.pcap` | The Take3 plate calibration routine, including the reads it performs |
| `blanks.pcap` | A nucleic-acid **blank** of all 16 micro-spots at 260/280/320 nm |
| `blank-2.pcap` | A full session: blanking and sample reading |
| `ladder.pcap` | A DNA ladder read |
| `Gen5_LVA_NAQ_000*.html` | Gen5's own exported results for those reads, for cross-checking |

## What they establish

- **Capability queries decide the read format.** Firmware 1.12 answers `z 2064`
  (extended optics) with `0`. Sending the extended form anyway makes the reader
  refuse the read with status `2D06` — the symptom reported on the PyLabRobot
  forum for this firmware. Omit the field and reads work.
- **Assay framing** is a 4-digit length, the body, and a 3-digit checksum that is
  the body's byte sum modulo 256. No ETX follows; the length delimits the record.
- **Several wavelengths go in one assay.** The last digit of the read-event block
  is the count, followed by one 10-character block per wavelength. Reading
  260/280/320 in one pass is about twice as fast as three passes.
- **Take3 geometry.** The plate is 17.50 mm tall (not the 96-well 14.22 mm), and
  the micro-spots sit at ordinary 96-well positions, 9.0 mm pitch. Alignment scans
  use a 21x21 raster over a 4.5 mm square centred on one spot.
- **Calibration is PC-side.** It reads A2 and H2 at 450 nm and derives X/Y offsets
  in micrometres. Nothing is written back to the instrument.
- **Baud rate is not fixed.** This reader answered at 9600 one day and 38400 the
  next, after Gen5 had driven it. Negotiate rather than assume.

The protocol is written up in `docs/PROTOCOL.md`; the quantification derived from
these and from the lab's own exports is in `docs/QUANTIFICATION.md`.

## Provenance

Nothing here was obtained by inspecting, patching or decompiling the vendor
software. This is a recording of traffic on a cable between two pieces of hardware
the lab owns.
