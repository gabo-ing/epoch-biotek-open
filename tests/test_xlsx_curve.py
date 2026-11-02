"""The workbook a colorimetric run produces.

A curve assay's result cannot be checked from the concentrations alone: they
mean nothing without the standards they were interpolated from. So what these
check is not only that the file opens, but that the curve travelled with the
numbers -- otherwise a figure in this spreadsheet is unauditable six months
later, including by the person who measured it.

In its own file rather than appended to test_xlsx.py because it covers a
different writer with different sheets; test_xlsx.py keeps the Take3 workbook.
"""

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import curve                     # noqa: E402
from epoch_open.xlsx import export_curve         # noqa: E402

STANDARDS = [
    curve.Standard("A2", 0, 0.000),
    curve.Standard("B2", 5, 0.100),
    curve.Standard("C2", 10, 0.200),
    curve.Standard("D2", 20, 0.400),
    curve.Standard("E2", 40, 0.800),
]


def _out_dir() -> Path:
    directory = Path(__file__).resolve().parent / "_out"
    directory.mkdir(exist_ok=True)
    return directory


def _written(name: str):
    """A real workbook on disk, plus the fit and results that made it."""
    fit = curve.fit_standards(STANDARDS)
    results = [
        curve.read_against("A3", {530: 0.305, 650: 0.010}, fit, name="cepa 12"),
        # Far above the top standard, so the out-of-range path is exercised.
        curve.read_against("B3", {530: 1.900, 650: 0.010}, fit),
    ]
    path = _out_dir() / name
    if path.exists():
        path.unlink()
    export_curve(path, results, fit, [530, 650],
                 metadata={"Lector": "SIMULADO"})
    return path, fit, results


def _text(path: Path) -> str:
    """Everything the workbook says, strings and numbers together."""
    with zipfile.ZipFile(path) as archive:
        return "".join(
            archive.read(name).decode("utf-8", "replace")
            for name in archive.namelist()
            if name.endswith(".xml")
        )


class TestCurveWorkbook:

    def test_every_part_is_valid_xml(self):
        path, _fit, _results = _written("curve-parts.xlsx")
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                ElementTree.fromstring(archive.read(name))

    def test_it_has_the_three_sheets(self):
        path, _fit, _results = _written("curve-sheets.xlsx")
        with zipfile.ZipFile(path) as archive:
            workbook = archive.read("xl/workbook.xml").decode()
        for sheet in ("Resumen", "Curva", "Detalle"):
            assert sheet in workbook, f"no {sheet} sheet"

    def test_the_standards_travel_with_the_results(self):
        """Without them a concentration here cannot be audited by anyone."""
        path, fit, _results = _written("curve-standards.xlsx")
        text = _text(path)
        for standard in fit.standards:
            assert standard.well in text, f"{standard.well} missing"

    def test_the_fit_is_recorded_not_just_a_pass_mark(self):
        path, _fit, _results = _written("curve-fit.xlsx")
        text = _text(path)
        for label in ("Pendiente", "Intercepto", "r2", "Peor residual"):
            assert label in text, f"{label} missing from the workbook"

    def test_a_sample_off_the_curve_keeps_its_warning_in_the_file(self):
        """The warning has to survive into the spreadsheet, not only the screen."""
        path, _fit, results = _written("curve-range.xlsx")
        assert not results[1].in_range
        assert "diluye" in _text(path).lower()

    def test_the_sample_name_is_used_when_there_is_one(self):
        path, _fit, _results = _written("curve-names.xlsx")
        assert "cepa 12" in _text(path)

    def test_the_measured_wavelengths_are_named_in_the_detail(self):
        """So a reader knows what was read, including the reference."""
        path, _fit, _results = _written("curve-nm.xlsx")
        text = _text(path)
        assert "530 nm" in text
        assert "650 nm" in text
