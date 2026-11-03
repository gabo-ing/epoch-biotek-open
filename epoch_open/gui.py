"""Epoch Take3 quantification -- the screen the lab technician uses.

Laid out to follow Gen5's own Take3 module, so there is as little to relearn as
possible: a separate grid for the blank and for the samples, both visible at once,
and a batch that stays open across plate loads until it is explicitly ended.

Written for someone who is not a computer person: no terminal, no settings file, no
COM port to choose. Interface text is Spanish and lives in TEXT below, so
translating means editing one block.
"""

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, config, take3
from .quant import (BLANK_CV_LIMIT_PERCENT, BLANK_DIVERGENCE_LIMIT_AU,
                    BLANK_SPREAD_LIMIT_AU, HIGH_REFERENCE_MARGIN, QuantError,
                    REFERENCE_NM, blank_for, blank_report, quantify, unit_for,
                    wavelengths_for)
from .reader import EpochReader, MockReader, ReaderError, ReaderInfo
from .xlsx import export_results

TEXT = {
    "title": "Cuantificacion Take3 - Epoch",
    "simulated": "MODO SIMULACION - no hay lector conectado. Los numeros NO son medidas reales.",
    "connected": "Lector {model}, serie {serial}, firmware {firmware}, en {port}",
    "searching": "MODO SIMULACION - buscando el lector... Los numeros NO son medidas reales.",
    "lost": "EL LECTOR NO RESPONDE - comprueba que sigue encendido. Reintentando...",
    "no_reader": "Enciende el lector para poder medir. Buscandolo...",
    "no_reader_hint": ("El lector no esta conectado. Enciendelo y espera unos "
                       "segundos: el programa lo detecta solo y se activan los "
                       "botones de lectura."),
    "found_now": "Lector encontrado y conectado. Ya puedes leer de verdad.",
    "found_busy_title": "Lector encontrado",
    "found_busy": "Se ha encontrado el lector encendido.\n\nEl lote actual tiene datos SIMULADOS, que no se pueden mezclar con medidas reales.\n\n¿Descartar el lote simulado y usar el lector?",
    "blank_plate": "Blanco",
    "sample_plate": "Muestras",
    "plate": "Placa Take3  {serial}",
    "sample_type": "Tipo de muestra:",
    "with_230": "Leer tambien 230 nm (para 260/230)",
    "read_blank": "1.  Leer blanco",
    "read_samples": "2.  Leer muestras",
    "end_batch": "3.  Fin del lote  (guardar Excel)",
    "clear_blank": "Limpiar",
    "reset_blanks": "Reiniciar",
    "clear_samples": "Limpiar",
    "all_samples": "Todos",
    "wavelengths": "Longitudes de onda: {list}",
    # "Camino optico" is the correct term and it is what the data sheet says, but
    # it told the reader nothing. The physical quantity is how thick the drop is
    # where the light crosses it, so the label says that.
    "plate_calibrated": "calibrada",
    "plate_uncalibrated": "SIN CALIBRAR",
    "plate_change": "Cambiar placa...",
    "prefs_open": "Preferencias...",
    "prefs_title": "Preferencias",
    "prefs_help": ("Estos son los mismos ajustes que Gen5 tiene en Take3 "
                   "Preferences, con sus valores de fabrica. Cambialos solo si "
                   "sabes por que."),
    "prefs_blank_group": "Validacion del blanco",
    "prefs_cv": "Limite de validacion (CV%):",
    "prefs_cv_help": ("Gen5 no deja leer muestras si el CV% mas alto de las "
                      "longitudes de onda supera este valor. Su valor de "
                      "fabrica es 10."),
    "prefs_ref_group": "Longitud de onda de referencia",
    "prefs_ref_nm": "Longitud de onda:",
    "prefs_ref_limit": "Limite:",
    "prefs_ref_unit": "DO a 0,5 mm",
    "prefs_ref_help": ("Si la referencia de una muestra supera la del blanco en "
                       "mas que este limite, la fila se marca en ambar. Gen5 "
                       "usa 0,1."),
    "prefs_extra_group": "Ajustes propios de este programa",
    "prefs_spread": "Dispersion maxima (DO):",
    "prefs_divergence": "Pozo divergente (DO):",
    "prefs_extra_help": ("Gen5 no tiene estos dos. La dispersion es un suelo "
                         "por debajo del CV%, que es una razon y no mide "
                         "tamanos absolutos. El de divergencia solo decide que "
                         "pozo se pinta en rojo; no bloquea la lectura."),
    "prefs_save": "Aceptar",
    "prefs_cancel": "Cancelar",
    "prefs_defaults": "Valores de fabrica",
    "prefs_bad_value": ("{field}: '{value}' no es un numero valido. Tiene que "
                        "ser mayor que cero."),
    "prefs_bad_nm": ("Longitud de onda de referencia: '{value}' no vale. El "
                     "Epoch lee entre 200 y 999 nm."),
    "prefs_saved": "Preferencias guardadas.",
    "path_nominal": ("Sin hoja de calibracion de esta placa: se usa 0,5 mm "
                     "nominal, las concentraciones pueden desviarse ~2%."),
    "plate_dialog_title": "Placa Take3",
    "plate_dialog_help": ("Copia aqui los valores de la hoja 'Take3 Pathlength Data "
                          "Sheet' que vino con la placa. Son 16 numeros, en mm, "
                          "alrededor de 0,5."),
    "plate_serial_label": "Numero de serie de la placa:",
    "plate_save": "Guardar",
    "plate_cancel": "Cancelar",
    "plate_nominal_btn": "Usar 0,5 mm nominal",
    "plate_saved": "Placa {serial} guardada. Se usara desde ahora.",
    "plate_bad_serial": "Escribe el numero de serie de la placa.",
    "plate_bad_value": ("{well}: '{value}' no es un numero valido. Los caminos "
                        "opticos van entre 0,2 y 1,2 mm (normalmente ~0,5)."),
    "plate_incomplete": ("Faltan {n} pozos. Completa los 16 valores de la hoja, "
                         "o elige 'Usar 0,5 mm nominal'."),
    "plate_known": "Esta placa ya estaba registrada; se muestran sus valores.",
    "blank_pending": "Falta leer el blanco",
    "blank_state_unread": "SIN LEER",
    "blank_state_valid": "VALIDO",
    "blank_state_invalid": "NO VALIDO",
    # Gen5's own word for a blanking whose wells disagree, kept so the two
    # programs say the same thing about the same plate. Seen on 3 November
    # 2026 beside a CV% of 29,242 with two wells painted red.
    "blank_state_diverging": "DIVERGENTE",
    "blank_field_date": "Fecha:",
    "blank_field_time": "Hora:",
    "blank_field_state": "Estado:",
    "blank_field_cv": "CV%:",
    "blank_why_divergent": ("Hay pozos de blanco que no concuerdan con el resto "
                            "(en rojo). Descartalos, o limpia todo y vuelve a "
                            "blanquear."),
    "blank_why_cv": ("Los pozos del blanco varian demasiado entre si "
                     "(CV% por encima del limite). Limpia la placa, vuelve a "
                     "cargar el agua y repite el blanco."),
    "blank_why_single": ("Con un solo pozo no se puede calcular el CV%, asi que "
                         "no hay forma de saber si el blanco es bueno. Marca al "
                         "menos dos pozos y repite el blanco."),
    "blank_why_spread": ("Los pozos del blanco no concuerdan entre si. Limpia la "
                         "placa y vuelve a blanquear."),
    "blank_why_pending": "Faltan pozos por leer (en azul).",
    "blank_why_empty": "No queda ningun pozo de blanco.",
    "blank_not_valid": ("El blanco no es valido todavia. Arreglalo antes de leer "
                        "las muestras:\n\n{reason}"),
    "blank_invalid_say": "Blanco NO valido. {reason}",
    "blank_done": "Blanco leido: {wells}",
    "batch_empty": "Lote vacio",
    "batch_state": "Lote: {reads} lecturas, {total} muestras",
    "naming_hint": "Doble clic = nombre",
    "grid_hint_blank": "Pozos con agua",
    "grid_hint_sample": "Pozos con muestra",
    "name_prompt": "Nombre de la muestra en {well}:",
    "name_title": "Nombre de muestra",
    "no_blank_wells": "Marca primero los pozos del blanco en el cuadro de arriba.",
    "no_sample_wells": "Marca los pozos de muestra en el cuadro de abajo.",
    "no_blank": "Primero hay que leer un blanco.",
    "reading": "Leyendo... no abras la tapa.",
    "blank_ok": "Blanco leido a las {time}. Ahora carga las muestras.",
    "done": "Lectura {read}: {n} muestras. Total en el lote: {total}.",
    "nothing_to_save": "El lote esta vacio; todavia no hay nada que guardar.",
    "saved": "Guardado en {path}. Lote cerrado.",
    "save_error": "No se pudo guardar el archivo:\n\n{error}",
    "read_error": "No se pudo leer:\n\n{error}",
    "columns": ("Lectura:Pozo", "Conc.", "260/280", "260/230", "Aviso"),
    "column_conc": "Conc. ({unit})",
    "instructions": (
        "1. Carga 2 uL de agua en los pozos del blanco y pulsa 'Leer blanco'.\n"
        "2. Limpia, carga 2 uL de cada muestra y pulsa 'Leer muestras'. "
        "Puedes repetir con mas placas; todo se acumula en el mismo lote.\n"
        "3. Cuando termines, pulsa 'Fin del lote' para guardar el Excel."
    ),
    # One line, for a laptop screen that has no room for three. The buttons are
    # numbered and the unavailable ones are greyed out, so the order is already
    # visible without the full text.
    "instructions_short": (
        "Blanco con agua -> muestras -> fin del lote. "
        "Doble clic en un pozo para ponerle nombre."
    ),
}

