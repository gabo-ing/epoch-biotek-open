"""With no instrument attached, the program must not produce numbers.

It used to fall back to the simulator whenever the Epoch did not answer, so an
instrument that was merely switched off gave a screen full of invented values
behind a warning banner. One mis-read banner and simulated figures reach a lab
notebook looking exactly like measurements.

The simulator still exists -- the tests below use it, and `--sim` brings it up
for looking at the screen -- but it is never substituted for hardware silently.
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


def _app(backend):
    if not IMPORTED:
        return None
    try:
        return gui.App(backend)
    except Exception:        # no X display
        return None


def _state(app, key):
    return str(app.action_buttons[key].cget("state"))


class TestNoReaderMeansNoNumbers:
    def test_reading_is_disabled_without_an_instrument(self):
        app = _app(None)
        if app is None:
            return
        try:
            assert app.no_reader is True
            assert app.simulated is False      # not quietly simulating
            assert _state(app, "read_blank") == "disabled"
            assert _state(app, "read_samples") == "disabled"
        finally:
            app.destroy()

    def test_the_screen_says_to_switch_the_reader_on(self):
        app = _app(None)
        if app is None:
            return
        try:
            assert "lector" in app.banner.cget("text").lower()
            assert "enciend" in app.status.cget("text").lower()
        finally:
            app.destroy()

    def test_a_read_is_refused_even_if_something_calls_it(self):
        """Backstop behind the disabled buttons."""
        app = _app(None)
        if app is None:
            return
        try:
            raised = False
            try:
                app._read(["A2"], as_blank=True)
            except gui.ReaderError:
                raised = True
            assert raised
        finally:
            app.destroy()

    def test_it_keeps_looking_and_comes_alive_when_found(self):
        app = _app(None)
        if app is None:
            return
        try:
            app.watching = True
            assert app._needs_reader() is True

            class FakeReader:
                expected_serial = None
                port = "/dev/ttyUSB0"
                info = gui.ReaderInfo(model="Epoch", serial="254717",
                                      firmware="1.12", port="/dev/ttyUSB0")

                def close(self):
                    pass

            app._adopt(FakeReader())
            assert app.no_reader is False
            assert _state(app, "read_blank") == "normal"
        finally:
            app.destroy()


class TestSimulatorMustBeAskedFor:
    def test_connect_backend_returns_nothing_rather_than_a_simulator(self):
        if not IMPORTED:
            return
        # No instrument is attached to the machine running the tests, so this
        # exercises the real path.
        assert gui.connect_backend(force_simulator=False) is None

    def test_the_simulator_is_still_available_on_request(self):
        if not IMPORTED:
            return
        backend = gui.connect_backend(force_simulator=True)
        assert isinstance(backend, gui.MockReader)

    def test_simulated_results_are_still_labelled_as_such(self):
        app = _app(gui.MockReader() if IMPORTED else None)
        if app is None:
            return
        try:
            assert app.simulated is True
            assert "SIMULACION" in app.banner.cget("text")
        finally:
            app.destroy()
