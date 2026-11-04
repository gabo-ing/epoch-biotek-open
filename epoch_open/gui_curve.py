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

from . import __version__, config, curve
from .curve import CurveError
from .reader import EpochReader, MockCurveReader, ReaderError
from .ui import (ACTION, ACTION_HOVER, ACTION_IDLE, ACTION_IDLE_HOVER,
                 ACTION_IDLE_INK, ACTION_INK, ACTION_OFF, ACTION_OFF_INK,
                 BAD, BAD_WELL, BAD_WELL_INK, BAD_WELL_LINE, CANVAS, EMPTY,
                 GOOD, GOOD_BADGE, GOOD_BADGE_INK, INK, LINE, MUTED, PANEL,
                 STATUS_BAR, TITLE_BAR, TITLE_INK, TITLE_MUTED, WARN_BADGE,
                 WARN_BADGE_INK, WARN_INK, WARN_ROW, WELL_HOVER, WELL_INK,
                 WELL_LINE, ZEBRA, RoundedButton, ScreenFit,
                 enable_dpi_awareness)
from .xlsx import export_curve

ROWS = "ABCDEFGH"
COLUMNS = tuple(range(1, 13))

# The three things a well can be. Spanish, because these are labels.
BLANK, STANDARD, SAMPLE = "blanco", "patron", "muestra"