SAMPLE_TYPES = ("dsDNA", "ssDNA", "RNA", "protein")


from .ui import (RoundedButton, ScreenFit, enable_dpi_awareness,
                 INK, MUTED, LINE, CANVAS, PANEL, CHOSEN, CHOSEN_INK,
                 EMPTY, GOOD, BAD, WARN_ROW, WARN_INK, ZEBRA, TITLE_BAR,
                 TITLE_INK, TITLE_MUTED, STATUS_BAR, WARN_BADGE,
                 WARN_BADGE_INK, GOOD_BADGE, GOOD_BADGE_INK, WELL_LINE,
                 WELL_INK, WELL_HOVER, BLANK_WELL, BLANK_PENDING,
                 BLANK_PENDING_INK, BAD_WELL, BAD_WELL_INK, BAD_WELL_LINE,
                 BLANK_WELL_INK, SAMPLE_WELL, SAMPLE_WELL_INK, ACTION,
                 ACTION_HOVER, ACTION_INK, ACTION_IDLE, ACTION_IDLE_HOVER,
                 ACTION_IDLE_INK, ACTION_OFF, ACTION_OFF_INK, ACTION_INK)

# Read from epoch_open.json beside the program; see epoch_open/config.py. Nothing
# here is tied to one lab: a different reader and a different Take3 plate need a
# config file, not a rebuild.
CONFIG = config.load()
PLATE_SERIAL = CONFIG.plate_serial
PLATE_READER_SERIAL = CONFIG.reader_serial


