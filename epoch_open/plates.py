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

    def indices_for(self, well: str) -> tuple[int, int]:
        """'C3' -> (3, 3): 1-based row and column, as the reader addresses them.

        Validated against this geometry rather than against the Take3's spot
        list. Both plates are declared to the reader as 8 x 12 -- the Take3's
        micro-spots sit at ordinary 96-well positions, which is why it is
        addressed as a 12-column plate with only columns 2 and 3 in use -- so
        the reader can address any of the 96 positions on either.

        take3.well_to_indices does the same arithmetic and then refuses
        anything outside columns 2 and 3, which is right when the question is
        "is there a micro-spot there" and wrong when it is "can the optics be
        pointed there". Using it for the latter made a flat 96-well plate
        unreadable: the first real read of one raised "column 1 is not one of
        (2, 3)" before the carriage moved.
        """
        letter, number = well[0].upper(), well[1:]
        row = ord(letter) - ord("A") + 1
        if not 1 <= row <= self.rows:
            raise ValueError(
                f"{well}: row {letter!r} is outside this plate's {self.rows}")
        try:
            column = int(number)
        except ValueError:
            raise ValueError(f"{well}: {number!r} is not a column number")
        if not 1 <= column <= self.columns:
            raise ValueError(
                f"{well}: column {column} is outside this plate's "
                f"{self.columns}")
        return row, column

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
