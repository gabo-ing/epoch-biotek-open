"""Talking to the Epoch, and a stand-in for when it is not connected.

The real protocol is not known yet -- it comes out of the Gen5 capture described in
docs/CAPTURE.md. What is already settled is the transport: the original disks ship
FTDI's stock CDM driver, so the reader is an ordinary USB serial port and pyserial is
all that is needed underneath (see docs/FINDINGS.md).

This module fixes the shape of the driver now so the interface can be built against it.
MockReader returns plausible numbers and lets the whole program be exercised today;
EpochReader is the real one, and every unknown in it is marked.
"""

import random
from dataclasses import dataclass

from . import take3
from .plates import TAKE3
from .quant import REFERENCE_NM, RawWell

# Confirmed on the instrument itself (serial 254717, plugged into colonial-one):
# it enumerates as FTDI's default ids and publishes useful identifying strings --
# manufacturer "BioTek", product "Epoch", and the FTDI serial set to the reader's own
# serial number. Matching those beats matching the ids, which any FTDI cable shares.
FTDI_VID = 0x0403
FTDI_PID = 0x6001
USB_MANUFACTURER = "BioTek"
USB_PRODUCT = "Epoch"

WAVELENGTHS = (230, 260, 280, 900, 977)

# Capability numbers for the 'z' query. An Epoch on firmware 1.12 answers
# 1 / 0 / 0 / 0 to these.
CAP_RDOP22 = 2000           # supports the RDOP22 read protocol at all
CAP_EXTRA_READ_FIELD = 2056  # optics record carries an extra three-digit field
CAP_EXTENDED_OPTICS = 2064   # optics record carries an extra optical-path byte
CAP_CARRIER_SPEED = 2138     # carriage speed can be selected


class ReaderError(Exception):
    """Something went wrong talking to the instrument."""


def _list_ports():
    """Attached serial ports, via pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise ReaderError(
            "pyserial is not installed, so the reader cannot be found. "
            "On Debian: apt install python3-serial"
        ) from exc
    return list(list_ports.comports())


@dataclass
class ReaderInfo:
    model: str
    serial: str
    firmware: str
    port: str


class ReaderBackend:
    """What the interface is allowed to assume about a reader."""

    def connect(self) -> ReaderInfo:
        raise NotImplementedError

    def read_wells(
        self, wells: list[str], wavelengths: list[int] | None = None
    ) -> dict[str, RawWell]:
        """Read the given wells and return one RawWell each."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class MockReader(ReaderBackend):
    """A fake instrument, for building and demonstrating without hardware.

    Numbers are invented. Nothing it produces is a measurement, and the interface
    says so on screen whenever this backend is in use.
    """

    def __init__(self, seed: int | None = None, blank: bool = False):
        self._random = random.Random(seed)
        self.simulating_blank = blank

    def connect(self) -> ReaderInfo:
        self.info = ReaderInfo(
            model="Epoch (simulated)",
            serial="254717",
            firmware="unknown",
            port="none",
        )
        return self.info

    def read_wells(
        self, wells: list[str], wavelengths: list[int] | None = None
    ) -> dict[str, RawWell]:
        wavelengths = wavelengths or [260, 280, REFERENCE_NM]
        readings = {}
        for well in wells:
            # Real blanks on this instrument scatter by about 3% at 260 nm.
            # The simulator used to use 0.002, which put a two-well blank over
            # the 5% disagreement threshold and popped a warning dialog at
            # anyone trying the program without hardware.
            background = 0.040 + self._random.gauss(0, 0.0006)
            signal = 0.0 if self.simulating_blank else self._random.uniform(0.005, 0.25)
            values = {REFERENCE_NM: round(background, 4)}
            for wavelength in wavelengths:
                if wavelength == REFERENCE_NM:
                    continue
                # Rough shape of a nucleic-acid spectrum: 280 about 55% of 260.
                scale = {260: 1.0, 280: 0.55, 230: 0.48}.get(wavelength, 0.5)
                values[wavelength] = round(
                    background + signal * scale + self._random.gauss(0, 0.0008), 4
                )
            readings[well] = RawWell(well=well, readings=values)
        return readings

    def close(self) -> None:
        pass