class App(ScreenFit, tk.Tk):
    PROBE_MS = 3000          # how often to look for the reader

    def __init__(self, backend=None, watch: bool = False):
        super().__init__()
        self.title(f'{TEXT["title"]}  {__version__}')
        self._size_to_screen()

        # None means no instrument was found. The program then shows the screen
        # but refuses to read: inventing numbers that look like measurements is
        # a worse failure than being unable to measure. The simulator is still
        # there for tests and for looking at the screen, but it has to be asked
        # for with --sim, which nobody types by accident.
        self.backend = backend
        self.no_reader = backend is None
        self.simulated = isinstance(backend, MockReader)

        # The technician will often start the program before switching the Epoch
        # on. Rather than make her restart it, keep looking for the instrument in
        # the background and switch over when it answers.
        self.watching = watch
        self.lost = False
        self._probe_thread: threading.Thread | None = None
        self._probe_found = None       # set by the probe thread, read by the GUI
        self._probe_declined = False   # she said no once; do not nag
        # One lock over the serial port: a probe must never run mid-read.
        self._port_lock = threading.Lock()
        # An EpochReader handed to us is already connected; re-connecting would
        # renegotiate the baud rate for nothing.
        if self.no_reader:
            self.info = ReaderInfo(model="Epoch", serial="?",
                                   firmware="?", port="?")
        elif self.simulated:
            self.info = self.backend.connect()
        else:
            # A connected EpochReader already asked the instrument who it is;
            # re-connecting would renegotiate the baud rate for nothing.
            self.info = self.backend.info or ReaderInfo(
                model="Epoch", serial="?", firmware="?",
                port=self.backend.port or "?",
            )

        self.blank_selected: set[str] = set()
        self.sample_selected: set[str] = set()
        self.blank_buttons: dict[str, tk.Button] = {}
        self.sample_buttons: dict[str, tk.Button] = {}
        self.action_buttons: dict[str, tk.Button] = {}

        self.sample_names: dict[str, str] = {}
        self.plate_serial = CONFIG.plate_serial
        self.pathlengths = CONFIG.pathlengths

        # `blank_raw` is every well the last blanking actually measured;
        # `blank_selected` is which of those still count. Discarding a bad well
        # takes it out of the second without losing the reading, so it can be
        # put back without re-reading the plate.
        self.blank_raw: dict | None = None
        self.blank_time: datetime | None = None
        self.blank_report = None
        self.blank: dict | None = None
        self.results: list = []          # (read_number, QuantResult)
        self.read_number = 0

        self._style()
        self._build()
        self._refresh_state()
        self._shrink_to_content()

        if os.environ.get("EPOCH_GUI_TOPMOST") == "1":
            self.attributes("-topmost", True)
            self.geometry("+0+0")
            self.lift()

        # Screenshot aid: drive a simulated run so the window can be reviewed with
        # data in it. Simulator only -- it will not move real hardware unasked.
        if os.environ.get("EPOCH_GUI_DEMO") == "1" and self.simulated:
            self.after(300, self._demo_run)

        if self.watching:
            self.after(self.PROBE_MS, self._probe_tick)

    # ---------------------------------------------------------------- styling

    def _build(self) -> None:
        self._build_banner()

        # Packed before the body although it sits below it. The packer hands
        # out space in the order it is given, so whatever goes last is what
        # gets squeezed to nothing when the window is shorter than its
        # contents -- and that was this bar, the one line saying what the
        # program is waiting for. Reserving its slab first makes the body
        # absorb the shortfall instead, which it can: it scrolls and it has
        # slack. The bar has one line and no slack at all.
        self.status = tk.Label(
            self, text=self._idle_text(), anchor="w", justify="left",
            bg=STATUS_BAR, fg=MUTED, padx=16, pady=5 if self.compact else 8,
            font=(self.ui_font, self.base_pt - 1),
        )
        self.status.pack(fill="x", side="bottom")

        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 10))

        self._build_header(left)

        # Side by side, not stacked: two 8-row grids one above the other make the
        # window taller than the screen, which pushed the action buttons off the
        # bottom edge where nobody could reach them.
        grids = ttk.Frame(left)
        grids.pack(fill="x")
        self._build_grid(
            grids, TEXT["blank_plate"], self.blank_selected,
            self.blank_buttons, nameable=False,
        )
        self._build_grid(
            grids, TEXT["sample_plate"], self.sample_selected,
            self.sample_buttons, nameable=True,
        )
        self._build_buttons(left)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self._build_results(right)

    def _build_banner(self) -> None:
        """The app's own title bar, with the connection badge sitting in it."""
        bar = tk.Frame(self, bg=TITLE_BAR)
        bar.pack(fill="x")

        tk.Label(bar, text=TEXT["title"], bg=TITLE_BAR, fg=TITLE_INK,
                 font=(self.ui_font, self.base_pt + 4, "bold"),
                 padx=16,
                 pady=4 if self.tiny else (7 if self.compact else 12),
                 ).pack(side="left")
        tk.Label(bar, text=__version__, bg=TITLE_BAR, fg=TITLE_MUTED,
                 font=(self.ui_font, self.base_pt - 1)).pack(
            side="left", pady=(6, 0))

        # The badge floats at the right-hand end of the title bar, the way a
        # notification pill does, rather than being a full-width stripe.
        self.banner = tk.Label(bar, padx=14, pady=7,
                               font=(self.ui_font, self.base_pt, "bold"))
        self.banner.pack(side="right", padx=14, pady=8)
        self._refresh_banner()

    def _refresh_banner(self) -> None:
        """The badge is the one place that says whether the numbers are real.

        Simulation is amber rather than red by request. The wording carries the
        weight instead, because this is the state in which the screen is showing
        numbers that were never measured.
        """
        if self.no_reader:
            text = TEXT["no_reader"]
            bg, fg = WARN_BADGE, WARN_BADGE_INK
        elif self.lost:
            text, bg, fg = TEXT["lost"], BAD, "#ffffff"
        elif self.simulated:
            text = TEXT["searching"] if self.watching else TEXT["simulated"]
            bg, fg = WARN_BADGE, WARN_BADGE_INK
        else:
            text = TEXT["connected"].format(
                model=self.info.model, serial=self.info.serial,
                firmware=self.info.firmware, port=self.info.port,
            )
            bg, fg = GOOD_BADGE, GOOD_BADGE_INK
        self.banner.configure(text=text, bg=bg, fg=fg)

    def _build_header(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 6))

        plate_row = ttk.Frame(frame)
        plate_row.pack(fill="x", pady=(0, 4))
        self.plate_label = ttk.Label(plate_row, style="Head.TLabel")
        self.plate_label.pack(side="left")
        self.plate_state = ttk.Label(plate_row)
        self.plate_state.pack(side="left", padx=(8, 0))
        ttk.Button(plate_row, text=TEXT["plate_change"],
                   command=self._change_plate).pack(side="right")
        ttk.Button(plate_row, text=TEXT["prefs_open"],
                   command=self._preferences).pack(side="right", padx=(0, 6))

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=TEXT["sample_type"]).pack(side="left")
        self.sample_type = tk.StringVar(value=SAMPLE_TYPES[0])
        combo = ttk.Combobox(row, textvariable=self.sample_type,
                             values=SAMPLE_TYPES, state="readonly", width=9)
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_state())

        self.with_230 = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text=TEXT["with_230"], variable=self.with_230,
                        command=self._refresh_state).pack(anchor="w")

        self.wavelength_label = ttk.Label(frame, text="", style="Muted.TLabel")
        self.wavelength_label.pack(anchor="w")

        # Only shown when the plate has no calibration sheet, because then the
        # results are up to 2.4% off and there is something to do about it.
        self.path_warning = ttk.Label(frame, text=TEXT["path_nominal"],
                                      style="Bad.TLabel", wraplength=330)

    def _build_grid(self, parent, title, selection, buttons, nameable) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=4 if self.compact else 8,
                               style="Card.TLabelframe")
        frame.pack(side="left", fill="y", padx=(0, 8))

        if not self.tiny:
            ttk.Label(frame, text=(TEXT["grid_hint_sample"] if nameable
                                   else TEXT["grid_hint_blank"]),
                      style="CardMuted.TLabel").pack(
                pady=(0, 3 if self.compact else 6))

        grid = ttk.Frame(frame, style="Card.TFrame")
        grid.pack()

        for position, column in enumerate(take3.COLUMNS):
            ttk.Label(grid, text=str(column), width=7, anchor="center",
                      style="CardMuted.TLabel").grid(row=0, column=position + 1)

        for row_index, row_letter in enumerate(take3.ROWS):
            ttk.Label(grid, text=row_letter, width=2, anchor="e",
                      style="CardMuted.TLabel").grid(
                row=row_index + 1, column=0, padx=(0, 5))
            for position, column in enumerate(take3.COLUMNS):
                name = f"{row_letter}{column}"
                button = RoundedButton(
                    grid, text=name, width=self.px(72),
                    height=self.px(20 if self.tiny else
                                   (22 if self.compact else 28)),
                    radius=self.px(4),
                    bg=EMPTY, fg=WELL_INK, outline=WELL_LINE,
                    hover=WELL_HOVER, parent_bg=PANEL,
                    font=("TkDefaultFont", self.base_pt - 1),
                    command=lambda n=name, s=selection, b=buttons: self._toggle(n, s, b),
                )
                # Which green this well turns when it is chosen.
                button.selected_bg = SAMPLE_WELL if nameable else BLANK_WELL
                button.selected_fg = SAMPLE_WELL_INK if nameable else BLANK_WELL_INK
                # 2px between wells: 1px of padding on each facing edge.
                button.grid(row=row_index + 1, column=position + 1, padx=1, pady=1)
                if nameable:
                    button.bind("<Double-Button-1>",
                                lambda _e, n=name: self._name_well(n))
                buttons[name] = button

        if not nameable:
            self._build_blank_status(frame)

        controls = ttk.Frame(frame, style="Card.TFrame")
        controls.pack(fill="x", pady=(8, 0))
        if nameable:
            ttk.Button(controls, text=TEXT["all_samples"],
                       command=lambda: self._select_all(selection, buttons)).pack(
                side="left", expand=True, fill="x", padx=1)
            ttk.Button(controls, text=TEXT["clear_blank"],
                       command=lambda: self._clear(selection, buttons)).pack(
                side="left", expand=True, fill="x", padx=1)
        else:
            # Gen5 calls this "Reset Blanks", and it throws away the readings as
            # well as the selection. Clearing only the marks would leave the old
            # blank still being subtracted from the next samples.
            ttk.Button(controls, text=TEXT["reset_blanks"],
                       command=self._reset_blanks).pack(
                side="left", expand=True, fill="x", padx=1)

        # On a laptop screen this line is what pushes the buttons off the
        # bottom. The short status bar says the same thing there.
        if nameable and not self.compact:
            ttk.Label(frame, text=TEXT["naming_hint"], wraplength=self.px(220),
                      style="CardMuted.TLabel").pack(pady=(6, 0))

    def _build_blank_status(self, parent) -> None:
        """Date, time, verdict and CV of the last blanking.

        The same four fields Gen5 prints beside its blanking grid, in the same
        order, because that is what the technician already checks before she
        trusts a blank. It sits under the grid rather than beside it only
        because this column is narrow.
        """
        box = ttk.Frame(parent, style="Card.TFrame")
        box.pack(fill="x", pady=(6, 0))

        self.blank_fields: dict[str, ttk.Label] = {}
        fields = (("date", TEXT["blank_field_date"]),
                  ("time", TEXT["blank_field_time"]),
                  ("state", TEXT["blank_field_state"]),
                  ("cv", TEXT["blank_field_cv"]))
        for row, (key, label) in enumerate(fields):
            ttk.Label(box, text=label, style="CardMuted.TLabel").grid(
                row=row, column=0, sticky="w")
            value = ttk.Label(box, text="-", style="Card.TLabel")
            value.grid(row=row, column=1, sticky="w", padx=(6, 0))
            self.blank_fields[key] = value


    def _build_buttons(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(3 if self.compact else 6, 0))

        self.blank_label = ttk.Label(frame, text="", style="Bad.TLabel")
        self.blank_label.pack()
        self.batch_label = ttk.Label(frame, text="", style="Muted.TLabel")
        self.batch_label.pack(pady=(0, 4 if self.compact else 8))

        for key, command in (("read_blank", self._read_blank),
                             ("read_samples", self._read_samples),
                             ("end_batch", self._end_batch)):
            button = RoundedButton(
                frame, text=TEXT[key], command=command,
                height=self.px(30 if self.tiny else (34 if self.compact else 42)),
                radius=self.px(6),
                bg=ACTION, fg=ACTION_INK, hover=ACTION_HOVER,
                parent_bg=CANVAS, stretch=True,
                font=(self.ui_font, self.base_pt + 1, "bold"),
            )
            button.pack(fill="x", pady=2 if self.compact else 3)
            self.action_buttons[key] = button

    def _build_results(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text="Resultados", padding=8,
                               style="Card.TLabelframe")
        frame.pack(fill="both", expand=True)

        # A small requested height, not the 26 rows this asked for before. The
        # table is packed with expand=True so it fills whatever space there is;
        # asking for 26 rows only forced the window taller than a laptop screen
        # and pushed the buttons off the bottom.
        self.table = ttk.Treeview(frame, columns=TEXT["columns"],
                                  show="headings", height=8)
        # Every column keeps its width except the warnings, which take whatever
        # is left. Previously they were fixed too, so on a narrow screen the
        # warning column was the part that fell off the edge.
        # Measurements are right-aligned so the decimal points line up down the
        # column and a tenfold difference is visible without reading the digits.
        numeric = {"Conc.", "260/280", "260/230"}
        for column, width in zip(TEXT["columns"],
                                 [self.px(w) for w in (130, 115, 90, 90, 240)]):
            self.table.heading(
                column, text=column,
                anchor="e" if column in numeric else "w",
            )
            self.table.column(column, width=width,
                              anchor="e" if column in numeric else "w",
                              stretch=(column == TEXT["columns"][-1]),
                              minwidth=self.px(60))
        self.table.column(TEXT["columns"][-1], anchor="w", minwidth=self.px(120))

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview,
                                  style="Dark.Vertical.TScrollbar")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.tag_configure("odd", background=ZEBRA)
        self.table.tag_configure("even", background=PANEL)
        self.table.tag_configure("warn", background=WARN_ROW, foreground=WARN_INK)

    # --------------------------------------------------------------- state

    def _toggle(self, name, selection, buttons) -> None:
        button = buttons[name]
        if name in selection:
            selection.discard(name)
            button.configure(bg=EMPTY, fg=WELL_INK, outline=WELL_LINE,
                             hover=WELL_HOVER,
                             font=("TkDefaultFont", self.base_pt - 1))
        else:
            selection.add(name)
            button.configure(bg=button.selected_bg, fg=button.selected_fg,
                             outline=button.selected_bg, hover=None,
                             font=("TkDefaultFont", self.base_pt - 1, "bold"))
        self._refresh_state()

    def _select_all(self, selection, buttons) -> None:
        for name in buttons:
            if name not in selection:
                self._toggle(name, selection, buttons)

    def _clear(self, selection, buttons) -> None:
        for name in list(selection):
            self._toggle(name, selection, buttons)

    def _blank_pending_wells(self) -> set[str]:
        """Wells marked for the blank that the last blanking did not measure.

        Marking a well after reading leaves the blank half measured. That must
        not count as a blank: the samples would be corrected with a mixture of
        the wells that were read and nothing at all for the rest.
        """
        if self.blank_raw is None:
            return set()
        return self.blank_selected - set(self.blank_raw)

    def _rebuild_blank(self) -> None:
        """Work out the blank in force, and judge it, from the current marks."""
        if self.blank_raw is None:
            self.blank, self.blank_report = None, None
            return

        kept = {well: reading for well, reading in self.blank_raw.items()
                if well in self.blank_selected}
        self.blank = kept or None
        self.blank_report = blank_report(
            kept,
            CONFIG.blank_cv_limit_percent,
            CONFIG.blank_spread_limit_au,
            CONFIG.blank_divergence_limit_au,
        ) if kept else None

    def _blank_ok(self) -> bool:
        """Whether samples may be read against this blank."""
        return (self.blank_raw is not None
                and not self._blank_pending_wells()
                and self.blank_report is not None
                and self.blank_report.valid)

    def _blank_reason(self) -> str:
        """Why the blank is not usable, in words she can act on."""
        if self._blank_pending_wells():
            return TEXT["blank_why_pending"]
        if self.blank_report is None:
            return TEXT["blank_why_empty"]
        return {
            "cv": TEXT["blank_why_cv"],
            "single": TEXT["blank_why_single"],
            "divergent": TEXT["blank_why_divergent"],
            "spread": TEXT["blank_why_spread"],
            "empty": TEXT["blank_why_empty"],
        }.get(self.blank_report.reason, "")

    def _blank_well_style(self, name: str):
        """How one well of the blank grid should look: (bg, fg, outline, hover)."""
        if name not in self.blank_selected:
            return EMPTY, WELL_INK, WELL_LINE, WELL_HOVER
        if self.blank_raw is None or name not in self.blank_raw:
            return BLANK_PENDING, BLANK_PENDING_INK, BLANK_PENDING, None
        if self.blank_report and name in self.blank_report.divergent:
            return BAD_WELL, BAD_WELL_INK, BAD_WELL_LINE, None
        return BLANK_WELL, BLANK_WELL_INK, BLANK_WELL, None

    def _refresh_blank_wells(self) -> None:
        for name, button in self.blank_buttons.items():
            bg, fg, outline, hover = self._blank_well_style(name)
            marked = name in self.blank_selected
            button.configure(
                bg=bg, fg=fg, outline=outline, hover=hover,
                font=("TkDefaultFont", self.base_pt - 1, "bold") if marked
                else ("TkDefaultFont", self.base_pt - 1),
            )

    def _refresh_blank_display(self) -> None:
        """Repaint the blank grid and the four status fields beside it."""
        self._refresh_blank_wells()

        if self.blank_raw is None:
            for key in ("date", "time", "cv"):
                self.blank_fields[key].configure(text="-")
            self.blank_fields["state"].configure(
                text=TEXT["blank_state_unread"], style="CardMuted.TLabel")
            self.blank_label.configure(text=TEXT["blank_pending"],
                                       style="Bad.TLabel")
            return

        when = self.blank_time or datetime.now()
        self.blank_fields["date"].configure(text=when.strftime("%d-%m-%Y"))
        self.blank_fields["time"].configure(text=when.strftime("%H:%M:%S"))

        ok = self._blank_ok()
        if ok:
            state = TEXT["blank_state_valid"]
        elif self.blank_report is not None and self.blank_report.reason == "cv":
            # Gen5 distinguishes this case by name, so we do too.
            state = TEXT["blank_state_diverging"]
        else:
            state = TEXT["blank_state_invalid"]
        self.blank_fields["state"].configure(
            text=state, style="CardGood.TLabel" if ok else "CardBad.TLabel")

        # A CV needs at least two wells. Printing 0,00 for a single one would
        # read as perfect agreement rather than as nothing to compare.
        if self.blank_report and len(self.blank_report.wells) > 1:
            # Comma for the decimal mark, as Gen5 prints it here.
            text = f"{self.blank_report.cv_260:.3f}".replace(".", ",") + "%"
        else:
            text = "-"
        self.blank_fields["cv"].configure(text=text)

        if ok:
            self.blank_label.configure(
                text=TEXT["blank_done"].format(
                    wells=", ".join(sorted(self.blank or {}))),
                style="Good.TLabel")
        else:
            self.blank_label.configure(text=self._blank_reason(),
                                       style="Bad.TLabel")


    def _reset_blanks(self) -> None:
        """Throw the blanking away: both the readings and the marks.

        What Gen5 calls Reset Blanks. Clearing only the marks would leave the
        old readings still being subtracted from the next samples.
        """
        self.blank_raw = None
        self.blank_time = None
        self._clear(self.blank_selected, self.blank_buttons)
        self._refresh_state()

    def _refresh_plate(self) -> None:
        """Show which plate is loaded and whether its sheet is in."""
        self.plate_label.configure(
            text=TEXT["plate"].format(serial=self.plate_serial or "?"))
        calibrated = bool(self.pathlengths)
        self.plate_state.configure(
            text=TEXT["plate_calibrated"] if calibrated
            else TEXT["plate_uncalibrated"],
            style="Good.TLabel" if calibrated else "Bad.TLabel",
        )
        if calibrated:
            self.path_warning.pack_forget()
        else:
            self.path_warning.pack(anchor="w", pady=(2, 0))

    def _preferences(self) -> None:
        """Open the thresholds, and apply them without a restart.

        The limits are read from CONFIG every time a blank is judged, so
        writing them back into CONFIG and re-running the verdict is all that
        is needed: a blanking already on screen is re-judged under the new
        numbers the moment the dialog closes.
        """
        dialog = PreferencesDialog(self, CONFIG)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        CONFIG.blank_cv_limit_percent = dialog.result["cv"]
        CONFIG.reference_limit_od = dialog.result["ref_limit"]
        CONFIG.blank_spread_limit_au = dialog.result["spread"]
        CONFIG.blank_divergence_limit_au = dialog.result["divergence"]
        try:
            config.save(CONFIG)
        except OSError as exc:
            messagebox.showerror(TEXT["title"],
                                 TEXT["save_error"].format(error=exc))
            return

        self._refresh_state()
        self._say(TEXT["prefs_saved"])

    def _change_plate(self) -> None:
        dialog = PlateDialog(self, self.plate_serial, self.pathlengths)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        serial, table = dialog.result
        self.plate_serial = serial
        CONFIG.set_plate(serial, table)
        self.pathlengths = CONFIG.pathlengths
        try:
            config.save(CONFIG)
        except OSError as exc:
            messagebox.showwarning(TEXT["title"], str(exc))
        self._refresh_plate()
        self._say(TEXT["plate_saved"].format(serial=serial))

    def _refresh_table_columns(self) -> None:
        """Say the unit once, in the heading, and hide 260/230 when it is not read."""
        self.table.heading(
            "Conc.",
            text=TEXT["column_conc"].format(unit=unit_for(self.sample_type.get())),
        )
        shown_columns = [c for c in TEXT["columns"]
                         if c != "260/230" or self.with_230.get()]
        self.table.configure(displaycolumns=shown_columns)

    def _refresh_state(self) -> None:
        wavelengths = wavelengths_for(self.sample_type.get(), self.with_230.get())
        self.wavelength_label.configure(
            text=TEXT["wavelengths"].format(
                list=", ".join(f"{w}" for w in wavelengths) + " nm"
            )
        )
        self._rebuild_blank()
        self._refresh_blank_display()

        self.batch_label.configure(
            text=TEXT["batch_state"].format(reads=self.read_number,
                                            total=len(self.results))
            if self.results else TEXT["batch_empty"]
        )
        self._refresh_table_columns()
        self._refresh_actions()
        self._refresh_plate()

    def _refresh_actions(self) -> None:
        """Show what to press next, and make the rest unpressable.

        The order is fixed -- blank, samples, save -- so the screen can simply
        refuse the steps that are not available yet. Stopping the mistake is
        kinder than explaining it in a dialog after the fact.
        """
        if not self._blank_ok():
            nxt = "read_blank"
        elif not self.results:
            nxt = "read_samples"
        else:
            nxt = "end_batch"

        # Nothing can be read without an instrument that is answering. The
        # buttons say so by being unpressable rather than by failing afterwards.
        can_read = not (self.no_reader or self.lost)
        usable = {
            "read_blank": can_read,
            # Not merely "a blank was read": a blank that failed its own
            # checks must not be subtracted from anybody's samples.
            "read_samples": can_read and self._blank_ok(),
            "end_batch": bool(self.results),
        }
        if not can_read:
            nxt = "end_batch" if self.results else None
        for key, button in self.action_buttons.items():
            if not usable[key]:
                button.configure(state="disabled", bg=ACTION_OFF,
                                 fg=ACTION_OFF_INK, hover=None, cursor="")
            else:
                is_next = key == nxt
                button.configure(
                    state="normal", cursor="hand2",
                    fg=ACTION_INK if is_next else ACTION_IDLE_INK,
                    bg=ACTION if is_next else ACTION_IDLE,
                    hover=ACTION_HOVER if is_next else ACTION_IDLE_HOVER,
                )

    def _idle_text(self) -> str:
        if self.no_reader:
            return TEXT["no_reader_hint"]
        return TEXT["instructions_short"] if self.compact else TEXT["instructions"]

    def _say(self, message: str) -> None:
        self.status.configure(text=message)
        self.update_idletasks()

    def _name_well(self, name: str) -> None:
        answer = simpledialog.askstring(
            TEXT["name_title"], TEXT["name_prompt"].format(well=name),
            initialvalue=self.sample_names.get(name, ""), parent=self,
        )
        if answer is None:
            return
        answer = answer.strip()
        if answer:
            self.sample_names[name] = answer
            if name not in self.sample_selected:
                self._toggle(name, self.sample_selected, self.sample_buttons)
        else:
            self.sample_names.pop(name, None)
        self.sample_buttons[name].configure(
            text=self.sample_names.get(name, name)[:7]
        )

    # --------------------------------------------------- finding the reader

    def _probe_tick(self) -> None:
        """Look for the instrument every few seconds, without freezing the window.

        Connecting walks several baud rates and can take seconds, so it runs in a
        thread; only this method, on the GUI thread, ever touches a widget.
        """
        if not self.watching:
            return

        found, self._probe_found = self._probe_found, None
        if found is not None:
            self._adopt(found)
        elif self._needs_reader() and self._probe_thread is None:
            self._probe_thread = threading.Thread(target=self._probe, daemon=True)
            self._probe_thread.start()

        self.after(self.PROBE_MS, self._probe_tick)

    def _needs_reader(self) -> bool:
        return self.simulated or self.lost or self.no_reader

    def _probe(self) -> None:
        """Background thread: try to open the reader, give up quietly if absent."""
        if not self._port_lock.acquire(blocking=False):
            self._probe_thread = None
            return
        try:
            reader = EpochReader(expected_serial=PLATE_READER_SERIAL)
            try:
                reader.connect()
            except (ReaderError, NotImplementedError, OSError):
                return          # not switched on yet; try again next tick
            self._probe_found = reader
        finally:
            self._port_lock.release()
            self._probe_thread = None

    def _adopt(self, reader) -> None:
        """Switch to the real instrument, but never mix simulated data into a batch."""
        if not self._needs_reader():
            reader.close()
            return

        simulated_data = self.simulated and (self.blank is not None or self.results)
        if simulated_data:
            if self._probe_declined:
                reader.close()
                return
            if not messagebox.askyesno(TEXT["found_busy_title"], TEXT["found_busy"]):
                self._probe_declined = True
                reader.close()
                return
            self.blank = None
            self.results = []
            self.read_number = 0
            self.sample_names = {}
            self._fill_table()

        self.backend = reader
        self.simulated = False
        self.lost = False
        self.no_reader = False
        # What the instrument reported when it answered, not what the config
        # file hoped for. This is quoted on screen and stamped into every export,
        # so a guess here is a false provenance record.
        self.info = reader.info or ReaderInfo(
            model="Epoch", serial="?", firmware="?", port=reader.port or "?",
        )
        self._refresh_banner()
        self._refresh_state()
        self._say(TEXT["found_now"])

    def _mark_lost(self) -> None:
        """A read failed: say so plainly and start looking for the reader again."""
        if self.simulated:
            return
        self.lost = True
        try:
            self.backend.close()
        except Exception:
            pass
        self._refresh_banner()
        if self.watching and self._probe_thread is None:
            self.after(self.PROBE_MS, self._probe_tick)

    # -------------------------------------------------------------- actions

    def _read(self, wells: list[str], as_blank: bool):
        if self.backend is None:
            # The buttons are disabled in this state, so this is a backstop
            # rather than a path anyone should reach.
            raise ReaderError(TEXT["no_reader_hint"])
        if isinstance(self.backend, MockReader):
            # Simulation only: tell the fake instrument what is on the plate.
            self.backend.simulating_blank = as_blank
        with self._port_lock:
            return self.backend.read_wells(
                wells, wavelengths_for(self.sample_type.get(), self.with_230.get())
            )

    def _read_blank(self) -> None:
        wells = sorted(self.blank_selected)
        if not wells:
            messagebox.showinfo(TEXT["title"], TEXT["no_blank_wells"])
            return

        self._say(TEXT["reading"])
        try:
            raw = self._read(wells, as_blank=True)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._mark_lost()
            messagebox.showerror(TEXT["title"], TEXT["read_error"].format(error=exc))
            self._say(self._idle_text())
            return

        self.blank_raw = raw
        self.blank_time = datetime.now()
        self._refresh_state()

        # No dialog on a bad blank. The verdict, the CV and the offending wells
        # are all on screen now and stay there; a modal would only have to be
        # dismissed before she could act on what it was telling her about.
        if self._blank_ok():
            self._say(TEXT["blank_ok"].format(
                time=self.blank_time.strftime("%H:%M")))
        else:
            self._say(TEXT["blank_invalid_say"].format(
                reason=self._blank_reason()))

    def _read_samples(self) -> None:
        wells = sorted(self.sample_selected)
        if not wells:
            messagebox.showinfo(TEXT["title"], TEXT["no_sample_wells"])
            return
        if self.blank_raw is None:
            messagebox.showinfo(TEXT["title"], TEXT["no_blank"])
            return
        if not self._blank_ok():
            messagebox.showinfo(
                TEXT["title"],
                TEXT["blank_not_valid"].format(reason=self._blank_reason()))
            return

        self._say(TEXT["reading"])
        try:
            raw = self._read(wells, as_blank=False)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._mark_lost()
            messagebox.showerror(TEXT["title"], TEXT["read_error"].format(error=exc))
            self._say(self._idle_text())
            return

        sample_type = self.sample_type.get()
        self.read_number += 1
        for well in wells:
            try:
                self.results.append((
                    self.read_number,
                    quantify(raw[well], blank_for(self.blank, well),
                             sample_type, self.pathlengths,
                             CONFIG.reference_limit_od),
                ))
            except QuantError as exc:
                self.table.insert("", "end",
                                  values=(well, "-", "-", "-", "-", str(exc)),
                                  tags=("warn",))

        self._fill_table()
        self._refresh_state()
        self._say(TEXT["done"].format(read=self.read_number, n=len(wells),
                                      total=len(self.results)))

    def _fill_table(self) -> None:
        for row in self.table.get_children():
            self.table.delete(row)

        def shown(value, digits):
            return f"{value:.{digits}f}" if value is not None else "-"

        for index, (read_number, result) in enumerate(self.results):
            note = "; ".join(w.short for w in result.warnings)
            label = self.sample_names.get(result.well, result.well)
            stripe = "odd" if index % 2 else "even"
            self.table.insert(
                "", "end",
                values=(f"{read_number}:{label}",
                        shown(result.concentration, 1),
                        shown(result.ratio_260_280, 2),
                        shown(result.ratio_260_230, 2),
                        note),
                tags=("warn",) if note else (stripe,),
            )

    def _end_batch(self) -> None:
        if not self.results:
            messagebox.showinfo(TEXT["title"], TEXT["nothing_to_save"])
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"cuantificacion_{datetime.now():%Y%m%d_%H%M}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        metadata = {
            "Programa": f"epoch-open {__version__}",
            "Placa Take3": self.plate_serial,
            "Espesor de gota": ("medido pozo a pozo, hoja de la placa"
                                if self.pathlengths else "0,5 mm nominal"),
            "Lector": self.info.model,
            "Numero de serie": self.info.serial,
            "Firmware": self.info.firmware,
            "Tipo de muestra": self.sample_type.get(),
        }
        if self.simulated:
            metadata["AVISO"] = "DATOS SIMULADOS - no son medidas reales"

        try:
            export_results(path, self.results,
                           sample_names=self.sample_names, metadata=metadata)
        except OSError as exc:
            messagebox.showerror(TEXT["title"], TEXT["save_error"].format(error=exc))
            return

        self.results = []
        self.read_number = 0
        self.blank_raw = None
        self.blank_time = None
        self._fill_table()
        self._refresh_state()
        self._say(TEXT["saved"].format(path=Path(path).name))

    # ----------------------------------------------------------------- demo

    def _demo_run(self) -> None:
        for well in ("A2", "A3"):
            self._toggle(well, self.blank_selected, self.blank_buttons)
        for well in ("B2", "C2", "D2", "E2"):
            self._toggle(well, self.sample_selected, self.sample_buttons)
        for well, label in (("B2", "APP 1a"), ("C2", "APP 2a"),
                            ("D2", "SA 1a"), ("E2", "SA 2a")):
            self.sample_names[well] = label
            self.sample_buttons[well].configure(text=label[:7])

        self._read_blank()
        self._read_samples()
        self._read_samples()


