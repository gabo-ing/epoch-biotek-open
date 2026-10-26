"""Smoke tests for the interface module.

These exist because of a real failure: a patch wired `CONFIG` into the GUI but
only half applied. The line *using* CONFIG landed, the lines *defining* it did
not, and the module was committed in that state. The whole suite passed, because
nothing imported gui.py. The program crashed with NameError at startup.

Importing the module and checking its module-level names is cheap and would have
caught it. Building a window is not attempted: it needs a display.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tkinter = pytest.importorskip("tkinter") if hasattr(pytest, "importorskip") else None

try:
    from epoch_open import gui
    IMPORTED = True
except ImportError:          # no tkinter on this machine
    gui = None
    IMPORTED = False


class TestModuleImports:
    def test_module_imports(self):
        if not IMPORTED:
            return          # tkinter absent; nothing to check
        assert gui is not None

    def test_config_is_defined(self):
        """The exact bug: CONFIG used but never defined."""
        if not IMPORTED:
            return
        assert hasattr(gui, "CONFIG")
        assert gui.CONFIG is not None

    def test_settings_come_from_the_config(self):
        if not IMPORTED:
            return
        assert gui.PLATE_SERIAL == gui.CONFIG.plate_serial
        assert gui.PLATE_READER_SERIAL == gui.CONFIG.reader_serial

    def test_no_reader_serial_is_hardcoded(self):
        """Another owner's reader must not be rejected by a compiled-in serial."""
        source = (Path(__file__).resolve().parent.parent
                  / "epoch_open" / "gui.py").read_text()
        assert '"254717"' not in source

    def test_every_name_app_uses_at_import_time_exists(self):
        if not IMPORTED:
            return
        for name in ("TEXT", "SAMPLE_TYPES", "PLATE_SERIAL", "PLATE_READER_SERIAL",
                     "CONFIG", "App", "main", "connect_backend"):
            assert hasattr(gui, name), name

    def test_palette_names_are_all_defined(self):
        if not IMPORTED:
            return
        for name in ("INK", "MUTED", "LINE", "CANVAS", "PANEL", "CHOSEN",
                     "CHOSEN_INK", "EMPTY", "GOOD", "BAD", "WARN_ROW",
                     "ACTION", "ACTION_INK"):
            assert hasattr(gui, name), name
