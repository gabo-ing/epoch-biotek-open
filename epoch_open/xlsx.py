"""Minimal xlsx writer.

Gen5 exports xlsx, so this software does too: whatever the technician does with the
file afterwards stays exactly the same. An .xlsx is a zip of XML parts, and writing the
handful we need by hand keeps the program free of third-party packages -- which matters
because it has to bundle into one self-contained .exe.

Scope is deliberately small: one sheet, a header row, strings and numbers, sensible
column widths. No formulas, styles beyond bold headers, or multiple sheets.
"""

import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
{sheet_overrides}
</Types>"""

SHEET_OVERRIDE = (
    '<Override PartName="/xl/worksheets/sheet{n}.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
)

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

# Excel opens files without these, but it is markedly happier with them, and a
# "we found a problem with some content" dialog in front of a technician would
# undo a lot of goodwill.
CORE_PROPS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:creator>epoch-open</dc:creator>
<cp:lastModifiedBy>epoch-open</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>"""

APP_PROPS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>epoch-open</Application>
</Properties>"""

WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>{sheets}</sheets>
</workbook>"""

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{sheet_rels}
<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# Two cell formats: 0 = plain, 1 = bold (used for the header row).
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="1"><fill><patternFill patternType="none"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf/></cellStyleXfs>
<cellXfs count="2"><xf xfId="0"/><xf xfId="0" fontId="1" applyFont="1"/></cellXfs>
</styleSheet>"""


def column_letter(index: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    if index < 1:
        raise ValueError("column index is 1-based")
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _cell(ref: str, value, bold: bool = False) -> str:
    style = ' s="1"' if bold else ""

    if value is None or value == "":
        return f'<c r="{ref}"{style}/>'

    if isinstance(value, bool):
        # Before the int check: bool is a subclass of int.
        return f'<c r="{ref}"{style} t="inlineStr"><is><t>{"TRUE" if value else "FALSE"}</t></is></c>'

    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{style}><v>{value!r}</v></c>'

    text = escape(str(value))
    # xml:space keeps leading/trailing spaces from being eaten.
    return f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet_xml(rows: list[list], widths: list[int] | None) -> str:
    # Excel uses <dimension> to size the sheet before parsing the rows.
    height = len(rows)
    width = max((len(r) for r in rows), default=1) or 1
    span = f"A1:{column_letter(width)}{max(height, 1)}"

    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        f'<dimension ref="{span}"/>',
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>',
        '<sheetFormatPr defaultRowHeight="15"/>',
    ]

    if widths:
        parts.append("<cols>")
        for i, width in enumerate(widths, start=1):
            parts.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
        parts.append("</cols>")

    parts.append("<sheetData>")
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{column_letter(col)}{row_index}", value, bold=(row_index == 1))
            for col, value in enumerate(row, start=1)
        )
        parts.append(f'<row r="{row_index}">{cells}</row>')
    parts.append("</sheetData></worksheet>")

    return "".join(parts)


def _safe_sheet_name(name: str, fallback: str) -> str:
    """Sheet names cannot contain []:*?/\\ and cap at 31 characters."""
    cleaned = "".join(c for c in name if c not in r"[]:*?/\\") [:31]
    return cleaned or fallback


def write_xlsx(
    path: str | Path,
    rows: list[list],
    sheet_name: str = "Results",
    widths: list[int] | None = None,
) -> Path:
    """Write one sheet. Row one is treated as a bold header."""
    return write_workbook(path, [(sheet_name, rows, widths)])


def write_workbook(path: str | Path, sheets: list[tuple]) -> Path:
    """Write several sheets: a list of (name, rows, widths) tuples.

    Gen5 puts a readable summary first and the per-well detail second, so anyone
    opening the file lands on the sheet meant for people.
    """
    path = Path(path)
    if not sheets:
        raise ValueError("refusing to write a workbook with no sheets")
    if all(not rows for _name, rows, _widths in sheets):
        raise ValueError("refusing to write an empty workbook")

    names = [
        _safe_sheet_name(name, f"Sheet{i}")
        for i, (name, _rows, _widths) in enumerate(sheets, start=1)
    ]

    sheet_tags = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(names, start=1)
    )
    rel_tags = "".join(
        '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>'
        % (i, i)
        for i in range(1, len(sheets) + 1)
    )
    overrides = "".join(SHEET_OVERRIDE.format(n=i) for i in range(1, len(sheets) + 1))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES.format(sheet_overrides=overrides))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", WORKBOOK.format(sheets=sheet_tags))
        z.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS.format(sheet_rels=rel_tags))
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("docProps/core.xml", CORE_PROPS.format(
            created=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")))
        z.writestr("docProps/app.xml", APP_PROPS)
        for i, (_name, rows, widths) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows, widths))

    return path


# Columns follow Gen5's own Take3 export, so the sheet looks familiar, with a
# sample-name column and the notes this software adds.
HEADERS = [
    "Sample Read#", "Location", "Sample", "Type",
    "260 Raw", "280 Raw", "320 Raw",
    "260", "280", "260/280", "260/230",
    "Conc.", "Unit", "Notes",
]
WIDTHS = [12, 10, 22, 9, 9, 9, 9, 9, 9, 9, 9, 10, 8, 46]


def results_to_rows(results, sample_names: dict | None = None) -> list[list]:
    """Turn QuantResult objects into spreadsheet rows.

    `results` is a flat sequence of (read_number, QuantResult) pairs, or plain
    QuantResults, which are all treated as read 1.
    """
    sample_names = sample_names or {}

    def rounded(value, digits):
        return round(value, digits) if value is not None else ""

    rows = [list(HEADERS)]
    for item in results:
        read_number, r = item if isinstance(item, tuple) else (1, item)
        rows.append([
            read_number,
            r.well,
            sample_names.get(r.well, ""),
            r.sample_type,
            rounded(r.raw.get(260), 4),
            rounded(r.raw.get(r.secondary_nm), 4),
            rounded(r.raw.get(320), 4),
            rounded(r.a260, 4),
            rounded(r.a_secondary, 4),
            rounded(r.ratio_260_280, 3),
            rounded(r.ratio_260_230, 3),
            rounded(r.concentration, 3),
            r.unit,
            " ".join(w.message for w in r.warnings),
        ])
    return rows


SUMMARY_HEADERS = [
    "Muestra", "Pozo", "Lectura", "Conc.", "Unidad", "260/280", "260/230", "Aviso",
]
SUMMARY_WIDTHS = [26, 8, 9, 11, 9, 10, 10, 50]


def results_to_summary(results, sample_names: dict | None = None) -> list[list]:
    """The sheet meant for people: one line per sample, named.

    Gen5's own summary is a matrix of plate rows against columns, which is why it
    has to be hand-labelled afterwards to be readable. Since this software knows
    each sample's name at read time, a flat named list says the same thing without
    anyone editing it later.
    """
    sample_names = sample_names or {}

    def rounded(value, digits):
        return round(value, digits) if value is not None else ""

    rows = [list(SUMMARY_HEADERS)]
    for item in results:
        read_number, r = item if isinstance(item, tuple) else (1, item)
        # Naming is optional. An unnamed sample falls back to its well, so the
        # column is never blank -- which is what Gen5 leaves behind for the user
        # to retype by hand.
        rows.append([
            sample_names.get(r.well) or r.well,
            r.well,
            read_number,
            rounded(r.concentration, 2),
            r.unit,
            rounded(r.ratio_260_280, 2),
            rounded(r.ratio_260_230, 2),
            " ".join(w.message for w in r.warnings),
        ])
    return rows


def export_results(path, results, sample_names=None, metadata: dict | None = None) -> Path:
    """Write both sheets: the named summary first, the per-well detail second."""
    summary = results_to_summary(results, sample_names)

    summary.append([])
    summary.append(["Leido el", datetime.now().strftime("%Y-%m-%d %H:%M")])
    for key, value in (metadata or {}).items():
        summary.append([key, value])

    detail = results_to_rows(results, sample_names)

    return write_workbook(
        path,
        [
            ("Resumen", summary, SUMMARY_WIDTHS),
            ("Detalle", detail, WIDTHS),
        ],
    )
