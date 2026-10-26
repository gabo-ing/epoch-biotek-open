"""Read a USBPcap capture and print the serial conversation it contains.

No third-party dependencies and no tshark: colonial-one has neither, and the format
is simple enough to parse directly.

    python usbpcap_read.py calibration.pcap                 # summary
    python usbpcap_read.py calibration.pcap --transcript    # the byte stream
    python usbpcap_read.py calibration.pcap --device 3      # one device only

The Epoch is an FTDI device, so its traffic is USB *bulk* transfers. FTDI prepends
two modem-status bytes to every IN packet, which are stripped here -- without that,
every reply looks like it has two bytes of junk in front.
"""

import argparse
import struct
import sys
from collections import Counter

PCAP_MAGIC_LE = 0xA1B2C3D4
PCAP_MAGIC_BE = 0xD4C3B2A1
PCAPNG_MAGIC = 0x0A0D0D0A
LINKTYPE_USBPCAP = 249

TRANSFER_NAMES = {0: "isochronous", 1: "interrupt", 2: "control", 3: "bulk"}


class Packet:
    __slots__ = ("timestamp", "device", "endpoint", "transfer", "from_device", "data")

    def __init__(self, timestamp, device, endpoint, transfer, from_device, data):
        self.timestamp = timestamp
        self.device = device
        self.endpoint = endpoint
        self.transfer = transfer
        self.from_device = from_device
        self.data = data


def read_pcap(path: str):
    """Yield Packet objects from a classic-format USBPcap file."""
    with open(path, "rb") as handle:
        blob = handle.read()

    if len(blob) < 24:
        raise ValueError("file is too short to be a pcap")

    magic = struct.unpack_from("<I", blob, 0)[0]
    if magic == PCAPNG_MAGIC:
        raise ValueError(
            "this is a pcapng file, not classic pcap. Re-run USBPcapCMD without "
            "pcapng output, or send it anyway and I will add pcapng support."
        )
    if magic == PCAP_MAGIC_LE:
        endian = "<"
    elif magic == PCAP_MAGIC_BE:
        endian = ">"
    else:
        raise ValueError(f"not a pcap file (magic 0x{magic:08x})")

    link_type = struct.unpack_from(endian + "I", blob, 20)[0]
    if link_type != LINKTYPE_USBPCAP:
        raise ValueError(
            f"link type {link_type} is not USBPcap ({LINKTYPE_USBPCAP}); "
            "this capture is not USB traffic"
        )

    offset = 24
    while offset + 16 <= len(blob):
        ts_sec, ts_usec, incl_len, _orig_len = struct.unpack_from(
            endian + "IIII", blob, offset
        )
        offset += 16
        record = blob[offset:offset + incl_len]
        offset += incl_len
        if len(record) < 27:
            continue

        header_len = struct.unpack_from("<H", record, 0)[0]
        device = struct.unpack_from("<H", record, 19)[0]
        endpoint = record[21]
        transfer = record[22]
        info = record[16]
        data = record[header_len:]

        yield Packet(
            timestamp=ts_sec + ts_usec / 1_000_000,
            device=device,
            endpoint=endpoint,
            transfer=transfer,
            from_device=bool(info & 0x01),
            data=data,
        )


def strip_ftdi_status(packet: Packet) -> bytes:
    """Drop the two modem-status bytes FTDI puts at the head of every IN packet."""
    if packet.from_device and len(packet.data) >= 2:
        return packet.data[2:]
    return packet.data


def printable(data: bytes) -> str:
    """Readable rendering: ASCII where possible, escapes for the control bytes."""
    out = []
    for byte in data:
        if byte == 0x02:
            out.append("<STX>")
        elif byte == 0x03:
            out.append("<ETX>")
        elif byte == 0x06:
            out.append("<ACK>")
        elif byte == 0x15:
            out.append("<NAK>")
        elif byte in (0x0D, 0x0A):
            out.append("\\r" if byte == 0x0D else "\\n")
        elif 32 <= byte < 127:
            out.append(chr(byte))
        else:
            out.append(f"<{byte:02X}>")
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--device", type=int, help="only this USB device address")
    parser.add_argument("--transcript", action="store_true",
                        help="print the byte stream rather than a summary")
    parser.add_argument("--all-transfers", action="store_true",
                        help="include control/interrupt traffic, not just bulk")
    parser.add_argument("--limit", type=int, default=400)
    args = parser.parse_args()

    try:
        packets = list(read_pcap(args.path))
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"{len(packets)} USB packets in {args.path}\n")

    by_device = Counter()
    for packet in packets:
        if packet.data:
            by_device[(packet.device, TRANSFER_NAMES.get(packet.transfer, "?"))] += 1

    print("Packets carrying data, by device and transfer type:")
    for (device, transfer), count in sorted(by_device.items(), key=lambda kv: -kv[1]):
        print(f"  device {device:3}  {transfer:12}  {count:6}")
    print()

    if not args.transcript:
        print("Re-run with --transcript to see the byte stream, "
              "and --device N to narrow it to the reader.")
        return 0

    start = packets[0].timestamp if packets else 0
    shown = 0
    for packet in packets:
        if args.device is not None and packet.device != args.device:
            continue
        if not args.all_transfers and packet.transfer != 3:
            continue
        payload = strip_ftdi_status(packet)
        if not payload:
            continue

        direction = "reader ->" if packet.from_device else "   -> reader"
        print(f"[{packet.timestamp - start:8.3f}s] dev {packet.device:3} "
              f"ep 0x{packet.endpoint:02x} {direction} {printable(payload)}")

        shown += 1
        if shown >= args.limit:
            print(f"\n... stopped at {args.limit} packets (--limit to raise)")
            break

    if shown == 0:
        print("No bulk data found. Try --all-transfers, or check --device.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
