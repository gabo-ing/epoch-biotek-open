"""The standard-curve arithmetic, and what it refuses to do.

Unlike the Take3 side, there is no instrument constant to check against here:
a curve assay's answer depends entirely on standards measured in the same run.
So what these tests pin is not a number but a set of refusals -- the cases
where the honest output is "this curve cannot answer that" rather than a
figure that looks like a measurement.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import curve                 # noqa: E402


def series(points, wells=None):
    """Standards from (concentration, absorbance) pairs."""
    wells = wells or [f"A{i + 1}" for i in range(len(points))]
    return [curve.Standard(well=w, concentration=c, absorbance=a)
            for w, (c, a) in zip(wells, points)]


# A clean 0-40 series with a 0.0200 AU per unit response, the shape a real
# Salkowski curve has.
CLEAN = series([(0, 0.000), (5, 0.100), (10, 0.200),
                (20, 0.400), (40, 0.800)])


class TestAGoodCurve:

    def test_it_recovers_the_response_it_was_built_from(self):
        fit = curve.fit_standards(CLEAN)
        assert abs(fit.slope - 0.0200) < 1e-9
        assert abs(fit.intercept) < 1e-9
        assert fit.r_squared > 0.9999
        assert fit.usable
        assert fit.notes == ()

    def test_a_sample_in_the_middle_reads_back_its_concentration(self):
        fit = curve.fit_standards(CLEAN)
        result = curve.read_against("B1", {530: 0.300}, fit)
        assert abs(result.concentration - 15.0) < 1e-6
        assert result.in_range
        assert result.notes == []

    def test_the_blank_is_subtracted_before_the_curve_is_consulted(self):
        """A reagent blank shifts every well, standards included."""
        fit = curve.fit_standards(CLEAN)
        result = curve.read_against("B1", {530: 0.350}, fit, blank=0.050)
        assert abs(result.concentration - 15.0) < 1e-6


class TestItRefusesRatherThanGuesses:

    def test_two_standards_are_not_a_curve(self):
        """r-squared is exactly 1 for any two points, which proves nothing."""
        try:
            curve.fit_standards(series([(0, 0.0), (10, 0.2)]))
        except curve.CurveError:
            return
        raise AssertionError("two standards were accepted as a curve")

    def test_standards_all_at_one_concentration_define_no_line(self):
        fit = curve.fit_standards(series([(5, 0.1), (5, 0.11), (5, 0.09)]))
        assert not fit.usable
        assert [n.code for n in fit.notes] == ["duplicate"]

    def test_a_curve_running_backwards_is_not_used(self):
        """More colour must mean more absorbance, or something is swapped."""
        fit = curve.fit_standards(
            series([(0, 0.9), (10, 0.5), (20, 0.1)]))
        assert not fit.usable
        assert "slope" in [n.code for n in fit.notes]

    def test_no_concentration_comes_off_an_unusable_curve(self):
        """The measurement survives; the interpretation does not.

        This used to raise, which refused the reading as well as the
        concentration. Gen5 reads a plate with no blank and no standards at
        all, and so does this now: the absorbance is a measurement either
        way. What must never happen is a number in the concentration column
        that came off a curve running backwards.
        """
        fit = curve.fit_standards(series([(0, 0.9), (10, 0.5), (20, 0.1)]))
        result = curve.read_against("B1", {530: 0.3}, fit)
        assert result.concentration is None
        assert abs(result.absorbance - 0.3) < 1e-9

    def test_a_plain_read_needs_no_curve_at_all(self):
        result = curve.read_against("B1", {530: 0.42})
        assert result.concentration is None
        assert abs(result.absorbance - 0.42) < 1e-9

    def test_a_plain_read_needs_no_blank(self):
        """Nothing subtracted means raw, not refused."""
        result = curve.read_against("B1", {530: 0.42})
        assert abs(result.absorbance - 0.42) < 1e-9

    def test_a_flat_curve_scores_zero_rather_than_a_perfect_fit(self):
        """Identical absorbances fit a flat line exactly; r2 is 0/0.

        Reporting 1.0 there would be the worst possible answer: a perfect
        score for a curve carrying no information at all.
        """
        fit = curve.fit_standards(series([(0, 0.2), (10, 0.2), (20, 0.2)]))
        assert fit.r_squared == 0.0
        assert not fit.usable


class TestTheEdgesOfTheCurve:

    def test_a_sample_above_the_top_standard_is_flagged_not_reported(self):
        """Colorimetric assays flatten out; past the top point there is no line."""
        fit = curve.fit_standards(CLEAN)
        result = curve.read_against("B1", {530: 1.600}, fit)
        assert not result.in_range
        assert "above_range" in [n.code for n in result.notes]
        # The number is still produced, so it can be seen to be absurd, but it
        # travels with the warning attached.
        assert result.concentration > fit.top_concentration

    def test_the_warning_says_to_dilute(self):
        fit = curve.fit_standards(CLEAN)
        result = curve.read_against("B1", {530: 1.600}, fit)
        message = str(result.notes[0])
        assert "diluye" in message.lower()

    def test_a_sample_below_the_lowest_standard_is_flagged(self):
        fit = curve.fit_standards(CLEAN)
        result = curve.read_against("B1", {530: -0.020}, fit)
        assert not result.in_range
        assert "below_range" in [n.code for n in result.notes]

    def test_reading_below_the_blank_is_called_negative(self):
        fit = curve.fit_standards(CLEAN)
        result = curve.read_against("B1", {530: 0.100}, fit, blank=0.200)
        assert result.concentration < 0
        assert "negative" in [n.code for n in result.notes]


class TestWhenTheCurveIsMerelySuspect:

    def test_a_poor_fit_is_noted_but_still_usable(self):
        """A bad r-squared is worth a second look, not a refusal.

        The technician can see the number and decide. Refusing outright would
        mean a curve that is good enough for a rough answer produces nothing.
        """
        fit = curve.fit_standards(
            series([(0, 0.00), (10, 0.40), (20, 0.10), (40, 0.75)]))
        assert fit.r_squared < curve.R_SQUARED_MIN
        assert "r_squared" in [n.code for n in fit.notes]
        assert fit.usable

    def test_one_badly_placed_standard_is_named(self):
        """So the well to re-pipette is known, not just that something is off."""
        fit = curve.fit_standards(
            series([(0, 0.000), (5, 0.100), (10, 0.200),
                    (20, 0.250), (40, 0.800)]))
        outliers = [n for n in fit.notes if n.code == "outlier"]
        assert outliers, "no standard was singled out"
        assert outliers[0].well == "A4", "named the wrong standard"

    def test_the_named_well_is_a_field_not_a_parsed_sentence(self):
        """The screen colours a well from this, so it cannot depend on wording."""
        fit = curve.fit_standards(
            series([(0, 0.000), (5, 0.100), (10, 0.200),
                    (20, 0.250), (40, 0.800)]))
        note = [n for n in fit.notes if n.code == "outlier"][0]
        assert note.well in ("A4",)
        assert note.well in note.message      # it is in the sentence too

    def test_a_thin_curve_says_so(self):
        fit = curve.fit_standards(series([(0, 0.0), (10, 0.2), (20, 0.4)]))
        assert "thin" in [n.code for n in fit.notes]
        assert fit.usable

    def test_a_saturating_curve_passes_every_automatic_check(self):
        """The known blind spot, pinned so it is not mistaken for safety.

        This is a curve whose absorbance steps shrink as concentration rises --
        a colorimetric assay running out of reagent at the top, which is the
        most likely real failure here. It fits a straight line with
        r-squared 0.99, clears the 0.98 gate, and produces no notes at all.
        Every automatic check passes, and the top of the range is still wrong:
        read against this line, a high sample is under-reported.

        No threshold in this module catches it, and the residual does not
        either -- the worst point sits about 4% of the span off the line,
        inside RESIDUAL_LIMIT. That is why `worst_residual` is on the screen
        and in the exported workbook as a number rather than as a pass mark:
        a person looking at the standards can see a bend that no single
        statistic here will report. The honest fix is experimental, not
        arithmetic -- keep the top standard below saturation, which is what
        the above_range warning pushes samples towards.
        """
        fit = curve.fit_standards(
            series([(0, 0.000), (10, 0.200), (20, 0.380),
                    (30, 0.540), (40, 0.680), (50, 0.800)]))
        assert fit.r_squared > curve.R_SQUARED_MIN, "r2 clears the gate"
        assert fit.notes == (), "and nothing is flagged"
        assert fit.usable

        # The bend is real: the fit under-reads at both ends and over-reads in
        # the middle, which is the signature of a curve that is not a line.
        assert fit.residual(fit.standards[0]) < 0
        assert fit.residual(fit.standards[-1]) < 0
        assert fit.worst_residual() > 0.03
        span = fit.top - fit.bottom
        assert fit.worst_residual() / span < curve.RESIDUAL_LIMIT, (
            "inside the outlier limit, which is the point: it is not caught")


class TestTheReference:

    def test_a_reference_wavelength_is_subtracted(self):
        value = curve.corrected({530: 0.500, 650: 0.080}, 530, reference_nm=650)
        assert abs(value - 0.420) < 1e-9

    def test_without_a_reference_the_reading_is_untouched(self):
        value = curve.corrected({530: 0.500, 650: 0.080}, 530)
        assert abs(value - 0.500) < 1e-9

    def test_asking_for_a_reference_that_was_not_read_is_an_error(self):
        try:
            curve.corrected({530: 0.5}, 530, reference_nm=650)
        except curve.CurveError:
            return
        raise AssertionError("a missing reference passed silently")

    def test_a_missing_measurement_wavelength_is_an_error(self):
        try:
            curve.corrected({650: 0.1}, 530)
        except curve.CurveError:
            return
        raise AssertionError("a missing measurement wavelength passed silently")


class TestFindingThePeak:

    def test_the_scan_asks_for_no_more_than_gen5_does(self):
        """Six, which is where Gen5's own Read Step dialog stops.

        Nine fit the protocol -- the wavelength-count field in the 'D' assay
        record holds one digit -- and nine is what this was until Gen5's read
        dialog was photographed on 3 November 2026 and turned out to offer
        1 to 6. Whether the instrument accepts seven is untested, and the
        vendor's own software never asks, so neither do we.
        """
        assert len(curve.SCAN_NM) == 6
        assert len(curve.SCAN_NM) <= 9, "the protocol could not carry more"

    def test_the_scan_brackets_the_default_wavelength(self):
        assert curve.SCAN_NM[0] < curve.DEFAULT_NM < curve.SCAN_NM[-1]

    def test_it_reports_where_the_colour_actually_absorbed(self):
        readings = {490: 0.10, 510: 0.28, 530: 0.44, 550: 0.31,
                    570: 0.12, 590: 0.04}
        assert curve.peak_wavelength(readings) == 530

    def test_a_peak_elsewhere_is_reported_honestly(self):
        """The point of scanning is to be told when 530 is the wrong default."""
        readings = {490: 0.10, 510: 0.24, 530: 0.40, 550: 0.52,
                    570: 0.22, 590: 0.05}
        assert curve.peak_wavelength(readings) == 550

    def test_an_unread_scan_is_an_error_not_a_guess(self):
        try:
            curve.peak_wavelength({260: 0.5})
        except curve.CurveError:
            return
        raise AssertionError("peak_wavelength invented an answer")
