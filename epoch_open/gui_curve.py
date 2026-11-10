"""Epoch Multispectral -- colorimetric assays read against a standard curve.

The second of the two programs in this project. The first, epoch-take3, reads
nucleic acids off a Take3 micro-volume plate and turns absorbance into
concentration with physics. This one reads an ordinary transparent plate at
whatever wavelength the assay calls for, and turns absorbance into
concentration by interpolating a curve measured on the same plate.

Written for the Salkowski assay for indole-3-acetic acid at 530 nm, but
nothing on the screen is specific to it: the wavelength, the unit and the
standards are typed in, so Bradford at 595, MTT at 570 or an ELISA at 405 are
the same three steps with different numbers.

It deliberately looks like its sibling -- same palette, same drawn buttons,
same window behaviour, all from epoch_open/ui.py -- because it is the same
instrument on the same bench in front of the same person. What differs is
only what genuinely differs: one plate grid instead of two, because a 96-well
plate holds the blank, the standards and the samples side by side; and a
panel for the curve, which is the thing that can be wrong here.

The Take3 plate must never be used for this. Salkowski reagent is ferric
chloride in strong acid; it would ruin the quartz micro-spots the other
program depends on, and the plate holds 2 uL where this assay needs ~200. The
warning is on the screen rather than only in the documentation, because that
is where it will be read.
"""

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, config, curve, i18n, launch
from .curve import CurveError, MOST_WAVELENGTHS
from .reader import EpochReader, MockCurveReader, ReaderError
from .ui import (ACTION, ACTION_HOVER, ACTION_IDLE, ACTION_IDLE_HOVER,
                 ACTION_IDLE_INK, ACTION_INK, ACTION_OFF, ACTION_OFF_INK,
                 BAD, BAD_WELL, BAD_WELL_INK, BAD_WELL_LINE, CANVAS, EMPTY,
                 GOOD, GOOD_BADGE, GOOD_BADGE_INK, INK, LINE, MUTED, PANEL,
                 STATUS_BAR, TITLE_BAR, TITLE_INK, TITLE_MUTED, WARN_BADGE,
                 WARN_BADGE_INK, WARN_INK, WARN_ROW, WELL_HOVER, WELL_INK,
                 WELL_LINE, ZEBRA, LanguageDialog, RoundedButton, ScreenFit,
                 enable_dpi_awareness)
from .xlsx import export_curve

ROWS = "ABCDEFGH"
COLUMNS = tuple(range(1, 13))

# The three things a well can be. Spanish, because these are labels.
BLANK, STANDARD, SAMPLE = "blanco", "patron", "muestra"

# The English, in Gen5's vocabulary: "Standard", "Known concentration",
# "Reference wavelength", "Read Step", "Standard Curve". The one place it
# departs is the Take3 warning, which is Gabo's own sentence and says what
# happens rather than why -- that is the part that makes somebody put the
# plate down.
_EN_TEXT = {
    "meta_blank": "Blank absorbance",
    "meta_blank_none": "none",
    "meta_reader": "Reader",
    "meta_simulated": "SIMULATED - not real measurements",
    "decimal": ".",
    "language_button": "Language / Idioma...",
    "results": "Results",
    "title": "Epoch Multispectral",
    "subtitle": "Colorimetric assays against a standard curve",
    "simulated": ("SIMULATION MODE - no reader connected. These numbers are "
                  "NOT real measurements."),
    "connected": "Reader {model}, serial {serial}, firmware {firmware}, on {port}",
    "no_reader": "Switch the reader on to measure. Looking for it...",
    "no_reader_hint": ("The reader is not connected. Switch it on and wait a "
                       "few seconds: the program finds it by itself."),
    "lost": "THE READER IS NOT ANSWERING - check it is still on.",

    "take3_warning": ("Do NOT use the Take3 plate for this kind of "
                      "measurement. The plate could be damaged beyond "
                      "repair. Use clear plastic plates only"),

    "plate": "96-well plate",
    "roles": "What I am marking:",
    "role_blanco": "Blank",
    "role_patron": "Standard",
    "role_muestra": "Sample",
    "role_hint": ("Click a well to mark it. Double click a standard for its "
                  "concentration, a sample for its name."),

    "settings": "Read",
    "wavelength": "Wavelengths:",
    "wavelength_change": "Change...",
    "wl_title": "Wavelengths",
    "wl_help": ("The same choices Gen5 offers in its Read Step. The reader "
                "takes up to {most} per read, counting the reference, and "
                "measures them all in a single pass."),
    "wl_count": "How many:",
    "wl_ref_group": "Reference",
    "wl_save": "OK",
    "wl_cancel": "Cancel",
    "wl_primary": ("The first one is used for the standard curve. The others "
                   "are measured and recorded, but a curve describes a single "
                   "wavelength."),
    "wl_bad": ("{value} is not a valid wavelength. The Epoch reads between "
               "200 and 999 nm, in whole numbers."),
    "wl_repeated": "Wavelength {value} is repeated.",
    "wl_ref_clash": ("The reference ({value} nm) is also one of the measured "
                     "wavelengths. Choose another, or drop the reference."),
    "wavelength_hint": ("Up to {most}, comma separated. The first is the one\n"
                        "used for the curve; the rest are read and kept too."),
    "use_reference": "Subtract reference",
    "unit": "Unit:",
    "reference_hint": ("The reference corrects for turbidity and marks on the "
                       "bottom of the well. If you use it, it is applied to "
                       "the standards too."),

    "read_blank": "1.  Read blank",
    "read_standards": "2.  Read standards",
    "read_samples": "3.  Read samples",
    "end_batch": "4.  End batch  (save Excel)",
    "scan": "Find peak",
    "clear": "Clear all",

    "curve": "Standard curve",
    "curve_none": "No curve yet",
    "curve_field_n": "Standards:",
    "curve_field_slope": "Slope:",
    "curve_field_r2": "r2:",
    "curve_field_resid": "Worst residual:",
    "curve_field_range": "Range (abs):",
    "curve_field_state": "Status:",
    "curve_usable": "USABLE",
    "curve_unusable": "NOT USABLE",
    "curve_unread": "NOT READ",
    "curve_others": ("The curve shown is the one at {primary} nm. There are "
                     "also curves at {others} nm, and each sample is computed "
                     "against its own."),

    "columns": ("Sample", "Read:Well", "nm", "Abs.", "Conc.", "Notes"),

    "reading": "Reading... do not open the lid.",
    "blank_done": "Blank read at {time}: mean absorbance {abs:.4f}.",
    "standards_done": "Curve fitted on {n} standards, r2 = {r2:.4f}.",
    "samples_done": "Read {read}: {n} samples. Batch total: {total}.",
    "scan_done": ("Peak at {nm} nm. If that is not the value you have set, "
                  "change it before fitting the curve."),
    "scan_edge": ("Peak at {nm} nm, which is the edge of the scan: the real "
                  "maximum may lie beyond it. Check the colour by eye."),

    "no_blank_wells": "Mark at least one well as blank first.",
    "no_standard_wells": ("Mark at least {n} wells as standards and give each "
                          "one its concentration (double click)."),
    "no_concentrations": ("Concentrations are missing on these standards: "
                          "{wells}. Double click each one to type it in."),
    "no_sample_wells": "Mark the sample wells.",
    "no_blank_yet": "The blank has to be read first.",
    "no_curve_yet": "The standards have to be read first.",
    "curve_not_usable": ("This curve cannot be used to measure:\n\n{reason}"
                         "\n\nCorrect it before reading samples."),
    "nothing_to_scan": "Mark a well with colour in it to find the peak.",
    "nothing_to_save": "The batch is empty; there is nothing to save yet.",
    "saved": "Saved to {path}. Batch closed.",
    "save_error": "The file could not be saved:\n\n{error}",
    "read_error": "The read failed:\n\n{error}",
    "bad_wavelength": ("'{value}' is not valid. Enter between 1 and {most} "
                       "wavelengths, comma separated, each between 200 and "
                       "999 nm.\nFor example: 490, 530, 590"),
    "too_many_wavelengths": ("That is {count} wavelengths, and the reader "
                             "takes {most} per read, counting the reference."),
    "conc_prompt": "Concentration of the standard in {well} ({unit}):",
    "conc_title": "Standard concentration",
    "name_prompt": "Name of the sample in {well}:",
    "name_title": "Sample name",

    "next_mark_blank": "Mark the reagent blank wells.",
    "next_empty_plate": ("Mark sample wells to read absorbance, or start with "
                         "the blank if you want concentrations."),
    "next_read_blank": "Now press '1. Read blank'.",
    "next_mark_standards": ("Mark at least {need} wells as standards (you "
                            "have {have}), or read the samples as they are "
                            "for absorbance only."),
    "next_plain_read": ("Mark sample wells and press '3. Read samples' to "
                        "read absorbance. For concentrations, mark at least "
                        "{need} standards first."),
    "next_concentrations": ("Double click each standard to type its "
                            "concentration. Missing: {wells}."),
    "next_read_standards": "Now press '2. Read standards'.",
    "next_curve_bad": "The curve is not usable yet. See the note on the right.",
    "next_mark_samples": "Mark the sample wells.",
    "next_read_samples": "Now press '3. Read samples'.",
    "next_save": "When you are done, press '4. End batch' to save.",
    "next_no_reader": "Switch the reader on to measure.",
    "next_bad_wavelength": ("Check the wavelength: it has to be between 200 "
                            "and 999."),

    "instructions": ("Reagent blank -> standards with their concentrations "
                     "-> samples -> end batch."),
}

