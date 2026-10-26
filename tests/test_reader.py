"""Tests for command construction and response parsing.

These need no instrument: they pin the wire format so a later refactor cannot
silently change what gets sent to the reader.
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open.plates import PLATE_96, PlateGeometry  # noqa: E402
from epoch_open.reader import EpochReader, MockReader  # noqa: E402


class TestPlateGeometry:
    def test_96_well_matches_the_documented_example(self):
        # The worked example in PyLabRobot's backend, byte for byte.
        assert PLATE_96.to_command() == "08120112207434014351135308559127881422\x03"

    def test_command_ends_with_etx(self):
        assert PLATE_96.to_command().endswith("\x03")

    def test_fields_are_zero_padded_to_fixed_width(self):
        small = PlateGeometry(
            name="t", rows=4, columns=4,
            first_well_y=1.0, last_well_y=2.0, first_well_x=3.0, last_well_x=4.0,
            size_y=5.0, size_x=6.0, size_z=7.0,
        )
        body = small.to_command().rstrip("\x03")
        # 2+2+5+5+5+5+5+5+4 = 38 characters, always.
        assert len(body) == 38
        assert body.startswith("0404")


class TestAbsorbanceCommand:
    # The exact record the reader accepted on 2026-10-22 (serial 254717, fw 1.12).
    CONFIRMED = "00460101010202000120010000110010000010000080260047"

    def test_matches_the_record_the_instrument_accepted(self):
        assert EpochReader._absorbance_command(260, 1, 1, 2, 2) == self.CONFIRMED

    def test_length_field_counts_body_plus_checksum(self):
        command = EpochReader._absorbance_command(260, 1, 1, 8, 12)
        body = command[4:-3]
        assert int(command[:4]) == len(body) + 3
        assert int(command[:4]) == len(command) - 4

    def test_checksum_is_byte_sum_mod_256(self):
        command = EpochReader._absorbance_command(260, 1, 1, 8, 12)
        body = command[4:-3]
        assert command[-3:] == f"{sum(body.encode()) % 256:03}"

    def test_extended_optics_adds_the_path_byte(self):
        plain = EpochReader._absorbance_command(260, 1, 1, 2, 2)
        extended = EpochReader._absorbance_command(
            260, 1, 1, 2, 2, extended_optics=True
        )
        # One character longer, and the length field tracks it.
        assert len(extended) == len(plain) + 1
        assert int(extended[:4]) == int(plain[:4]) + 1

    def test_extra_read_field_adds_three_digits(self):
        plain = EpochReader._absorbance_command(260, 1, 1, 2, 2)
        extra = EpochReader._absorbance_command(
            260, 1, 1, 2, 2, extra_read_field=True
        )
        assert len(extra) == len(plain) + 3

    def test_wavelength_is_four_digits(self):
        assert "0260" in EpochReader._absorbance_command(260, 1, 1, 8, 12)
        assert "0977" in EpochReader._absorbance_command(977, 1, 1, 8, 12)

    def test_well_bounds_are_two_digits_each(self):
        command = EpochReader._absorbance_command(260, 2, 3, 4, 11)
        assert command[4:].startswith("01" + "02" + "03" + "04" + "11")

    def test_no_etx_follows_the_checksum(self):
        # The length field delimits the record; an ETX here is rejected.
        assert not EpochReader._absorbance_command(260, 1, 1, 8, 12).endswith("\x03")

    def test_wavelength_out_of_range_is_rejected(self):
        with pytest.raises(ValueError):
            EpochReader._absorbance_command(100, 1, 1, 8, 12)
        with pytest.raises(ValueError):
            EpochReader._absorbance_command(1200, 1, 1, 8, 12)

    def test_unordered_bounds_are_rejected(self):
        with pytest.raises(ValueError):
            EpochReader._absorbance_command(260, 5, 1, 2, 2)

    def test_whole_range_of_interest_is_accepted(self):
        for wavelength in (230, 260, 280, 900, 977):
            assert EpochReader._absorbance_command(wavelength, 1, 1, 4, 4)


class TestRealResponseParsing:
    """The exact body the instrument returned for a 2x2 read of an empty carriage."""

    REAL = (
        b"01,1,\r000:00:00.0,000,01,01,+0.0000,01,02,+0.0000\r\n"
        b",02,02,+0.0000,02,01,+0.0000\r\n000\x1a246\x1a0000\x03"
    )

    def test_all_four_wells_are_recovered(self):
        parsed = EpochReader._parse_body(self.REAL)
        assert set(parsed) == {(1, 1), (1, 2), (2, 1), (2, 2)}

    def test_values_are_zero_for_an_empty_carriage(self):
        parsed = EpochReader._parse_body(self.REAL)
        assert all(value == 0.0 for value in parsed.values())

    def test_trailing_checksum_block_is_not_mistaken_for_data(self):
        parsed = EpochReader._parse_body(self.REAL)
        assert len(parsed) == 4


class TestBodyParsing:
    HEADER = b"x" * 22

    def test_triples_become_row_column_value(self):
        body = self.HEADER + b"1,1,0.123,1,2,0.456\r\n"
        assert EpochReader._parse_body(body) == {(1, 1): 0.123, (1, 2): 0.456}

    def test_multiple_rows_are_parsed(self):
        body = self.HEADER + b"1,1,0.100\r\n,2,1,0.200\r\n"
        parsed = EpochReader._parse_body(body)
        assert parsed[(1, 1)] == 0.100
        assert parsed[(2, 1)] == 0.200

    def test_overflow_marker_becomes_nan(self):
        body = self.HEADER + b"1,1,*****\r\n"
        assert math.isnan(EpochReader._parse_body(body)[(1, 1)])

    def test_indices_stay_one_based(self):
        body = self.HEADER + b"8,12,0.500\r\n"
        assert (8, 12) in EpochReader._parse_body(body)

    def test_malformed_response_is_reported_clearly(self):
        from epoch_open.reader import ReaderError

        with pytest.raises(ReaderError, match="not in the expected form"):
            EpochReader._parse_body(b"nonsense with no line ending")


class TestMockReaderStillWorks:
    def test_mock_returns_a_reading_per_well(self):
        readings = MockReader(seed=1).read_wells(["B2", "B3"])
        assert set(readings) == {"B2", "B3"}

    def test_mock_includes_the_reference_wavelength(self):
        reading = MockReader(seed=1).read_wells(["B2"])["B2"]
        assert 320 in reading.readings

    def test_mock_honours_the_requested_wavelengths(self):
        reading = MockReader(seed=1).read_wells(["B2"], [230, 260, 280, 320])["B2"]
        assert set(reading.readings) == {230, 260, 280, 320}

    def test_mock_blank_has_almost_no_signal(self):
        blank = MockReader(seed=3, blank=True).read_wells(["B2"])["B2"]
        assert abs(blank.corrected(260)) < 0.005


class TestWellSelection:
    def test_a_single_well_is_its_own_rectangle(self):
        assert EpochReader.bounding_rectangle(["C2"]) == (3, 2, 3, 2)

    def test_a_column_of_wells(self):
        # The real 'extraccion_gabriel' read: column 3, rows E to H.
        assert EpochReader.bounding_rectangle(["E3", "F3", "G3", "H3"]) == (5, 3, 8, 3)

    def test_two_wells_in_one_column(self):
        # The real 'apa_y_app_salting_out' read: column 2, rows C and D.
        assert EpochReader.bounding_rectangle(["C2", "D2"]) == (3, 2, 4, 2)

    def test_scattered_wells_give_the_enclosing_block(self):
        assert EpochReader.bounding_rectangle(["C2", "F3"]) == (3, 2, 6, 3)

    def test_order_does_not_matter(self):
        assert EpochReader.bounding_rectangle(["H3", "A2"]) == (1, 2, 8, 3)

    def test_whole_plate(self):
        from epoch_open import take3

        assert EpochReader.bounding_rectangle(take3.all_wells()) == (1, 2, 8, 3)

    def test_empty_selection_is_refused(self):
        with pytest.raises(ValueError):
            EpochReader.bounding_rectangle([])


class TestSimulatedBlank:
    def test_blank_mode_produces_no_signal(self):
        reader = MockReader(seed=5)
        reader.simulating_blank = True
        blank = reader.read_wells(["B2"])["B2"]
        assert abs(blank.corrected(260)) < 0.005

    def test_sample_mode_produces_signal(self):
        reader = MockReader(seed=5)
        reader.simulating_blank = False
        sample = reader.read_wells(["B2"])["B2"]
        assert sample.corrected(260) > 0.004

    def test_a_simulated_sample_quantifies_positive_against_its_blank(self):
        """The defect this guards: a blank with sample-strength signal made every
        simulated concentration negative, which looked like a maths bug."""
        from epoch_open.quant import quantify

        reader = MockReader(seed=7)
        reader.simulating_blank = True
        blank = reader.read_wells(["B2"])["B2"]
        reader.simulating_blank = False
        sample = reader.read_wells(["B2"])["B2"]

        assert quantify(sample, blank).concentration > 0


class TestTake3Geometry:
    """Pinned to the strings Gen5 itself sent, from captures/lecturas.pcap."""

    GEN5_A2 = "21210089201342021130256308534127761750"
    GEN5_H2 = "21210719207642021130256308534127761750"

    def test_a2_scan_matches_gen5_exactly(self):
        from epoch_open.plates import take3_spot_geometry

        assert take3_spot_geometry(1, 2).to_command().rstrip("\x03") == self.GEN5_A2

    def test_h2_scan_matches_gen5_exactly(self):
        from epoch_open.plates import take3_spot_geometry

        assert take3_spot_geometry(8, 2).to_command().rstrip("\x03") == self.GEN5_H2

    def test_scan_is_a_21_by_21_raster(self):
        from epoch_open.plates import take3_spot_geometry

        geometry = take3_spot_geometry(1, 2)
        assert (geometry.rows, geometry.columns) == (21, 21)

    def test_scan_square_is_4_5_mm(self):
        from epoch_open.plates import take3_spot_geometry

        g = take3_spot_geometry(1, 2)
        assert g.last_well_x - g.first_well_x == pytest.approx(4.5)
        assert g.last_well_y - g.first_well_y == pytest.approx(4.5)

    def test_plate_is_17_5_mm_tall(self):
        """Not the 96-well 14.22 mm assumed before Gen5's own string was seen."""
        from epoch_open.plates import TAKE3, TAKE3_SIZE_Z

        assert TAKE3_SIZE_Z == 17.50
        assert TAKE3.size_z == 17.50

    def test_row_pitch_is_9_mm(self):
        from epoch_open.plates import take3_spot_centre

        assert take3_spot_centre(2, 2)[1] - take3_spot_centre(1, 2)[1] == pytest.approx(9.0)

    def test_column_3_is_9_mm_right_of_column_2(self):
        from epoch_open.plates import take3_spot_centre

        assert take3_spot_centre(1, 3)[0] - take3_spot_centre(1, 2)[0] == pytest.approx(9.0)


