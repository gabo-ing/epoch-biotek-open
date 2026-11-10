"""The epoch-multispectral screen: the plate, the gates, and the warnings.

What matters here is mostly refusal. The program's whole value over writing
absorbances into a spreadsheet by hand is that it will not let a sample be
read against a curve that cannot support it, and will not quietly keep a
curve that the plate no longer matches.

These build a real window, so they are skipped when there is no display --
but see tests/test_gui_starts.py, which turns "the window would not build"
from a skip into a failure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from epoch_open import curve, gui_curve
    from epoch_open.gui_curve import TEXT
    from epoch_open.reader import MockCurveReader
    IMPORTED = True
except ImportError:          # no tkinter on this machine
    gui_curve = None
    IMPORTED = False


def _app(seed: int = 5):
    if not IMPORTED:
        return None
    try:
        return gui_curve.App(MockCurveReader(seed=seed))
    except Exception:        # no X display
        return None


def _on_screen(widget, text):
    """Whether any widget in the tree actually displays `text`.

    Asserting on the table alone would pass for a string nothing renders,
    which is the failure mode worth guarding: the Take3 warning is the one
    piece of text in this program whose absence could cost a plate.
    """
    try:
        if text in str(widget.cget("text")):
            return True
    except Exception:
        pass
    return any(_on_screen(child, text) for child in widget.winfo_children())


def _mark(app, role, wells):
    app.role.set(role)
    for well in wells:
        app._click_well(well)


def _loaded(app, standards=None, samples=("A3", "B3")):
    """A plate marked up the way it would be at the bench."""
    standards = standards or {"A2": 0, "B2": 5, "C2": 10, "D2": 20, "E2": 40}
    _mark(app, gui_curve.BLANK, ["A1", "B1", "C1"])
    _mark(app, gui_curve.STANDARD, list(standards))
    app.concentrations.update(standards)
    _mark(app, gui_curve.SAMPLE, list(samples))
    app._refresh_state()


def _state(app, key):
    return str(app.action_buttons[key].cget("state"))


class TestThePlate:

    def test_it_is_a_whole_96_well_plate(self):
        """Not the Take3's 16 micro-spots: this assay is in an ordinary plate."""
        app = _app()
        if app is None:
            return
        try:
            assert len(app.wells) == 96
            assert len(gui_curve.ROWS) == 8
            assert len(gui_curve.COLUMNS) == 12
            for well in ("A1", "H12", "D6"):
                assert well in app.wells
        finally:
            app.destroy()

    def test_a_well_can_be_marked_and_unmarked(self):
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.BLANK, ["A1"])
            assert app.roles["A1"] == gui_curve.BLANK
            _mark(app, gui_curve.BLANK, ["A1"])       # same role again
            assert "A1" not in app.roles
        finally:
            app.destroy()

    def test_marking_a_well_with_another_role_moves_it(self):
        """The common slip is a row marked samples that should be standards."""
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.SAMPLE, ["C5"])
            _mark(app, gui_curve.STANDARD, ["C5"])
            assert app.roles["C5"] == gui_curve.STANDARD
        finally:
            app.destroy()

    def test_a_standard_shows_its_concentration_on_the_well(self):
        """So the series can be checked by looking at the plate."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            assert app.wells["C2"].cget("text") == "10"
            assert app.wells["A1"].cget("text") == ""
        finally:
            app.destroy()

    def test_a_standard_with_no_concentration_is_marked_unknown(self):
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.STANDARD, ["F7"])
            app._refresh_state()
            assert app.wells["F7"].cget("text") == "?"
        finally:
            app.destroy()


class TestTheStepsOpenInOrder:

    def test_the_steps_that_need_something_first_are_shut(self):
        """Standards need a blank; saving needs a result.

        Reading samples does not need either, because an absorbance is a
        measurement on its own -- see TestAPlainReadNeedsNothing.
        """
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            assert _state(app, "read_blank") == "normal"
            assert _state(app, "read_standards") == "disabled"
            assert _state(app, "end_batch") == "disabled"
        finally:
            app.destroy()

    def test_standards_wait_for_the_blank(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            assert _state(app, "read_standards") == "disabled"
            app._read_blank()
            assert _state(app, "read_standards") == "normal"
        finally:
            app.destroy()

    def test_a_curve_turns_absorbances_into_concentrations(self):
        """Without one the samples still read; they just read in AU."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app, samples=("A3",))
            app._read_blank()
            app._read_samples()
            assert app.results[-1].concentration is None, (
                "a concentration appeared with no curve behind it")

            app._read_standards()
            assert app.fit is not None and app.fit.usable
            app._read_samples()
            assert app.results[-1].concentration is not None
        finally:
            app.destroy()

    def test_too_few_standards_keeps_the_curve_shut(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app, standards={"A2": 0, "B2": 10})
            app._read_blank()
            assert _state(app, "read_standards") == "disabled"
        finally:
            app.destroy()

    def test_a_standard_without_its_concentration_keeps_the_curve_shut(self):
        """An unlabelled standard would silently drop out of the fit."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            _mark(app, gui_curve.STANDARD, ["F2"])     # no concentration
            app._refresh_state()
            assert app._missing_concentrations() == ["F2"]
            assert _state(app, "read_standards") == "disabled"
        finally:
            app.destroy()

    def test_saving_opens_once_something_has_been_read(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            assert _state(app, "end_batch") == "disabled"
            app._read_samples()
            assert app.results
            assert _state(app, "end_batch") == "normal"
        finally:
            app.destroy()


class TestTheCurveIsThrownAwayWhenItStopsApplying:

    def test_changing_the_plate_discards_the_curve(self):
        """Standards no longer marked must not keep quantifying samples."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            assert app.fit is not None
            _mark(app, gui_curve.STANDARD, ["A2"])     # unmark one standard
            assert app.fit is None
            # Samples can still be read -- they just come back in absorbance,
            # because there is no longer a curve to interpret them with.
            app.role.set(gui_curve.SAMPLE)
            app._click_well("A3")
            app._read_samples()
            assert app.results[-1].concentration is None
        finally:
            app.destroy()

    def test_rereading_the_blank_discards_the_curve(self):
        """Every standard's absorbance was measured against the old blank."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            assert app.fit is not None
            app._read_blank()
            assert app.fit is None
        finally:
            app.destroy()

    def test_switching_the_reference_on_discards_the_curve(self):
        """It is subtracted from the standards too, so the curve changes."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            assert app.fit is not None
            app.use_reference.set(True)
            app._reference_toggled()
            assert app.fit is None
        finally:
            app.destroy()

    def test_clearing_resets_everything_measured(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            app._clear()
            assert app.roles == {}
            assert app.concentrations == {}
            assert app.blank_values == {}
            assert app.fit is None
        finally:
            app.destroy()


class TestTheSettings:

    def test_a_nonsense_wavelength_stops_reading(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app.nm.set("quinientos")
            app._refresh_state()
            assert app._wavelengths() is None
            assert _state(app, "read_blank") == "disabled"
        finally:
            app.destroy()

    def test_a_wavelength_off_the_instrument_is_refused(self):
        """The Epoch reads 200-999 nm; see docs and reader.py."""
        app = _app()
        if app is None:
            return
        try:
            for bad in ("100", "1200", "0", "-530"):
                app.nm.set(bad)
                assert app._wavelengths() is None, f"{bad} nm was accepted"
            app.nm.set("530")
            assert app._wavelengths() == [530]
        finally:
            app.destroy()

    def test_the_default_is_530_for_salkowski(self):
        app = _app()
        if app is None:
            return
        try:
            assert app.nm.get() == str(curve.DEFAULT_NM) == "530"
        finally:
            app.destroy()

    def test_the_reference_is_added_to_the_read_when_switched_on(self):
        app = _app()
        if app is None:
            return
        try:
            app.use_reference.set(True)
            assert app._wavelengths() == [530, 650]
            assert app._reference_nm() == 650
        finally:
            app.destroy()

    def test_a_reference_equal_to_the_measurement_is_ignored(self):
        """Subtracting a wavelength from itself would zero every well."""
        app = _app()
        if app is None:
            return
        try:
            app.use_reference.set(True)
            app.reference_nm.set("530")
            assert app._wavelengths() == [530]
            assert app._reference_nm() is None
        finally:
            app.destroy()


class TestWhatTheScreenSays:

    def test_the_take3_plate_warning_is_on_the_screen(self):
        """Gabo's point, and the expensive mistake: acid ruins the quartz.

        Checked as screen text rather than documentation, because the person
        loading the plate is looking at the screen.
        """
        app = _app()
        if app is None:
            return
        try:
            warning = gui_curve.TEXT["take3_warning"]
            assert "Take3" in warning
            assert _on_screen(app, warning), (
                "the warning exists in the table but is on no widget")
        finally:
            app.destroy()

    def test_the_curve_panel_reports_the_fit(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            assert app.curve_fields["n"].cget("text") == "5"
            assert app.curve_fields["state"].cget("text") == \
                gui_curve.TEXT["curve_usable"]
            # The decimal mark of the language in force, as elsewhere.
            assert TEXT["decimal"] in app.curve_fields["r2"].cget("text")
        finally:
            app.destroy()

    def test_an_unread_curve_says_so_rather_than_showing_zeros(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            assert app.curve_fields["state"].cget("text") == \
                gui_curve.TEXT["curve_unread"]
            assert app.curve_fields["r2"].cget("text") == "-"
        finally:
            app.destroy()

    def test_a_sample_off_the_top_of_the_curve_is_shown_as_a_warning_row(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app, samples=("A3",))
            app._read_blank()
            app._read_standards()
            # Put the sample far above the top standard.
            app.backend.truth["A3"] = 400.0
            app._read_samples()
            result = app.results[-1]
            assert not result.in_range
            rows = app.table.get_children()
            assert "warn" in app.table.item(rows[-1], "tags")
        finally:
            app.destroy()

    def test_a_badly_placed_standard_is_painted_red(self):
        """So the well to re-pipette is identified on the plate itself.

        The fit is installed directly rather than measured, because the
        simulator cannot produce this situation: `_invent_truth` gives each
        standard the absorbance its *declared* concentration implies, so
        simulated standards are exactly linear by construction. That is the
        right behaviour for a simulator -- it keeps the demo curve a real line
        -- but it means a mis-pipetted standard is only reachable with
        hardware, or here.
        """
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app.blank_values = {}
            # Four standards on a line and one well off it, which is what a
            # standard diluted wrong actually looks like.
            app.fits = {app._primary(): curve.fit_standards([
                curve.Standard("A2", 0, 0.000),
                curve.Standard("B2", 5, 0.100),
                curve.Standard("C2", 10, 0.200),
                curve.Standard("D2", 20, 0.250),
                curve.Standard("E2", 40, 0.800),
            ])}
            named = [n.well for n in app.fit.notes if n.well]
            assert named == ["D2"], f"singled out {named} instead of D2"

            app._refresh_wells()
            assert app.wells["D2"].cget("bg") == gui_curve.BAD_WELL
            # Its neighbours stay the ordinary standard colour.
            assert app.wells["C2"].cget("bg") != gui_curve.BAD_WELL
        finally:
            app.destroy()

    def test_the_simulator_keeps_its_standards_on_a_line(self):
        """Pins the behaviour the test above has to work around.

        A simulator that randomised the standards would make the program look
        broken -- r-squared near zero, every curve rejected -- when it was
        working correctly. So this is deliberate, and worth a test of its own
        so nobody 'fixes' it into noise later.
        """
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            app._read_standards()
            assert app.fit.r_squared > 0.99
            assert app.fit.notes == ()
        finally:
            app.destroy()


class TestTheStepsCanBeWalkedInOrder:
    """The order the screen tells you to work in has to actually work.

    Both bugs here were found by Gabo using the program on real hardware on
    3 November 2026, and neither was visible to any automated test.

    The first: marking a sample well threw away the curve. `_click_well`
    invalidated the fit on any change at all, so fitting a curve and then
    marking the samples it was fitted for left no curve, and step 3 could
    never be reached. Every test in this suite marked its samples *before*
    reading anything -- the one order in which the bug cannot appear.

    The second: after reading a blank, every other button stayed grey and
    nothing said why. The gating was right and the silence was not.
    """

    def _ready(self, app):
        """Blank read and curve fitted, nothing marked as a sample yet."""
        app.role.set(gui_curve.BLANK)
        for well in ("A1", "B1", "C1"):
            app._click_well(well)
        app._read_blank()

        app.role.set(gui_curve.STANDARD)
        series = {"A2": 0, "B2": 5, "C2": 10, "D2": 20}
        for well in series:
            app._click_well(well)
        app.concentrations.update(series)
        app._refresh_state()
        app._read_standards()
        assert app.fit is not None and app.fit.usable
        return app

    def test_marking_a_sample_keeps_the_curve(self):
        app = _app()
        if app is None:
            return
        try:
            self._ready(app)
            app.role.set(gui_curve.SAMPLE)
            app._click_well("A3")
            assert app.fit is not None, (
                "marking a sample threw away the curve, so step 3 was "
                "unreachable")
            assert _state(app, "read_samples") == "normal"
        finally:
            app.destroy()

    def test_the_three_reads_happen_in_the_order_the_screen_gives(self):
        app = _app()
        if app is None:
            return
        try:
            self._ready(app)
            app.role.set(gui_curve.SAMPLE)
            app._click_well("A3")
            app._read_samples()
            assert app.results, "no sample was quantified"
            assert _state(app, "end_batch") == "normal"
        finally:
            app.destroy()

    def test_unmarking_a_standard_still_discards_the_curve(self):
        """The narrowed rule must not have narrowed too far."""
        app = _app()
        if app is None:
            return
        try:
            self._ready(app)
            app.role.set(gui_curve.STANDARD)
            app._click_well("A2")
            assert app.fit is None
        finally:
            app.destroy()

    def test_changing_the_blank_wells_still_discards_the_curve(self):
        app = _app()
        if app is None:
            return
        try:
            self._ready(app)
            app.role.set(gui_curve.BLANK)
            app._click_well("D1")
            assert app.fit is None
        finally:
            app.destroy()


class TestItSaysWhatIsMissing:
    """A greyed-out button with no reason is worse than an error message."""

    def test_the_warning_names_the_consequence_and_the_alternative(self):
        """Both halves have to survive translation.

        "Do not use the Take3" on its own is a rule to be forgotten. What
        stops somebody is the consequence, and what they need next is the
        alternative, so each language is checked for both rather than for a
        word count.
        """
        tables = gui_curve.TEXT_BY_LANGUAGE
        for code, expected in (("en", ("damaged", "clear plastic")),
                               ("es", ("dañarse", "transparentes"))):
            text = tables[code]["take3_warning"].lower()
            for part in expected:
                assert part in text, f"{code}: no {part!r} in the warning"

    def test_it_names_the_next_action_at_every_stage(self):
        app = _app()
        if app is None:
            return
        try:
            assert app.next_label.cget("text"), "silent with an empty plate"

            app.role.set(gui_curve.BLANK)
            for well in ("A1", "B1", "C1"):
                app._click_well(well)
            assert TEXT["next_read_blank"] in app.next_label.cget("text")

            app._read_blank()
            # The moment Gabo got stuck: blank read, everything else grey.
            said = app.next_label.cget("text")
            assert TEXT["role_patron"].lower() in said.lower(), (
                f"after the blank it said {said!r}, which does not mention "
                "the standards that are actually missing")
            assert str(curve.MIN_STANDARDS) in said
        finally:
            app.destroy()

    def test_it_names_the_wells_whose_concentration_is_missing(self):
        app = _app()
        if app is None:
            return
        try:
            app.role.set(gui_curve.BLANK)
            for well in ("A1", "B1", "C1"):
                app._click_well(well)
            app._read_blank()

            app.role.set(gui_curve.STANDARD)
            for well in ("A2", "B2", "C2"):
                app._click_well(well)
            app.concentrations["A2"] = 0
            app._refresh_state()

            said = app.next_label.cget("text")
            assert "B2" in said and "C2" in said, (
                "it should name the standards still missing a concentration")
            assert "A2" not in said, "A2 already has one"
        finally:
            app.destroy()

    def test_it_asks_for_the_reader_when_there_is_none(self):
        if not IMPORTED:
            return
        try:
            app = gui_curve.App(None)
        except Exception:
            return
        try:
            assert app.next_label.cget("text") == TEXT["next_no_reader"]
        finally:
            app.destroy()


class TestAPlainReadNeedsNothing:
    """The instrument reads. Everything else is optional.

    Gabo put it plainly on 3 November 2026: the Take3 definitely needs a
    blank -- a nucleic-acid concentration comes from Beer-Lambert on a
    blank-corrected absorbance, so without one there is nothing to report --
    but this module should work as a spectrophotometer, which reads.

    Gen5 agrees: an absorbance endpoint read needs no blank, no standards and
    no data reduction configured at all. This program used to require a
    usable curve before it would read a sample, which made a measurement
    conditional on an interpretation of it.

    The guarantee that survives is narrower and the one that matters: a
    concentration is never reported from a curve that cannot support it. It
    comes back as None instead, and the column is left empty.
    """

    def test_samples_read_with_nothing_else_marked(self):
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.SAMPLE, ["A1", "B1"])
            app._refresh_state()
            assert _state(app, "read_samples") == "normal", (
                "a plain read was refused")
            app._read_samples()
            assert len(app.results) == 2
        finally:
            app.destroy()

    def test_what_comes_back_is_absorbance_and_no_concentration(self):
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            app._read_samples()
            result = app.results[-1]
            assert result.absorbance > 0
            assert result.concentration is None, (
                "a concentration appeared with no curve behind it")
        finally:
            app.destroy()

    def test_the_table_shows_a_dash_rather_than_a_zero(self):
        """A zero would read as a measured concentration of nothing."""
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            app._read_samples()
            row = app.table.get_children()[-1]
            values = app.table.item(row, "values")
            # Found by name, not position: the columns changed once already
            # when the wavelength column was added, and a test that counts
            # from the left fails for a reason that has nothing to do with
            # what it is checking.
            column = gui_curve.TEXT["columns"].index("Conc.")
            assert values[column] == "-", (
                f"concentration cell was {values[column]!r}")
        finally:
            app.destroy()

    def test_the_guidance_offers_the_plain_read(self):
        """It must not send her off to build a curve she does not want."""
        app = _app()
        if app is None:
            return
        try:
            app._refresh_state()
            first = app.next_label.cget("text").lower()
            assert TEXT["next_empty_plate"].lower() == first

            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            assert (TEXT["next_read_samples"]
                    in app.next_label.cget("text"))
        finally:
            app.destroy()

    def test_a_blank_is_still_subtracted_when_there_is_one(self):
        """Optional does not mean ignored."""
        app = _app()
        if app is None:
            return
        try:
            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            app._read_samples()
            raw = app.results[-1].absorbance

            app.results.clear()
            _mark(app, gui_curve.BLANK, ["A2", "B2"])
            app._read_blank()
            assert app.blank_values
            app._read_samples()
            corrected = app.results[-1].absorbance

            blank = app._blank_at(app._primary())
            assert abs(raw - corrected - blank) < 0.02, (
                "the blank was not subtracted once it existed")
        finally:
            app.destroy()

    def test_a_curve_still_quantifies_when_there_is_one(self):
        """The two modes coexist; adding standards upgrades the answer."""
        app = _app()
        if app is None:
            return
        try:
            _loaded(app, samples=("A3",))
            app._read_blank()
            app._read_standards()
            app._read_samples()
            assert app.results[-1].concentration is not None
        finally:
            app.destroy()


class TestSeveralWavelengthsInOneRead:
    """Up to six wavelengths per read, as Gen5's Read Step offers.

    The instrument takes them in a single pass, which is how the reference
    read and the peak scan already worked; what was missing was a way to ask.
    Asked for on 5 November 2026, after comparing coffee at 490 and 530 by
    doing two separate reads.

    The curve belongs to the first wavelength alone. A calibration measured
    at 530 nm says nothing about absorbance at 490, so the others come back
    as absorbance with no concentration -- the same rule as a read with no
    curve at all.
    """

    def _choose(self, app, measured, reference=None):
        """Apply a dialog result without opening the dialog."""
        app.nm.set(", ".join(str(nm) for nm in measured))
        app.use_reference.set(reference is not None)
        if reference is not None:
            app.reference_nm.set(str(reference))
        app._invalidate()
        app._refresh_state()

    def test_it_asks_the_instrument_for_all_of_them_at_once(self):
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [490, 530, 590], reference=650)
            assert app._measured() == [490, 530, 590]
            assert app._wavelengths() == [490, 530, 590, 650]
            assert app._primary() == 490
        finally:
            app.destroy()

    def test_one_press_gives_a_row_per_wavelength(self):
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [490, 530, 590])
            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            app._read_samples()
            assert [r.wavelength for r in app.results] == [490, 530, 590]
            assert {r.read_number for r in app.results} == {1}, (
                "all three came from one read and must say so")
        finally:
            app.destroy()

    def test_the_blank_is_kept_per_wavelength(self):
        """A blank at 490 says nothing about 530."""
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [490, 530])
            _mark(app, gui_curve.BLANK, ["A2", "B2"])
            app._read_blank()
            assert sorted(app.blank_values) == [490, 530]
            assert app._blank_at(490) != app._blank_at(530)
            assert app._blank_at(999) == 0.0, (
                "a wavelength never blanked must subtract nothing, not guess")
        finally:
            app.destroy()

    def test_each_wavelength_is_quantified_against_its_own_curve(self):
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [530, 490])
            _mark(app, gui_curve.BLANK, ["A2", "B2"])
            app._read_blank()
            series = {"A3": 0, "B3": 5, "C3": 10, "D3": 20}
            _mark(app, gui_curve.STANDARD, list(series))
            app.concentrations.update(series)
            app._refresh_state()
            app._read_standards()
            assert app.fit is not None and app.fit.usable

            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            app._read_samples()

            assert sorted(app.fits) == [490, 530], (
                "the standards were measured at both, so both get a curve")

            by_nm = {r.wavelength: r for r in app.results}
            assert by_nm[530].concentration is not None
            assert by_nm[490].concentration is not None, (
                "490 nm has its own curve and should use it")

            # And it must be its OWN curve, not the other one's.
            at_490 = app.fits[490].concentration_for(by_nm[490].absorbance)
            assert abs(by_nm[490].concentration - at_490) < 1e-9
            assert app.fits[490].slope != app.fits[530].slope, (
                "the two curves describe different wavelengths")
        finally:
            app.destroy()

    def test_six_is_the_limit_counting_the_reference(self):
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [400, 450, 500, 550, 600, 650])
            assert app._wavelengths() is not None, "six measured is allowed"

            self._choose(app, [400, 450, 500, 550, 600, 650], reference=700)
            assert app._wavelengths() is None, (
                "seven with the reference must be refused")
        finally:
            app.destroy()

    def test_a_repeated_wavelength_is_collapsed(self):
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [530, 530, 490])
            assert app._measured() == [530, 490]
        finally:
            app.destroy()

    def test_one_wavelength_still_behaves_as_before(self):
        app = _app()
        if app is None:
            return
        try:
            self._choose(app, [530])
            _mark(app, gui_curve.SAMPLE, ["A1"])
            app._refresh_state()
            app._read_samples()
            assert len(app.results) == 1
            assert app.results[0].wavelength == 530
        finally:
            app.destroy()
