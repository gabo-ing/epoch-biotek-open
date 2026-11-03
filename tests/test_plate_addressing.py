"""Turning a well name into a position the reader can be pointed at.

This file exists because of a bug that 345 tests did not see. `read_plate`
converted well names with `take3.well_to_indices`, which refuses any column
but 2 and 3 -- correct when the question is "is there a micro-spot there",
wrong when it is "can the optics be pointed there". A flat 96-well plate was
therefore unreadable, and `epoch-multispectral` could never have worked
against the instrument.

Nothing caught it because the simulator has its own `read_plate` that never
touches the conversion, so every test of the colorimetric program ran past
the broken line. It surfaced the first time the real reader was asked for a
96-well plate, on 3 November 2026:

    ValueError: column 1 is not one of (2, 3)

The lesson is in the shape of the mistake rather than the line of code: a
simulator that re-implements the path it is standing in for proves only that
the simulator works.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import take3                       # noqa: E402
from epoch_open.plates import PLATE_96, TAKE3      # noqa: E402
from epoch_open.reader import EpochReader          # noqa: E402


class TestAFlatPlateCanBeAddressed:

    def test_every_one_of_the_96_positions_resolves(self):
        seen = set()
        for row in "ABCDEFGH":
            for column in range(1, 13):
                seen.add(PLATE_96.indices_for(f"{row}{column}"))
        assert len(seen) == 96

    def test_the_corners_land_where_they_should(self):
        assert PLATE_96.indices_for("A1") == (1, 1)
        assert PLATE_96.indices_for("H12") == (8, 12)
        assert PLATE_96.indices_for("D6") == (4, 6)

    def test_column_one_is_addressable(self):
        """The exact call that failed against the instrument."""
        assert PLATE_96.indices_for("A1") == (1, 1)

    def test_a_lowercase_row_is_accepted(self):
        assert PLATE_96.indices_for("c7") == PLATE_96.indices_for("C7")

    def test_off_the_plate_is_refused(self):
        for bad in ("A0", "A13", "I1", "Z4"):
            try:
                PLATE_96.indices_for(bad)
            except ValueError:
                continue
            raise AssertionError(f"{bad} was accepted")

    def test_rubbish_is_refused_rather_than_guessed(self):
        for bad in ("AA", "A", "Ax"):
            try:
                PLATE_96.indices_for(bad)
            except (ValueError, IndexError):
                continue
            raise AssertionError(f"{bad} was accepted")


class TestTheTake3StillAddressesItsSpots:

    def test_its_micro_spots_resolve_the_same_way_as_before(self):
        """The Take3 is declared to the reader as an 8 x 12 plate.

        Its spots sit at ordinary 96-well positions, which is why it is
        addressed as a 12-column plate with only columns 2 and 3 in use. So
        the geometry must agree with take3's own mapping on every real spot.
        """
        for row in take3.ROWS:
            for column in take3.COLUMNS:
                well = f"{row}{column}"
                assert TAKE3.indices_for(well) == take3.well_to_indices(well)

    def test_the_geometry_allows_what_the_spot_list_does_not(self):
        """Two different questions, and they are allowed to disagree.

        take3.well_to_indices answers "is there a micro-spot at A1" -- no.
        The geometry answers "can the carriage be sent to A1" -- yes, it is
        an ordinary 96-well position. Conflating them is what broke the flat
        plate.
        """
        assert TAKE3.indices_for("A1") == (1, 1)
        try:
            take3.well_to_indices("A1")
        except ValueError:
            return
        raise AssertionError("take3 should still refuse A1 as a spot")


class TestTheBoundingRectangle:

    def test_it_covers_a_whole_flat_plate(self):
        wells = [f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]
        assert EpochReader.bounding_rectangle(wells, PLATE_96) == (1, 1, 8, 12)

    def test_it_tightens_to_what_was_asked_for(self):
        assert EpochReader.bounding_rectangle(
            ["B2", "D5"], PLATE_96) == (2, 2, 4, 5)

    def test_it_still_defaults_to_the_take3(self):
        """Called without a geometry it must behave as it always did."""
        assert EpochReader.bounding_rectangle(["A2", "H3"]) == (1, 2, 8, 3)
