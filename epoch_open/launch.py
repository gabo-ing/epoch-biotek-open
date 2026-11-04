"""Starting a program, and saying something useful when it cannot start.

There are two programs now -- epoch-take3 and epoch-multispectral -- and both
fail the same way on a Python without tkinter, which is the failure a lab
actually hits: tkinter is in the standard library but not in every build of
it, and the person running into this did not choose their Python and should
not have to read a traceback to learn that a standard-library module is
absent.

Kept out of the launcher scripts so the two cannot drift apart, and kept free
of any tkinter import of its own, since the whole point is to run before that
import is attempted.
"""

import sys


def tkinter_help() -> str:
    """Where tkinter comes from on this platform.

    Platform-specific on purpose. The message used to name a Debian command
    whatever machine it appeared on, which is no use to the Windows and Mac
    users this gets shared with.
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


def no_tkinter(exc: ModuleNotFoundError) -> int:
    """Explain a missing tkinter, or re-raise anything else.

    Called from each launcher's except clause. The launchers do their own
    `from epoch_open.gui import main` rather than handing a module name to
    importlib, and that is not a style preference -- it is the difference
    between a working .exe and a broken one.

    PyInstaller decides what to bundle by reading import statements. A name
    passed to importlib.import_module is just a string to it, so the module
    is left out of the build and the frozen program dies on launch with
    "No module named 'epoch_open.gui'". It works perfectly from source, so
    nothing catches it until someone runs the executable -- which is how this
    was found, on 4 November 2026, on the Dell at the bench.
    """
    # Only tkinter is explained away. Anything else missing is a real problem
    # and has to keep its traceback.
    if exc.name not in ("tkinter", "_tkinter"):
        raise exc
    print(
        "This program needs tkinter, and this Python does not have it.\n"
        f"({sys.executable}, Python "
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro})\n\n"
        + tkinter_help(),
        file=sys.stderr,
    )
    return 1
