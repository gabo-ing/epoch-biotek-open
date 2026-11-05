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
from epoch_open.xlsx import (curve_to_detail, curve_to_summary,  # noqa: E402
                             export_curve)

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


class TestABatchReadAtTwoWavelengths:
    """The same plate at 490 nm and then at 530 nm, in one batch.

    Gabo did this on 5 November 2026 to compare his coffee at two
    wavelengths, and the workbook could not express it. Sixteen rows came
    out, eight measured at each, with nothing on any row saying which --
    and a footer reading "Longitud de onda: 530 nm", taken from the last
    read and therefore wrong about half the file.

    That is worse than an omission. A reader had no way to know the rows
    differed, and every indication that they did not.
    """

    def _batch(self):
        fit = curve.fit_standards(STANDARDS)
        return [
            curve.read_against("A1", {490: 0.384}, None, wavelength=490),
            curve.read_against("A1", {530: 0.294}, None, wavelength=530),
            curve.read_against("B1", {530: 0.276}, fit, wavelength=530),
        ]

    def test_each_row_carries_the_wavelength_it_was_read_at(self):
        results = self._batch()
        assert [r.wavelength for r in results] == [490, 530, 530]

    def test_the_summary_distinguishes_the_two_reads_of_one_well(self):
        results = self._batch()
        results[0].read_number, results[1].read_number = 1, 2
        rows = curve_to_summary(results, "ug/mL")
        header = rows[0]
        nm = header.index("nm")
        well = header.index("Pozo")
        a1_rows = [r for r in rows[1:] if r[well] == "A1"]
        assert len(a1_rows) == 2
        assert {r[nm] for r in a1_rows} == {490, 530}, (
            "both readings of A1 look identical in the summary")

    def test_the_footer_lists_every_wavelength_not_the_last(self):
        path = _out_dir() / "two-wavelengths.xlsx"
        if path.exists():
            path.unlink()
        results = self._batch()
        export_curve(path, results, None, [530], unit="ug/mL")
        text = _text(path)
        assert "490" in text and "530" in text
        assert "Longitudes de onda leidas" in text, (
            "the footer must summarise the batch, not name one read's setting")

    def test_the_detail_sheet_has_a_column_for_each_wavelength(self):
        rows = curve_to_detail(self._batch(), None, [530])
        header = rows[0]
        assert "490 nm" in header and "530 nm" in header, (
            f"detail header was {header}")

    def test_a_single_wavelength_batch_is_unchanged(self):
        """The common case must not have grown noise."""
        results = [curve.read_against("A1", {530: 0.3}, None, wavelength=530)]
        rows = curve_to_summary(results, "ug/mL")
        assert rows[1][rows[0].index("nm")] == 530
        assert rows[1][rows[0].index("Ref. nm")] == "", (
            "no reference was used, so that cell stays empty")


class TestAWorkbookWithACurvePerWavelength:
    """Standards measured at several wavelengths produce several curves.

    Each sample row is quantified against the curve for its own wavelength,
    so every one of those curves has to be in the file. A workbook recording
    only the first would leave the other concentrations unauditable -- real
    numbers, derived from a calibration nobody can see.
    """

    def _fits(self):
        return {
            490: curve.fit_standards([
                curve.Standard("A2", 0, 0.000),
                curve.Standard("B2", 5, 0.046),
                curve.Standard("C2", 10, 0.091),
                curve.Standard("D2", 20, 0.183),
            ]),
            530: curve.fit_standards(STANDARDS),
        }

    def test_every_curve_gets_its_own_block(self):
        path = _out_dir() / "curve-per-wavelength.xlsx"
        if path.exists():
            path.unlink()
        export_curve(path, [], self._fits(), [490, 530], unit="ug/mL")
        text = _text(path)
        assert "Curva a 490 nm" in text
        assert "Curva a 530 nm" in text

    def test_each_curve_reports_its_own_r2(self):
        path = _out_dir() / "curve-per-wavelength-r2.xlsx"
        if path.exists():
            path.unlink()
        export_curve(path, [], self._fits(), [490, 530], unit="ug/mL")
        assert _text(path).count("r2 de la curva a") == 2

    def test_a_single_curve_still_reads_as_one(self):
        """The ordinary case must not have grown wavelength labels."""
        path = _out_dir() / "curve-single-still.xlsx"
        if path.exists():
            path.unlink()
        export_curve(path, [], curve.fit_standards(STANDARDS), [530],
                     unit="ug/mL")
        text = _text(path)
        assert "Pendiente" in text
        assert "Curva a " not in text
