"""Tests for the xlsx writer.

These check the file really is a well-formed xlsx -- every part present and every
part valid XML -- rather than just that the call returned without raising.
"""

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open.quant import RawWell, quantify  # noqa: E402
from epoch_open.xlsx import (  # noqa: E402
    column_letter,
    export_results,
    results_to_rows,
    write_xlsx,
)

REQUIRED_PARTS = [
    "[Content_Types].xml",
    "_rels/.rels",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
    "xl/styles.xml",
    "xl/worksheets/sheet1.xml",
]


def tmp_path_for(name: str) -> Path:
    directory = Path(__file__).resolve().parent / "_out"
    directory.mkdir(exist_ok=True)
    return directory / name


class TestColumnLetter:
    def test_first_column(self):
        assert column_letter(1) == "A"

    def test_last_single_letter(self):
        assert column_letter(26) == "Z"

    def test_first_double_letter(self):
        assert column_letter(27) == "AA"

    def test_zero_is_rejected(self):
        with pytest.raises(ValueError):
            column_letter(0)


class TestWriteXlsx:
    def test_all_parts_are_present(self):
        path = write_xlsx(tmp_path_for("parts.xlsx"), [["A"], ["B"]])
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        for part in REQUIRED_PARTS:
            assert part in names

    def test_every_part_is_valid_xml(self):
        path = write_xlsx(
            tmp_path_for("valid.xlsx"),
            [["Well", "Conc"], ["A1", 123.4], ["A2", None]],
        )
        with zipfile.ZipFile(path) as z:
            for part in REQUIRED_PARTS:
                ElementTree.fromstring(z.read(part))  # raises if malformed

    def test_text_needing_escapes_survives(self):
        nasty = 'R&D <sample> "quoted"'
        path = write_xlsx(tmp_path_for("escape.xlsx"), [["Note"], [nasty]])
        with zipfile.ZipFile(path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
            ElementTree.fromstring(sheet)
        root = ElementTree.fromstring(sheet)
        texts = [e.text for e in root.iter() if e.tag.endswith("}t")]
        assert nasty in texts

    def test_numbers_are_written_as_numbers(self):
        path = write_xlsx(tmp_path_for("nums.xlsx"), [["n"], [42.5]])
        with zipfile.ZipFile(path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
        assert "<v>42.5</v>" in sheet
        assert "inlineStr" not in sheet.split("<row r=\"2\"")[1]

    def test_empty_workbook_is_refused(self):
        with pytest.raises(ValueError):
            write_xlsx(tmp_path_for("empty.xlsx"), [])

    def test_illegal_sheet_name_characters_are_stripped(self):
        path = write_xlsx(tmp_path_for("name.xlsx"), [["x"]], sheet_name="a/b*c?d")
        with zipfile.ZipFile(path) as z:
            workbook = z.read("xl/workbook.xml").decode()
        ElementTree.fromstring(workbook)
        assert 'name="abcd"' in workbook


class TestResultsExport:
    def make_results(self):
        blank = RawWell("blank", {260: 0.045, 280: 0.045, 320: 0.040})
        wells = [
            RawWell("B2", {260: 0.098, 280: 0.074, 320: 0.044}),
            RawWell("B3", {260: 0.103, 280: 0.078, 320: 0.048}),
        ]
        return [quantify(w, blank) for w in wells]

    def test_header_and_one_row_per_result(self):
        rows = results_to_rows(self.make_results())
        assert rows[0][0] == "Sample Read#"
        assert rows[0][1] == "Location"
        assert len(rows) == 3
        assert rows[1][1] == "B2"

    def test_read_number_defaults_to_one(self):
        rows = results_to_rows(self.make_results())
        assert rows[1][0] == 1

    def test_read_numbers_are_kept_when_given(self):
        results = self.make_results()
        rows = results_to_rows([(1, results[0]), (2, results[1])])
        assert rows[1][0] == 1
        assert rows[2][0] == 2

    def test_sample_names_are_filled_in(self):
        rows = results_to_rows(self.make_results(), {"B2": "tubo 1"})
        assert rows[1][2] == "tubo 1"
        assert rows[2][2] == ""

    def test_raw_values_are_carried_through(self):
        rows = results_to_rows(self.make_results())
        assert rows[1][4] == 0.098   # 260 raw
        assert rows[1][6] == 0.044   # 320 raw

    def test_export_writes_a_readable_file(self):
        path = export_results(
            tmp_path_for("results.xlsx"),
            self.make_results(),
            sample_names={"B2": "tubo 1"},
            metadata={"Reader serial": "254717"},
        )
        assert path.exists()
        with zipfile.ZipFile(path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
            ElementTree.fromstring(sheet)
        assert "tubo 1" in sheet
        assert "254717" in sheet


class TestTwoSheetExport:
    def make_results(self):
        blank = RawWell("B3", {260: 0.053, 280: 0.049, 320: 0.044})
        wells = [
            RawWell("C2", {260: 0.058, 280: 0.053, 320: 0.044}),
            RawWell("D2", {260: 0.087, 280: 0.073, 320: 0.056}),
        ]
        return [(1, quantify(w, blank)) for w in wells]

    def test_workbook_has_both_sheets(self):
        path = export_results(
            tmp_path_for("two_sheets.xlsx"),
            self.make_results(),
            sample_names={"C2": "APP 1a", "D2": "SA 1a"},
        )
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            workbook = z.read("xl/workbook.xml").decode()
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names
        assert "Resumen" in workbook and "Detalle" in workbook

    def test_both_sheets_are_valid_xml(self):
        path = export_results(tmp_path_for("two_valid.xlsx"), self.make_results())
        with zipfile.ZipFile(path) as z:
            for part in ("xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml",
                         "xl/workbook.xml", "[Content_Types].xml",
                         "xl/_rels/workbook.xml.rels"):
                ElementTree.fromstring(z.read(part))

    def test_summary_carries_the_sample_name(self):
        from epoch_open.xlsx import results_to_summary

        rows = results_to_summary(self.make_results(), {"C2": "APP 1a"})
        assert rows[0][0] == "Muestra"
        assert rows[1][0] == "APP 1a"
        assert rows[1][1] == "C2"

    def test_summary_and_detail_cover_the_same_wells(self):
        from epoch_open.xlsx import results_to_summary

        results = self.make_results()
        summary = results_to_summary(results)
        detail = results_to_rows(results)
        assert len(summary) == len(detail)


class TestOptionalNaming:
    def results(self):
        blank = RawWell("B3", {260: 0.053, 280: 0.049, 320: 0.044})
        return [quantify(RawWell("C2", {260: 0.058, 280: 0.053, 320: 0.044}), blank)]

    def test_unnamed_sample_falls_back_to_its_well(self):
        from epoch_open.xlsx import results_to_summary

        rows = results_to_summary(self.results())
        assert rows[1][0] == "C2"

    def test_a_name_replaces_the_well_in_the_summary(self):
        from epoch_open.xlsx import results_to_summary

        rows = results_to_summary(self.results(), {"C2": "APP 1a"})
        assert rows[1][0] == "APP 1a"

    def test_the_well_is_always_kept_in_its_own_column(self):
        from epoch_open.xlsx import results_to_summary

        rows = results_to_summary(self.results(), {"C2": "APP 1a"})
        assert rows[1][1] == "C2"


class TestExcelCompatibility:
    """Parts Excel expects. LibreOffice opens files without them; Excel may show
    a 'we found a problem with some content' repair dialog instead."""

    REQUIRED = [
        "[Content_Types].xml", "_rels/.rels",
        "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml",
        "docProps/core.xml", "docProps/app.xml",
        "xl/worksheets/sheet1.xml",
    ]

    def make(self, name):
        blank = RawWell("A3", {260: 0.053, 280: 0.050, 320: 0.045})
        wells = [RawWell("A2", {260: 0.497, 280: 0.287, 320: 0.042})]
        return export_results(tmp_path_for(name), [(1, quantify(w, blank)) for w in wells])

    def test_every_expected_part_is_present(self):
        path = self.make("excel_parts.xlsx")
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        for part in self.REQUIRED:
            assert part in names, part

    def test_all_parts_are_valid_xml(self):
        path = self.make("excel_xml.xlsx")
        with zipfile.ZipFile(path) as z:
            for part in z.namelist():
                if part.endswith(".xml") or part.endswith(".rels"):
                    ElementTree.fromstring(z.read(part))

    def test_worksheet_declares_its_dimension(self):
        path = self.make("excel_dim.xlsx")
        with zipfile.ZipFile(path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
        assert "<dimension ref=" in sheet
        assert "<sheetViews>" in sheet

    def test_content_types_covers_every_part(self):
        path = self.make("excel_ct.xlsx")
        with zipfile.ZipFile(path) as z:
            content_types = z.read("[Content_Types].xml").decode()
            names = z.namelist()
        for part in names:
            if part in ("[Content_Types].xml",) or part.endswith(".rels"):
                continue
            assert f'PartName="/{part}"' in content_types, part

    def test_every_relationship_target_exists(self):
        path = self.make("excel_rels.xlsx")
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            for rels_part, base in (("_rels/.rels", ""), ("xl/_rels/workbook.xml.rels", "xl/")):
                root = ElementTree.fromstring(z.read(rels_part))
                for rel in root:
                    target = rel.get("Target")
                    assert (base + target) in names, f"{rels_part} -> {target}"


class TestProvenance:
    """A result file must say which build produced it. Without this, a number
    questioned years later cannot be traced to the software that made it."""

    def test_the_package_has_a_version(self):
        from epoch_open import __version__

        assert __version__
        assert __version__[0].isdigit()

    def test_metadata_reaches_the_summary_sheet(self):
        from epoch_open import __version__

        blank = RawWell("A3", {260: 0.053, 280: 0.050, 320: 0.045})
        results = [(1, quantify(RawWell("A2", {260: 0.497, 280: 0.287, 320: 0.042}),
                                blank))]
        path = export_results(
            tmp_path_for("prov.xlsx"), results,
            metadata={"Programa": f"epoch-open {__version__}", "Firmware": "1.12"},
        )
        with zipfile.ZipFile(path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
        assert __version__ in sheet
        assert "1.12" in sheet
