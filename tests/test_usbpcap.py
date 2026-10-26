"""Tests for the USBPcap reader.

Builds capture files by hand so the parser is exercised before a real capture
arrives. The conversation used is the one the instrument actually produced on
2026-10-22: 'C' asking for the serial number, answered with 254717.
"""

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import usbpcap_read  # noqa: E402

LINKTYPE_USBPCAP = 249


def usb_packet(data: bytes, device: int = 3, endpoint: int = 0x02,
               transfer: int = 3, from_device: bool = False) -> bytes:
    """One USBPcap record: a 27-byte header followed by the payload."""
    header = struct.pack(
        "<HQIHBHHBBI",
        27,                       # headerLen
        0,                        # irpId
        0,                        # status
        9,                        # function
        1 if from_device else 0,  # info: bit 0 set means device -> host
        1,                        # bus
        device,
        endpoint,
        transfer,
        len(data),
    )
    return header + data


def write_pcap(path: Path, records: list[bytes], link_type=LINKTYPE_USBPCAP) -> Path:
    blob = bytearray(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, link_type))
    for i, record in enumerate(records):
        blob += struct.pack("<IIII", 1700000000 + i, 500000, len(record), len(record))
        blob += record
    path.write_bytes(bytes(blob))
    return path


def tmp_path_for(name: str) -> Path:
    directory = Path(__file__).resolve().parent / "_out"
    directory.mkdir(exist_ok=True)
    return directory / name


class TestReadPcap:
    def conversation(self) -> list[bytes]:
        return [
            usb_packet(b"C", from_device=False),
            # FTDI puts two modem-status bytes in front of every IN packet.
            usb_packet(b"\x01\x60\x06254717  0000\x03", endpoint=0x81,
                       from_device=True),
        ]

    def test_packets_are_recovered(self):
        path = write_pcap(tmp_path_for("conv.pcap"), self.conversation())
        packets = list(usbpcap_read.read_pcap(str(path)))
        assert len(packets) == 2

    def test_direction_is_read_correctly(self):
        path = write_pcap(tmp_path_for("dir.pcap"), self.conversation())
        out, back = list(usbpcap_read.read_pcap(str(path)))
        assert out.from_device is False
        assert back.from_device is True

    def test_ftdi_status_bytes_are_stripped(self):
        path = write_pcap(tmp_path_for("ftdi.pcap"), self.conversation())
        _out, back = list(usbpcap_read.read_pcap(str(path)))
        payload = usbpcap_read.strip_ftdi_status(back)
        assert payload.startswith(b"\x06254717")
        assert b"\x01\x60" not in payload[:2]

    def test_outbound_packets_are_left_alone(self):
        path = write_pcap(tmp_path_for("out.pcap"), self.conversation())
        out, _back = list(usbpcap_read.read_pcap(str(path)))
        assert usbpcap_read.strip_ftdi_status(out) == b"C"

    def test_device_and_transfer_are_read(self):
        path = write_pcap(tmp_path_for("dev.pcap"), self.conversation())
        packet = next(iter(usbpcap_read.read_pcap(str(path))))
        assert packet.device == 3
        assert packet.transfer == 3        # bulk

    def test_a_non_usb_capture_is_refused(self):
        path = write_pcap(tmp_path_for("eth.pcap"), [b"\x00" * 40], link_type=1)
        with pytest.raises(ValueError, match="not USBPcap"):
            list(usbpcap_read.read_pcap(str(path)))

    def test_pcapng_is_named_as_such(self):
        path = tmp_path_for("ng.pcap")
        path.write_bytes(struct.pack("<I", 0x0A0D0D0A) + b"\x00" * 40)
        with pytest.raises(ValueError, match="pcapng"):
            list(usbpcap_read.read_pcap(str(path)))

    def test_a_truncated_file_is_refused(self):
        path = tmp_path_for("short.pcap")
        path.write_bytes(b"\x00" * 8)
        with pytest.raises(ValueError, match="too short"):
            list(usbpcap_read.read_pcap(str(path)))


class TestPrintable:
    def test_control_bytes_are_named(self):
        assert usbpcap_read.printable(b"\x06") == "<ACK>"
        assert usbpcap_read.printable(b"\x03") == "<ETX>"

    def test_the_real_reply_reads_clearly(self):
        rendered = usbpcap_read.printable(b"\x06254717  0000\x03")
        assert rendered == "<ACK>254717  0000<ETX>"

    def test_unknown_bytes_become_hex(self):
        assert usbpcap_read.printable(b"\xff") == "<FF>"
