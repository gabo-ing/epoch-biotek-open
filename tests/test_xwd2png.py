"""Round-trip test for the xwd -> PNG converter.

Builds a tiny xwd by hand, converts it, and checks the PNG really decodes back to
the pixels that went in. Without this the converter is only ever checked by eye.
"""

import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import xwd2png  # noqa: E402


def make_xwd(path: Path, pixels: list[list[tuple[int, int, int]]]) -> Path:
    """Write a minimal 32-bpp ZPixmap xwd holding `pixels` (rows of RGB)."""
    height = len(pixels)
    width = len(pixels[0])
    header_size = 100            # 25 words
    stride = width * 4

    header = [
        header_size, 7, 2, 24,   # size, version, ZPixmap, depth
        width, height, 0, 0,     # width, height, xoffset, byte_order(LSB)
        32, 0, 32, 32,           # bitmap unit/order/pad, bits_per_pixel
        stride, 4,               # bytes_per_line, visual_class (TrueColor)
        0x00FF0000, 0x0000FF00, 0x000000FF,   # red, green, blue masks
        8, 256, 0,               # bits_per_rgb, colormap_entries, ncolors
        width, height, 0, 0, 0,  # window geometry
    ]

    blob = bytearray(struct.pack(">25I", *header))
    for row in pixels:
        for r, g, b in row:
            blob += struct.pack("<I", (r << 16) | (g << 8) | b)

    path.write_bytes(bytes(blob))
    return path


def decode_png(path: Path):
    """Minimal PNG reader for filter-type-0 truecolour images."""
    blob = path.read_bytes()
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"

    chunks, offset = {}, 8
    while offset < len(blob):
        length = struct.unpack_from(">I", blob, offset)[0]
        tag = blob[offset + 4:offset + 8]
        chunks.setdefault(tag, b"")
        chunks[tag] += blob[offset + 8:offset + 8 + length]
        offset += 12 + length

    width, height, depth, colour = struct.unpack_from(">IIBB", chunks[b"IHDR"], 0)
    assert depth == 8 and colour == 2

    raw = zlib.decompress(chunks[b"IDAT"])
    rows = []
    stride = width * 3
    for y in range(height):
        start = y * (stride + 1)
        assert raw[start] == 0, "expected filter type 0"
        rows.append(list(raw[start + 1:start + 1 + stride]))
    return width, height, rows


def tmp_path_for(name: str) -> Path:
    directory = Path(__file__).resolve().parent / "_out"
    directory.mkdir(exist_ok=True)
    return directory / name


class TestXwdToPng:
    PIXELS = [
        [(255, 0, 0), (0, 255, 0)],
        [(0, 0, 255), (255, 255, 255)],
    ]

    def test_pixels_survive_the_round_trip(self):
        source = make_xwd(tmp_path_for("tiny.xwd"), self.PIXELS)
        width, height, rows = xwd2png.read_xwd(str(source))
        assert (width, height) == (2, 2)

        out = tmp_path_for("tiny.png")
        xwd2png.write_png(str(out), width, height, rows)

        png_width, png_height, png_rows = decode_png(out)
        assert (png_width, png_height) == (2, 2)
        assert png_rows[0][:3] == [255, 0, 0]
        assert png_rows[0][3:6] == [0, 255, 0]
        assert png_rows[1][:3] == [0, 0, 255]

    def test_channels_are_not_swapped(self):
        # A pure red pixel must stay red, not become blue.
        source = make_xwd(tmp_path_for("red.xwd"), [[(255, 0, 0)]])
        _w, _h, rows = xwd2png.read_xwd(str(source))
        assert list(rows[0][:3]) == [255, 0, 0]

    def test_downscale_averages_a_block(self):
        pixels = [[(255, 255, 255), (255, 255, 255)],
                  [(0, 0, 0), (0, 0, 0)]]
        source = make_xwd(tmp_path_for("avg.xwd"), pixels)
        width, height, rows = xwd2png.read_xwd(str(source))
        width, height, rows = xwd2png.downscale(width, height, rows, 2)
        assert (width, height) == (1, 1)
        assert list(rows[0]) == [127, 127, 127]

    def test_unsupported_version_is_refused(self):
        bad = tmp_path_for("bad.xwd")
        header = [100, 6, 2, 24] + [0] * 21
        bad.write_bytes(struct.pack(">25I", *header))
        with pytest.raises(ValueError, match="version"):
            xwd2png.read_xwd(str(bad))
