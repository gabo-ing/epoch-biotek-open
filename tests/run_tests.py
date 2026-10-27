"""Run the test suite without pytest installed.

Supplies just enough of pytest's surface (approx, raises) for these tests, then
walks the Test* classes and runs their test_* methods. If real pytest is available,
`python3 -m pytest tests/` works too and is preferred.
"""

import sys
import traceback
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class _Approx:
    def __init__(self, expected, rel=1e-6, abs_=0.0):
        self.expected = expected
        self.rel = rel
        self.abs = abs_

    def __eq__(self, actual):
        tolerance = max(self.abs, abs(self.expected) * self.rel)
        return abs(actual - self.expected) <= tolerance

    def __repr__(self):
        return f"approx({self.expected})"


class _Raises:
    def __init__(self, exc_type, match=None):
        self.exc_type = exc_type
        self.match = match

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _tb):
        if exc_type is None:
            raise AssertionError(f"expected {self.exc_type.__name__}, nothing raised")
        if not issubclass(exc_type, self.exc_type):
            return False
        if self.match and self.match not in str(exc):
            raise AssertionError(f"{self.match!r} not found in {str(exc)!r}")
        return True


def _install_pytest_stub() -> None:
    if "pytest" in sys.modules:
        return
    try:
        import pytest  # noqa: F401
        return
    except ImportError:
        pass

    stub = ModuleType("pytest")
    stub.approx = lambda expected, rel=1e-6, abs=0.0: _Approx(expected, rel, abs)
    stub.raises = lambda exc_type, match=None: _Raises(exc_type, match)
    sys.modules["pytest"] = stub


def main() -> int:
    _install_pytest_stub()

    # Found on disk, not listed by hand: a hand-written list means a new test
    # file is silently never run, and a suite that skips tests is worse than no
    # suite at all -- it reports success over code nobody exercised.
    import importlib

    here = Path(__file__).resolve().parent
    modules = [
        importlib.import_module(path.stem)
        for path in sorted(here.glob("test_*.py"))
    ]

    passed, failures = 0, []
    classes = [
        obj
        for module in modules
        for name, obj in vars(module).items()
        if name.startswith("Test") and isinstance(obj, type)
    ]

    for cls in classes:
        instance = cls()
        methods = sorted(m for m in dir(instance) if m.startswith("test_"))
        for method_name in methods:
            label = f"{cls.__name__}.{method_name}"
            try:
                getattr(instance, method_name)()
                passed += 1
                print(f"  ok   {label}")
            except Exception:
                failures.append((label, traceback.format_exc()))
                print(f"  FAIL {label}")

    print(f"\n{passed} passed, {len(failures)} failed")
    for label, tb in failures:
        print(f"\n--- {label} ---\n{tb}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