_ES_TEXT = {
    "meta_blank": "Absorbancia del blanco",
    "meta_blank_none": "ninguno",
    "meta_reader": "Lector",
    "meta_simulated": "SIMULADO - no son medidas reales",
    "decimal": ",",
    "language_button": "Idioma / Language...",
    "results": "Resultados",
    "title": "Epoch Multispectral",
    "subtitle": "Ensayos colorimetricos con curva de calibrado",
    "simulated": ("MODO SIMULACION - no hay lector conectado. Los numeros NO "
                  "son medidas reales."),
    "connected": "Lector {model}, serie {serial}, firmware {firmware}, en {port}",
    "no_reader": "Enciende el lector para poder medir. Buscandolo...",
    "no_reader_hint": ("El lector no esta conectado. Enciendelo y espera unos "
                       "segundos: el programa lo detecta solo."),
    "lost": "EL LECTOR NO RESPONDE - comprueba que sigue encendido.",

    # Gabo's wording, verbatim. It says what happens rather than why the
    # chemistry causes it, which is the part that makes someone put the plate
    # down. Accented, unlike most of the text here: that was habit rather than
    # a constraint, and the interface already carries non-ASCII elsewhere.
    "take3_warning": ("NO uses la placa Take3 para este tipo de mediciones. "
                      "La placa podría dañarse de forma irreversible. "
                      "Utiliza sólo placas de plástico transparentes"),

    "plate": "Placa de 96 pozos",
    "roles": "Que estoy marcando:",
    "role_blanco": "Blanco",
    "role_patron": "Patron",
    "role_muestra": "Muestra",
    "role_hint": ("Pulsa un pozo para marcarlo. Doble clic en un patron para "
                  "su concentracion, en una muestra para su nombre."),

    "settings": "Lectura",
    "wavelength": "Longitudes de onda:",
    "wavelength_change": "Cambiar...",
    "wl_title": "Longitudes de onda",
    "wl_help": ("Las mismas opciones que Gen5 ofrece en su Read Step. El "
                "lector admite hasta {most} por lectura, contando la "
                "referencia, y las lee todas en una sola pasada."),
    "wl_count": "Cuantas:",
    "wl_ref_group": "Referencia",
    "wl_save": "Aceptar",
    "wl_cancel": "Cancelar",
    "wl_primary": ("La primera es la que se usa para la curva de calibrado. "
                   "Las demas se miden y se guardan, pero una curva describe "
                   "una sola longitud de onda."),
    "wl_bad": ("{value} no vale como longitud de onda. El Epoch lee entre "
               "200 y 999 nm, en numeros enteros."),
    "wl_repeated": "La longitud de onda {value} esta repetida.",
    "wl_ref_clash": ("La referencia ({value} nm) es tambien una de las "
                     "longitudes medidas. Elige otra, o quita la referencia."),
    "wavelength_hint": ("Hasta {most}, separadas por comas. La primera es la que\n"
                        "se usa para la curva; las demas se leen y se guardan igual."),
    "use_reference": "Restar referencia",
    "unit": "Unidad:",
    "reference_hint": ("La referencia corrige turbidez y marcas en el fondo "
                       "del pozo. Si la usas, se aplica tambien a los patrones."),

    "read_blank": "1.  Leer blanco",
    "read_standards": "2.  Leer patrones",
    "read_samples": "3.  Leer muestras",
    "end_batch": "4.  Fin del lote  (guardar Excel)",
    "scan": "Buscar pico",
    "clear": "Limpiar todo",

    "curve": "Curva de calibrado",
    "curve_none": "Sin curva todavia",
    "curve_field_n": "Patrones:",
    "curve_field_slope": "Pendiente:",
    "curve_field_r2": "r2:",
    "curve_field_resid": "Peor residual:",
    "curve_field_range": "Rango (abs):",
    "curve_field_state": "Estado:",
    "curve_usable": "UTILIZABLE",
    "curve_unusable": "NO UTILIZABLE",
    "curve_unread": "SIN LEER",
    "curve_others": ("Se muestra la curva de {primary} nm. Tambien hay curva "
                     "a {others} nm, y cada muestra se calcula con la suya."),

    # "Lectura:Pozo" rather than the well alone, as epoch-take3 does: a batch
    # can hold the same well read twice, and two rows reading A1 with nothing
    # to tell them apart is the screen's version of the bug the workbook had.
    "columns": ("Muestra", "Lectura:Pozo", "nm", "Abs.", "Conc.", "Aviso"),

    "reading": "Leyendo... no abras la tapa.",
    "blank_done": "Blanco leido a las {time}: {abs:.4f} de absorbancia media.",
    "standards_done": "Curva ajustada con {n} patrones, r2 = {r2:.4f}.",
    "samples_done": "Lectura {read}: {n} muestras. Total en el lote: {total}.",
    "scan_done": ("Pico en {nm} nm. Si no es el valor que tienes puesto, "
                  "cambialo antes de ajustar la curva."),
    "scan_edge": ("Pico en {nm} nm, que es el extremo del barrido: el maximo "
                  "real puede estar mas alla. Comprueba el color a ojo."),

    "no_blank_wells": "Marca primero algun pozo como blanco.",
    "no_standard_wells": ("Marca al menos {n} pozos como patron y ponle a cada "
                          "uno su concentracion (doble clic)."),
    "no_concentrations": ("Faltan concentraciones en los patrones: {wells}. "
                          "Doble clic en cada uno para escribirla."),
    "no_sample_wells": "Marca los pozos de muestra.",
    "no_blank_yet": "Primero hay que leer el blanco.",
    "no_curve_yet": "Primero hay que leer los patrones.",
    "curve_not_usable": ("La curva no sirve para medir:\n\n{reason}\n\n"
                         "Arreglala antes de leer muestras."),
    "nothing_to_scan": "Marca algun pozo con color para buscar el pico.",
    "nothing_to_save": "El lote esta vacio; todavia no hay nada que guardar.",
    "saved": "Guardado en {path}. Lote cerrado.",
    "save_error": "No se pudo guardar el archivo:\n\n{error}",
    "read_error": "No se pudo leer:\n\n{error}",
    "bad_wavelength": ("'{value}' no vale. Escribe entre 1 y {most} longitudes "
                       "de onda separadas por comas, cada una entre 200 y 999 nm.\n"
                       "Ejemplo: 490, 530, 590"),
    "too_many_wavelengths": ("Son {count} longitudes de onda y el lector "
                             "admite {most} por lectura, contando la "
                             "referencia."),
    "conc_prompt": "Concentracion del patron en {well} ({unit}):",
    "conc_title": "Concentracion del patron",
    "name_prompt": "Nombre de la muestra en {well}:",
    "name_title": "Nombre de muestra",

    # What is standing between her and the next read. The buttons grey
    # themselves out correctly and say nothing about why, which is the worst
    # of both: a refusal with no reason. Gabo read a blank, found every other
    # button still dead, and asked what was wrong -- nothing was.
    "next_mark_blank": "Marca los pozos del blanco de reactivo.",
    # The opening line, with nothing marked at all. It has to offer both
    # paths: this module is a spectrophotometer that can also build a curve,
    # not a curve tool that refuses to read.
    "next_empty_plate": ("Marca pozos de muestra para leer absorbancia, o "
                         "empieza por el blanco si quieres concentraciones."),
    "next_read_blank": "Ahora pulsa '1. Leer blanco'.",
    "next_mark_standards": ("Marca al menos {need} pozos como patron "
                            "(llevas {have}), o lee las muestras tal cual "
                            "para obtener solo absorbancia."),
    "next_plain_read": ("Marca pozos de muestra y pulsa '3. Leer muestras' "
                        "para leer absorbancia. Para concentraciones, marca "
                        "antes al menos {need} patrones."),
    "next_concentrations": ("Doble clic en cada patron para escribir su "
                            "concentracion. Faltan: {wells}."),
    "next_read_standards": "Ahora pulsa '2. Leer patrones'.",
    "next_curve_bad": "La curva no sirve todavia. Mira el aviso de la derecha.",
    "next_mark_samples": "Marca los pozos de muestra.",
    "next_read_samples": "Ahora pulsa '3. Leer muestras'.",
    "next_save": "Cuando termines, pulsa '4. Fin del lote' para guardar.",
    "next_no_reader": "Enciende el lector para poder medir.",
    "next_bad_wavelength": "Revisa la longitud de onda: tiene que estar entre 200 y 999.",

    "instructions": ("Blanco de reactivo -> patrones con su concentracion -> "
                     "muestras -> fin del lote."),
}

