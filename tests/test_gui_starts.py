"""The programs must actually start, and a failure to start must fail loudly.

Every other GUI test here opens with some form of::

    app = _app()
    if app is None:
        return

which is right, because the suite has to pass on a machine with no display.
But it means a program that cannot build its own window does not fail those
tests -- it skips every one of them, and the suite reports a clean run over
software that is completely broken.

That has now happened twice in this project. The second time, moving `_style`
into the shared ui module left `ttk` unimported there, so every window raised
NameError on construction, and all 262 tests still passed.

So this file tells the two cases apart. If a bare tk.Tk() can be created, a
display exists, and from then on an App that will not build is a failure
rather than a skip.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _display_works() -> bool:
    """Whether this machine can open a window at all."""
    try:
        import tkinter as tk
    except ImportError:
        return False
    try:
        probe = tk.Tk()
    except Exception:
        return False
    probe.destroy()
    return True


class TestTheProgramsStart:

    def test_take3_builds_its_window(self):
        if not _display_works():
            return
        from epoch_open import gui

        app = gui.App(gui.MockReader())      # must not raise
        try:
            app.update_idletasks()
            assert app.winfo_exists()
            assert app.status.cget("text")
        finally:
            app.destroy()

    def test_multispectral_builds_its_window(self):
        if not _display_works():
            return
        try:
            from epoch_open import gui_curve
        except ImportError:                  # not written yet
            return
        from epoch_open.reader import MockCurveReader

        app = gui_curve.App(MockCurveReader())
        try:
            app.update_idletasks()
            assert app.winfo_exists()
            assert app.status.cget("text")
        finally:
            app.destroy()

    def test_the_shared_module_has_what_its_own_code_needs(self):
        """A plain import catches a name the shared chrome forgot to bring.

        Cheap, and it does not need a display: the NameError that caused this
        file to exist was in a method, not at import time, so this is a
        backstop rather than the main guard.
        """
        from epoch_open import ui

        assert ui.ttk is not None
        assert hasattr(ui.ScreenFit, "_style")
        assert hasattr(ui.ScreenFit, "_size_to_screen")
        assert hasattr(ui.ScreenFit, "_shrink_to_content")
