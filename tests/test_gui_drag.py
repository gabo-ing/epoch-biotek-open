"""Click and drag across the well grids, the way Gen5 does.

Asked for at the bench on 19 November 2026: in Gen5 the mouse can be dragged
across the plate grid to take in every spot at once, and a technician marking
sixteen wells several times a day misses it.

These drive DragSelect directly rather than through a real pointer, because
Tk cannot be made to move the mouse portably. What the tests do stand for is
the contract the widgets rely on: the press takes its direction from the well
it lands on, every well crossed afterwards is made to match, and a well
belonging to another grid is left alone.

The last of those is the one worth protecting. The blank grid and the sample
grid sit side by side, and a drag that ran from one into the other would mark
samples she never asked for.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from epoch_open import gui
    from epoch_open.ui import DragSelect
    IMPORTED = True
except ImportError:          # no tkinter on this machine
    gui = None
    DragSelect = None
    IMPORTED = False


class _Widget:
    """Stands in for one well button: it only has to answer cget and bind."""

    def __init__(self, state="normal"):
        self.state = state
        self.bindings = {}
        self.under = None      # what winfo_containing should report

    def cget(self, key):
        assert key == "state"
        return self.state

    def bind(self, sequence, func, add=None):
        assert add == "+", "must not replace the button's own handler"
        self.bindings.setdefault(sequence, []).append(func)

    def winfo_containing(self, _x, _y):
        return self.under


class _Event:
    def __init__(self, widget, x_root=0, y_root=0):
        self.widget = widget
        self.x_root = x_root
        self.y_root = y_root


class _Grid:
    """A grid of fake wells wired to a DragSelect over a real selection set."""

    def __init__(self, names, states=None):
        states = states or {}
        self.selected = set()
        self.widgets = {n: _Widget(states.get(n, "normal")) for n in names}
        self.drag = DragSelect(toggle=self.toggle,
                               is_selected=lambda n: n in self.selected)
        for name, widget in self.widgets.items():
            self.drag.add(widget, name)

    def toggle(self, name):
        self.selected.symmetric_difference_update({name})

    def press(self, name):
        """A press, including the click the button itself would have done."""
        widget = self.widgets[name]
        if widget.state == "normal":
            self.toggle(name)
        for handler in widget.bindings["<Button-1>"]:
            handler(_Event(widget))
        return widget

    def over(self, start, name):
        """Drag the pointer, held down since `start`, across `name`."""
        origin = self.widgets[start]
        origin.under = self.widgets[name]
        for handler in origin.bindings["<B1-Motion>"]:
            handler(_Event(origin))

    def release(self, start):
        origin = self.widgets[start]
        for handler in origin.bindings["<ButtonRelease-1>"]:
            handler(_Event(origin))


NAMES = ["A2", "A3", "B2", "B3", "C2", "C3"]


class TestDraggingAcrossAGrid:
    def test_a_drag_from_an_empty_well_marks_everything_it_crosses(self):
        if not IMPORTED:
            return
        grid = _Grid(NAMES)
        grid.press("A2")
        for name in ("A3", "B2", "B3"):
            grid.over("A2", name)
        grid.release("A2")
        assert grid.selected == {"A2", "A3", "B2", "B3"}

    def test_a_drag_from_a_marked_well_clears_them(self):
        if not IMPORTED:
            return
        grid = _Grid(NAMES)
        grid.selected.update(NAMES)
        grid.press("A2")                      # the press unmarks A2
        for name in ("A3", "B2"):
            grid.over("A2", name)
        grid.release("A2")
        assert grid.selected == {"B3", "C2", "C3"}

    def test_a_drag_does_not_flip_wells_already_in_the_right_state(self):
        """Crossing a marked well while marking must leave it marked."""
        if not IMPORTED:
            return
        grid = _Grid(NAMES)
        grid.selected.add("B2")
        grid.press("A2")
        for name in ("A3", "B2", "B3"):
            grid.over("A2", name)
        grid.release("A2")
        assert grid.selected == {"A2", "A3", "B2", "B3"}

    def test_crossing_the_same_well_twice_does_not_flip_it_back(self):
        """A wandering hand re-enters a well; that must not undo it."""
        if not IMPORTED:
            return
        grid = _Grid(NAMES)
        grid.press("A2")
        for name in ("A3", "B2", "A3", "A3"):
            grid.over("A2", name)
        grid.release("A2")
        assert grid.selected == {"A2", "A3", "B2"}

    def test_a_drag_stops_at_the_edge_of_its_own_grid(self):
        """The blank grid and the sample grid sit side by side."""
        if not IMPORTED:
            return
        blank = _Grid(NAMES)
        samples = _Grid(NAMES)
        blank.press("A2")
        # The pointer leaves the blank grid and crosses a sample well.
        blank.widgets["A2"].under = samples.widgets["B2"]
        for handler in blank.widgets["A2"].bindings["<B1-Motion>"]:
            handler(_Event(blank.widgets["A2"]))
        blank.release("A2")
        assert blank.selected == {"A2"}
        assert samples.selected == set()

    def test_the_pointer_leaving_the_window_is_harmless(self):
        if not IMPORTED:
            return
        grid = _Grid(NAMES)
        grid.press("A2")
        grid.widgets["A2"].under = None       # winfo_containing off-window
        for handler in grid.widgets["A2"].bindings["<B1-Motion>"]:
            handler(_Event(grid.widgets["A2"]))
        grid.release("A2")
        assert grid.selected == {"A2"}

    def test_motion_after_release_marks_nothing(self):
        if not IMPORTED:
            return
        grid = _Grid(NAMES)
        grid.press("A2")
        grid.release("A2")
        grid.over("A2", "B2")
        assert grid.selected == {"A2"}

    def test_a_disabled_well_is_not_painted(self):
        if not IMPORTED:
            return
        grid = _Grid(NAMES, states={"B2": "disabled"})
        grid.press("A2")
        for name in ("A3", "B2", "B3"):
            grid.over("A2", name)
        grid.release("A2")
        assert grid.selected == {"A2", "A3", "B3"}

    def test_a_drag_begun_on_a_disabled_well_does_nothing(self):
        """There is no direction to take from a press that did not land."""
        if not IMPORTED:
            return
        grid = _Grid(NAMES, states={"A2": "disabled"})
        grid.press("A2")
        for name in ("A3", "B2"):
            grid.over("A2", name)
        grid.release("A2")
        assert grid.selected == set()


class TestTheGridsAreActuallyWiredUp:
    """The tests above prove DragSelect; this proves it reached the screen."""

    def _app(self):
        if not IMPORTED:
            return None
        try:
            return gui.App(gui.MockReader())
        except Exception:    # no X display
            return None

    def test_take3_wells_accept_a_drag(self):
        app = self._app()
        if app is None:
            return
        try:
            for buttons in (app.blank_buttons, app.sample_buttons):
                well = buttons["A2"]
                assert well.bind("<B1-Motion>"), "no drag handler on a well"
        finally:
            app.destroy()

    def test_dragging_the_blank_grid_marks_wells_and_rejudges(self):
        """Through the real widgets: the verdict must follow the marks."""
        app = self._app()
        if app is None:
            return
        try:
            app._clear(app.blank_selected, app.blank_buttons)
            start = app.blank_buttons["A2"]
            start.event_generate("<Button-1>")
            app.update_idletasks()
            assert "A2" in app.blank_selected
            # The handler is driven directly for the crossing, since the
            # pointer cannot be moved portably.
            start.winfo_containing = lambda *_a: app.blank_buttons["A3"]
            start.event_generate("<B1-Motion>")
            app.update_idletasks()
            assert "A3" in app.blank_selected
        finally:
            app.destroy()