TEXT_BY_LANGUAGE = {"en": _EN_TEXT, "es": _ES_TEXT}

TEXT = i18n.register({}, TEXT_BY_LANGUAGE)

# Role colours. One hue per role so the plate can be read at a glance, with
# the paler shade meaning "marked, not measured yet" and the stronger one
# "measured". Built on the shared palette rather than beside it: the chrome,
# the greens and the reds all come from ui.py, and only these three role hues
# are this program's own, because the other program has no roles.
ROLE_PENDING = {
    BLANK:    ("#cfe0f5", "#1d3a5f"),      # pale blue
    STANDARD: ("#f0e3fb", "#4c1d95"),      # pale violet
    SAMPLE:   ("#d6f0da", "#14532d"),      # pale green
}
ROLE_DONE = {
    BLANK:    ("#9dbce8", "#102844"),
    STANDARD: ("#d3b8ee", "#3b0764"),
    SAMPLE:   ("#43a047", "#ffffff"),
}

CONFIG = config.load()

# Settle the language before any window exists: a widget copies its text when
# it is built, so this has to happen first. A command-line --lang wins over
# the configuration file, which is the escape hatch for somebody who cannot
# read the dialog that would let them change it.
i18n.set_language(launch.language_override() or CONFIG.language)
READER_SERIAL = CONFIG.reader_serial