class TestCalibrationCaptureFindings:
    """What captures/calibracion.pcap showed about the calibration routine."""

    def test_the_overflow_marker_parses_as_nan(self):
        import math

        body = b"x" * 22 + b"01,01,*******\r\n"
        parsed = EpochReader._parse_body(body)
        assert math.isnan(parsed[(1, 1)])

    def test_the_real_body_header_is_22_bytes(self):
        # "01,1,\r000:00:00.0,000," is exactly 22 bytes before the first triple.
        header = b"01,1,\r000:00:00.0,000,"
        assert len(header) == 22
        parsed = EpochReader._parse_body(header + b"01,01,+0.5000\r\n")
        assert parsed[(1, 1)] == 0.5


class TestBatchedRead:
    """Multi-wavelength assay and reply parsing, pinned to captured Gen5 traffic."""

    GEN5_ASSAY = "0066110102080200012001000011001000003000008026000000802800000080320024"

    def test_assay_matches_gen5_byte_for_byte(self):
        built = EpochReader._multi_absorbance_command([260, 280, 320], 1, 2, 8, 2)
        assert built == self.GEN5_ASSAY

    def test_wavelength_count_is_the_last_digit_of_the_read_event(self):
        for n, wls in ((1, [260]), (2, [260, 320]), (3, [260, 280, 320])):
            cmd = EpochReader._multi_absorbance_command(wls, 1, 2, 8, 2)
            assert cmd[4:].startswith("11")
            assert f"100100000{n}" in cmd

    def test_each_wavelength_adds_a_ten_character_block(self):
        one = EpochReader._multi_absorbance_command([260], 1, 2, 8, 2)
        three = EpochReader._multi_absorbance_command([260, 280, 320], 1, 2, 8, 2)
        assert len(three) == len(one) + 20

    def test_too_many_wavelengths_is_refused(self):
        with pytest.raises(ValueError, match="single digit"):
            EpochReader._multi_absorbance_command(list(range(200, 210)), 1, 2, 8, 2)

    def test_no_wavelengths_is_refused(self):
        with pytest.raises(ValueError):
            EpochReader._multi_absorbance_command([], 1, 2, 8, 2)

    # A real reply captured from the instrument, trimmed to two wells per block.
    REPLY = (
        b"01,1,\r000:00:00.0,000,01,02,+0.0462,08,02,+0.0473\r\n000\x1a084"
        b"\r000:00:08.7,000,01,02,+0.0442,08,02,+0.0445\r\n000\x1a079"
        b"\r000:00:17.6,000,01,02,+0.0412,08,02,+0.0409\r\n000\x1a081\x1a0000\x03"
    )

    def test_reply_splits_into_one_table_per_wavelength(self):
        tables = EpochReader._parse_multi_body(self.REPLY, 3)
        assert len(tables) == 3

    def test_values_land_in_the_right_block(self):
        a260, a280, a320 = EpochReader._parse_multi_body(self.REPLY, 3)
        assert a260[(1, 2)] == 0.0462      # matches Gen5's export for this blank
        assert a280[(1, 2)] == 0.0442
        assert a320[(1, 2)] == 0.0412

    def test_last_well_of_each_block_is_kept(self):
        a260, _a280, a320 = EpochReader._parse_multi_body(self.REPLY, 3)
        assert a260[(8, 2)] == 0.0473
        assert a320[(8, 2)] == 0.0409

    def test_a_wrong_block_count_is_reported(self):
        from epoch_open.reader import ReaderError

        with pytest.raises(ReaderError, match="Expected 2 wavelength blocks"):
            EpochReader._parse_multi_body(self.REPLY, 2)

    def test_trailing_checksum_is_not_read_as_data(self):
        tables = EpochReader._parse_multi_body(self.REPLY, 3)
        assert all(len(t) == 2 for t in tables)


class TestBatchingIsTheDefault:
    def test_read_wells_batches_unless_told_otherwise(self):
        import inspect

        signature = inspect.signature(EpochReader.read_wells)
        assert signature.parameters["batch"].default is True

    def test_sequential_path_is_still_available(self):
        import inspect

        # Kept deliberately: it is the path proven first, and useful for diagnosis.
        assert "batch" in inspect.signature(EpochReader.read_wells).parameters