class EpochReader(ReaderBackend):
    """The real instrument over its FTDI serial port.

    Port settings and the command framing are confirmed against reader 254717
    (firmware 1.12); see docs/PROTOCOL.md. The command vocabulary comes from
    PyLabRobot's BioTek backend, which is MIT licensed.

    Reading plates is not implemented yet: the grammar of the read-configuration
    string is still unknown, and guessing it would produce numbers that look
    plausible and are wrong.
    """

    # The reader does not always sit at one rate: it answered at 9600 on
    # 2026-10-22 and at 38400 on 2026-10-26 after Gen5 had driven it. So the rate
    # is negotiated rather than assumed, cheapest-first.
    BAUDRATES = (9600, 38400, 19200, 57600, 115200, 38461)
    BAUDRATE = BAUDRATES[0]
    ACK = b"\x06"
    ETX = b"\x03"

    def __init__(self, port: str | None = None, timeout: float = 20.0,
                 expected_serial: str | None = None):
        self.port = port
        self.baudrate = None
        self.timeout = timeout
        self.expected_serial = expected_serial
        # What the instrument said about itself when it answered. The screen and
        # every exported file quote this, so it must come from the reader rather
        # than from the config file.
        self.info: ReaderInfo | None = None
        self._serial = None
        self._plate = None
        self._capabilities: dict[int, bytes] = {}

    # ------------------------------------------------------------- discovery

    @staticmethod
    def find_port(expected_serial: str | None = None) -> str | None:
        """Find the reader's serial port, so the technician never picks a COM port.

        Tried in order of how certain each match is: the instrument's own serial
        number, then its USB product string, then the bare FTDI ids. The last is a
        weak match -- any FTDI cable shares it -- so it only counts when exactly one
        such device is attached.

        Returns None when nothing matches, or when the choice would be a guess.
        """
        for port in _list_ports():
            if expected_serial and port.serial_number == expected_serial:
                return port.device

        named = [
            p for p in _list_ports()
            if (p.product or "") == USB_PRODUCT
            or (p.manufacturer or "") == USB_MANUFACTURER
        ]
        if len(named) == 1:
            return named[0].device

        ftdi = [p for p in _list_ports() if p.vid == FTDI_VID and p.pid == FTDI_PID]
        return ftdi[0].device if len(ftdi) == 1 else None

    @staticmethod
    def describe_ports() -> list[str]:
        """Human-readable list of attached serial devices, for the help screen."""
        return [
            f"{p.device}: {p.manufacturer or '?'} {p.product or '?'} "
            f"(serial {p.serial_number or '?'})"
            for p in _list_ports()
        ]

    # --------------------------------------------------------------- protocol

    def _read_until(self, terminator: bytes, timeout: float) -> bytes:
        import time

        result = b""
        deadline = time.time() + timeout
        while not result.endswith(terminator):
            chunk = self._serial.read(1)
            result += chunk
            if time.time() > deadline:
                raise ReaderError(
                    f"The reader stopped responding (got {result!r} so far). "
                    "Check that it is switched on and connected."
                )
            if not chunk:
                time.sleep(0.01)
        return result

    def send_command(self, command: str, parameter: str | None = None,
                     timeout: float | None = None) -> bytes:
        """Send one command and return the response, ACK and ETX included."""
        if self._serial is None:
            raise ReaderError("Not connected to the reader.")
        timeout = self.timeout if timeout is None else timeout

        # Gen5 purges repeatedly before each command; PyLabRobot copies it.
        for _ in range(6):
            self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

        self._serial.write(command.encode())
        self._serial.flush()

        if parameter is None:
            return self._read_until(self.ETX, timeout)

        self._read_until(self.ACK, timeout)
        self._serial.write(parameter.encode())
        self._serial.flush()
        return self._read_until(self.ETX, timeout)

    @staticmethod
    def _payload(response: bytes) -> str:
        """Strip the ACK and ETX and return the text between them."""
        return response[1:-1].decode("ascii", "replace").strip()

    # ---------------------------------------------------------------- queries

    def get_serial_number(self) -> str:
        return self._payload(self.send_command("C", timeout=2)).split()[0]

    def query_capability(self, number: int) -> bytes:
        """Ask whether the reader has a given capability; byte 0 is '1' or '0'.

        Cached per connection: the answers cannot change while the reader is on.
        """
        if number in self._capabilities:
            return self._capabilities[number]

        response = self.send_command("z", f"{number:04}\x03", timeout=5)
        data = response[1:-5] if response.startswith(self.ACK) else response[:-5]
        if len(data) != 17 or data[:1] not in (b"0", b"1"):
            raise ReaderError(
                f"Unexpected answer to capability query {number}: {data!r}"
            )
        self._capabilities[number] = data
        return data

    def supports(self, number: int) -> bool:
        return self.query_capability(number)[:1] == b"1"

    def get_firmware_version(self) -> str:
        # e.g. "7200201  Version 1.12   0000"
        payload = self._payload(self.send_command("e", timeout=2))
        parts = payload.split()
        if "Version" in parts:
            return parts[parts.index("Version") + 1]
        return payload

    # ------------------------------------------------------------- lifecycle

    def connect(self) -> ReaderInfo:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise ReaderError(
                "pyserial is not installed. On Debian: apt install python3-serial"
            ) from exc

        port = self.port or self.find_port(self.expected_serial)
        if port is None:
            attached = self.describe_ports()
            raise ReaderError(
                "Could not find the plate reader. Check that it is switched on and "
                "the USB cable is connected.\n\nSerial ports seen:\n"
                + ("\n".join(attached) if attached else "  (none)")
            )

        serial_number = firmware = None
        last_error = None

        for baudrate in self.BAUDRATES:
            try:
                self._serial = serial.Serial(
                    port,
                    baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_TWO,
                    rtscts=True,
                    timeout=0.3,
                )
            except serial.SerialException as exc:
                raise ReaderError(
                    f"Could not open {port}: {exc}\n\n"
                    "On Linux this usually means the account is not in the "
                    "'dialout' group."
                ) from exc

            self._serial.rts = True
            try:
                serial_number = self.get_serial_number()
                firmware = self.get_firmware_version()
                self.baudrate = baudrate
                break
            except (ReaderError, ValueError, IndexError) as exc:
                last_error = exc
                self._serial.close()
                self._serial = None

        if serial_number is None:
            raise ReaderError(
                f"The reader did not answer on {port} at any of "
                f"{', '.join(str(b) for b in self.BAUDRATES)} baud. "
                f"Last error: {last_error}"
            )

        self._capabilities.clear()

        if self.expected_serial and serial_number != self.expected_serial:
            self.close()
            raise ReaderError(
                f"Found a reader with serial {serial_number}, expected "
                f"{self.expected_serial}."
            )

        self.port = port
        self.info = ReaderInfo(
            model="Epoch", serial=serial_number, firmware=firmware, port=port
        )
        return self.info

    # ------------------------------------------------------------- reading

    def set_plate(self, geometry) -> bytes:
        """Tell the reader where the wells are. Required before every read."""
        response = self.send_command("y", geometry.to_command(), timeout=5)
        self._plate = geometry
        return response

    @staticmethod
    def _encode_assay(body: str) -> str:
        """Frame an assay record: 4-digit length, body, 3-digit checksum.

        The length counts the body plus the checksum field. The checksum is the
        sum of the body's bytes modulo 256. No ETX follows -- the reader takes the
        length field's word for where the record ends.
        """
        length = len(body) + 3
        if length > 9999:
            raise ValueError("assay record exceeds the four-digit length field")
        return f"{length:04}{body}{sum(body.encode('ascii')) % 256:03}"

    @staticmethod
    def _absorbance_command(
        wavelength: int,
        min_row: int,
        min_col: int,
        max_row: int,
        max_col: int,
        extended_optics: bool = False,
        extra_read_field: bool = False,
    ) -> str:
        """Build the 'D' assay for a single-wavelength endpoint read.

        Bounds are 1-based and inclusive. Two capability flags change the shape of
        the optics record: 2064 adds a byte to the optical path, 2056 adds a
        three-digit read field. An Epoch on firmware 1.12 reports neither, and
        sending the extended form makes the reader refuse the read with 0x2D06.
        """
        if not 200 <= wavelength <= 999:
            raise ValueError(
                f"wavelength {wavelength} nm is outside the Epoch's 200-999 nm range"
            )
        if not (1 <= min_row <= max_row <= 99 and 1 <= min_col <= max_col <= 99):
            raise ValueError("well bounds must be ordered and between 1 and 99")

        return EpochReader._multi_absorbance_command(
            [wavelength], min_row, min_col, max_row, max_col,
            extended_optics=extended_optics, extra_read_field=extra_read_field,
            record_type="01",
        )

    @staticmethod
    def _multi_absorbance_command(
        wavelengths: list[int],
        min_row: int,
        min_col: int,
        max_row: int,
        max_col: int,
        extended_optics: bool = False,
        extra_read_field: bool = False,
        record_type: str = "11",
    ) -> str:
        """Build a 'D' assay reading several wavelengths in one pass.

        Recovered from Gen5 reading a Take3 at 260/280/320 (captures/blanks.pcap):

            11 01 02 08 02 0001200100001 1001000003 0000080260 0000080280 0000080320
            ^^             ^^^^^^^^^^^^^ ^^^^^^^^^^ ^^^^^^^^^^ one 10-char block per
            record type    fixed         last digit = wavelength count

        Gen5 uses record type 11 for these; the single-wavelength form this driver
        has been using since 2026-10-22 uses 01 and is proven on the instrument.
        """
        if not wavelengths:
            raise ValueError("at least one wavelength is required")
        if len(wavelengths) > 9:
            raise ValueError("the wavelength count field holds a single digit")
        for wavelength in wavelengths:
            if not 200 <= wavelength <= 999:
                raise ValueError(
                    f"wavelength {wavelength} nm is outside the Epoch's 200-999 nm range"
                )
        if not (1 <= min_row <= max_row <= 99 and 1 <= min_col <= max_col <= 99):
            raise ValueError("well bounds must be ordered and between 1 and 99")

        header = (
            f"{record_type}{min_row:02}{min_col:02}{max_row:02}{max_col:02}"
            "0001200100001"
        )
        read_event = f"100100000{len(wavelengths)}"
        blocks = "".join(
            "0" + ("6" if extended_optics else "") + "00008"
            + ("000" if extra_read_field else "") + f"{w:04}"
            for w in wavelengths
        )
        return EpochReader._encode_assay(header + read_event + blocks)

    @staticmethod
    def _parse_body(body: bytes) -> dict[tuple[int, int], float]:
        """Parse a read response into {(row, column): absorbance}, both 1-based.

        The body is a header of 22 bytes followed by rows separated by CRLF, each a
        flat comma-separated run of (row, column, value) triples. A value containing
        '*' is the reader saying it overflowed, which becomes NaN.
        """
        HEADER = 22
        try:
            end = body.rindex(b"\r\n")
        except ValueError as exc:
            raise ReaderError(
                f"The reader's response was not in the expected form: {body[:80]!r}"
            ) from exc

        values: dict[tuple[int, int], float] = {}
        for row in body[HEADER:end].split(b"\r\n,"):
            fields = row.split(b",")
            for i in range(0, len(fields) - 2, 3):
                group = fields[i : i + 3]
                try:
                    row_index = int(group[0])
                    column_index = int(group[1])
                    raw = group[2].decode("ascii", "replace")
                except (ValueError, IndexError):
                    continue
                values[(row_index, column_index)] = (
                    float("nan") if "*" in raw else float(raw)
                )
        return values

    @staticmethod
    def _parse_multi_body(body: bytes, count: int) -> list[dict[tuple[int, int], float]]:
        """Split a multi-wavelength reply into one table per wavelength, in order.

        The reader returns the wavelengths as consecutive timestamped blocks:

            01,1,\r000:00:00.0,000,01,02,+0.0462,...\r\n000<1A>084
                   \r000:00:08.7,000,01,02,+0.0442,...\r\n000<1A>079
                   \r000:00:17.6,000,...

        Each block opens with a running-time stamp, so splitting on that gives the
        blocks; everything before the first one is the header.
        """
        import re

        sections = re.split(rb"\d{3}:\d{2}:\d{2}\.\d,\d{3},", body)[1:]
        if len(sections) != count:
            raise ReaderError(
                f"Expected {count} wavelength blocks in the reply but found "
                f"{len(sections)}."
            )

        tables = []
        for section in sections:
            # Each block ends at its trailing checksum, marked by 0x1A.
            data = section.split(b"\x1a")[0]
            values: dict[tuple[int, int], float] = {}
            fields = [f for f in re.split(rb"[,\r\n]+", data) if f]
            for i in range(0, len(fields) - 2, 3):
                try:
                    row = int(fields[i])
                    column = int(fields[i + 1])
                    raw = fields[i + 2].decode("ascii", "replace")
                except (ValueError, IndexError):
                    continue
                values[(row, column)] = float("nan") if "*" in raw else float(raw)
            tables.append(values)
        return tables

    def read_absorbance(
        self,
        wavelength: int,
        geometry=None,
        min_row: int = 1,
        min_col: int = 1,
        max_row: int | None = None,
        max_col: int | None = None,
        timeout: float = 180.0,
    ) -> dict[tuple[int, int], float]:
        """Read one wavelength over a rectangle of wells.

        Returns {(row, column): absorbance} with 1-based indices. The reader closes
        the carriage itself, so the plate must already be loaded.
        """
        if geometry is not None:
            self.set_plate(geometry)
        if self._plate is None:
            raise ReaderError("Set the plate geometry before reading.")

        max_row = self._plate.rows if max_row is None else max_row
        max_col = self._plate.columns if max_col is None else max_col

        if not self.supports(CAP_RDOP22):
            raise ReaderError(
                "This reader does not support the RDOP22 read protocol, which is "
                "the only one this driver implements."
            )

        command = self._absorbance_command(
            wavelength,
            min_row,
            min_col,
            max_row,
            max_col,
            extended_optics=self.supports(CAP_EXTENDED_OPTICS),
            extra_read_field=self.supports(CAP_EXTRA_READ_FIELD),
        )
        self.send_command("D", command)

        response = self.send_command("O")
        if response != b"\x060000\x03":
            raise ReaderError(
                f"The reader refused to start the read (replied {response!r})."
            )

        body = self._read_until(self.ETX, timeout=timeout)
        return self._parse_body(body)

    @staticmethod
    def bounding_rectangle(wells: list[str]) -> tuple[int, int, int, int]:
        """The smallest rectangle of the plate containing every named spot.

        The reader reads rectangles, not arbitrary sets. Selecting C2 and F3 means
        reading the block from C2 to F3 and discarding what was not asked for --
        which costs a little time and nothing else, since unused spots are empty.
        """
        if not wells:
            raise ValueError("no wells selected")
        indices = [take3.well_to_indices(w) for w in wells]
        rows = [r for r, _ in indices]
        columns = [c for _, c in indices]
        return min(rows), min(columns), max(rows), max(columns)

    # Seconds to wait after the carriage closes before the first read. A 2 uL drop
    # is still moving when the tray stops. On 2026-10-26 one well read 0.013 AU high
    # at 260 nm -- the first wavelength read, taken straight after the carriage
    # closed -- while 280 and 320 on the same well were normal. A drop or bubble
    # would have shifted all three together, so this looks like settling rather than
    # optics. HYPOTHESIS, not yet confirmed: re-read that well after a pause and see
    # whether the anomaly disappears.
    SETTLE_SECONDS = 3.0

    def read_batched(
        self, wells: list[str], wavelengths: list[int], timeout: float = 300.0
    ) -> dict[str, RawWell]:
        """Read every wavelength in a single pass, the way Gen5 does.

        Verified on reader 254717 on 2026-10-26: a four-well, three-wavelength read
        took 22.3 s batched against 44.8 s as three separate passes, a 2.01x
        speedup, with 320 nm identical to 0.0001 AU and 260 nm within 0.003 AU of
        the sequential read taken 22 s earlier.

        This is the default. `batch=False` falls back to one pass per wavelength,
        which is the path proven since 2026-10-22 and is kept for diagnosis.
        """
        if not self.supports(CAP_RDOP22):
            raise ReaderError("This reader does not support the RDOP22 read protocol.")

        min_row, min_col, max_row, max_col = self.bounding_rectangle(wells)
        wanted = {take3.well_to_indices(w): w for w in wells}
        ordered = sorted(set(wavelengths))

        self.set_plate(TAKE3)
        import time
        time.sleep(self.SETTLE_SECONDS)

        command = self._multi_absorbance_command(
            ordered, min_row, min_col, max_row, max_col,
            extended_optics=self.supports(CAP_EXTENDED_OPTICS),
            extra_read_field=self.supports(CAP_EXTRA_READ_FIELD),
        )
        self.send_command("D", command)

        response = self.send_command("O")
        if response != b"\x060000\x03":
            raise ReaderError(
                f"The reader refused to start the read (replied {response!r})."
            )

        body = self._read_until(self.ETX, timeout=timeout)
        tables = self._parse_multi_body(body, len(ordered))

        gathered: dict[str, dict[int, float]] = {w: {} for w in wells}
        for wavelength, table in zip(ordered, tables):
            for position, absorbance in table.items():
                well = wanted.get(position)
                if well is not None:
                    gathered[well][wavelength] = absorbance

        return {w: RawWell(well=w, readings=v) for w, v in gathered.items()}

    def read_wells(
        self, wells: list[str], wavelengths: list[int] | None = None,
        settle: float | None = None, batch: bool = True,
    ) -> dict[str, RawWell]:
        """Read the named Take3 spots at each wavelength.

        One pass per wavelength -- the reader does a single wavelength per assay --
        then the values are gathered per well. The 320 nm reference is always
        included, because nothing can be background-corrected without it.
        """
        wavelengths = list(wavelengths or [260, 280, REFERENCE_NM])
        if REFERENCE_NM not in wavelengths:
            wavelengths.append(REFERENCE_NM)

        if batch:
            return self.read_batched(wells, wavelengths)

        min_row, min_col, max_row, max_col = self.bounding_rectangle(wells)
        wanted = {take3.well_to_indices(w): w for w in wells}
        gathered: dict[str, dict[int, float]] = {w: {} for w in wells}

        self.set_plate(TAKE3)

        import time
        time.sleep(self.SETTLE_SECONDS if settle is None else settle)

        for wavelength in sorted(set(wavelengths)):
            values = self.read_absorbance(
                wavelength,
                min_row=min_row,
                min_col=min_col,
                max_row=max_row,
                max_col=max_col,
            )
            for position, absorbance in values.items():
                well = wanted.get(position)
                if well is not None:
                    gathered[well][wavelength] = absorbance

        missing = [w for w, values in gathered.items() if len(values) < len(set(wavelengths))]
        if missing:
            raise ReaderError(
                "The reader did not return every wavelength for: "
                + ", ".join(sorted(missing))
            )

        return {
            well: RawWell(well=well, readings=values)
            for well, values in gathered.items()
        }

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