class App(ScreenFit, tk.Tk):
    """The whole program. One window, four steps, in order."""

    def __init__(self, backend=None):
        super().__init__()
        self.title(f'{TEXT["title"]}  {__version__}')
        self._size_to_screen()

        self.backend = backend
        self.simulated = isinstance(backend, MockCurveReader)
        self.lost = False
        self._port_lock = threading.Lock()

        # What is marked where, and what has been measured.
        self.roles: dict[str, str] = {}
        self.concentrations: dict[str, float] = {}
        self.names: dict[str, str] = {}
        self.wells: dict[str, RoundedButton] = {}

        # One blank per wavelength. A blank read at 490 nm says nothing
        # about 530, and subtracting it there would be inventing a
        # correction rather than applying one.
        self.blank_values: dict[int, float] = {}
        self.blank_time: datetime | None = None
        # A curve per wavelength. The standards are measured at every
        # wavelength the read asks for, so fitting only one threw away
        # readings the instrument had already taken.
        self.fits: dict = {}
        self.results: list = []
        self.read_number = 0

        self.nm = tk.StringVar(value=str(curve.DEFAULT_NM))
        self.use_reference = tk.BooleanVar(value=False)
        self.reference_nm = tk.StringVar(value=str(curve.DEFAULT_REFERENCE_NM))
        self.unit = tk.StringVar(value=curve.DEFAULT_UNIT)
        self.role = tk.StringVar(value=BLANK)

        self._style()
        self._draw()
        # Checked against the screen only once the state is on it: a warning
        # or a status line can widen the layout after it is built, and the
        # fit has to judge what she will actually see.
        self._fit_to_screen(self._draw)

        if os.environ.get("EPOCH_GUI_TOPMOST") == "1":
            self.attributes("-topmost", True)
            self.geometry("+0+0")
            self.lift()

    # ------------------------------------------------------------- building

    def _draw(self) -> None:
        """Build the screen and put the current state on it.

        One call, because _fit_to_screen may run it again after stepping
        down a tier, and a rebuilt screen with no state on it would show
        a blank plate and empty fields.
        """
        self._build()
        self._refresh_state()

    def _build(self) -> None:
        # Cleared because _fit_to_screen may call this a second time, having
        # destroyed everything the first pass made.
        self.wells = {}
        self.role_buttons = {}
        self.action_buttons = {}
        self._build_banner()

        # Before the body, so the packer cannot squeeze it off the window when
        # the layout is taller than the screen. See ui.ScreenFit and
        # tests/test_gui_fit.py -- this went wrong once already.
        self.status = tk.Label(
            self, text=TEXT["instructions"], anchor="w", justify="left",
            bg=STATUS_BAR, fg=MUTED, padx=16, pady=5 if self.compact else 8,
            font=(self.ui_font, self.base_pt - 1),
        )
        self.status.pack(fill="x", side="bottom")

        body = ttk.Frame(self, padding=4 if self.tiny else 8)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 10))
        self._build_settings(left)
        self._build_plate(left)
        self._build_buttons(left)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self._build_curve(right)
        self._build_results(right)

    def _build_banner(self) -> None:
        bar = tk.Frame(self, bg=TITLE_BAR)
        bar.pack(fill="x")
        tk.Label(bar, text=TEXT["title"], bg=TITLE_BAR, fg=TITLE_INK,
                 font=(self.ui_font, self.base_pt + 4, "bold"), padx=16,
                 pady=4 if self.tiny else (7 if self.compact else 12),
                 ).pack(side="left")
        tk.Label(bar, text=__version__, bg=TITLE_BAR, fg=TITLE_MUTED,
                 font=(self.ui_font, self.base_pt - 1)).pack(
            side="left", pady=(6, 0))
        if not self.tiny:
            tk.Label(bar, text=TEXT["subtitle"], bg=TITLE_BAR, fg=TITLE_MUTED,
                     font=(self.ui_font, self.base_pt - 1), padx=12).pack(
                side="left", pady=(6, 0))

        self.banner = tk.Label(bar, padx=14, pady=7,
                               font=(self.ui_font, self.base_pt, "bold"))
        self.banner.pack(side="right", padx=14, pady=3 if self.tiny else 8)
        self._refresh_banner()

    def _refresh_banner(self) -> None:
        """The one place that says whether the numbers are real."""
        if self.backend is None:
            text, bg, fg = TEXT["no_reader"], BAD, "#ffffff"
        elif self.simulated:
            text, bg, fg = TEXT["simulated"], WARN_BADGE, WARN_BADGE_INK
        elif self.lost:
            text, bg, fg = TEXT["lost"], BAD, "#ffffff"
        else:
            info = self.backend.info
            text = TEXT["connected"].format(
                model=info.model, serial=info.serial,
                firmware=info.firmware, port=info.port)
            bg, fg = GOOD_BADGE, GOOD_BADGE_INK
        self.banner.configure(text=text, bg=bg, fg=fg)

    def _build_settings(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text=TEXT["settings"],
                               padding=5 if self.tiny else 8,
                               style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text=TEXT["wavelength"], style="Card.TLabel").pack(side="left")
        self.wavelength_label = ttk.Label(
            row, text="", style="Card.TLabel",
            font=(self.ui_font, self.base_pt, "bold"))
        self.wavelength_label.pack(side="left", padx=(6, 0))
        ttk.Button(row, text=TEXT["wavelength_change"],
                   command=self._choose_wavelengths).pack(side="left", padx=8)

        unit_row = ttk.Frame(frame, style="Card.TFrame")
        unit_row.pack(fill="x", pady=(6, 0))
        ttk.Label(unit_row, text=TEXT["unit"], style="Card.TLabel").pack(side="left")
        ttk.Entry(unit_row, textvariable=self.unit, width=8).pack(side="left",
                                                                  padx=6)
        ttk.Button(unit_row, text=TEXT["language_button"],
                   command=self._choose_language).pack(side="right")

        # The one thing in this program that can damage the other one.
        # Wrapped wider and padded less on a short screen: the warning has to
        # stay, but three bold lines in a tall box is 59 px that the save
        # button needs more.
        tk.Label(frame, text=TEXT["take3_warning"], bg=BAD_WELL, fg=BAD_WELL_INK,
                 wraplength=self.px(400 if self.tiny else 340),
                 justify="left", padx=8, pady=3 if self.tiny else 6,
                 font=(self.ui_font, self.base_pt - 1, "bold"),
                 ).pack(fill="x", pady=(4 if self.tiny else 8, 0))

    def _build_plate(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text=TEXT["plate"],
                               padding=4 if self.compact else 8,
                               style="Card.TLabelframe")
        frame.pack(fill="x")

        roles = ttk.Frame(frame, style="Card.TFrame")
        roles.pack(fill="x", pady=(0, 3 if self.tiny else 6))
        ttk.Label(roles, text=TEXT["roles"], style="CardMuted.TLabel").pack(
            side="left", padx=(0, 8))
        self.role_buttons = {}
        for role in (BLANK, STANDARD, SAMPLE):
            button = RoundedButton(
                roles, text=TEXT[f"role_{role}"], width=self.px(78),
                height=self.px(22 if self.compact else 26), radius=self.px(4),
                parent_bg=PANEL, font=(self.ui_font, self.base_pt - 1, "bold"),
                command=lambda r=role: self._choose_role(r),
            )
            button.pack(side="left", padx=2)
            self.role_buttons[role] = button

        grid = ttk.Frame(frame, style="Card.TFrame")
        grid.pack()

        well_w = self.px(34 if self.compact else 40)
        well_h = self.px(15 if self.tiny else (20 if self.compact else 24))

        for index, column in enumerate(COLUMNS):
            ttk.Label(grid, text=str(column), width=4, anchor="center",
                      style="CardMuted.TLabel").grid(row=0, column=index + 1)
        for row_index, letter in enumerate(ROWS):
            ttk.Label(grid, text=letter, width=2, anchor="e",
                      style="CardMuted.TLabel").grid(
                row=row_index + 1, column=0, padx=(0, 4))
            for index, column in enumerate(COLUMNS):
                name = f"{letter}{column}"
                button = RoundedButton(
                    grid, text="", width=well_w, height=well_h,
                    radius=self.px(3), bg=EMPTY, fg=WELL_INK,
                    outline=WELL_LINE, hover=WELL_HOVER, parent_bg=PANEL,
                    font=(self.ui_font, max(6, self.base_pt - 3)),
                    command=lambda n=name: self._click_well(n),
                )
                button.grid(row=row_index + 1, column=index + 1, padx=1, pady=1)
                button.bind("<Double-Button-1>",
                            lambda _e, n=name: self._edit_well(n))
                self.wells[name] = button

        if not self.tiny:
            ttk.Label(frame, text=TEXT["role_hint"], style="CardMuted.TLabel",
                      wraplength=self.px(470)).pack(anchor="w", pady=(6, 0))

    def _build_buttons(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(8, 0))

        self.action_buttons = {}
        steps = (
            ("read_blank", self._read_blank),
            ("read_standards", self._read_standards),
            ("read_samples", self._read_samples),
            ("end_batch", self._end_batch),
        )
        for key, command in steps:
            button = RoundedButton(
                frame, text=TEXT[key], width=self.px(300),
                height=self.px(23 if self.tiny else
                               (26 if self.compact else 32)),
                radius=self.px(5), parent_bg=CANVAS, stretch=True,
                font=(self.ui_font, self.base_pt, "bold"),
                command=command,
            )
            button.pack(fill="x", pady=1 if self.tiny else 2)
            self.action_buttons[key] = button

        # Always says what is missing. Packed before the secondary buttons so
        # it sits directly under the numbered steps it is talking about.
        self.next_label = tk.Label(
            frame, text="", anchor="w", justify="left", bg=CANVAS, fg=ACTION,
            wraplength=self.px(420 if self.tiny else 300),
            font=(self.ui_font, self.base_pt, "bold"))
        self.next_label.pack(fill="x", pady=(3 if self.tiny else 6, 0))

        extras = ttk.Frame(frame)
        extras.pack(fill="x", pady=(2 if self.tiny else 4, 0))
        for key, command in (("scan", self._scan_peak), ("clear", self._clear)):
            button = RoundedButton(
                extras, text=TEXT[key], width=self.px(146),
                height=self.px(22 if self.compact else 26), radius=self.px(4),
                bg=ACTION_IDLE, fg=ACTION_IDLE_INK, hover=ACTION_IDLE_HOVER,
                parent_bg=CANVAS, font=(self.ui_font, self.base_pt - 1),
                command=command,
            )
            button.pack(side="left", padx=2)
            self.action_buttons[key] = button

    def _build_curve(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text=TEXT["curve"],
                               padding=5 if self.tiny else 8,
                               style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 4 if self.tiny else 8))

        self.curve_fields = {}
        grid = ttk.Frame(frame, style="Card.TFrame")
        grid.pack(anchor="w")
        fields = ("n", "slope", "r2", "resid", "range", "state")
        for index, key in enumerate(fields):
            row, column = divmod(index, 2)
            cell = ttk.Frame(grid, style="Card.TFrame")
            cell.grid(row=row, column=column, sticky="w", padx=(0, 22), pady=1)
            ttk.Label(cell, text=TEXT[f"curve_field_{key}"],
                      style="CardMuted.TLabel").pack(side="left")
            value = ttk.Label(cell, text="-", style="Card.TLabel",
                              font=(self.ui_font, self.base_pt, "bold"))
            value.pack(side="left", padx=(5, 0))
            self.curve_fields[key] = value

        self.curve_notes = tk.Label(
            frame, text="", bg=PANEL, fg=WARN_INK, anchor="w", justify="left",
            wraplength=self.px(560), font=(self.ui_font, self.base_pt - 1))
        self.curve_notes.pack(fill="x", pady=(6, 0))

    def _build_results(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text=TEXT["results"], padding=8,
                               style="Card.TLabelframe")
        frame.pack(fill="both", expand=True)

        self.table = ttk.Treeview(frame, columns=TEXT["columns"],
                                  show="headings", height=8)
        numeric = {"Abs.", "Conc.", "nm"}
        widths = [self.px(w) for w in (130, 85, 50, 75, 85, 200)]
        for column, width in zip(TEXT["columns"], widths):
            anchor = "e" if column in numeric else "w"
            self.table.heading(column, text=column, anchor=anchor)
            self.table.column(column, width=width, anchor=anchor,
                              stretch=(column == TEXT["columns"][-1]),
                              minwidth=self.px(50))

        scrollbar = ttk.Scrollbar(frame, orient="vertical",
                                  command=self.table.yview,
                                  style="Dark.Vertical.TScrollbar")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.tag_configure("odd", background=ZEBRA)
        self.table.tag_configure("even", background=PANEL)
        self.table.tag_configure("warn", background=WARN_ROW, foreground=WARN_INK)

    # ---------------------------------------------------------------- wells

    def _choose_role(self, role: str) -> None:
        self.role.set(role)
        self._refresh_state()

    def _click_well(self, name: str) -> None:
        """Assign the role being marked, or clear the well if it already has it.

        Clicking a well that holds a different role moves it rather than
        refusing, because the common mistake is marking a row as samples when
        it should have been standards, and the fix should be one click.
        """
        wanted = self.role.get()
        previous = self.roles.get(name)
        if previous == wanted:
            self.roles.pop(name, None)
            self.concentrations.pop(name, None)
            self.names.pop(name, None)
        else:
            self.roles[name] = wanted

        # Only the blank and the standards can invalidate a curve. Marking a
        # sample cannot: the curve was measured from other wells and still
        # describes them.
        #
        # This threw the curve away on every click, which made the program's
        # own three steps impossible to walk in order -- fit the curve, mark
        # the samples it was fitted for, and the curve is gone. Every
        # automated test marked its samples before reading anything, which is
        # the one order that hides it. Gabo found it in about a minute of
        # clicking.
        if STANDARD in (previous, wanted) or BLANK in (previous, wanted):
            self._invalidate()
        self._refresh_state()

    def _edit_well(self, name: str) -> None:
        """Double click: a concentration for a standard, a name for a sample."""
        role = self.roles.get(name)
        if role == STANDARD:
            answer = simpledialog.askfloat(
                TEXT["conc_title"],
                TEXT["conc_prompt"].format(well=name, unit=self.unit.get()),
                initialvalue=self.concentrations.get(name),
                minvalue=0.0, parent=self,
            )
            if answer is not None:
                self.concentrations[name] = answer
                self._invalidate()
        elif role == SAMPLE:
            answer = simpledialog.askstring(
                TEXT["name_title"], TEXT["name_prompt"].format(well=name),
                initialvalue=self.names.get(name, ""), parent=self)
            if answer is not None:
                self.names[name] = answer.strip()
        self._refresh_state()

    def _wells_for(self, role: str) -> list[str]:
        return sorted(
            (w for w, r in self.roles.items() if r == role),
            key=lambda w: (int(w[1:]), w[0]),
        )

    def _invalidate(self) -> None:
        """Changing the plate throws away a curve measured on the old one.

        Keeping it would let a sample be read against standards that are no
        longer marked, which is the quiet kind of wrong this program exists to
        avoid.
        """
        self.fits = {}

    @property
    def fit(self):
        """The curve a concentration is read against: the primary one.

        A property, so the panel, the step gates and the export keep asking
        for "the" curve while the rest stay reachable through `fits`.
        """
        return self.fits.get(self._primary())

    def _clear(self) -> None:
        self.roles.clear()
        self.concentrations.clear()
        self.names.clear()
        self.blank_values = {}
        self.blank_time = None
        self.fits = {}
        self._refresh_state()

    # ---------------------------------------------------------------- state

    def _parse_nm(self, value: str) -> int | None:
        try:
            nm = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return nm if 200 <= nm <= 999 else None

    def _measured(self) -> list[int] | None:
        """The wavelengths to measure, in the order she wrote them.

        Several, because the instrument takes up to six in one pass and Gen5
        offers exactly that. The first is the one a curve is built and read
        against; the rest are measured and recorded beside it, which is the
        whole point of asking for them.
        """
        text = self.nm.get().replace(";", ",").replace(" ", ",")
        wanted = []
        for part in (p for p in text.split(",") if p):
            nm = self._parse_nm(part)
            if nm is None:
                return None
            if nm not in wanted:
                wanted.append(nm)
        return wanted or None

    def _wavelengths(self) -> list[int] | None:
        """Everything this read asks the instrument for, reference included."""
        wanted = self._measured()
        if wanted is None:
            return None
        if self.use_reference.get():
            typed = self._parse_nm(self.reference_nm.get())
            if typed is None:
                return None
            if typed not in wanted:
                wanted = wanted + [typed]
        if len(wanted) > MOST_WAVELENGTHS:
            return None
        return wanted

    def _reference_nm(self) -> int | None:
        if not self.use_reference.get():
            return None
        reference = self._parse_nm(self.reference_nm.get())
        return None if reference in (self._measured() or []) else reference

    def _primary(self) -> int | None:
        """The wavelength a curve is built and read against."""
        measured = self._measured()
        return measured[0] if measured else None

    def _blank_at(self, nm: int) -> float:
        """The blank for one wavelength, or zero where none was read."""
        return self.blank_values.get(nm, 0.0)

    def _choose_language(self) -> None:
        """Change the language, and say that it starts next time.

        Written to the configuration rather than applied to the running
        window: every widget on screen copied its text when it was built.
        """
        dialog = LanguageDialog(self, CONFIG.language, i18n.LANGUAGES)
        self.wait_window(dialog)
        if dialog.result is None or dialog.result == CONFIG.language:
            return
        CONFIG.language = dialog.result
        try:
            config.save(CONFIG)
        except OSError as exc:
            messagebox.showerror(TEXT["title"], str(exc))
            return
        self._say(LanguageDialog.NOTE.splitlines()[
            0 if dialog.result == "en" else 1])

    def _choose_wavelengths(self) -> None:
        """Open the read settings, and apply them if she accepts.

        Changing what is read invalidates a curve: it was measured at one
        wavelength with one reference, and both can change here.
        """
        dialog = WavelengthsDialog(
            self, self._measured() or [curve.DEFAULT_NM],
            self.use_reference.get(),
            self._parse_nm(self.reference_nm.get()) or curve.DEFAULT_REFERENCE_NM)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        measured, use_reference, reference = dialog.result
        self.nm.set(", ".join(str(nm) for nm in measured))
        self.use_reference.set(use_reference)
        if reference is not None:
            self.reference_nm.set(str(reference))
        self._invalidate()
        self._refresh_state()

    def _summarise_wavelengths(self) -> str:
        measured = self._measured() or []
        if not measured:
            return "-"
        shown = ", ".join(str(nm) for nm in measured) + " nm"
        reference = self._reference_nm()
        return f"{shown}  (ref. {reference})" if reference else shown

    def _reference_toggled(self) -> None:
        # The reference is subtracted from the standards as well, so turning it
        # on or off after fitting changes what the curve means.
        self._invalidate()
        self._refresh_state()

    def _missing_concentrations(self) -> list[str]:
        return [w for w in self._wells_for(STANDARD)
                if w not in self.concentrations]

    def _can_read(self) -> bool:
        return (self.backend is not None and not self.lost
                and self._wavelengths() is not None)

    def _can_fit(self) -> bool:
        standards = self._wells_for(STANDARD)
        return (bool(self.blank_values)
                and len(standards) >= curve.MIN_STANDARDS
                and not self._missing_concentrations())

    def _curve_ok(self) -> bool:
        return self.fit is not None and self.fit.usable

    def _refresh_state(self) -> None:
        self._refresh_banner()
        self._refresh_roles()
        self._refresh_wells()
        self._refresh_curve()
        self._refresh_actions()
        self.next_label.configure(text=self._next_step())
        self.wavelength_label.configure(text=self._summarise_wavelengths())

    def _refresh_roles(self) -> None:
        for role, button in self.role_buttons.items():
            chosen = self.role.get() == role
            button.configure(
                bg=ACTION if chosen else ACTION_IDLE,
                fg=ACTION_INK if chosen else ACTION_IDLE_INK,
                hover=ACTION_HOVER if chosen else ACTION_IDLE_HOVER,
            )

    def _refresh_wells(self) -> None:
        divergent = set()
        if self.fit is not None:
            divergent = {n.well for n in self.fit.notes if n.well}

        for name, button in self.wells.items():
            role = self.roles.get(name)
            if role is None:
                button.configure(bg=EMPTY, fg=WELL_INK, outline=WELL_LINE,
                                 hover=WELL_HOVER, text="")
                continue

            if name in divergent:
                fill, ink, outline = BAD_WELL, BAD_WELL_INK, BAD_WELL_LINE
            else:
                measured = (
                    (role == BLANK and bool(self.blank_values))
                    or (role == STANDARD and self.fit is not None)
                    or (role == SAMPLE and any(r.well == name
                                               for r in self.results))
                )
                table = ROLE_DONE if measured else ROLE_PENDING
                fill, ink = table[role]
                outline = fill

            label = ""
            if role == STANDARD:
                value = self.concentrations.get(name)
                label = f"{value:g}" if value is not None else "?"
            button.configure(bg=fill, fg=ink, outline=outline, hover=fill,
                             text=label)

    def _refresh_curve(self) -> None:
        fields = self.curve_fields
        if self.fit is None:
            for value in fields.values():
                value.configure(text="-", style="Card.TLabel")
            fields["state"].configure(text=TEXT["curve_unread"])
            self.curve_notes.configure(text="")
            return

        fit = self.fit
        fields["n"].configure(text=str(fit.n))
        fields["slope"].configure(
            text=f"{fit.slope:.5f}".replace(".", TEXT["decimal"]))
        fields["r2"].configure(text=f"{fit.r_squared:.4f}".replace(".", TEXT["decimal"]))
        fields["resid"].configure(
            text=f"{fit.worst_residual():.4f}".replace(".", TEXT["decimal"]))
        fields["range"].configure(
            text=f"{fit.bottom:.3f} - {fit.top:.3f}".replace(".", TEXT["decimal"]))
        fields["state"].configure(
            text=TEXT["curve_usable"] if fit.usable else TEXT["curve_unusable"],
            style="CardGood.TLabel" if fit.usable else "CardBad.TLabel")
        notes = [str(n) for n in fit.notes]
        others = [nm for nm in sorted(self.fits) if nm != self._primary()]
        if others:
            notes.insert(0, TEXT["curve_others"].format(
                primary=self._primary(),
                others=", ".join(str(nm) for nm in others)))
        self.curve_notes.configure(text="\n".join(notes))

    def _refresh_actions(self) -> None:
        can_read = self._can_read()
        enabled = {
            "read_blank": can_read and bool(self._wells_for(BLANK)),
            "read_standards": can_read and self._can_fit(),
            # No curve required. Without one this reads absorbances, which
            # is what the instrument does and what Gen5 offers before any
            # data reduction is set up. A concentration still needs a usable
            # curve; that check is in curve.read_against.
            "read_samples": can_read and bool(self._wells_for(SAMPLE)),
            "end_batch": bool(self.results),
            "scan": can_read,
            "clear": True,
        }

        # Which step is the obvious next one, so exactly one button is the
        # bright one and the order does not have to be remembered.
        nxt = None
        if can_read:
            if not self.blank_values:
                nxt = "read_blank"
            elif not self._curve_ok():
                nxt = "read_standards"
            elif self.results:
                # Something has been measured, so saving it is the next thing
                # that matters. Reading another plate into the same batch is
                # still one press away -- the button stays enabled, just not
                # the bright one.
                nxt = "end_batch"
            elif self._wells_for(SAMPLE):
                nxt = "read_samples"

        for key, button in self.action_buttons.items():
            if key in ("scan", "clear"):
                button.configure(state="normal" if enabled[key] else "disabled")
                continue
            if not enabled[key]:
                button.configure(state="disabled", bg=ACTION_OFF,
                                 fg=ACTION_OFF_INK, hover=None)
            elif key == nxt:
                button.configure(state="normal", bg=ACTION, fg=ACTION_INK,
                                 hover=ACTION_HOVER)
            else:
                button.configure(state="normal", bg=ACTION_IDLE,
                                 fg=ACTION_IDLE_INK, hover=ACTION_IDLE_HOVER)

    def _next_step(self) -> str:
        """The one thing standing between her and the next read.

        Written as a single sentence naming an action, in the order the steps
        actually unlock, so the answer to "why is that button dead" is always
        on screen rather than inferable from which buttons are dead.
        """
        if self.backend is None or self.lost:
            return TEXT["next_no_reader"]
        if self._wavelengths() is None:
            return TEXT["next_bad_wavelength"]

        # A sample marked and nothing else means she wants a plain read, and
        # that needs neither a blank nor standards. Saying so beats sending
        # her to fetch a curve she may not want.
        if (self._wells_for(SAMPLE) and not self._wells_for(STANDARD)
                and self.fit is None):
            if self.results:
                return TEXT["next_save"]
            return TEXT["next_read_samples"]

        if not self.blank_values:
            if not self.roles:
                return TEXT["next_empty_plate"]
            if not self._wells_for(BLANK):
                return TEXT["next_mark_blank"]
            return TEXT["next_read_blank"]

        standards = self._wells_for(STANDARD)
        if len(standards) < curve.MIN_STANDARDS:
            if not standards:
                return TEXT["next_plain_read"].format(
                    need=curve.MIN_STANDARDS)
            return TEXT["next_mark_standards"].format(
                need=curve.MIN_STANDARDS, have=len(standards))
        missing = self._missing_concentrations()
        if missing:
            return TEXT["next_concentrations"].format(
                wells=", ".join(missing))
        if self.fit is None:
            return TEXT["next_read_standards"]
        if not self.fit.usable:
            return TEXT["next_curve_bad"]

        if not self._wells_for(SAMPLE):
            if self.results:
                return TEXT["next_save"]
            return TEXT["next_mark_samples"]
        if self.results:
            return TEXT["next_save"]
        return TEXT["next_read_samples"]

    def _busy(self) -> None:
        """Grey every action out for the duration of a read.

        A read blocks the event loop, so a second press does not go nowhere:
        it waits in the queue and fires the moment the first read returns.
        One intended press, two reads, and at a couple of minutes a plate
        that is not a small waste.

        Gloved fingers on a trackpad produce exactly that, which is how it
        was found -- a blank read twice from one press at the bench on
        5 November 2026, and once when the same button was pressed again
        bare-handed.

        Disabling swallows it: RoundedButton ignores a press unless its state
        is normal, so the queued click lands on a dead button and stops there.
        The states are restored by the _refresh_state that every read path
        ends with, including the failures.
        """
        for button in self.action_buttons.values():
            button.configure(state="disabled")
        self.update_idletasks()

    def _say(self, message: str) -> None:
        self.status.configure(text=message)
        self.update_idletasks()

    # -------------------------------------------------------------- reading

    def _read(self, wells: list[str], wavelengths: list[int]) -> dict:
        if self.backend is None:
            raise ReaderError(TEXT["no_reader_hint"])
        if self.simulated:
            self._invent_truth(wells)
        with self._port_lock:
            return self.backend.read_plate(wells, wavelengths)

    def _invent_truth(self, wells: list[str]) -> None:
        """Tell the simulator what it is pretending to hold.

        Simulation only. The standards get the concentrations that were typed
        in, so the fake curve is a real line through them; blanks get zero;
        samples get a plausible spread, with one deliberately off the top of
        the curve so the out-of-range warning can be seen without reagents.
        """
        import random

        truth = self.backend.truth
        for well in wells:
            role = self.roles.get(well)
            if role == STANDARD:
                truth[well] = self.concentrations.get(well, 0.0)
            elif role == BLANK:
                truth[well] = 0.0
            elif role == SAMPLE:
                top = max(self.concentrations.values(), default=40.0) or 40.0
                if well not in truth:
                    # Mostly inside the curve, the way a run that was diluted
                    # sensibly looks. Spreading them past the top standard
                    # filled the demo with out-of-range warnings and made a
                    # working program look like a failing one.
                    truth[well] = random.uniform(0.05, 0.92) * top

    def _failed(self, exc) -> None:
        self.lost = True
        messagebox.showerror(TEXT["title"],
                             TEXT["read_error"].format(error=exc))
        self._refresh_state()
        self._say(TEXT["instructions"])

    def _read_blank(self) -> None:
        wells = self._wells_for(BLANK)
        if not wells:
            messagebox.showinfo(TEXT["title"], TEXT["no_blank_wells"])
            return
        wavelengths = self._wavelengths()
        if wavelengths is None:
            measured = self._measured() or []
            if len(measured) > MOST_WAVELENGTHS or (
                    self.use_reference.get() and
                    len(measured) >= MOST_WAVELENGTHS):
                messagebox.showerror(TEXT["title"],
                                     TEXT["too_many_wavelengths"].format(
                                         count=len(measured),
                                         most=MOST_WAVELENGTHS))
            else:
                messagebox.showerror(
                    TEXT["title"],
                    TEXT["bad_wavelength"].format(value=self.nm.get(),
                                                  most=MOST_WAVELENGTHS))
            return

        self._say(TEXT["reading"])
        self._busy()
        try:
            raw = self._read(wells, wavelengths)
        except (ReaderError, CurveError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        reference = self._reference_nm()
        try:
            # A blank per wavelength. The reference, where one is used, is
            # subtracted inside each -- so the blank for 530 already has 650
            # taken off it, and a sample at 530 gets the same treatment.
            self.blank_values = {
                nm: curve.mean(curve.corrected(readings, nm, reference)
                               for readings in raw.values())
                for nm in (self._measured() or [])
            }
        except CurveError as exc:
            self._failed(exc)
            return

        self.blank_time = datetime.now()
        # A new blank invalidates a curve fitted against the old one.
        self._invalidate()
        self._refresh_state()
        self._say(TEXT["blank_done"].format(
            time=self.blank_time.strftime("%H:%M"),
            abs=self._blank_at(self._primary() or 0)))

    def _read_standards(self) -> None:
        wells = self._wells_for(STANDARD)
        if not self.blank_values:
            messagebox.showinfo(TEXT["title"], TEXT["no_blank_yet"])
            return
        if len(wells) < curve.MIN_STANDARDS:
            messagebox.showinfo(TEXT["title"], TEXT["no_standard_wells"].format(
                n=curve.MIN_STANDARDS))
            return
        missing = self._missing_concentrations()
        if missing:
            messagebox.showinfo(TEXT["title"], TEXT["no_concentrations"].format(
                wells=", ".join(missing)))
            return

        wavelengths = self._wavelengths()
        self._say(TEXT["reading"])
        self._busy()
        try:
            raw = self._read(wells, wavelengths)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        # The curve is built at the first wavelength only. Reading the
        # standards at others is fine and their values are kept, but a curve
        # describes one wavelength: a 530 nm calibration says nothing about
        # absorbance at 490.
        reference = self._reference_nm()
        try:
            # One set of standards per wavelength, each blanked with its own
            # blank. The instrument measured them all; fitting only the
            # first discarded the rest.
            by_nm = {
                nm: [
                    curve.Standard(
                        well=well,
                        concentration=self.concentrations[well],
                        absorbance=curve.corrected(raw[well], nm, reference)
                        - self._blank_at(nm),
                    )
                    for well in wells
                ]
                for nm in (self._measured() or [])
            }
            self.fits = {nm: curve.fit_standards(standards,
                                                 unit=self.unit.get())
                         for nm, standards in by_nm.items()}
        except CurveError as exc:
            self.fits = {}
            self._refresh_state()
            messagebox.showerror(TEXT["title"], str(exc))
            return

        self._refresh_state()
        if self.fit.usable:
            self._say(TEXT["standards_done"].format(
                n=self.fit.n, r2=self.fit.r_squared))
        else:
            self._say(" ".join(str(n) for n in self.fit.notes))

    def _read_samples(self) -> None:
        wells = self._wells_for(SAMPLE)
        if not wells:
            messagebox.showinfo(TEXT["title"], TEXT["no_sample_wells"])
            return

        wavelengths = self._wavelengths()
        self._say(TEXT["reading"])
        self._busy()
        try:
            raw = self._read(wells, wavelengths)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        measured = self._measured() or []
        primary, reference = self._primary(), self._reference_nm()
        self.read_number += 1
        try:
            # One row per well per wavelength. The curve applies to the
            # primary wavelength alone, so the others come back as
            # absorbance with no concentration -- which is what they are.
            fresh = [
                curve.read_against(
                    well, raw[well],
                    # Each wavelength against its own curve. Reading
                    # 490 nm off a 530 nm calibration would give a plausible
                    # number that means nothing.
                    self.fits.get(nm),
                    wavelength=nm,
                    reference_nm=reference,
                    # No blank read means nothing is subtracted, rather than
                    # nothing being read.
                    blank=self._blank_at(nm),
                    name=self.names.get(well, ""),
                    unit=self.unit.get(),
                )
                for well in wells
                for nm in measured
            ]
        except CurveError as exc:
            messagebox.showerror(TEXT["title"], str(exc))
            return

        for result in fresh:
            result.read_number = self.read_number
        self.results.extend(fresh)
        self._refresh_state()
        self._refresh_table()
        self._say(TEXT["samples_done"].format(
            read=self.read_number, n=len(fresh), total=len(self.results)))

    def _scan_peak(self) -> None:
        """Read a spread of visible wavelengths and say where the colour peaks.

        Costs one read: the reader takes nine wavelengths in a single pass, and
        the scan is exactly nine. Worth doing once per reagent batch instead of
        trusting a wavelength from a paper.
        """
        wells = self._wells_for(SAMPLE) or self._wells_for(STANDARD)
        if not wells:
            messagebox.showinfo(TEXT["title"], TEXT["nothing_to_scan"])
            return

        self._say(TEXT["reading"])
        self._busy()
        try:
            raw = self._read(wells, list(curve.SCAN_NM))
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        # Average the wells so one odd drop does not decide the answer.
        try:
            averaged = {nm: curve.mean(raw[w][nm] for w in wells
                                       if nm in raw[w])
                        for nm in curve.SCAN_NM}
            peak = curve.peak_wavelength(averaged)
        except CurveError as exc:
            self._failed(exc)
            return

        self._refresh_state()
        at_edge = peak in (curve.SCAN_NM[0], curve.SCAN_NM[-1])
        self._say((TEXT["scan_edge"] if at_edge else TEXT["scan_done"]).format(
            nm=peak))

    def _refresh_table(self) -> None:
        self.table.delete(*self.table.get_children())
        for index, result in enumerate(self.results):
            notes = "  ".join(n.short for n in result.notes)
            tag = "warn" if result.notes else ("odd" if index % 2 else "even")
            self.table.insert("", "end", tags=(tag,), values=(
                result.name or result.well,
                f"{result.read_number}:{result.well}" if result.read_number
                else result.well,
                result.wavelength,
                f"{result.absorbance:.4f}".replace(".", TEXT["decimal"]),
                ("-" if result.concentration is None
                 else f"{result.concentration:.2f}".replace(".", TEXT["decimal"])),
                notes,
            ))

    def _end_batch(self) -> None:
        if not self.results:
            messagebox.showinfo(TEXT["title"], TEXT["nothing_to_save"])
            return

        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".xlsx",
            initialfile=f"multispectral-{stamp}.xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        wavelengths = self._wavelengths() or [curve.DEFAULT_NM]
        try:
            written = export_curve(
                path, self.results, self.fits, wavelengths,
                unit=self.unit.get(),
                metadata={
                    # The wavelengths are per row, and summarised by
                    # export_curve from the readings themselves. Naming one
                    # here was how a batch read at 490 and then 530 came out
                    # of the file claiming 530 throughout.
                    TEXT["meta_blank"]: ", ".join(
                        f"{nm} nm: {value:.4f}"
                        for nm, value in sorted(self.blank_values.items())
                    ) or TEXT["meta_blank_none"],
                    TEXT["meta_reader"]: (TEXT["meta_simulated"]
                                          if self.simulated else
                                          getattr(self.backend, "info", None)
                                          and self.backend.info.serial),
                })
        except OSError as exc:
            messagebox.showerror(TEXT["title"],
                                 TEXT["save_error"].format(error=exc))
            return

        self.results = []
        self.read_number = 0
        self._refresh_table()
        self._refresh_state()
        self._say(TEXT["saved"].format(path=written))


class WavelengthsDialog(tk.Toplevel):
    """Choose what a read asks the instrument for.

    Laid out the way Gen5's Read Step dialog is -- a count, then that many
    boxes, then the reference -- because that is the screen this lab already
    knows for this decision, and because a comma-separated list in a text
    field is a worse version of the same thing: it has to be parsed, and it
    cannot show that six is the limit.

    The limit is the instrument's, or near enough: Gen5 offers one to six and
    stops. See curve.MOST_WAVELENGTHS.
    """

    def __init__(self, parent, measured, use_reference, reference_nm):
        super().__init__(parent)
        self.title(TEXT["wl_title"])
        self.transient(parent)
        self.resizable(False, False)
        self.configure(bg=CANVAS)
        self.result = None
        self.px = parent.px
        self.ui_font = parent.ui_font
        self.base_pt = parent.base_pt

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=TEXT["wl_help"].format(most=MOST_WAVELENGTHS),
                  wraplength=self.px(430),
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        box = ttk.LabelFrame(body, text=TEXT["wl_title"], padding=10,
                             style="Card.TLabelframe")
        box.pack(fill="x", pady=(0, 10))

        count_row = ttk.Frame(box, style="Card.TFrame")
        count_row.pack(fill="x", pady=(0, 8))
        ttk.Label(count_row, text=TEXT["wl_count"],
                  style="Card.TLabel").pack(side="left")
        self.count = tk.IntVar(value=max(1, min(len(measured),
                                                MOST_WAVELENGTHS)))
        for n in range(1, MOST_WAVELENGTHS + 1):
            ttk.Radiobutton(count_row, text=str(n), value=n,
                            variable=self.count, command=self._count_changed,
                            style="Card.TRadiobutton").pack(side="left",
                                                            padx=(8, 0))

        fields = ttk.Frame(box, style="Card.TFrame")
        fields.pack(fill="x")
        self.boxes = []
        self.values = []
        for index in range(MOST_WAVELENGTHS):
            cell = ttk.Frame(fields, style="Card.TFrame")
            cell.grid(row=0, column=index, padx=(0, 6))
            ttk.Label(cell, text=str(index + 1), style="CardMuted.TLabel").pack()
            value = tk.StringVar(
                value=str(measured[index]) if index < len(measured) else "")
            entry = ttk.Entry(cell, textvariable=value, width=6,
                              justify="center")
            entry.pack()
            self.values.append(value)
            self.boxes.append(entry)

        ttk.Label(box, text=TEXT["wl_primary"], wraplength=self.px(420),
                  style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))

        reference = ttk.LabelFrame(body, text=TEXT["wl_ref_group"],
                                   padding=10, style="Card.TLabelframe")
        reference.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(reference, style="Card.TFrame")
        row.pack(fill="x")
        self.use_reference = tk.BooleanVar(value=use_reference)
        ttk.Checkbutton(row, text=TEXT["use_reference"],
                        variable=self.use_reference,
                        style="Card.TCheckbutton").pack(side="left")
        self.reference = tk.StringVar(value=str(reference_nm))
        ttk.Entry(row, textvariable=self.reference, width=6).pack(side="left",
                                                                  padx=6)
        ttk.Label(reference, text=TEXT["reference_hint"],
                  wraplength=self.px(420),
                  style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        ttk.Button(buttons, text=TEXT["wl_cancel"],
                   command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text=TEXT["wl_save"],
                   command=self._save).pack(side="right")

        self._count_changed()
        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    def _count_changed(self) -> None:
        """Only the boxes in use are editable, as in Gen5's own dialog."""
        wanted = self.count.get()
        for index, entry in enumerate(self.boxes):
            entry.configure(state="normal" if index < wanted else "disabled")

    def _save(self) -> None:
        measured = []
        for index in range(self.count.get()):
            raw = self.values[index].get().strip()
            try:
                nm = int(raw)
            except ValueError:
                nm = -1
            if not 200 <= nm <= 999:
                messagebox.showerror(TEXT["wl_title"],
                                     TEXT["wl_bad"].format(value=raw or "''"),
                                     parent=self)
                return
            if nm in measured:
                messagebox.showerror(TEXT["wl_title"],
                                     TEXT["wl_repeated"].format(value=nm),
                                     parent=self)
                return
            measured.append(nm)

        reference = None
        if self.use_reference.get():
            raw = self.reference.get().strip()
            try:
                reference = int(raw)
            except ValueError:
                reference = -1
            if not 200 <= reference <= 999:
                messagebox.showerror(TEXT["wl_title"],
                                     TEXT["wl_bad"].format(value=raw or "''"),
                                     parent=self)
                return
            if reference in measured:
                messagebox.showerror(
                    TEXT["wl_title"],
                    TEXT["wl_ref_clash"].format(value=reference), parent=self)
                return
            if len(measured) + 1 > MOST_WAVELENGTHS:
                messagebox.showerror(
                    TEXT["wl_title"],
                    TEXT["too_many_wavelengths"].format(
                        count=len(measured) + 1, most=MOST_WAVELENGTHS),
                    parent=self)
                return

        self.result = (measured, self.use_reference.get(), reference)
        self.destroy()


def connect_backend(force_simulator: bool = False):
    """The real instrument, or None when it does not answer.

    Same policy as epoch-take3: without an instrument the program opens with
    reading disabled rather than quietly producing invented numbers. The
    simulator has to be asked for.
    """
    if force_simulator:
        return MockCurveReader()

    reader = EpochReader(expected_serial=READER_SERIAL)
    try:
        reader.connect()
        return reader
    except (ReaderError, NotImplementedError, OSError) as exc:
        print(f"No reader: {exc}\nReading is disabled until one is found.",
              file=sys.stderr)
        return None


def main() -> int:
    enable_dpi_awareness()          # before any Tk window exists
    simulate = "--simulate" in sys.argv
    app = App(connect_backend(force_simulator=simulate))
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
