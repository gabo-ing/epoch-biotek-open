"""The window has to open somewhere the whole of it can be seen.

On the test laptops it did not. It opened taller than the usable screen and
the status bar -- the single line telling the technician which step she is on
and why a button is refusing her -- sat underneath the taskbar, unreadable
until the window was moved or maximised.

Two independent faults put it there, and either one alone would have been
enough, so both are pinned here:

  * the opening size was measured against the whole screen panel, taskbar
    included, so a window sized to "the screen" does not fit on it;
  * the status bar was packed last, and Tk's packer squeezes the last widget
    first, so any shortfall at all deleted the bar outright instead of
    trimming the grid above it.

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


def _geometry(app):
    """The window's own geometry, as (width, height, x, y)."""
    app.update_idletasks()
    size, x, y = app.geometry().split("+")
    width, height = size.split("x")
    return int(width), int(height), int(x), int(y)


class TestTheWindowFitsOnTheScreen:

    def test_it_opens_inside_the_usable_area_not_merely_the_panel(self):
        """The bottom edge is the one that matters: the status bar is on it."""
        app = _app()
        if app is None:
            return
        try:
            work_w, work_h = app._work_area()
            width, height, x, y = _geometry(app)
            assert x + width <= work_w, "right edge is off the usable screen"
            assert y + height <= work_h, "bottom edge is under the taskbar"
        finally:
            app.destroy()

    def test_the_usable_area_is_never_taller_than_the_screen(self):
        """A work area larger than the panel it sits on is Tk guessing.

        wm maxsize is right on Windows and macOS and merely repeats the screen
        size on X11. Trusting a nonsense answer would undo the whole fix, so a
        bad one has to fall back instead.
        """
        app = _app()
        if app is None:
            return
        try:
            work_w, work_h = app._work_area()
            assert 0 < work_w <= app.winfo_screenwidth()
            assert 0 < work_h <= app.winfo_screenheight()
        finally:
            app.destroy()

    def test_it_does_not_open_wider_than_its_contents_need(self):
        """The opening size is a guess made before anything is built.

        Once the widgets exist they can say what they want, and on a cramped
        laptop the slack between the guess and the truth is the difference
        between the status bar clearing the taskbar and hiding behind it.
        """
        app = _app()
        if app is None:
            return
        try:
            width, height, _x, _y = _geometry(app)
            min_w, min_h = app.minsize()
            assert width <= max(app.winfo_reqwidth(), min_w)
            assert height <= max(app.winfo_reqheight(), min_h)
        finally:
            app.destroy()


class TestTheStatusBarSurvivesASqueeze:

    def test_it_is_still_on_screen_at_the_smallest_allowed_size(self):
        """Regression: it used to be laid out below the bottom of the window.

        At 900x600 -- the minimum the window itself permits -- the bar was
        placed at y=911 and never mapped. The number it reported was not a
        little clipped; the widget was not on the window at all.
        """
        app = _app()
        if app is None:
            return
        try:
            min_w, min_h = app.minsize()
            app.geometry(f"{min_w}x{min_h}")
            app.update_idletasks()
            bottom = app.status.winfo_y() + app.status.winfo_height()
            assert app.status.winfo_ismapped(), "status bar fell off the window"
            assert bottom <= app.winfo_height(), (
                f"status bar ends at {bottom} in a window "
                f"{app.winfo_height()} tall")
        finally:
            app.destroy()

    def test_the_body_gives_up_the_room_rather_than_the_bar(self):
        """Shrinking must cost the grid its slack, not cost the bar its line."""
        app = _app()
        if app is None:
            return
        try:
            app.update_idletasks()
            roomy = app.status.winfo_height()
            min_w, min_h = app.minsize()
            app.geometry(f"{min_w}x{min_h}")
            app.update_idletasks()
            assert app.status.winfo_height() >= roomy - 2, (
                "the status bar was trimmed to make room for the grid")
        finally:
            app.destroy()

    def test_the_bar_is_packed_before_the_body_claims_the_cavity(self):
        """Tk squeezes the last widget packed, so order is the whole fix.

        Checked directly rather than through sizes, because a window that
        happens to be roomy enough hides the fault this pins.
        """
        app = _app()
        if app is None:
            return
        try:
            order = [str(w) for w in app.pack_slaves()]
            assert str(app.status) in order
            body = [name for name in order if name != str(app.status)]
            assert order.index(str(app.status)) < max(
                order.index(name) for name in body), (
                "the status bar is packed last, so it is squeezed first")
        finally:
            app.destroy()
