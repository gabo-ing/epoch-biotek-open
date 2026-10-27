"""The reader being switched on (or off) after the program has started.

The technician will routinely open the program before the Epoch has finished
warming up, so the window has to notice the instrument appearing instead of
staying in simulation until someone restarts it. The reverse matters more: if
the reader stops answering mid-session, the program must say so rather than
quietly produce simulated numbers that look like measurements.

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


class FakeReader:
    """Stands in for a connected EpochReader without touching a serial port."""

    def __init__(self, serial="254717", port="/dev/ttyUSB0"):
        self.expected_serial = serial
        self.port = port
        self.closed = False

    def close(self):
        self.closed = True


def _app():
    """A real window, or None when there is no display to put it on."""
    if not IMPORTED:
        return None
    try:
        return gui.App(gui.MockReader())
    except Exception:        # no X display
        return None


class TestReaderAppears:
    def test_adopts_a_reader_when_the_batch_is_empty(self):
        app = _app()
        if app is None:
            return
        try:
            assert app.simulated is True
            app.watching = True
            app._adopt(FakeReader())
            assert app.simulated is False
            assert app.lost is False
            assert app.info.serial == "254717"
            assert "Lector" in app.banner.cget("text")
        finally:
            app.destroy()

    def test_keeps_simulated_data_out_of_a_real_batch(self):
        """Saying no leaves the simulated batch alone, and it does not ask twice."""
        app = _app()
        if app is None:
            return
        try:
            app.watching = True
            app.blank = {"A2": object()}
            app.results = [(1, object())]
            reader = FakeReader()
            gui.messagebox.askyesno = lambda *a, **k: False
            app._adopt(reader)
            assert app.simulated is True          # still simulating
            assert app.blank is not None          # batch untouched
            assert reader.closed is True          # port handed back
            assert app._probe_declined is True

            second = FakeReader()
            app._adopt(second)
            assert app.simulated is True
            assert second.closed is True
        finally:
            app.destroy()

    def test_discards_the_simulated_batch_when_she_agrees(self):
        app = _app()
        if app is None:
            return
        try:
            app.watching = True
            app.blank = {"A2": object()}
            app.results = [(1, object())]
            app.read_number = 1
            gui.messagebox.askyesno = lambda *a, **k: True
            app._adopt(FakeReader())
            assert app.simulated is False
            assert app.blank is None
            assert app.results == []
            assert app.read_number == 0
        finally:
            app.destroy()


class TestReaderDisappears:
    def test_a_failed_read_marks_the_reader_lost(self):
        app = _app()
        if app is None:
            return
        try:
            app._adopt(FakeReader())
            assert app.simulated is False
            app.watching = True
            app._mark_lost()
            assert app.lost is True
            # Never a silent fall back to fabricated data.
            assert app.simulated is False
            assert "NO RESPONDE" in app.banner.cget("text")
        finally:
            app.destroy()

    def test_losing_the_reader_while_simulating_changes_nothing(self):
        app = _app()
        if app is None:
            return
        try:
            app._mark_lost()
            assert app.lost is False
        finally:
            app.destroy()


class TestProbeSafety:
    def test_probe_skips_while_the_port_is_busy(self):
        """A probe must never open the port in the middle of a read."""
        app = _app()
        if app is None:
            return
        try:
            app._port_lock.acquire()
            app._probe()
            assert app._probe_found is None
        finally:
            app._port_lock.release()
            app.destroy()
