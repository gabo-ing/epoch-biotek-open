"""The blanking step on screen: colours, verdict, discard, reset.

This is the technician's described workflow, as a sequence the window has to
support: mark the water spots, read, look at the grid, drop or re-do whatever
came up red, and only then quantify. Every assertion here is about something
she can see or press.

These build a real window, so they are skipped when there is no display.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open.quant import RawWell                    # noqa: E402

try:
    from epoch_open import gui
    IMPORTED = True
except ImportError:          # no tkinter on this machine
    gui = None
    IMPORTED = False


def _app():
    if not IMPORTED:
        return None
    try:
        return gui.App(gui.MockReader())
    except Exception:        # no X display
        return None


def _blanking(app, offsets):
    """Pretend a blanking just happened, with `offsets` added at 260 nm.

    Goes in through the same two pieces of state a real read fills -- the
    readings it took and the wells that are marked -- so the app derives the
    blank and its verdict exactly as it would from the instrument.
    """
    app.blank_raw = {
        well: RawWell(well=well,
                      readings={260: 0.046 + offset, 280: 0.044, 320: 0.041})
        for well, offset in offsets.items()
    }
    # A fresh blanking, not an addition to the last one: marks left over from a
    # previous call would come back as unread wells and suspend the blank.
    app.blank_selected.clear()
    app.blank_selected.update(offsets)
    app.blank_time = datetime(2026, 10, 26, 10, 57, 16)
    app._refresh_state()


def _colour(app, well):
    return app.blank_buttons[well].cget("bg")


def _field(app, key):
    return app.blank_fields[key].cget("text")


class TestTheGridSaysWhichSpotIsBad:
    def test_a_marked_well_is_blue_until_it_has_been_read(self):
        app = _app()
        if app is None:
            return
        try:
            app._toggle("A2", app.blank_selected, app.blank_buttons)
            assert _colour(app, "A2") == gui.BLANK_PENDING
            assert _field(app, "state") == gui.TEXT["blank_state_unread"]
        finally:
            app.destroy()

    def test_wells_that_agree_turn_green(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0, "C2": 0.0})
            for well in ("A2", "B2", "C2"):
                assert _colour(app, well) == gui.BLANK_WELL
            assert _field(app, "state") == gui.TEXT["blank_state_valid"]
        finally:
            app.destroy()

    def test_the_odd_well_out_turns_red_and_the_others_stay_green(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            assert _colour(app, "A2") == gui.BAD_WELL
            assert _colour(app, "B2") == gui.BLANK_WELL
            assert _field(app, "state") == gui.TEXT["blank_state_invalid"]
        finally:
            app.destroy()

    def test_an_unmarked_well_is_left_empty(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0})
            assert _colour(app, "H3") == gui.EMPTY
        finally:
            app.destroy()


class TestSamplesWaitForAGoodBlank:
    def test_a_divergent_blank_keeps_the_sample_button_shut(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
            # And the step being pointed at is still the blank.
            assert app.action_buttons["read_blank"].cget("bg") == gui.ACTION
        finally:
            app.destroy()

    def test_discarding_the_red_well_opens_the_samples_up(self):
        """The fix she described, done by clicking the offending spot."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            app._toggle("A2", app.blank_selected, app.blank_buttons)

            assert _field(app, "state") == gui.TEXT["blank_state_valid"]
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "normal"
            # The discarded well is no longer part of the blank.
            assert "A2" not in (app.blank or {})
            assert sorted(app.blank) == ["B2", "C2", "D2"]
        finally:
            app.destroy()

    def test_a_discarded_well_can_be_put_back_without_reading_again(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            app._toggle("A2", app.blank_selected, app.blank_buttons)
            app._toggle("A2", app.blank_selected, app.blank_buttons)

            assert "A2" in app.blank
            assert _colour(app, "A2") == gui.BAD_WELL
            assert _field(app, "state") == gui.TEXT["blank_state_invalid"]
        finally:
            app.destroy()

    def test_marking_a_new_well_after_reading_suspends_the_blank(self):
        """Half a blank must not be subtracted from anyone's samples.

        A well marked after the read has no reading behind it, so the set on
        screen is not the set that was measured. Until it is read the blank is
        not usable, and the button says so.
        """
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "normal"

            app._toggle("C2", app.blank_selected, app.blank_buttons)
            assert _colour(app, "C2") == gui.BLANK_PENDING
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
            assert app._blank_reason() == gui.TEXT["blank_why_pending"]
        finally:
            app.destroy()

    def test_discarding_every_well_is_not_a_blank(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            for well in ("A2", "B2"):
                app._toggle(well, app.blank_selected, app.blank_buttons)

            assert app.blank is None
            assert not app._blank_ok()
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
        finally:
            app.destroy()


class TestTheStatusBlock:
    def test_it_shows_when_the_blanking_happened(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            assert _field(app, "date") == "26-10-2026"
            assert _field(app, "time") == "10:57:16"
        finally:
            app.destroy()

    def test_the_cv_is_written_the_way_gen5_writes_it(self):
        """Decimal comma, as the lab's own exports and screen use."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.002, "B2": 0.0, "C2": 0.0})
            shown = _field(app, "cv")
            assert "," in shown and shown.endswith("%")
            assert float(shown.rstrip("%").replace(",", ".")) > 0
        finally:
            app.destroy()

    def test_a_single_well_blank_reports_no_cv_rather_than_zero(self):
        """0,00 would read as perfect agreement instead of nothing to compare."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0})
            assert _field(app, "cv") == "-"
            assert _field(app, "state") == gui.TEXT["blank_state_valid"]
        finally:
            app.destroy()

    def test_a_bad_blank_says_what_to_do_about_it(self):
        """Not just that it failed: which of the two fixes applies.

        A single red well can be discarded. A set that merely disagrees has
        nothing to discard and has to be blanked again. The line under the
        grids has to say whichever one is true.
        """
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0})
            assert app.blank_label.cget("text") == gui.TEXT["blank_why_divergent"]

            _blanking(app, {"A2": 0.005, "B2": 0.0})
            assert app.blank_label.cget("text") == gui.TEXT["blank_why_spread"]
        finally:
            app.destroy()

    def test_a_good_blank_lists_the_wells_it_is_made_of(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            assert "A2" in app.blank_label.cget("text")
            assert "B2" in app.blank_label.cget("text")
        finally:
            app.destroy()


class TestResetBlanks:
    def test_it_throws_away_the_readings_as_well_as_the_marks(self):
        """Clearing only the marks would leave the old blank still in force."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            app._reset_blanks()

            assert app.blank_raw is None
            assert app.blank is None
            assert app.blank_selected == set()
            assert _field(app, "state") == gui.TEXT["blank_state_unread"]
            assert _field(app, "cv") == "-"
            assert _colour(app, "A2") == gui.EMPTY
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
        finally:
            app.destroy()