TEXT = {
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
    "wavelength": "Longitud de onda (nm):",
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

    "columns": ("Muestra", "Pozo", "Abs.", "Conc.", "Aviso"),

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
    "bad_wavelength": ("'{value}' no es una longitud de onda valida. El Epoch "
                       "lee entre 200 y 999 nm, en numeros enteros."),
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

        self.blank_value: float | None = None
        self.blank_time: datetime | None = None
        self.fit = None
        self.results: list = []
        self.read_number = 0

        self.nm = tk.StringVar(value=str(curve.DEFAULT_NM))
        self.use_reference = tk.BooleanVar(value=False)
        self.reference_nm = tk.StringVar(value=str(curve.DEFAULT_REFERENCE_NM))
        self.unit = tk.StringVar(value=curve.DEFAULT_UNIT)
        self.role = tk.StringVar(value=BLANK)

        self._style()
        self._build()
        self._refresh_state()
        self._shrink_to_content()

        if os.environ.get("EPOCH_GUI_TOPMOST") == "1":
            self.attributes("-topmost", True)
            self.geometry("+0+0")
            self.lift()

    # ------------------------------------------------------------- building

    def _build(self) -> None:
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
        entry = ttk.Entry(row, textvariable=self.nm, width=6)
        entry.pack(side="left", padx=6)
        entry.bind("<FocusOut>", lambda _e: self._refresh_state())
        entry.bind("<Return>", lambda _e: self._refresh_state())

        ttk.Label(row, text=TEXT["unit"], style="Card.TLabel").pack(
            side="left", padx=(14, 0))
        ttk.Entry(row, textvariable=self.unit, width=8).pack(side="left", padx=6)

        ref = ttk.Frame(frame, style="Card.TFrame")
        ref.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(ref, text=TEXT["use_reference"],
                        variable=self.use_reference,
                        command=self._reference_toggled,
                        style="Card.TCheckbutton").pack(side="left")
        self.reference_entry = ttk.Entry(ref, textvariable=self.reference_nm,
                                         width=6)
        self.reference_entry.pack(side="left", padx=6)

        if not self.tiny:
            ttk.Label(frame, text=TEXT["reference_hint"], style="CardMuted.TLabel",
                      wraplength=self.px(340)).pack(anchor="w", pady=(4, 0))

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
        frame = ttk.LabelFrame(parent, text="Resultados", padding=8,
                               style="Card.TLabelframe")
        frame.pack(fill="both", expand=True)

        self.table = ttk.Treeview(frame, columns=TEXT["columns"],
                                  show="headings", height=8)
        numeric = {"Abs.", "Conc."}
        widths = [self.px(w) for w in (150, 60, 80, 90, 240)]
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
        self.fit = None

    def _clear(self) -> None:
        self.roles.clear()
        self.concentrations.clear()
        self.names.clear()
        self.blank_value = None
        self.blank_time = None
        self.fit = None
        self._refresh_state()

    # ---------------------------------------------------------------- state

    def _parse_nm(self, value: str) -> int | None:
        try:
            nm = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return nm if 200 <= nm <= 999 else None

    def _wavelengths(self) -> list[int] | None:
        """Every wavelength this read needs, or None if the settings are wrong."""
        nm = self._parse_nm(self.nm.get())
        if nm is None:
            return None
        wanted = [nm]
        if self.use_reference.get():
            reference = self._parse_nm(self.reference_nm.get())
            if reference is None:
                return None
            if reference != nm:
                wanted.append(reference)
        return wanted

    def _reference_nm(self) -> int | None:
        if not self.use_reference.get():
            return None
        reference = self._parse_nm(self.reference_nm.get())
        nm = self._parse_nm(self.nm.get())
        return None if reference == nm else reference

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
        return (self.blank_value is not None
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
                    (role == BLANK and self.blank_value is not None)
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
            text=f"{fit.slope:.5f}".replace(".", ","))
        fields["r2"].configure(text=f"{fit.r_squared:.4f}".replace(".", ","))
        fields["resid"].configure(
            text=f"{fit.worst_residual():.4f}".replace(".", ","))
        fields["range"].configure(
            text=f"{fit.bottom:.3f} - {fit.top:.3f}".replace(".", ","))
        fields["state"].configure(
            text=TEXT["curve_usable"] if fit.usable else TEXT["curve_unusable"],
            style="CardGood.TLabel" if fit.usable else "CardBad.TLabel")
        self.curve_notes.configure(
            text="\n".join(str(n) for n in fit.notes))

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
            if self.blank_value is None:
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

        if self.blank_value is None:
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
            messagebox.showerror(
                TEXT["title"], TEXT["bad_wavelength"].format(value=self.nm.get()))
            return

        self._say(TEXT["reading"])
        try:
            raw = self._read(wells, wavelengths)
        except (ReaderError, CurveError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        nm, reference = wavelengths[0], self._reference_nm()
        try:
            self.blank_value = curve.mean(
                curve.corrected(readings, nm, reference)
                for readings in raw.values())
        except CurveError as exc:
            self._failed(exc)
            return

        self.blank_time = datetime.now()
        # A new blank invalidates a curve fitted against the old one.
        self._invalidate()
        self._refresh_state()
        self._say(TEXT["blank_done"].format(
            time=self.blank_time.strftime("%H:%M"), abs=self.blank_value))

    def _read_standards(self) -> None:
        wells = self._wells_for(STANDARD)
        if self.blank_value is None:
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
        try:
            raw = self._read(wells, wavelengths)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        nm, reference = wavelengths[0], self._reference_nm()
        try:
            standards = [
                curve.Standard(
                    well=well,
                    concentration=self.concentrations[well],
                    absorbance=curve.corrected(raw[well], nm, reference)
                    - self.blank_value,
                )
                for well in wells
            ]
            self.fit = curve.fit_standards(standards, unit=self.unit.get())
        except CurveError as exc:
            self.fit = None
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
        try:
            raw = self._read(wells, wavelengths)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._failed(exc)
            return

        nm, reference = wavelengths[0], self._reference_nm()
        self.read_number += 1
        try:
            fresh = [
                curve.read_against(
                    well, raw[well], self.fit, wavelength=nm,
                    reference_nm=reference,
                    # No blank read means nothing is subtracted, rather than
                    # nothing being read.
                    blank=self.blank_value or 0.0,
                    name=self.names.get(well, ""),
                    unit=self.unit.get(),
                )
                for well in wells
            ]
        except CurveError as exc:
            messagebox.showerror(TEXT["title"], str(exc))
            return

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
                result.well,
                f"{result.absorbance:.4f}".replace(".", ","),
                ("-" if result.concentration is None
                 else f"{result.concentration:.2f}".replace(".", ",")),
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
                path, self.results, self.fit, wavelengths,
                unit=self.unit.get(),
                metadata={
                    "Longitud de onda": f"{wavelengths[0]} nm",
                    "Referencia": (f"{self._reference_nm()} nm"
                                   if self._reference_nm() else "no"),
                    "Absorbancia del blanco": round(self.blank_value or 0.0, 4),
                    "Lector": ("SIMULADO - no son medidas reales"
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
