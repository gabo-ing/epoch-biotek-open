"""What the program says when a dependency is missing.

Both messages used to name a Debian command whatever machine they appeared on,
which is useless to the Windows and Mac users this is meant to be shared with.
A missing tkinter did not even get that far: it ended in a traceback at import,
which is not something a person who did not choose their Python should have to
read.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from epoch_open import reader          # noqa: E402  (after the path fix)


def _launcher_help(platform):
    """tkinter_help() as it reads on a given platform.

    Imported now rather than exec'd out of the launcher's source. It used to
    live in run_gui.py, where the only way to reach it without tkinter
    installed was to read the file and exec the part above the import. Both
    programs share it from epoch_open/launch.py, which deliberately imports no
    tkinter of its own, so it can simply be called.
    """
    from epoch_open.launch import tkinter_help

    real, sys.platform = sys.platform, platform
    try:
        return tkinter_help()
    finally:
        sys.platform = real


def _hint(platform):
    real, sys.platform = sys.platform, platform
    try:
        return reader.pyserial_hint()
    finally:
        sys.platform = real


class TestPyserialHint:
    def test_each_platform_gets_its_own_command(self):
        assert "apt install" in _hint("linux")
        assert "pip3 install pyserial" in _hint("darwin")
        assert "pip install pyserial" in _hint("win32")

    def test_no_platform_is_told_to_use_apt_wrongly(self):
        assert "apt" not in _hint("darwin")
        assert "apt" not in _hint("win32")

    def test_the_mac_is_told_about_externally_managed_environments(self):
        """The error a Mac actually hits first."""
        text = _hint("darwin")
        assert "externally managed" in text
        assert "venv" in text

    def test_the_hint_reaches_the_error_the_user_sees(self):
        """A missing pyserial must carry the advice, not just the diagnosis."""
        raised = None
        real_meta = sys.meta_path[:]
        # pyserial is importable here and already cached, so blocking the
        # finder alone would do nothing: the cached module satisfies the
        # import and the failure path is never reached.
        cached = {name: module for name, module in sys.modules.items()
                  if name == "serial" or name.startswith("serial.")}

        class Block:
            def find_spec(self, name, path=None, target=None):
                if name == "serial" or name.startswith("serial."):
                    raise ImportError("blocked")
                return None

        for name in cached:
            del sys.modules[name]
        sys.meta_path.insert(0, Block())
        try:
            reader._list_ports()
        except reader.ReaderError as exc:
            raised = str(exc)
        finally:
            sys.meta_path[:] = real_meta
            sys.modules.update(cached)

        assert raised is not None
        assert "pyserial is not installed" in raised
        assert "Install it with" in raised


class TestMissingTkinter:
    def test_each_platform_is_told_where_tkinter_comes_from(self):
        assert "apt install python3-tk" in _launcher_help("linux")
        assert "brew install python-tk" in _launcher_help("darwin")
        assert "python.org" in _launcher_help("win32")

    def test_the_mac_hint_names_this_python_version(self):
        """Homebrew packages Tk per minor version, so the number matters."""
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert f"python-tk@{version}" in _launcher_help("darwin")

    def test_windows_is_warned_off_the_store_build(self):
        assert "Microsoft Store" in _launcher_help("win32")

    def test_the_launcher_catches_only_tkinter(self):
        """Any other missing module must still raise, not be swallowed."""
        source = (ROOT / "epoch_open" / "launch.py").read_text()
        assert 'exc.name not in ("tkinter", "_tkinter")' in source
        assert "raise" in source

    def test_both_programs_have_a_launcher(self):
        """Two programs now, and each needs its own way in.

        Named after the program rather than after the window, because the
        wrong plate in the wrong assay is the expensive mistake here: the
        Take3's quartz spots do not survive Salkowski reagent.
        """
        take3 = (ROOT / "run_take3.py").read_text()
        multi = (ROOT / "run_multispectral.py").read_text()
        assert "epoch_open.gui" in take3
        assert "epoch_open.gui_curve" in multi
        # Each should point at the other, so whoever opens the wrong one is
        # told where the right one is.
        assert "run_multispectral.py" in take3
        assert "run_take3.py" in multi
        assert "Take3" in multi