class PreferencesDialog(tk.Toplevel):
    """The handful of numbers that decide a verdict, in one place.

    Deliberately shaped like Gen5's Take3 Preferences dialog -- same grouping,
    same field names, same units -- because the technician has used that
    screen for years and this is where she would go looking. The defaults are
    Gen5's factory values, read off this lab's licensed copy; see
    docs/GEN5_NOTES.md.

    Nothing here is needed in ordinary use. It exists because the one thing
    worse than a wrong threshold is a wrong threshold nobody can reach: this
    ships as a single .exe, so without this dialog changing a limit means
    editing JSON next to the executable, or a rebuild.
    """

    def __init__(self, parent, config):
        super().__init__(parent)
        self.title(TEXT["prefs_title"])
        self.transient(parent)
        self.resizable(False, False)
        self.configure(bg=CANVAS)
        self.result = None
        self.px = parent.px
        self.ui_font = parent.ui_font
        self.base_pt = parent.base_pt

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=TEXT["prefs_help"], wraplength=self.px(420),
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        self.fields = {}

        blank = ttk.LabelFrame(body, text=TEXT["prefs_blank_group"], padding=10,
                               style="Card.TLabelframe")
        blank.pack(fill="x", pady=(0, 10))
        self._row(blank, "cv", TEXT["prefs_cv"], config.blank_cv_limit_percent)
        ttk.Label(blank, text=TEXT["prefs_cv_help"], wraplength=self.px(390),
                  style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))

        reference = ttk.LabelFrame(body, text=TEXT["prefs_ref_group"],
                                   padding=10, style="Card.TLabelframe")
        reference.pack(fill="x", pady=(0, 10))
        self._row(reference, "ref_nm", TEXT["prefs_ref_nm"], REFERENCE_NM)
        self._row(reference, "ref_limit", TEXT["prefs_ref_limit"],
                  config.reference_limit_od, suffix=TEXT["prefs_ref_unit"])
        ttk.Label(reference, text=TEXT["prefs_ref_help"],
                  wraplength=self.px(390),
                  style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))

        extra = ttk.LabelFrame(body, text=TEXT["prefs_extra_group"], padding=10,
                               style="Card.TLabelframe")
        extra.pack(fill="x", pady=(0, 12))
        self._row(extra, "spread", TEXT["prefs_spread"],
                  config.blank_spread_limit_au)
        self._row(extra, "divergence", TEXT["prefs_divergence"],
                  config.blank_divergence_limit_au)
        ttk.Label(extra, text=TEXT["prefs_extra_help"],
                  wraplength=self.px(390),
                  style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        ttk.Button(buttons, text=TEXT["prefs_defaults"],
                   command=self._defaults).pack(side="left")
        ttk.Button(buttons, text=TEXT["prefs_cancel"],
                   command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text=TEXT["prefs_save"],
                   command=self._save).pack(side="right")

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    def _row(self, parent, key, label, value, suffix=""):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=26, style="Card.TLabel").pack(side="left")
        variable = tk.StringVar(value=str(value).replace(".", ","))
        entry = ttk.Entry(row, textvariable=variable, width=10)
        entry.pack(side="left")
        if suffix:
            ttk.Label(row, text=suffix, style="CardMuted.TLabel").pack(
                side="left", padx=(6, 0))
        self.fields[key] = variable

    def _defaults(self) -> None:
        """Gen5's factory values, and this program's own starting points."""
        for key, value in (("cv", BLANK_CV_LIMIT_PERCENT),
                           ("ref_nm", REFERENCE_NM),
                           ("ref_limit", HIGH_REFERENCE_MARGIN),
                           ("spread", BLANK_SPREAD_LIMIT_AU),
                           ("divergence", BLANK_DIVERGENCE_LIMIT_AU)):
            self.fields[key].set(str(value).replace(".", ","))

    def _number(self, key, label):
        """A positive number, with a comma accepted as the decimal mark."""
        raw = self.fields[key].get().strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            value = -1.0
        if value <= 0:
            messagebox.showerror(
                TEXT["prefs_title"],
                TEXT["prefs_bad_value"].format(field=label, value=
                                               self.fields[key].get()),
                parent=self)
            return None
        return value

    def _save(self) -> None:
        values = {}
        for key, label in (("cv", TEXT["prefs_cv"]),
                           ("ref_limit", TEXT["prefs_ref_limit"]),
                           ("spread", TEXT["prefs_spread"]),
                           ("divergence", TEXT["prefs_divergence"])):
            value = self._number(key, label)
            if value is None:
                return
            values[key] = value

        # The reference wavelength is shown because Gen5 shows it, but it is
        # not editable in effect: every reading this program takes includes
        # 320 nm and the whole correction is built on it. Changing it here
        # would be a lie, so it is checked and refused rather than ignored.
        shown = self.fields["ref_nm"].get().strip()
        if shown not in (str(REFERENCE_NM), f"{REFERENCE_NM},0"):
            messagebox.showerror(
                TEXT["prefs_title"],
                TEXT["prefs_bad_nm"].format(value=shown), parent=self)
            return

        self.result = values
        self.destroy()


