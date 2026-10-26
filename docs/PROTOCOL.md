# Epoch serial protocol — confirmed on reader 254717

Verified live on 2026-10-22 against the instrument on colonial-one. Command vocabulary
from PyLabRobot's `legacy/plate_reading/agilent/biotek_backend.py` (MIT); the port
settings and the responses below are what this reader actually did.

## Port settings

| | |
|---|---|
| Device | `/dev/ttyUSB0` (FTDI, `ftdi_sio`) |
| Baud | **9600** |
| Framing | 8 data bits, no parity, **2 stop bits** |
| Flow control | RTS/CTS, RTS asserted |

PyLabRobot falls back to 38461 baud when 9600 times out. **This reader does not need
that** — at 38461 it returns noise (`b'x<\x0f\x80'`). Stay at 9600.

The reader is silent until spoken to: nothing is emitted on power-up or on connect.

## Framing

A command is a single ASCII character. Responses are `ACK (0x06) ... ETX (0x03)`.

    send: "C"
    recv: 0x06 "254717  0000" 0x03

For a command that takes a parameter, the reader ACKs the command character first, then
the parameter is written and the real response read to ETX:

    send: "&"  -> recv 0x06
    send: "S1" -> recv ... 0x03

The trailing `0000` looks like a status or error field; `0000` accompanied every
successful response. Purge the input buffer before each command — Gen5 does, and
PyLabRobot copies it.

## Confirmed commands (read-only, nothing moves)

| Cmd | Meaning | This reader's response |
|---|---|---|
| `C` | Serial number | `\x06254717  0000\x03` → **254717** |
| `e` | Firmware version | `\x067200201  Version 1.12   0000\x03` → part 7200201, **v1.12** |

Both match the instrument's own labelling and its USB descriptor, so this is genuinely
our reader and the dialect is right.

## Capability negotiation — the key to reading

Before building a read, ask the reader what shape of record it wants. Command `z`
with a four-digit capability number returns 17 bytes whose first byte is `1` or `0`.

| Query | Meaning | **This Epoch (fw 1.12)** |
|---|---|---|
| 2000 | Supports the RDOP22 read protocol | **1** (`1 Protocol V1.00 `) |
| 2056 | Optics record carries an extra three-digit field | **0** |
| 2064 | Optics record carries an extra optical-path byte | **0** |
| 2138 | Carriage speed can be selected | **0** |

**This is what made reads fail.** PyLabRobot's older backend always emitted the
extended-optics form. This reader does not have that field, and answers `O` with
status `2D06` when asked to run such an assay. Omit it and the read runs.

## Reading — confirmed working

### 1. Set the plate geometry

`y` + the geometry string (see `epoch_open/plates.py`). Replies `0000` + ETX.

### 2. Configure the assay

`D` + an assay record framed as **4-digit length, body, 3-digit checksum**, with the
length counting body-plus-checksum and the checksum being the body's byte sum modulo
256. **No ETX follows** — the length field delimits the record.

The body, for a single-wavelength endpoint read with neither capability:

    01 RR CC RR CC 0001200100001 1001000001 0 00008 WWWW
    |  |  |  |  |  |             |          |  |     wavelength, 4 digits
    |  |  |  |  |  |             |          |  fixed
    |  |  |  |  |  |             |          optical path (a '6' here iff cap 2064)
    |  |  |  |  |  read event, fixed
    |  |  |  |  fixed read settings
    |  min row, min col, max row, max col (1-based, inclusive)
    record type

Confirmed accepted by this reader, byte for byte:

    00460101010202000120010000110010000010000080260047

### 3. Start the read

`O`, which must answer exactly `\x060000\x03`.

### 4. Collect the data

Read until ETX. A 2x2 read of an empty carriage took 12.2 s and returned:

    01,1,\r000:00:00.0,000,01,01,+0.0000,01,02,+0.0000\r\n
    ,02,02,+0.0000,02,01,+0.0000\r\n000\x1a246\x1a0000\x03

A 22-byte header, then CRLF-separated rows of flat `row,column,value` triples,
1-based, then a trailing checksum/status block that the parser must not mistake for
data. A value containing `*` means the reader overflowed; it becomes NaN.

## Other commands (from PyLabRobot, not all tried here)

| Cmd | Meaning | Status |
|---|---|---|
| `J` | Open / eject carriage | **confirmed, tray moves** |
| `A` | Close carriage | **confirmed, tray moves** |
| `i` + `x` | Home | untried |
| `&` + `S1`/`S0` | Slow mode | unsupported here (cap 2138 = 0) |
| `h` / `g` | Temperature | n/a, the Epoch is unheated |
| `x` | Abort, sent without awaiting a reply | untried |

## What remains

Take3 micro-volume reads need the plate's spot geometry, which is the only missing
input — the read mechanism itself is done. A Take3 read is then just this same
absorbance read repeated at 230/260/280/900/977 nm over the micro-spot coordinates.
