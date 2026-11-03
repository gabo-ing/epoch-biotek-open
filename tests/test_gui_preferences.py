"""The Preferences dialog: the thresholds, reachable without a rebuild.

The program ships as a single .exe. Before this dialog existed, changing a
limit meant editing JSON next to the executable or rebuilding, which in
practice meant nobody would. The numbers are Gen5's and should rarely move --
but a threshold nobody can reach is worse than a wrong one.

These build real windows, so they are skipped when there is no display; see
tests/test_gui_starts.py, which makes a window that will not build a failure
rather than a skip.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from epoch_open import config, gui, quant
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


class _Silenced:
    """Swallow the error dialogs, and record that they were raised.

    _save() reports a bad value with messagebox.showerror, which is right on
    the bench and fatal in a test: it is modal, and with nobody to dismiss it
    the suite hangs rather than fails. Found exactly that way.
    """

    def __enter__(self):
        self.shown = []
        self._real = gui.messagebox.showerror
        gui.messagebox.showerror = lambda *a, **k: self.shown.append(a)
        return self

    def __exit__(self, *exc):
        gui.messagebox.showerror = self._real
        return False


def _dialog(app, cfg=None):
    return gui.PreferencesDialog(app, cfg or config.Config())


def _set(dialog, key, value):
    dialog.fields[key].set(value)


class TestItShowsWhatIsInForce:

    def test_it_opens_on_the_current_values(self):
        app = _app()
        if app is None:
            return
        try:
            cfg = config.Config()
            cfg.blank_cv_limit_percent = 7.5
            dialog = _dialog(app, cfg)
            assert dialog.fields["cv"].get() == "7,5"
            dialog.destroy()
        finally:
            app.destroy()

    def test_the_decimal_mark_is_the_one_the_lab_writes(self):
        """Spanish throughout the rest of the screen, so a comma here too."""
        app = _app()
        if app is None:
            return
        try:
            dialog = _dialog(app)
            assert "," in dialog.fields["ref_limit"].get()
            assert "." not in dialog.fields["ref_limit"].get()
            dialog.destroy()
        finally:
            app.destroy()

    def test_the_defaults_shown_are_gen5_s_factory_values(self):
        """10 and 0,1, read off the lab's licensed Take3 Preferences dialog."""
        app = _app()
        if app is None:
            return
        try:
            dialog = _dialog(app)
            dialog._defaults()
            assert dialog.fields["cv"].get() == "10,0"
            assert dialog.fields["ref_limit"].get() == "0,1"
            assert dialog.fields["ref_nm"].get() == "320"
            dialog.destroy()
        finally:
            app.destroy()


class TestSaving:

    def test_a_valid_edit_comes_back_as_numbers(self):
        app = _app()
        if app is None:
            return
        try:
            dialog = _dialog(app)
            _set(dialog, "cv", "6,5")
            dialog._save()
            assert dialog.result is not None
            assert dialog.result["cv"] == 6.5
        finally:
            app.destroy()

    def test_a_comma_and_a_point_are_both_accepted(self):
        """Whichever she types, the number has to arrive intact."""
        app = _app()
        if app is None:
            return
        try:
            for typed in ("6,5", "6.5"):
                dialog = _dialog(app)
                _set(dialog, "cv", typed)
                dialog._save()
                assert dialog.result["cv"] == 6.5, f"{typed} was misread"
        finally:
            app.destroy()

    def test_rubbish_is_refused_rather_than_silently_defaulted(self):
        app = _app()
        if app is None:
            return
        try:
            with _Silenced() as quiet:
                dialog = _dialog(app)
                _set(dialog, "cv", "mucho")
                dialog._save()
                assert dialog.result is None, "nonsense was accepted"
                assert quiet.shown, "it failed without saying why"
                assert dialog.winfo_exists(), "the dialog closed on a bad value"
                dialog.destroy()
        finally:
            app.destroy()

    def test_zero_and_negatives_are_refused(self):
        """A CV% limit of zero would reject every blank ever read."""
        app = _app()
        if app is None:
            return
        try:
            with _Silenced():
                for bad in ("0", "-1", "0,0"):
                    dialog = _dialog(app)
                    _set(dialog, "cv", bad)
                    dialog._save()
                    assert dialog.result is None, f"{bad} was accepted"
                    dialog.destroy()
        finally:
            app.destroy()

    def test_the_reference_wavelength_cannot_be_moved(self):
        """It is shown because Gen5 shows it, but every read is built on 320.

        Letting it be changed here would be a lie: the program always reads
        320 nm and subtracts it. Refusing is honest; ignoring the edit would
        leave her believing something had changed.
        """
        app = _app()
        if app is None:
            return
        try:
            with _Silenced() as quiet:
                dialog = _dialog(app)
                _set(dialog, "ref_nm", "340")
                dialog._save()
                assert dialog.result is None
                assert quiet.shown, "it refused without saying why"
                dialog.destroy()
        finally:
            app.destroy()

    def test_cancel_changes_nothing(self):
        app = _app()
        if app is None:
            return
        try:
            dialog = _dialog(app)
            _set(dialog, "cv", "99")
            dialog.destroy()
            assert dialog.result is None
        finally:
            app.destroy()


class TestItActuallyChangesTheVerdict:

    def test_a_tighter_cv_limit_fails_a_blank_that_passed(self):
        """The point of the dialog: the number has to reach the verdict.

        Checked through quant.blank_report rather than the screen, because
        this is about the limit being used, not about where it is displayed.
        """
        if not IMPORTED:
            return
        from tests.test_blanking import GEN5_VALID_RUN, wells

        blanks = wells(GEN5_VALID_RUN)
        assert quant.blank_report(blanks).valid
        tightened = quant.blank_report(blanks, cv_limit_percent=1.0)
        assert not tightened.valid
        assert tightened.reason == "cv"

    def test_the_window_rejudges_without_a_restart(self):
        """A blanking already on screen must be re-judged when the limit moves."""
        app = _app()
        if app is None:
            return
        try:
            from tests.test_blanking import GEN5_VALID_RUN

            app.blank_selected.clear()
            app.blank_raw = {}
            for well, values in GEN5_VALID_RUN.items():
                app.blank_raw[well] = quant.RawWell(
                    well, {260: values[0], 280: values[1], 320: values[2]})
                app.blank_selected.add(well)

            app._refresh_state()
            assert app._blank_ok(), "the Gen5-accepted blank should pass"

            original = gui.CONFIG.blank_cv_limit_percent
            try:
                gui.CONFIG.blank_cv_limit_percent = 1.0
                app._refresh_state()
                assert not app._blank_ok(), "the tighter limit was not applied"
                assert app.blank_report.reason == "cv"
            finally:
                gui.CONFIG.blank_cv_limit_percent = original
                app._refresh_state()
        finally:
            app.destroy()