class PlateDialog(tk.Toplevel):
    """Enter a Take3 plate and the pathlengths from its data sheet.

    Laid out the way the sheet is, rows A-H against columns 2 and 3, so the
    numbers can be copied straight across without counting places. The program
    ships as a single .exe, so this is the only way an owner can register a
    replacement plate.
    """

    def __init__(self, parent, serial: str | None, table: dict | None):
        super().__init__(parent)
        self.title(TEXT["plate_dialog_title"])
        self.transient(parent)
        self.resizable(False, False)
        self.configure(bg=CANVAS)
        self.result: tuple[str, dict] | None = None

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=TEXT["plate_dialog_help"], wraplength=380,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(0, 12))
        ttk.Label(row, text=TEXT["plate_serial_label"]).pack(side="left")
        self.serial = tk.StringVar(value=serial or "")
        serial_entry = ttk.Entry(row, textvariable=self.serial, width=14)
        serial_entry.pack(side="left", padx=(8, 0))
        self._opened_with = (serial or "").strip()
        self.serial.trace_add("write", self._serial_changed)

        self.known_label = ttk.Label(body, text="", style="Good.TLabel")
        self.known_label.pack(anchor="w", pady=(0, 6))

        grid = ttk.LabelFrame(body, text="mm", padding=10,
                              style="Card.TLabelframe")
        grid.pack()
        inner = ttk.Frame(grid, style="Card.TFrame")
        inner.pack()

        for position, column in enumerate(take3.COLUMNS):
            ttk.Label(inner, text=str(column), width=9, anchor="center",
                      style="CardMuted.TLabel").grid(row=0, column=position + 1)

        self.entries: dict[str, tk.StringVar] = {}
        for row_index, letter in enumerate(take3.ROWS):
            ttk.Label(inner, text=letter, width=2, anchor="e",
                      style="CardMuted.TLabel").grid(
                row=row_index + 1, column=0, padx=(0, 6))
            for position, column in enumerate(take3.COLUMNS):
                well = f"{letter}{column}"
                var = tk.StringVar(
                    value=f"{table[well]:.4f}" if table and well in table else "")
                self.entries[well] = var
                ttk.Entry(inner, textvariable=var, width=9,
                          justify="center").grid(
                    row=row_index + 1, column=position + 1, padx=2, pady=2)

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text=TEXT["plate_cancel"],
                   command=self.destroy).pack(side="right")
        tk.Button(buttons, text=TEXT["plate_save"], command=self._save,
                  bg=ACTION, fg=ACTION_INK, relief="flat", bd=0,
                  padx=16, pady=6, font=("TkDefaultFont", 10, "bold"),
                  cursor="hand2").pack(side="right", padx=(0, 8))
        ttk.Button(buttons, text=TEXT["plate_nominal_btn"],
                   command=self._nominal).pack(side="left")

        serial_entry.focus_set()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    # ------------------------------------------------------------------

    def _serial_changed(self, *_args) -> None:
        """Repopulate when the serial changes, so one plate's numbers cannot be
        saved under another plate's serial.

        Typing a new serial over a pre-filled form and pressing save would
        otherwise register the new plate with the old plate's pathlengths, which
        is wrong by a couple of percent and invisible afterwards.
        """
        typed = self.serial.get().strip()
        if typed == self._opened_with:
            return
        self._opened_with = typed

        known = CONFIG.pathlengths_for(typed) if typed else None
        for well, var in self.entries.items():
            var.set(f"{known[well]:.4f}" if known and well in known else "")
        self.known_label.configure(
            text=TEXT["plate_known"] if known else "",
            style="Good.TLabel" if known else "Muted.TLabel",
        )

    def _serial_or_complain(self) -> str | None:
        serial = self.serial.get().strip()
        if not serial:
            messagebox.showwarning(TEXT["plate_dialog_title"],
                                   TEXT["plate_bad_serial"], parent=self)
            return None
        return serial

    def _nominal(self) -> None:
        """Register the plate without a sheet. Honest, and flagged on the screen."""
        serial = self._serial_or_complain()
        if serial:
            self.result = (serial, {})
            self.destroy()

    def _save(self) -> None:
        serial = self._serial_or_complain()
        if not serial:
            return

        table: dict[str, float] = {}
        missing = []
        for well, var in self.entries.items():
            text = var.get().strip().replace(",", ".")
            if not text:
                missing.append(well)
                continue
            try:
                value = float(text)
            except ValueError:
                messagebox.showwarning(
                    TEXT["plate_dialog_title"],
                    TEXT["plate_bad_value"].format(well=well, value=var.get()),
                    parent=self)
                return
            if not 0.2 <= value <= 1.2:
                messagebox.showwarning(
                    TEXT["plate_dialog_title"],
                    TEXT["plate_bad_value"].format(well=well, value=var.get()),
                    parent=self)
                return
            table[well] = value

        if missing:
            messagebox.showwarning(
                TEXT["plate_dialog_title"],
                TEXT["plate_incomplete"].format(n=len(missing)), parent=self)
            return

        self.result = (serial, table)
        self.destroy()


def connect_backend(force_simulator: bool = False):
    """The real instrument, or None when it does not answer.

    It used to fall back to the simulator, so that an Epoch that was merely
    switched off produced a screen full of invented numbers behind a warning
    banner. That is the wrong failure: a quantification that cannot happen
    should look like nothing, not like a result. Without an instrument the
    program opens with reading disabled and waits for one to appear.

    The simulator is still here, for the tests and for looking at the screen
    without hardware, but it has to be asked for.
    """
    if force_simulator:
        return MockReader()

    reader = EpochReader(expected_serial=PLATE_READER_SERIAL)
    try:
        reader.connect()
        return reader
    except (ReaderError, NotImplementedError, OSError) as exc:
        print(f"No reader: {exc}\nReading is disabled until one is found.",
              file=sys.stderr)
        return None


def main() -> int:
    force = "--sim" in sys.argv or os.environ.get("EPOCH_GUI_SIM") == "1"
    enable_dpi_awareness()          # before any Tk window exists
    App(connect_backend(force), watch=not force).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
