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

from . import i18n

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


# What the workbook calls things, per language.
#
# The English is Gen5's own vocabulary wherever Gen5 has a word for the thing
# -- "Standard", "Known concentration", "Blank", "Reference wavelength" --
# read off its help files and its exported result tables. Someone who has
# used the instrument's own software should not have to learn a second set of
# names for the same quantities, and someone comparing the two files side by
# side should be able to line the columns up by eye.
#
# The detail sheet's own headers are deliberately *not* in here: they already
# copy Gen5's export exactly ("Sample Read#", "Location", "260 Raw") in both
# languages, which is what makes that sheet recognisable.
_EN_TEXT = {
    "sheet_summary": "Summary",
    "sheet_detail": "Detail",
    "sheet_curve": "Curve",

    "summary_headers": ["Sample", "Well", "Read", "Conc.", "Unit",
                        "260/280", "260/230", "Notes"],
    "curve_summary_headers": ["Read", "Sample", "Well", "nm", "Ref. nm",
                              "Absorbance", "Concentration", "Unit",
                              "In range", "Notes"],
    "curve_fit_headers": ["Well", "Known concentration", "Absorbance",
                          "Residual"],
    "detail_headers": ["Read", "Well", "Role"],

    "read_on": "Read on",
    "in_range_yes": "yes",
    "in_range_no": "NO",
    "role_standard": "standard",
    "role_sample": "sample",

    "curve_at": "Curve at {nm} nm",
    "curve_plain": "Curve",
    "fit": "Fit",
    "fit_formula": "absorbance = slope x concentration + intercept",
    "slope": "Slope",
    "intercept": "Intercept",
    "r2": "r2",
    "worst_residual": "Worst residual",
    "standards": "Standards",
    "unit": "Unit",
    "measurable_range": "Measurable range (absorbance)",
    "status": "Status",
    "usable": "USABLE",
    "not_usable": "NOT USABLE",
    "curve_note": "Curve note",
    "r2_at": "r2 of the curve at {nm} nm",
    "r2_plain": "r2 of the curve",
    "no_curve_label": "Curve",
    "no_curve": "none: absorbance read directly",
    "wavelengths_read": "Wavelengths read",
}

_ES_TEXT = {
    "sheet_summary": "Resumen",
    "sheet_detail": "Detalle",
    "sheet_curve": "Curva",

    "summary_headers": ["Muestra", "Pozo", "Lectura", "Conc.", "Unidad",
                        "260/280", "260/230", "Aviso"],
    "curve_summary_headers": ["Lectura", "Muestra", "Pozo", "nm", "Ref. nm",
                              "Absorbancia", "Concentracion", "Unidad",
                              "En rango", "Aviso"],
    "curve_fit_headers": ["Pozo", "Concentracion patron", "Absorbancia",
                          "Residual"],
    "detail_headers": ["Lectura", "Pozo", "Rol"],

    "read_on": "Leido el",
    "in_range_yes": "si",
    "in_range_no": "NO",
    "role_standard": "patron",
    "role_sample": "muestra",

    "curve_at": "Curva a {nm} nm",
    "curve_plain": "Curva",
    "fit": "Ajuste",
    "fit_formula": "absorbancia = pendiente x concentracion + intercepto",
    "slope": "Pendiente",
    "intercept": "Intercepto",
    "r2": "r2",
    "worst_residual": "Peor residual",
    "standards": "Patrones",
    "unit": "Unidad",
    "measurable_range": "Rango medible (absorbancia)",
    "status": "Estado",
    "usable": "UTILIZABLE",
    "not_usable": "NO UTILIZABLE",
    "curve_note": "Aviso de la curva",
    "r2_at": "r2 de la curva a {nm} nm",
    "r2_plain": "r2 de la curva",
    "no_curve_label": "Curva",
    "no_curve": "ninguna: lectura directa en absorbancia",
    "wavelengths_read": "Longitudes de onda leidas",
}

TEXT_BY_LANGUAGE = {"en": _EN_TEXT, "es": _ES_TEXT}

TEXT = i18n.register({}, TEXT_BY_LANGUAGE)


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

    rows = [list(TEXT["summary_headers"])]
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
    summary.append([TEXT["read_on"],
                    datetime.now().strftime("%Y-%m-%d %H:%M")])
    for key, value in (metadata or {}).items():
        summary.append([key, value])

    detail = results_to_rows(results, sample_names)

    return write_workbook(
        path,
        [
            (TEXT["sheet_summary"], summary, SUMMARY_WIDTHS),
            (TEXT["sheet_detail"], detail, WIDTHS),
        ],
    )


# ---------------------------------------------------------------------------
# Colorimetric standard-curve assays (epoch_open/curve.py).
#
# A different workbook from the Take3 one, because a different thing has to be
# auditable. On the Take3 side the calculation is physics and the inputs are
# the plate's pathlengths, so the detail sheet carries the raw absorbances. In
# a curve assay the calculation *is* the curve, so the standards and the fit
# have to travel with the results: a concentration read off an unrecorded
# curve cannot be checked by anybody later, including the person who measured
# it.

CURVE_SUMMARY_WIDTHS = [8, 24, 7, 7, 9, 13, 14, 10, 10, 46]

CURVE_FIT_WIDTHS = [10, 22, 13, 12]


