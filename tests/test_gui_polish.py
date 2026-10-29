"""The screen guiding the technician through the three steps, in order.

Two things are being protected here. The buttons must refuse the steps that are
not available yet, rather than accepting the press and explaining the mistake in
a dialog afterwards. And the results table must not spend width on a column that
says the same thing on every row, because the column that gets squeezed out on a
narrow screen is the one carrying the warnings.

These build a real window, so they are skipped when there is no display.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def _state(app, key):
    return str(app.action_buttons[key].cget("state"))


def _blank(app, wells=("A2", "A3"), spread=0.0):
    """Install a blanking that really happened, as a read would install it.

    The app derives the blank in force, and its verdict, from the readings it
    took and the wells still marked, so a test cannot just assign `app.blank`.
    Identical readings make a blank that passes; `spread` pulls one well away
    to make one that does not.
    """
    from datetime import datetime

    from epoch_open.quant import RawWell

    app.blank_raw = {}
    for offset, well in enumerate(wells):
        app.blank_raw[well] = RawWell(
            well=well,
            readings={260: 0.046 + (spread if offset else 0.0),
                      280: 0.044, 320: 0.041},
        )
    app.blank_selected.update(wells)
    app.blank_time = datetime.now()
    app._refresh_state()


class TestTheNextStepIsObvious:
    def test_only_the_blank_can_be_read_first(self):
        app = _app()
        if app is None:
            return
        try:
            assert _state(app, "read_blank") == "normal"
            assert _state(app, "read_samples") == "disabled"
            assert _state(app, "end_batch") == "disabled"
            # And it is the one picked out in the strong colour.
            assert app.action_buttons["read_blank"].cget("bg") == gui.ACTION
        finally:
            app.destroy()

    def test_samples_open_up_once_a_blank_exists(self):
        app = _app()
        if app is None:
            return
        try:
            _blank(app)
            assert _state(app, "read_samples") == "normal"
            assert app.action_buttons["read_samples"].cget("bg") == gui.ACTION
            # Nothing has been measured, so there is nothing to save.
            assert _state(app, "end_batch") == "disabled"
        finally:
            app.destroy()

    def test_saving_opens_up_once_something_has_been_read(self):
        app = _app()
        if app is None:
            return
        try:
            _blank(app)
            app.results = [(1, object())]
            app._refresh_actions()
            assert _state(app, "end_batch") == "normal"
            assert app.action_buttons["end_batch"].cget("bg") == gui.ACTION
            # Still readable, just no longer the step being pointed at.
            assert _state(app, "read_samples") == "normal"
            assert app.action_buttons["read_samples"].cget("bg") == gui.ACTION_IDLE
        finally:
            app.destroy()


class TestResultsTable:
    def test_the_unit_is_in_the_heading_not_a_column(self):
        app = _app()
        if app is None:
            return
        try:
            assert "Unidad" not in gui.TEXT["columns"]
            assert "ng/uL" in app.table.heading("Conc.")["text"]
        finally:
            app.destroy()

    def test_the_heading_follows_the_sample_type(self):
        app = _app()
        if app is None:
            return
        try:
            app.sample_type.set("protein")
            app._refresh_table_columns()
            assert "mg/mL" in app.table.heading("Conc.")["text"]
        finally:
            app.destroy()

    def test_260_230_is_hidden_until_it_is_read(self):
        app = _app()
        if app is None:
            return
        try:
            shown = [str(c) for c in app.table.cget("displaycolumns")]
            assert "260/230" not in shown
            app.with_230.set(True)
            app._refresh_table_columns()
            shown = [str(c) for c in app.table.cget("displaycolumns")]
            assert "260/230" in shown
        finally:
            app.destroy()

    def test_the_warning_column_is_the_one_that_grows(self):
        """On a narrow window the warnings must survive, not the dashes."""
        app = _app()
        if app is None:
            return
        try:
            assert app.table.column("Aviso", "stretch")
            assert not app.table.column("Conc.", "stretch")
        finally:
            app.destroy()


class TestItFitsTheScreen:
    def test_the_window_is_not_wider_than_the_screen(self):
        app = _app()
        if app is None:
            return
        try:
            # Without this the geometry reads back as 1x1 and the assertion
            # below passes without testing anything.
            app.update_idletasks()
            geometry = app.geometry().split("+")[0]
            width, height = (int(n) for n in geometry.split("x"))
            assert width > 1 and height > 1
            assert width <= app.winfo_screenwidth()
            assert height <= app.winfo_screenheight()
        finally:
            app.destroy()

    def test_the_contents_fit_without_being_cut_off(self):
        """A laptop screen must still show the buttons and the status line."""
        app = _app()
        if app is None:
            return
        try:
            app.update_idletasks()
            width, height = (int(n) for n in app.geometry().split("+")[0].split("x"))
            assert app.winfo_reqwidth() <= width
            assert app.winfo_reqheight() <= height
        finally:
            app.destroy()
