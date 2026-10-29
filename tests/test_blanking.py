"""Judging a set of blank wells before anything is quantified against them.

The workflow this protects is the technician's own, described at the bench: read
the blanks, look at the grid, and if a spot is off, wipe the plate and blank
again until they all come up good. The program has to be able to say which spot
is off, and has to refuse to quantify until none of them is.

The one piece of ground truth available is Gen5_LVA_NAQ_0001, an eight-well
blanking run that Gen5 itself declared VALID. Anything here that claims to match
Gen5 is checked against that file. The pass/fail thresholds are *not* from Gen5 --
there is no export of a run it rejected -- so they are this project's own, and
the tests below pin the behaviour we chose rather than a recovered constant.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open.quant import (                          # noqa: E402
    BLANK_DIVERGENCE_LIMIT_AU,
    BLANK_SPREAD_LIMIT_AU,
    RawWell,
    blank_report,
    divergent_blank_wells,
)

# Exactly the numbers in the "Blank Results" table of Gen5_LVA_NAQ_0001:
# 260 / 280 / 320 nm raw absorbance per well. Gen5 printed Status VALID.
GEN5_VALID_RUN = {
    "A2": (0.046, 0.044, 0.041),
    "B2": (0.046, 0.043, 0.040),
    "C2": (0.046, 0.043, 0.039),
    "D2": (0.050, 0.047, 0.043),
    "E2": (0.049, 0.046, 0.043),
    "F2": (0.050, 0.047, 0.043),
    "G2": (0.044, 0.042, 0.039),
    "H2": (0.047, 0.044, 0.040),
}

# The per-wavelength CV Gen5 printed on the [AVE] row of that same table.
GEN5_REPORTED_CV = {260: 4.32, 280: 4.22, 320: 4.23}


def wells(table):
    return {name: RawWell(well=name,
                          readings={260: v[0], 280: v[1], 320: v[2]})
            for name, v in table.items()}


def flat(names, delta_260=0.0):
    """Blank wells that all read the same, optionally with one pulled away."""
    table = {}
    for index, name in enumerate(names):
        offset = delta_260 if index == 0 else 0.0
        table[name] = (0.046 + offset, 0.044, 0.041)
    return wells(table)


class TestAgainstTheOneRealRun:
    def test_the_run_gen5_called_valid_is_called_valid_here(self):
        report = blank_report(wells(GEN5_VALID_RUN))
        assert report.valid
        assert report.divergent == ()
        assert report.reason == ""

    def test_a_blank_gen5_passed_keeps_room_under_both_limits(self):
        """The thresholds have to clear real good blanks, not just scrape past.

        This run spans 0,002 AU, half the spread limit, and its worst well sits
        0,0015 AU from the median against a 0,003 divergence limit. Those two
        margins are what the defaults were set from; if a change here makes this
        test tight, the change will be reddening wells at the bench on blanks
        the instrument's own software was happy with.
        """
        report = blank_report(wells(GEN5_VALID_RUN))
        assert report.spread_au <= BLANK_SPREAD_LIMIT_AU / 2 + 1e-9
        assert divergent_blank_wells(wells(GEN5_VALID_RUN),
                                     BLANK_DIVERGENCE_LIMIT_AU * 0.8) == set()

    def test_the_cv_is_reported_for_every_wavelength_read(self):
        report = blank_report(wells(GEN5_VALID_RUN))
        assert sorted(report.cv_percent) == [260, 280, 320]

    def test_the_cv_agrees_with_gen5_to_a_few_tenths(self):
        """Exact agreement is not available and is not claimed.

        Gen5 rounds the raw absorbances to three decimals before printing them,
        which on a ~0,045 blank moves a recomputed CV by more than the gap
        between the sample and population conventions, so the file cannot say
        which Gen5 used. See `blank_cv_percent`. What matters for the bench is
        that the number on our screen is recognisably the number she is used to.
        """
        report = blank_report(wells(GEN5_VALID_RUN))
        for wavelength, reported in GEN5_REPORTED_CV.items():
            assert abs(report.cv_percent[wavelength] - reported) < 0.4

    def test_a_single_well_blank_has_no_cv_to_report(self):
        """Gen5 prints no CV for its one-well blanks, and neither can we."""
        report = blank_report(wells({"A3": (0.053, 0.049, 0.045)}))
        assert report.valid
        assert report.cv_percent[260] == 0.0


class TestFindingTheBadSpot:
    def test_one_bad_well_is_named_and_its_neighbours_are_not(self):
        blanks = flat(["A2", "B2", "C2", "D2"], delta_260=0.010)
        assert divergent_blank_wells(blanks) == {"A2"}

    def test_the_median_is_what_keeps_the_good_wells_clean(self):
        """A mean would be dragged towards the outlier and smear the verdict.

        With one well 0,010 off, the mean of four moves 0,0025 -- past the
        divergence limit on its own -- so every good well would be measured
        against a centre the bad well had already moved.
        """
        blanks = flat(["A2", "B2", "C2", "D2"], delta_260=0.010)
        report = blank_report(blanks)
        assert report.divergent == ("A2",)
        assert not report.valid
        assert report.reason == "divergent"

    def test_two_wells_that_disagree_are_both_flagged(self):
        """Neither can be called the wrong one, so neither is trusted."""
        blanks = flat(["A2", "B2"], delta_260=0.008)
        assert divergent_blank_wells(blanks) == {"A2", "B2"}

    def test_a_lone_well_cannot_diverge_from_anything(self):
        assert divergent_blank_wells(flat(["A2"])) == set()

    def test_wells_that_agree_are_left_alone(self):
        assert divergent_blank_wells(flat(["A2", "B2", "C2"])) == set()

    def test_a_well_just_inside_the_limit_passes(self):
        blanks = flat(["A2", "B2", "C2"],
                      delta_260=BLANK_DIVERGENCE_LIMIT_AU * 0.9)
        assert divergent_blank_wells(blanks) == set()

    def test_divergence_is_measured_after_the_320_correction(self):
        """A well whose background is high but whose signal matches is fine.

        320 nm is subtracted from every reading before anything is compared,
        so a spot sitting on more background than its neighbours is not a bad
        blank -- what gets subtracted from the samples is the difference, and
        that is what has to agree.
        """
        blanks = wells({
            "A2": (0.046, 0.044, 0.041),
            "B2": (0.066, 0.064, 0.061),     # +0,020 of pure background
            "C2": (0.046, 0.044, 0.041),
        })
        assert divergent_blank_wells(blanks) == set()


class TestDiscardingAndRecovering:
    def test_dropping_the_bad_well_makes_the_blank_usable(self):
        """The technician's actual fix, as a calculation."""
        blanks = flat(["A2", "B2", "C2", "D2"], delta_260=0.010)
        assert not blank_report(blanks).valid

        kept = {name: well for name, well in blanks.items() if name != "A2"}
        assert blank_report(kept).valid

    def test_a_blank_with_nothing_left_in_it_is_not_valid(self):
        report = blank_report({})
        assert not report.valid
        assert report.reason == "empty"
        assert report.wells == ()


class TestTheTwoLimitsTogether:
    def test_an_outlier_is_named_rather_than_the_whole_set_condemned(self):
        blanks = flat(["A2", "B2", "C2"], delta_260=0.010)
        report = blank_report(blanks)
        assert report.reason == "divergent"
        assert report.divergent == ("A2",)

    def test_two_wells_that_merely_disagree_fail_on_spread_with_nothing_red(self):
        """Neither well is far enough from the median to be blamed.

        The median of two sits between them, so each is 0,0025 from it, inside
        the 0,003 divergence limit -- while the pair spans 0,005, past the 0,004
        spread limit. Nothing is painted red because there is nothing to
        discard: the only honest instruction is to blank again.
        """
        blanks = flat(["A2", "B2"], delta_260=0.005)
        report = blank_report(blanks)
        assert not report.valid
        assert report.reason == "spread"
        assert report.divergent == ()

    def test_both_limits_can_be_loosened_until_the_blank_passes(self):
        blanks = flat(["A2", "B2", "C2"], delta_260=0.010)
        report = blank_report(blanks, spread_limit_au=0.050,
                              divergence_limit_au=0.050)
        assert report.valid