def curve_to_summary(results, unit: str) -> list[list]:
    """The samples, one row each, named if they were named.

    A well read without a usable curve has an absorbance and no
    concentration, and the cell is left empty rather than filled with a zero
    that would read as a measurement.
    """
    rows = [list(TEXT["curve_summary_headers"])]
    for result in results:
        quantified = result.concentration is not None
        rows.append([
            result.read_number or "",
            result.name or result.well,
            result.well,
            result.wavelength,
            result.reference_nm if result.reference_nm else "",
            round(result.absorbance, 4),
            round(result.concentration, 3) if quantified else "",
            unit if quantified else "",
            (TEXT["in_range_yes"] if result.in_range
             else TEXT["in_range_no"]) if quantified else "",
            "  ".join(str(n) for n in result.notes),
        ])
    return rows


def curve_to_fit_sheet(fits) -> list[list]:
    """Every curve in the run, one block each.

    Takes a mapping of wavelength to fit, or a single fit for the simple
    case. A run can hold a curve per wavelength -- the standards are
    measured at all of them -- and a sheet that recorded only one would
    leave the others' concentrations unauditable.
    """
    if fits is None:
        return []
    if not isinstance(fits, dict):
        fits = {getattr(fits, "wavelength", 0): fits}

    rows = []
    for nm, fit in sorted(fits.items()):
        if rows:
            rows.append([])
        if len(fits) > 1 or nm:
            rows.append([TEXT["curve_at"].format(nm=nm) if nm
                         else TEXT["curve_plain"]])
        rows.extend(_one_fit_sheet(fit))
    return rows


def _one_fit_sheet(fit) -> list[list]:
    """The standards, their residuals, and the line they produced.

    The fit's own misgivings are written out in full rather than summarised as
    a pass mark. A reader six months from now needs to know not just that the
    curve was accepted but what it was accepted in spite of.
    """
    rows = [list(TEXT["curve_fit_headers"])]
    for standard in fit.standards:
        rows.append([
            standard.well,
            standard.concentration,
            round(standard.absorbance, 4),
            round(fit.residual(standard), 5),
        ])

    rows.append([])
    rows.append([TEXT["fit"], TEXT["fit_formula"]])
    rows.append([TEXT["slope"], round(fit.slope, 6)])
    rows.append([TEXT["intercept"], round(fit.intercept, 6)])
    rows.append([TEXT["r2"], round(fit.r_squared, 6)])
    rows.append([TEXT["worst_residual"], round(fit.worst_residual(), 5)])
    rows.append([TEXT["standards"], fit.n])
    rows.append([TEXT["unit"], fit.unit])
    rows.append([TEXT["measurable_range"],
                 f"{fit.bottom:.4f} - {fit.top:.4f}"])
    rows.append([TEXT["status"],
                 TEXT["usable"] if fit.usable else TEXT["not_usable"]])
    for note in fit.notes:
        rows.append([TEXT["curve_note"], str(note)])
    return rows


def wavelengths_used(results, fallback=()) -> list[int]:
    """Every wavelength any reading in the batch was taken at.

    A batch is not one read. Taking the last read's settings as the batch's
    is what made the old workbook claim 530 nm over rows measured at 490.
    """
    seen = set()
    for result in results:
        seen.update(result.raw)
    return sorted(seen) or sorted(fallback)


def curve_to_detail(results, fit, wavelengths) -> list[list]:
    """Every well that was read, raw, with nothing subtracted.

    Including the standards, so the whole plate can be reconstructed from this
    sheet alone without trusting any of the arithmetic above it.
    """
    # Every wavelength anything in this batch was read at, not just the
    # last read's.
    wavelengths = wavelengths_used(results, wavelengths)
    rows = [list(TEXT["detail_headers"])
            + [f"{nm} nm" for nm in wavelengths]]
    for standard in (fit.standards if fit is not None else ()):
        rows.append(["", standard.well, TEXT["role_standard"]]
                    + [""] * len(wavelengths))
    for result in results:
        rows.append(
            [result.read_number or "", result.well, TEXT["role_sample"]]
            + [round(result.raw.get(nm), 4) if nm in result.raw else ""
               for nm in wavelengths]
        )
    return rows


def export_curve(path, results, fits, wavelengths,
                 metadata: dict | None = None, unit: str = ""):
    """Write what the run produced.

    Three sheets when there was a curve, two when there was not: a plain
    plate read has absorbances and no curve to record, and a Curva sheet
    describing nothing would be worse than its absence.
    """
    # One fit, a mapping of them, or none at all.
    if fits is not None and not isinstance(fits, dict):
        fits = {0: fits}
    primary = next(iter(fits.values())) if fits else None

    summary = curve_to_summary(results, primary.unit if primary else unit)

    summary.append([])
    summary.append([TEXT["read_on"],
                    datetime.now().strftime("%Y-%m-%d %H:%M")])
    if fits:
        for nm, fit in sorted(fits.items()):
            label = (TEXT["r2_at"].format(nm=nm) if nm else TEXT["r2_plain"])
            summary.append([label, round(fit.r_squared, 6)])
        summary.append([TEXT["standards"], primary.n])
    else:
        summary.append([TEXT["no_curve_label"], TEXT["no_curve"]])

    # Named here as a summary of the batch, never as a setting that applies
    # to every row: the per-row columns are what say how each was measured.
    used = wavelengths_used(results, wavelengths)
    summary.append([
        TEXT["wavelengths_read"],
        ", ".join(f"{nm} nm" for nm in used) if used else "-",
    ])
    for key, value in (metadata or {}).items():
        summary.append([key, value])

    sheets = [(TEXT["sheet_summary"], summary, CURVE_SUMMARY_WIDTHS)]
    if fits:
        sheets.append((TEXT["sheet_curve"], curve_to_fit_sheet(fits),
                       CURVE_FIT_WIDTHS))
    sheets.append(
        (TEXT["sheet_detail"],
         curve_to_detail(results, primary, wavelengths), None))
    return write_workbook(path, sheets)
