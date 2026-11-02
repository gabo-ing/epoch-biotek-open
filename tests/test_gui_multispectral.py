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

    def test_nothing_but_the_blank_is_available_at_the_start(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            assert _state(app, "read_blank") == "normal"
            assert _state(app, "read_standards") == "disabled"
            assert _state(app, "read_samples") == "disabled"
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

    def test_samples_wait_for_a_usable_curve(self):
        app = _app()
        if app is None:
            return
        try:
            _loaded(app)
            app._read_blank()
            assert _state(app, "read_samples") == "disabled"
            app._read_standards()
            assert app.fit is not None and app.fit.usable
            assert _state(app, "read_samples") == "normal"
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
            assert _state(app, "read_samples") == "disabled"
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
            assert app.blank_value is None
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
            assert "acido" in warning.lower()
            assert "plastico" in warning.lower()
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
            # Spanish decimal mark, as the rest of the program uses.
            assert "," in app.curve_fields["r2"].cget("text")
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
            app.blank_value = 0.0
            # Four standards on a line and one well off it, which is what a
            # standard diluted wrong actually looks like.
            app.fit = curve.fit_standards([
                curve.Standard("A2", 0, 0.000),
                curve.Standard("B2", 5, 0.100),
                curve.Standard("C2", 10, 0.200),
                curve.Standard("D2", 20, 0.250),
                curve.Standard("E2", 40, 0.800),
            ])
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
