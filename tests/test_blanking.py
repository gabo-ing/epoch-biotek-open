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

from epoch_open import quant
from epoch_open.quant import (                          # noqa: E402
    BLANK_DIVERGENCE_LIMIT_AU,
    BLANK_DISPERSION_LIMIT_AU,
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

        These wells disagree by a standard deviation of 0,00089 AU against a
        0,0025 limit, and the worst of them sits 0,0015 AU from the median
        against a 0,003 divergence limit. Those two margins are what the
        defaults were set from; if a change here makes this test tight, the
        change will be reddening wells at the bench on blanks the instrument's
        own software was happy with.
        """
        report = blank_report(wells(GEN5_VALID_RUN))
        assert report.dispersion_au <= BLANK_DISPERSION_LIMIT_AU / 2 + 1e-9
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

    def test_a_single_well_blank_is_refused_because_it_cannot_be_judged(self):
        """One well has no CV%, and Gen5 treats that as a failed blank.

        Its help is explicit: if the highest CV% exceeds the limit *or the CV%
        cannot be calculated*, it warns and will not read samples. One well
        cannot be checked against anything, so accepting it would mean
        quantifying against a blank nobody has any evidence about.

        This changed when that rule was read. A one-well blank used to pass.
        """
        report = blank_report(wells({"A3": (0.053, 0.049, 0.045)}))
        assert not report.valid
        assert report.reason == "single"
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
        # The well is named so it can be wiped or discarded. Whether the
        # blanking as a whole passes is a separate question, decided by CV%.
        assert "B2" not in report.divergent

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
    def test_an_outlier_is_named_without_the_naming_being_the_verdict(self):
        """Gen5 lets a bad well be clicked out of the average, not blocked on.

        So a divergent well is advice -- paint it red, say which spot to wipe --
        and the verdict itself comes from the CV% check. This is the behaviour
        that changed when Gen5's rule was read on 3 November 2026.
        """
        blanks = flat(["A2", "B2", "C2"], delta_260=0.010)
        report = blank_report(blanks)
        assert report.divergent == ("A2",)
        assert report.reason != "divergent"

    def test_two_wells_that_merely_disagree_fail_on_dispersion_with_nothing_red(self):
        """Neither well is far enough from the median to be blamed.

        The median of two sits between them, so each is 0,0025 from it, inside
        the 0,003 divergence limit -- while the pair disagrees by 0,005 AU, a
        standard deviation of 0,0035, past the 0,0025 disagreement limit.
        Nothing is painted red because there is nothing to discard: the only
        honest instruction is to blank again.
        """
        blanks = flat(["A2", "B2"], delta_260=0.005)
        report = blank_report(blanks)
        assert not report.valid
        assert report.reason == "dispersion"
        assert report.divergent == ()

    def test_the_limits_can_be_loosened_until_the_blank_passes(self):
        """All three are arguments, so a lab can move them without a rebuild."""
        blanks = flat(["A2", "B2", "C2"], delta_260=0.010)
        report = blank_report(blanks, cv_limit_percent=99.0,
                              dispersion_limit_au=0.050,
                              divergence_limit_au=0.050)
        assert report.valid

    def test_the_cv_limit_is_what_decides(self):
        """Tightening only the CV% limit must be enough to fail a blanking."""
        blanks = flat(["A2", "B2", "C2"], delta_260=0.010)
        loose = blank_report(blanks, cv_limit_percent=99.0,
                             dispersion_limit_au=0.050,
                             divergence_limit_au=0.050)
        tight = blank_report(blanks, cv_limit_percent=0.5,
                             dispersion_limit_au=0.050,
                             divergence_limit_au=0.050)
        assert loose.valid
        assert not tight.valid
        assert tight.reason == "cv"

    def test_the_run_gen5_accepted_passes_gen5_s_own_limit(self):
        """The whole point of matching: agreeing with it on real data.

        Gen5_LVA_NAQ_0001 was printed VALID by Gen5 with a CV% of 4,32 at
        260 nm, against the limit of 10 its preferences dialog ships with.
        """
        report = blank_report(wells(GEN5_VALID_RUN))
        assert report.valid
        assert max(report.cv_percent.values()) < quant.BLANK_CV_LIMIT_PERCENT
        assert quant.BLANK_CV_LIMIT_PERCENT == 10.0


class TestTheBlankingGen5Rejected:
    """The run Gabo photographed on 3 November 2026.

    Two clean Take3 spots and two deliberately smudged ones. Gen5 reported
    Status DIVERGING, CV% 29,242, and painted exactly the two smudged wells
    red while the clean pair stayed green.

    That screenshot is the only evidence this project has of Gen5 *rejecting*
    a blanking, and it caught a real bug the moment it arrived: the rule here
    measured each well's distance from the median, and with the wells in two
    groups the median lands in the gap between them, so all four came out
    red. The technician would have been told to wipe two spots that were fine.
    """

    def well(self, name, a260):
        return RawWell(name, {260: a260, 280: a260 * 0.95, 320: 0.040})

    def split(self):
        """Two clean wells and two smudged, as in the photograph."""
        return {"A2": self.well("A2", 0.046), "A3": self.well("A3", 0.047),
                "B2": self.well("B2", 0.085), "B3": self.well("B3", 0.090)}

    def test_only_the_smudged_wells_are_painted_red(self):
        report = blank_report(self.split())
        assert report.divergent == ("B2", "B3"), (
            "the clean wells must stay green; Gen5 left them green")

    def test_the_blanking_is_refused(self):
        report = blank_report(self.split())
        assert not report.valid
        assert report.reason == "cv"

    def test_a_cv_this_far_out_is_nowhere_near_the_limit(self):
        """Gen5 printed 29,242% against its limit of 10."""
        report = blank_report(self.split())
        assert report.cv_percent[260] > quant.BLANK_CV_LIMIT_PERCENT * 2

    def test_discarding_what_is_red_leaves_a_blank_that_passes(self):
        """The red set is a promise: drop these and the rest agree.

        If that were not true the colour would be decoration. It is the whole
        meaning of the hint beside Gen5's grid -- discard the diverging wells.
        """
        blanks = self.split()
        report = blank_report(blanks)
        kept = {w: b for w, b in blanks.items() if w not in report.divergent}
        assert len(kept) >= 2
        assert blank_report(kept).valid

    def test_a_single_bad_spot_among_four_names_only_that_one(self):
        blanks = {"A2": self.well("A2", 0.046), "A3": self.well("A3", 0.047),
                  "B2": self.well("B2", 0.046), "B3": self.well("B3", 0.090)}
        assert blank_report(blanks).divergent == ("B3",)

    def test_a_good_blanking_reddens_nothing(self):
        blanks = {n: self.well(n, 0.046 + i * 0.0005)
                  for i, n in enumerate(("A2", "A3", "B2", "B3"))}
        report = blank_report(blanks)
        assert report.valid
        assert report.divergent == ()


# The names of every Take3 microspot, in the order the grid shows them.
ALL_SPOTS = [f"{row}{column}" for column in (2, 3) for row in "ABCDEFGH"]


def like_the_real_plate(count):
    """`count` blank wells of exactly the quality Gen5 accepted.

    Built by cycling the eight real wells of Gen5_LVA_NAQ_0001, so the per-well
    disagreement is the same at any size: this is what one plate of that
    quality looks like whether two spots were blanked or forty-eight. It is the
    control for every claim below about the number of wells not mattering.
    """
    real = list(GEN5_VALID_RUN.values())
    names = [f"{row}{column}" for column in (2, 3, 4, 5, 6, 7)
             for row in "ABCDEFGH"][:count]
    return wells({name: real[index % len(real)]
                  for index, name in enumerate(names)})


class TestTheVerdictDoesNotDependOnHowManyWellsWereBlanked:
    """The bug this class exists for, found at the bench on 18 November 2026.

    A technician blanks every well before using it -- all sixteen spots, not
    the two or eight these thresholds were set from -- and was refused over and
    over, with a different well painted red each time. A different well every
    time is the signature: a dirty spot would be the same spot twice.

    The cause was that the absolute floor under the CV% was a range,
    `max - min`, judged against a fixed limit. A range grows with the number of
    wells however good the blanking is, so the gate tightened as she blanked
    more carefully, while the error a blank actually injects -- the error of the
    mean -- was shrinking as 1/sqrt(n) the whole time. See `blank_dispersion`.
    """

    def test_a_plate_gen5_would_accept_passes_at_every_size(self):
        for count in (2, 3, 4, 6, 8, 12, 16, 24, 48):
            report = blank_report(like_the_real_plate(count))
            assert report.valid, (count, report.reason,
                                  report.dispersion_au)

    def test_the_whole_plate_passes(self):
        """The exact thing she was doing, at the size she was doing it."""
        report = blank_report(like_the_real_plate(len(ALL_SPOTS)))
        assert report.valid
        assert report.reason == ""

    def test_the_measured_disagreement_does_not_drift_with_the_count(self):
        """A standard deviation estimates the same quantity at any n.

        The old range did not: it climbed from about 2.85 standard deviations
        at eight wells to 3.90 at twenty-four, purely from counting.
        """
        values = [blank_report(like_the_real_plate(n)).dispersion_au
                  for n in (8, 16, 24, 48)]
        assert max(values) - min(values) < 0.0002, values

    def test_the_old_range_rule_would_have_refused_the_whole_plate(self):
        """Why this is a regression test and not a preference.

        Kept as the arithmetic rather than the old code: on these wells the
        highest-to-lowest range passes the retired 0.004 AU limit at eight
        wells and fails it well before forty-eight, with nothing about the
        plate having changed.
        """
        def old_range(blanks):
            deltas = [b.corrected(260) for b in blanks.values()]
            return max(deltas) - min(deltas)

        spread_at_8 = old_range(like_the_real_plate(8))
        assert spread_at_8 <= 0.004
        # The range cannot shrink when wells are added, only grow.
        for count in (16, 24, 48):
            assert old_range(like_the_real_plate(count)) >= spread_at_8

    def test_one_bad_drop_among_many_is_named_but_no_longer_blocks_the_read(self):
        """Twenty-four drops means one of them will be short sooner or later.

        That well contributes a twenty-fourth of the blank, so it moves what
        gets subtracted by about 0.0001 AU -- nothing at 0.5 mm. It is still
        painted red so the spot can be wiped or dropped; refusing the whole
        read over it was the part that was wrong.
        """
        blanks = like_the_real_plate(24)
        victim = sorted(blanks)[7]
        raw = blanks[victim].readings
        blanks[victim] = RawWell(well=victim,
                                 readings={260: raw[260] + 0.004,
                                           280: raw[280], 320: raw[320]})
        report = blank_report(blanks)
        assert victim in report.divergent, "the bad spot must still be named"
        assert report.valid, "but it must not stop her reading samples"

    def test_a_genuinely_bad_plate_still_fails_at_every_size(self):
        """Scale-free has to cut both ways, or it is just a loosening."""
        for count in (2, 4, 8, 16, 24):
            names = [f"{row}{column}" for column in (2, 3, 4)
                     for row in "ABCDEFGH"][:count]
            blanks = {}
            for index, name in enumerate(names):
                # Alternating 0,005 AU apart: a plate half of whose spots are
                # dirty, which is 5 ng/uL of dsDNA between them at 0,5 mm.
                offset = 0.005 if index % 2 else 0.0
                blanks[name] = RawWell(
                    well=name,
                    readings={260: 0.046 + offset, 280: 0.044, 320: 0.041})
            report = blank_report(blanks)
            assert not report.valid, count
            assert report.reason == "dispersion", (count, report.reason)
