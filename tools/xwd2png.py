"""Convert an X11 xwd dump to PNG, using only the standard library.

colonial-one has xwd but no image tooling, so this closes the gap: capture a window
with `xwd`, convert here, and the result can be viewed like any other PNG.

Handles the common case -- ZPixmap, TrueColor, 24 or 32 bits per pixel -- which is
what a modern X server gives. Anything else raises rather than guessing.
"""

import struct
import sys
import zlib

# Field order of the xwd v7 header, all big-endian 32-bit words.
FIELDS = [
    "header_size", "file_version", "pixmap_format", "pixmap_depth",
    "pixmap_width", "pixmap_height", "xoffset", "byte_order",
    "bitmap_unit", "bitmap_bit_order", "bitmap_pad", "bits_per_pixel",
    "bytes_per_line", "visual_class", "red_mask", "green_mask", "blue_mask",
    "bits_per_rgb", "colormap_entries", "ncolors", "window_width",
    "window_height", "window_x", "window_y", "window_bdrwidth",
]


def _shift(mask: int) -> int:
    """How far right to shift to bring a channel mask down to bit 0."""
    if mask == 0:
        return 0
    shift = 0
    while not (mask >> shift) & 1:
        shift += 1
    return shift


def read_xwd(path: str):
    """Return (width, height, rows) where rows are bytearrays of RGB triples."""
    with open(path, "rb") as handle:
        blob = handle.read()

    header = dict(zip(FIELDS, struct.unpack_from(">25I", blob, 0)))

    if header["file_version"] != 7:
        raise ValueError(f"unsupported xwd version {header['file_version']}")
    if header["pixmap_format"] != 2:
        raise ValueError("only ZPixmap is supported")
    if header["bits_per_pixel"] not in (24, 32):
        raise ValueError(f"unsupported depth {header['bits_per_pixel']} bpp")

    width = header["pixmap_width"]
    height = header["pixmap_height"]
    stride = header["bytes_per_line"]
    pixel_bytes = header["bits_per_pixel"] // 8

    # Pixel data follows the header and the colormap.
    start = header["header_size"] + header["ncolors"] * 12

    red_shift = _shift(header["red_mask"])
    green_shift = _shift(header["green_mask"])
    blue_shift = _shift(header["blue_mask"])
    big_endian = header["byte_order"] == 1

    rows = []
    for y in range(height):
        base = start + y * stride
        row = bytearray(width * 3)
        for x in range(width):
            offset = base + x * pixel_bytes
            chunk = blob[offset:offset + pixel_bytes]
            if len(chunk) < pixel_bytes:
                break
            value = int.from_bytes(chunk, "big" if big_endian else "little")
            row[x * 3] = (value & header["red_mask"]) >> red_shift & 0xFF
            row[x * 3 + 1] = (value & header["green_mask"]) >> green_shift & 0xFF
            row[x * 3 + 2] = (value & header["blue_mask"]) >> blue_shift & 0xFF
        rows.append(row)

    return width, height, rows


def downscale(width: int, height: int, rows: list, factor: int):
    """Box-average by an integer factor, to keep the PNG a sensible size."""
    if factor <= 1:
        return width, height, rows

    new_width = width // factor
    new_height = height // factor
    out = []
    for y in range(new_height):
        row = bytearray(new_width * 3)
        sources = rows[y * factor:(y + 1) * factor]
        for x in range(new_width):
            r = g = b = 0
            count = 0
            for source in sources:
                for dx in range(factor):
                    i = (x * factor + dx) * 3
                    r += source[i]
                    g += source[i + 1]
                    b += source[i + 2]
                    count += 1
            row[x * 3] = r // count
            row[x * 3 + 1] = g // count
            row[x * 3 + 2] = b // count
        out.append(row)
    return new_width, new_height, out


def write_png(path: str, width: int, height: int, rows: list) -> None:
    raw = bytearray()
    for row in rows:
        raw.append(0)          # filter type 0 (None) for each scanline
        raw.extend(row)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")

    with open(path, "wb") as handle:
        handle.write(png)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: xwd2png.py input.xwd output.png [downscale_factor]")
        return 2

    factor = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    width, height, rows = read_xwd(sys.argv[1])
    width, height, rows = downscale(width, height, rows, factor)
    write_png(sys.argv[2], width, height, rows)
    print(f"wrote {sys.argv[2]} ({width}x{height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
