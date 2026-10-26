"""Tests for the quantification math.

The important ones reproduce this lab's own Gen5 numbers for plate 243819 on reader
254717. If these fail, results would silently disagree with years of historical data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open.quant import (  # noqa: E402
    PATHLENGTH_MM,
    QuantError,
    RawWell,
    quantify,
    to_1cm,
    wavelengths_for,
)


class TestAgainstRealGen5Output:
    """Row B2 of 14-1-14 ..._forma2.xlsx: raw 260/280/320 and what Gen5 reported.

    The blank is not in that export; it is reconstructed from Gen5's own corrected
    values, so what these pin is the shape of the calculation -- subtract 320,
    subtract the blank, divide by 0.5 mm, multiply by 50 -- not the blank itself.
    """

    SAMPLE = RawWell("B2", {260: 0.098, 280: 0.074, 320: 0.044})
    BLANK = RawWell("B2 blank", {260: 0.0528, 280: 0.0492, 320: 0.0440})
    GEN5_NG_UL = 45.23
    GEN5_RATIO = 1.825

    def test_concentration_matches_gen5(self):
        result = quantify(self.SAMPLE, self.BLANK)
        assert result.concentration == pytest.approx(self.GEN5_NG_UL, abs=0.5)

    def test_ratio_matches_gen5(self):
        result = quantify(self.SAMPLE, self.BLANK)
        assert result.ratio_260_280 == pytest.approx(self.GEN5_RATIO, abs=0.02)

    def test_concentration_is_a260_times_1000_for_dsdna(self):
        # 0.5 mm path and a factor of 50 collapse to exactly x1000.
        result = quantify(self.SAMPLE, self.BLANK)
        assert result.concentration == pytest.approx(result.a260 * 1000, rel=1e-9)

    def test_unit_is_ng_per_ul(self):
        assert quantify(self.SAMPLE, self.BLANK).unit == "ng/uL"


class TestBackgroundAndBlank:
    def test_reference_is_subtracted_from_each_wavelength(self):
        sample = RawWell("A2", {260: 0.100, 280: 0.060, 320: 0.040})
        result = quantify(sample)
        assert result.a260 == pytest.approx(0.060)
        assert result.a_secondary == pytest.approx(0.020)

    def test_blank_is_subtracted_after_the_background(self):
        sample = RawWell("A2", {260: 0.100, 280: 0.060, 320: 0.040})
        blank = RawWell("blank", {260: 0.050, 280: 0.045, 320: 0.040})
        result = quantify(sample, blank)
        assert result.a260 == pytest.approx(0.050)

    def test_a_missing_reference_reading_is_refused(self):
        with pytest.raises(QuantError, match="reference"):
            RawWell("A2", {260: 0.1, 280: 0.06})

    def test_a_missing_measurement_wavelength_is_reported(self):
        with pytest.raises(QuantError, match="no reading at"):
            quantify(RawWell("A2", {280: 0.06, 320: 0.04}))


class TestPathlength:
    def test_nominal_path_is_half_a_millimetre(self):
        assert PATHLENGTH_MM == 0.5

    def test_scaling_to_1cm_is_a_factor_of_twenty(self):
        assert to_1cm(0.05) == pytest.approx(1.0)


class TestSampleTypes:
    SAMPLE = RawWell("A2", {230: 0.050, 260: 0.100, 280: 0.060, 320: 0.040})

    def test_rna_uses_its_own_extinction(self):
        assert quantify(self.SAMPLE, sample_type="RNA").concentration == pytest.approx(
            0.060 * 20 * 40
        )

    def test_ssdna_uses_its_own_extinction(self):
        assert quantify(self.SAMPLE, sample_type="ssDNA").concentration == pytest.approx(
            0.060 * 20 * 33
        )

    def test_protein_is_reported_in_mg_per_ml(self):
        result = quantify(self.SAMPLE, sample_type="protein")
        assert result.unit == "mg/mL"

    def test_unknown_type_is_rejected(self):
        with pytest.raises(QuantError, match="Unknown sample type"):
            quantify(self.SAMPLE, sample_type="lipids")

    def test_260_230_is_computed_when_230_was_read(self):
        assert quantify(self.SAMPLE).ratio_260_230 is not None

    def test_260_230_is_absent_when_230_was_not_read(self):
        without = RawWell("A2", {260: 0.100, 280: 0.060, 320: 0.040})
        assert quantify(without).ratio_260_230 is None


class TestWavelengthPlanning:
    def test_reference_is_always_included(self):
        assert 320 in wavelengths_for("dsDNA")

    def test_230_is_added_only_when_asked(self):
        assert 230 not in wavelengths_for("dsDNA")
        assert 230 in wavelengths_for("dsDNA", with_230=True)


class TestWarnings:
    BLANK = RawWell("blank", {260: 0.045, 280: 0.045, 320: 0.040})

    def test_high_reference_is_flagged(self):
        dirty = RawWell("A2", {260: 0.200, 280: 0.150, 320: 0.090})
        result = quantify(dirty, self.BLANK)
        assert any(w.code == "high_reference" for w in result.warnings)

    def test_noise_floor_is_flagged(self):
        faint = RawWell("A2", {260: 0.046, 280: 0.0455, 320: 0.0405})
        result = quantify(faint, self.BLANK)
        assert any(w.code == "noise_floor" for w in result.warnings)

    def test_negative_concentration_is_explained(self):
        below = RawWell("A2", {260: 0.030, 280: 0.030, 320: 0.040})
        result = quantify(below, self.BLANK)
        assert any(w.code == "negative" for w in result.warnings)

    def test_clean_sample_has_no_warnings(self):
        clean = RawWell("A2", {260: 0.098, 280: 0.074, 320: 0.0405})
        blank = RawWell("blank", {260: 0.0528, 280: 0.0492, 320: 0.0400})
        assert quantify(clean, blank).warnings == []


class TestAgainstRealGen5WithItsOwnBlank:
    """31-3-15 DNA APP G/H/I: six wells and the blank Gen5 actually used.

    This export includes its blank table, so nothing here is reconstructed. If these
    break, the software has stopped agreeing with the lab's historical results.
    """

    BLANK = RawWell("B3", {260: 0.053, 280: 0.049, 320: 0.044})
    ROWS = [
        # well, 260 raw, 280 raw, 320 raw, Gen5 corrected 260, Gen5 ng/uL
        ("C2", 0.058, 0.053, 0.044, 0.005, 5.257),
        ("C3", 0.052, 0.049, 0.043, 0.000, -0.297),
        ("D2", 0.087, 0.073, 0.056, 0.022, 22.404),
        ("D3", 0.059, 0.054, 0.048, 0.002, 2.497),
        ("E2", 0.072, 0.063, 0.052, 0.011, 11.020),
        ("E3", 0.051, 0.047, 0.041, 0.001, 1.402),
    ]

    def results(self):
        for well, a260, a280, a320, gen5_260, gen5_ng in self.ROWS:
            sample = RawWell(well, {260: a260, 280: a280, 320: a320})
            yield well, quantify(sample, self.BLANK), gen5_260, gen5_ng

    def test_corrected_260_matches_gen5_for_every_well(self):
        for well, result, gen5_260, _ in self.results():
            assert result.a260 == pytest.approx(gen5_260, abs=5e-4), well

    def test_concentration_matches_gen5_within_rounding(self):
        # Gen5 reports from unrounded absorbances; the export rounds the raws to
        # three decimals, so agreement is limited to +/-1 ng/uL by the file itself.
        for well, result, _, gen5_ng in self.results():
            assert result.concentration == pytest.approx(gen5_ng, abs=1.0), well

    def test_a_single_blank_well_serves_every_sample(self):
        blanks = {"B3": self.BLANK}
        from epoch_open.quant import blank_for

        assert blank_for(blanks, "E2") is self.BLANK

    def test_empty_second_elution_reads_as_about_zero(self):
        # C3 is a second elution with nothing left in it; Gen5 reported -0.297.
        result = quantify(
            RawWell("C3", {260: 0.052, 280: 0.049, 320: 0.043}), self.BLANK
        )
        assert abs(result.concentration) < 1.0
        assert any(w.code == "noise_floor" for w in result.warnings)


class TestBlankSelection:
    A = RawWell("B2", {260: 0.050, 280: 0.046, 320: 0.040})
    B = RawWell("B3", {260: 0.052, 280: 0.048, 320: 0.042})

    def test_exact_well_blank_wins(self):
        from epoch_open.quant import blank_for

        assert blank_for({"B2": self.A, "B3": self.B}, "B2") is self.A

    def test_several_blanks_are_averaged_for_other_wells(self):
        from epoch_open.quant import blank_for

        averaged = blank_for({"B2": self.A, "B3": self.B}, "E2")
        assert averaged.readings[260] == pytest.approx(0.051)
        assert averaged.readings[320] == pytest.approx(0.041)

    def test_no_blank_means_no_subtraction(self):
        from epoch_open.quant import blank_for

        assert blank_for(None, "B2") is None


class TestAgainstRealGen5RNA:
    """clean_RNA_test_SA-APA: RNA, with two blank wells averaged by Gen5.

    Agreement is limited to about +/-1 ng/uL because the export rounds its raw
    absorbances to three decimals while Gen5 computed from unrounded ones.
    """

    BLANKS = {
        "A2": RawWell("A2", {260: 0.043, 280: 0.041, 320: 0.038}),
        "A3": RawWell("A3", {260: 0.044, 280: 0.041, 320: 0.038}),
    }
    ROWS = [
        ("B2", 0.056, 0.050, 0.039, 9.165),
        ("B3", 0.090, 0.067, 0.040, 34.913),
        ("C2", 0.054, 0.050, 0.039, 7.062),
        ("C3", 0.098, 0.073, 0.044, 38.311),
    ]

    def blank(self):
        from epoch_open.quant import average_blank

        return average_blank(self.BLANKS)

    def test_blank_average_matches_the_export(self):
        """Gen5's [AVE] row displays 0.044 / 0.041 / 0.038.

        The true mean of 0.043 and 0.044 is 0.0435; Gen5 shows 0.044 because it
        rounds half upward for display. We keep the unrounded mean and only round
        when printing, which is why this checks the mean rather than the display.
        """
        averaged = self.blank()
        assert averaged.readings[260] == pytest.approx(0.0435)
        assert averaged.readings[280] == pytest.approx(0.041)
        assert averaged.readings[320] == pytest.approx(0.038)

    def test_rna_concentrations_match_gen5(self):
        blank = self.blank()
        for well, a260, a280, a320, gen5_ng in self.ROWS:
            result = quantify(
                RawWell(well, {260: a260, 280: a280, 320: a320}), blank, "RNA"
            )
            assert result.concentration == pytest.approx(gen5_ng, abs=1.0), well

    def test_rna_factor_is_forty(self):
        blank = self.blank()
        result = quantify(
            RawWell("B3", {260: 0.090, 280: 0.067, 320: 0.040}), blank, "RNA"
        )
        # 0.5 mm path and a factor of 40 collapse to x800.
        assert result.concentration == pytest.approx(result.a260 * 800, rel=1e-9)


class TestBlankConsistency:
    def test_agreeing_blanks_raise_nothing(self):
        from epoch_open.quant import check_blanks

        blanks = {
            "A2": RawWell("A2", {260: 0.043, 320: 0.038}),
            "A3": RawWell("A3", {260: 0.044, 320: 0.038}),
        }
        assert check_blanks(blanks) == []

    def test_disagreeing_blanks_are_flagged(self):
        from epoch_open.quant import check_blanks

        blanks = {
            "A2": RawWell("A2", {260: 0.043, 320: 0.038}),
            "A3": RawWell("A3", {260: 0.095, 320: 0.038}),
        }
        warnings = check_blanks(blanks)
        assert warnings and warnings[0].code == "blank_spread"

    def test_a_single_blank_has_no_spread(self):
        from epoch_open.quant import blank_cv_percent, check_blanks

        blanks = {"A2": RawWell("A2", {260: 0.043, 320: 0.038})}
        assert blank_cv_percent(blanks) == 0.0
        assert check_blanks(blanks) == []


class TestPathlengthTable:
    SAMPLE = RawWell("A2", {260: 0.098, 280: 0.074, 320: 0.044})
    BLANK = RawWell("blank", {260: 0.0528, 280: 0.0492, 320: 0.0440})

    def test_nominal_is_used_when_no_table_is_given(self):
        from epoch_open.quant import DEFAULT_PATHLENGTH_MM

        result = quantify(self.SAMPLE, self.BLANK)
        assert result.pathlength_mm == DEFAULT_PATHLENGTH_MM

    def test_certified_table_changes_the_result(self):
        from epoch_open.take3 import CERTIFIED_PATHLENGTHS_MM

        nominal = quantify(self.SAMPLE, self.BLANK)
        certified = quantify(
            self.SAMPLE, self.BLANK, "dsDNA", CERTIFIED_PATHLENGTHS_MM
        )
        assert certified.pathlength_mm == 0.5125
        # A2 is the worst case on this plate: about 2.4% low if 0.5 is assumed.
        assert certified.concentration < nominal.concentration
        relative = abs(certified.concentration - nominal.concentration) / nominal.concentration
        assert 0.02 < relative < 0.03

    def test_a_scalar_pathlength_applies_everywhere(self):
        result = quantify(self.SAMPLE, self.BLANK, "dsDNA", 0.52)
        assert result.pathlength_mm == 0.52

    def test_a_well_missing_from_the_table_falls_back_to_nominal(self):
        result = quantify(self.SAMPLE, self.BLANK, "dsDNA", {"H3": 0.4982})
        assert result.pathlength_mm == 0.5

    def test_an_implausible_pathlength_is_refused(self):
        # The message is Spanish now; match on something stable within it.
        with pytest.raises(QuantError, match="poco creible"):
            quantify(self.SAMPLE, self.BLANK, "dsDNA", {"A2": 5.0})

    def test_default_table_is_half_a_millimetre_everywhere(self):
        from epoch_open.quant import default_pathlengths
        from epoch_open import take3

        table = default_pathlengths(take3.all_wells())
        assert len(table) == 16
        assert set(table.values()) == {0.5}


class TestWarningMessages:
    """Warnings carry a stable code and Spanish text for the technician."""

    BLANK = RawWell("blank", {260: 0.045, 280: 0.045, 320: 0.040})

    def test_warning_has_a_code_and_a_message(self):
        faint = RawWell("A2", {260: 0.046, 280: 0.0455, 320: 0.0405})
        warning = quantify(faint, self.BLANK).warnings[0]
        assert warning.code == "noise_floor"
        assert warning.message

    def test_messages_are_in_spanish(self):
        faint = RawWell("A2", {260: 0.046, 280: 0.0455, 320: 0.0405})
        message = quantify(faint, self.BLANK).warnings[0].message
        assert "limite de deteccion" in message
        assert "noise floor" not in message

    def test_every_code_has_a_message_template(self):
        from epoch_open.quant import MESSAGES

        expected = {
            "high_reference", "noise_floor", "ratio_260_280", "ratio_260_230",
            "negative", "blank_spread", "pathlength",
        }
        assert expected <= set(MESSAGES)

    def test_str_of_a_warning_is_its_message(self):
        from epoch_open.quant import warn

        warning = warn("noise_floor")
        assert str(warning) == warning.message
