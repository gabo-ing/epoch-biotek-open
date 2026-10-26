"""Tests for the Take3 layout, from the factory sheet for plate 243819."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import take3  # noqa: E402


class TestTake3Layout:
    def test_plate_holds_sixteen_spots(self):
        assert len(take3.all_wells()) == 16

    def test_spots_are_rows_a_to_h_in_columns_2_and_3(self):
        wells = take3.all_wells()
        assert wells[0] == "A2"
        assert wells[7] == "H2"
        assert wells[8] == "A3"
        assert wells[-1] == "H3"

    def test_names_are_unique(self):
        assert len(set(take3.all_wells())) == 16

    def test_bounds_cover_every_spot(self):
        assert take3.bounds() == (1, 2, 8, 3)

    def test_well_to_indices_is_one_based(self):
        assert take3.well_to_indices("A2") == (1, 2)
        assert take3.well_to_indices("H3") == (8, 3)

    def test_indices_round_trip(self):
        for well in take3.all_wells():
            row, column = take3.well_to_indices(well)
            assert take3.indices_to_well(row, column) == well

    def test_column_1_is_rejected(self):
        # Column 1 is a real 96-well position but not a Take3 micro-spot.
        with pytest.raises(ValueError):
            take3.well_to_indices("A1")

    def test_row_beyond_h_is_rejected(self):
        with pytest.raises(ValueError):
            take3.well_to_indices("I2")


class TestCertifiedPathlengths:
    def test_one_per_spot(self):
        assert set(take3.CERTIFIED_PATHLENGTHS_MM) == set(take3.all_wells())

    def test_all_near_half_a_millimetre(self):
        for well, value in take3.CERTIFIED_PATHLENGTHS_MM.items():
            assert 0.49 < value < 0.52, f"{well} = {value}"

    def test_mean_matches_the_sheet(self):
        values = take3.CERTIFIED_PATHLENGTHS_MM.values()
        assert abs(sum(values) / len(values) - take3.CERTIFIED_MEAN_MM) < 0.0005


class TestKnownPlates:
    def test_our_plate_is_known_by_serial(self):
        table = take3.pathlengths_for_plate("243819")
        assert table is not None
        assert len(table) == 16
        assert table["A2"] == 0.5125

    def test_serial_is_matched_despite_stray_whitespace(self):
        assert take3.pathlengths_for_plate("  243819 ") is not None

    def test_an_unknown_plate_falls_back_to_nominal(self):
        assert take3.pathlengths_for_plate("999999") is None

    def test_no_serial_falls_back_to_nominal(self):
        assert take3.pathlengths_for_plate(None) is None
