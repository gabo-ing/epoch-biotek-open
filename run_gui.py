"""Launch the quantification window.

    python3 run_gui.py           against the instrument
    python3 run_gui.py --sim     simulated numbers, for looking at the screen

Needs tkinter. It ships with the python.org builds of Python, but not with every
Python: Homebrew packages it separately, and Linux distributions do too. If it is
missing this prints how to get it rather than a traceback.
"""

import sys


def _tkinter_help() -> str:
    """Where tkinter comes from on this platform.

    Written for someone who did not choose their Python and should not have to
    read a traceback to find out that a standard-library module is absent.
    """
    if sys.platform == "darwin":
        return (
            "    brew install python-tk@{v}      if this Python came from Homebrew\n"
            "\n"
            "or install Python from https://www.python.org/downloads/ , which\n"
            "bundles Tk. That is the build this program is meant to run on."
        ).format(v=f"{sys.version_info.major}.{sys.version_info.minor}")
    if sys.platform == "win32":
        return (
            "    Install Python from https://www.python.org/downloads/\n"
            "\n"
            "Do not use the Microsoft Store build: it has shipped without tkinter."
        )
    return (
        "    sudo apt install python3-tk      (Debian/Ubuntu)\n"
        "    sudo dnf install python3-tkinter (Fedora)"
    )


try:
    from epoch_open.gui import main
except ModuleNotFoundError as exc:
    if exc.name not in ("tkinter", "_tkinter"):
        raise
    print(
        "This program needs tkinter, and this Python does not have it.\n"
        f"({sys.executable}, Python "
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro})\n\n"
        + _tkinter_help(),
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    sys.exit(main())
