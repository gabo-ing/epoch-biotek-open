"""Take3 micro-volume plate layout.

Confirmed from the factory documentation for plate 243819 (Take3 Pathlength Data
Sheet, 25 January 2011): the micro-volume area is **16 spots, rows A-H, columns 2
and 3**, addressed as positions on the standard 96-well grid. An earlier guess here
had them as a 4x4 block, which was wrong.

The plate also has a cuvette port and a BioCell that this software does not use.
"""

ROWS = "ABCDEFGH"
COLUMNS = (2, 3)

# Each plate carries a sheet of certified pathlengths, measured at the factory, in
# millimetres. They are a cross-check, not an input: the software measures the
# pathlength of every drop at read time from the 977/900 water peak, because what
# matters is how thick *this* drop is, not how deep the well is. Agreement between
# the two is the strongest evidence the optics and the arithmetic are both right.
CERTIFIED_PATHLENGTHS_MM = {
    "A2": 0.5125, "A3": 0.5096,
    "B2": 0.5063, "B3": 0.5087,
    "C2": 0.5041, "C3": 0.5043,
    "D2": 0.4999, "D3": 0.5006,
    "E2": 0.4991, "E3": 0.4992,
    "F2": 0.5003, "F3": 0.4993,
    "G2": 0.4988, "G3": 0.4973,
    "H2": 0.4980, "H3": 0.4982,
}
CERTIFIED_MEAN_MM = 0.5023
CERTIFIED_PLATE_SERIAL = "243819"

# Every Take3 plate the lab owns, by serial number, with the pathlengths from its own
# data sheet. Gen5 keys its plate entries by serial in exactly this way, so a second
# plate would be added here rather than replacing this one -- entering one plate's
# numbers against another plate's spots would be silently wrong.
KNOWN_PLATES = {
    CERTIFIED_PLATE_SERIAL: CERTIFIED_PATHLENGTHS_MM,
}


def pathlengths_for_plate(serial: str | None) -> dict[str, float] | None:
    """The certified pathlength table for a plate, or None if we do not have it.

    None means "fall back to the 0.5 mm nominal", which is what Gen5 does for a
    plate whose sheet was never entered.
    """
    if serial is None:
        return None
    return KNOWN_PLATES.get(str(serial).strip())


def all_wells() -> list[str]:
    """The 16 micro-spots, column by column: A2..H2 then A3..H3."""
    return [f"{row}{column}" for column in COLUMNS for row in ROWS]


def well_to_indices(well: str) -> tuple[int, int]:
    """'C3' -> (3, 3): 1-based row and column, as the reader addresses them."""
    row_letter, column_text = well[0].upper(), well[1:]
    if row_letter not in ROWS:
        raise ValueError(f"row {row_letter!r} is not one of {ROWS}")
    column = int(column_text)
    if column not in COLUMNS:
        raise ValueError(f"column {column} is not one of {COLUMNS}")
    return ROWS.index(row_letter) + 1, column


def indices_to_well(row: int, column: int) -> str:
    """(3, 3) -> 'C3'. Inverse of well_to_indices."""
    if not 1 <= row <= len(ROWS):
        raise ValueError(f"row {row} out of range")
    if column not in COLUMNS:
        raise ValueError(f"column {column} is not one of {COLUMNS}")
    return f"{ROWS[row - 1]}{column}"


def bounds() -> tuple[int, int, int, int]:
    """The rectangle covering every micro-spot: (min_row, min_col, max_row, max_col)."""
    return 1, min(COLUMNS), len(ROWS), max(COLUMNS)
