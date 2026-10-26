"""Plate geometry, in the form the reader wants it.

The reader is told where the wells are before every read: how many rows and columns,
the centre of the first and last well, and the plate's outside dimensions. All
distances are millimetres from the top-left corner of the plate, looking down on it.

Grammar recovered from PyLabRobot's BioTek backend (MIT) and its worked example:

    08 12 01122 07434 01435 11353 08559 12788 1422
    |  |  |     |     |     |     |     |     |
    |  |  |     |     |     |     |     |     plate height      14.22 mm
    |  |  |     |     |     |     |     plate width            127.88 mm
    |  |  |     |     |     |     plate depth                   85.59 mm
    |  |  |     |     |     last well centre x                 113.53 mm
    |  |  |     |     first well centre x                       14.35 mm
    |  |  |     last well centre y                              74.34 mm
    |  |  first well centre y                                   11.22 mm
    |  columns
    rows
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlateGeometry:
    """Where the wells are, in millimetres from the plate's top-left corner."""

    name: str
    rows: int
    columns: int
    first_well_y: float
    last_well_y: float
    first_well_x: float
    last_well_x: float
    size_y: float
    size_x: float
    size_z: float

    def to_command(self) -> str:
        """The parameter for the 'y' (set plate) command, ETX included."""
        return (
            f"{self.rows:02}"
            f"{self.columns:02}"
            f"{int(self.first_well_y * 100):05}"
            f"{int(self.last_well_y * 100):05}"
            f"{int(self.first_well_x * 100):05}"
            f"{int(self.last_well_x * 100):05}"
            f"{int(self.size_y * 100):05}"
            f"{int(self.size_x * 100):05}"
            f"{int(self.size_z * 100):04}"
            "\x03"
        )


# Standard SBS 96-well plate. These are the values in PyLabRobot's worked example and
# they match the SBS footprint, so this one is trustworthy.
PLATE_96 = PlateGeometry(
    name="96-well standard",
    rows=8,
    columns=12,
    first_well_y=11.22,
    last_well_y=74.34,
    first_well_x=14.35,
    last_well_x=113.53,
    size_y=85.59,
    size_x=127.88,
    size_z=14.22,
)

# Take3 micro-volume plate.
#
# Measured from Gen5's own `y` command, captured on 2026-10-26 (captures/lecturas.pcap):
#
#     21210089201342021130256308534127761750
#     ^^^^ 21 x 21 grid    ^^^^^^^^^^ 4.5 mm square around one spot
#
# Two things this corrected:
#   * the plate is 17.50 mm tall, not the 96-well 14.22 mm we had been declaring;
#   * Gen5 reads one micro-spot at a time as a 21 x 21 raster over a 4.5 mm square
#     centred on it, rather than addressing spots as cells of a 96-well grid.
#
# Spot centres sit at ordinary 96-well positions: A2 at (23.38, 11.17) mm and H2 at
# (23.38, 74.17) mm, a 9.0 mm row pitch.
TAKE3_SIZE_X = 127.76
TAKE3_SIZE_Y = 85.34
TAKE3_SIZE_Z = 17.50

# Centre of the first micro-spot (A2), and the pitch between spots.
TAKE3_FIRST_X = 23.38
TAKE3_FIRST_Y = 11.17
TAKE3_PITCH = 9.0

# Gen5 scans this square around each spot, at this many points per side.
TAKE3_SCAN_MM = 4.50
TAKE3_SCAN_POINTS = 21


def take3_spot_centre(row: int, column: int) -> tuple[float, float]:
    """Centre of one micro-spot in mm, from 1-based row and plate column (2 or 3)."""
    x = TAKE3_FIRST_X + (column - 2) * TAKE3_PITCH
    y = TAKE3_FIRST_Y + (row - 1) * TAKE3_PITCH
    return x, y


def take3_spot_geometry(row: int, column: int) -> PlateGeometry:
    """The geometry Gen5 declares to scan a single Take3 micro-spot."""
    x, y = take3_spot_centre(row, column)
    half = TAKE3_SCAN_MM / 2
    return PlateGeometry(
        name=f"Take3 spot r{row}c{column}",
        rows=TAKE3_SCAN_POINTS,
        columns=TAKE3_SCAN_POINTS,
        first_well_y=y - half,
        last_well_y=y + half,
        first_well_x=x - half,
        last_well_x=x + half,
        size_y=TAKE3_SIZE_Y,
        size_x=TAKE3_SIZE_X,
        size_z=TAKE3_SIZE_Z,
    )


# Whole-plate geometry with the Take3's real outside dimensions, for reads that
# address spots as 96-well positions rather than scanning them.
TAKE3 = PlateGeometry(
    name="Take3 micro-volume",
    rows=8,
    columns=12,
    first_well_y=11.17,
    last_well_y=74.17,
    first_well_x=14.38,
    last_well_x=113.38,
    size_y=TAKE3_SIZE_Y,
    size_x=TAKE3_SIZE_X,
    size_z=TAKE3_SIZE_Z,
)
