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
from .quant import (QuantError, blank_for, check_blanks, quantify, unit_for,
                    wavelengths_for)
from .reader import EpochReader, MockReader, ReaderError, ReaderInfo
from .xlsx import export_results

TEXT = {
    "title": "Cuantificacion Take3 - Epoch",
    "simulated": "MODO SIMULACION - no hay lector conectado. Los numeros NO son medidas reales.",
    "connected": "Lector {model}, serie {serial}, firmware {firmware}, en {port}",
    "searching": "MODO SIMULACION - buscando el lector... Los numeros NO son medidas reales.",
    "lost": "EL LECTOR NO RESPONDE - comprueba que sigue encendido. Reintentando...",
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
    "clear_samples": "Limpiar",
    "all_samples": "Todos",
    "wavelengths": "Longitudes de onda: {list}",
    # "Camino optico" is the correct term and it is what the data sheet says, but
    # it told the reader nothing. The physical quantity is how thick the drop is
    # where the light crosses it, so the label says that.
    "plate_calibrated": "calibrada",
    "plate_uncalibrated": "SIN CALIBRAR",
    "plate_change": "Cambiar placa...",
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


class RoundedButton(tk.Canvas):
    """A flat button with rounded corners, drawn rather than themed.

    tkinter's Button has no corner radius and ttk's themes will not give one, so
    the shape is drawn on a canvas. It accepts the same bg/fg/text/state keywords
    the rest of the screen already passes to Button, so it drops straight in
    wherever one was used.
    """

    def __init__(self, parent, text="", command=None, width=70, height=26,
                 radius=4, bg="#1e293b", fg="#e2e8f0", outline="",
                 hover=None, parent_bg="#0f172a",
                 font=("TkDefaultFont", 9), stretch=False):
        super().__init__(parent, width=width, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0, takefocus=0)
        self._text = text
        self._command = command
        self._radius = radius
        self._bg = bg
        self._fg = fg
        self._outline = outline
        self._hover = hover
        self._font = font
        self._state = "normal"
        self._hovering = False

        self.bind("<Button-1>", self._clicked)
        self.bind("<Enter>", self._entered)
        self.bind("<Leave>", self._left)
        # Redraw whenever the real size is known, not only when stretching: the
        # size at construction time is the requested one, not the mapped one.
        self.bind("<Configure>", lambda _e: self._draw())
        self._draw()

    # -- drawing ------------------------------------------------------------

    def _rounded(self, x1, y1, x2, y2, r, **kw):
        """A rounded rectangle as a smoothed polygon."""
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=12, **kw)

    def _draw(self) -> None:
        self.delete("all")
        # An unmapped widget reports 1, not 0, so this cannot be an "or": every
        # well was being drawn one pixel wide until the first redraw.
        width = self.winfo_width()
        if width <= 1:
            width = int(super().cget("width"))
        height = self.winfo_height()
        if height <= 1:
            height = int(super().cget("height"))

        fill = self._bg
        if self._hovering and self._state == "normal" and self._hover:
            fill = self._hover

        self._rounded(1, 1, width - 1, height - 1, self._radius,
                      fill=fill, outline=self._outline or fill,
                      width=1 if self._outline else 1)
        self.create_text(width / 2, height / 2, text=self._text,
                         fill=self._fg, font=self._font)

    # -- behaviour ----------------------------------------------------------

    def _clicked(self, _event) -> None:
        if self._state == "normal" and self._command:
            self._command()

    def _entered(self, _event) -> None:
        self._hovering = True
        if self._state == "normal":
            self.configure(cursor="hand2")
        self._draw()

    def _left(self, _event) -> None:
        self._hovering = False
        self._draw()

    # -- the Button-shaped interface the rest of the screen uses -------------

    def configure(self, **kw):           # noqa: D102 - matches tk.Button
        redraw = False
        for key in ("bg", "background"):
            if key in kw:
                self._bg = kw.pop(key)
                redraw = True
        for key in ("fg", "foreground"):
            if key in kw:
                self._fg = kw.pop(key)
                redraw = True
        if "text" in kw:
            self._text = kw.pop("text")
            redraw = True
        if "font" in kw:
            self._font = kw.pop("font")
            redraw = True
        if "outline" in kw:
            self._outline = kw.pop("outline")
            redraw = True
        if "hover" in kw:
            self._hover = kw.pop("hover")
            redraw = True
        if "state" in kw:
            self._state = kw.pop("state")
            redraw = True
        kw.pop("activebackground", None)
        kw.pop("activeforeground", None)
        kw.pop("disabledforeground", None)
        if kw:
            super().configure(**kw)
        if redraw:
            self._draw()
        return None

    config = configure

    def cget(self, key):                 # noqa: D102 - matches tk.Button
        return {
            "bg": self._bg, "background": self._bg,
            "fg": self._fg, "foreground": self._fg,
            "text": self._text, "state": self._state,
            "font": self._font,
        }.get(key, super().cget(key))

    def __getitem__(self, key):
        return self.cget(key)

# One place for colour, so the screen stays coherent. Greens mean "ready" or
# "chosen", red means "stop", amber marks a row that needs a second look.
#
# Dark theme. The two semantic colours that do not survive the move are called
# out: a dark bottle green and a cream warning row both vanish against slate, so
# "ready" becomes the emerald accent and the warning row becomes dark amber.
INK        = "#e2e8f0"      # main text
MUTED      = "#94a3b8"      # hints and secondary labels
LINE       = "#334155"      # borders
CANVAS     = "#0f172a"      # window background
PANEL      = "#1e293b"      # cards
CHOSEN     = "#10b981"      # a selected well
CHOSEN_INK = "#04231a"
EMPTY      = "#243244"      # an unselected well
GOOD       = "#10b981"      # connected, blank done
BAD        = "#f43f5e"      # simulation, blank missing
WARN_ROW   = "#422006"      # a result with something to say
ZEBRA      = "#172033"      # every other table row
TITLE_BAR  = "#111c33"      # the app's own title strip
WARN_BADGE = "#f59e0b"      # simulation: amber badge, dark text
WARN_BADGE_INK = "#2b1a02"
GOOD_BADGE = "#10b981"      # connected
GOOD_BADGE_INK = "#04231a"

# The wells. A blank is water and a sample is material, so they are not the same
# green: the blank grid is a soft mint that reads as "prepared", the sample grid
# a vivid green that reads as "loaded". An empty well is outline only.
WELL_LINE       = "#475569"   # muted slate outline, unselected
WELL_INK        = "#cbd5e1"
BLANK_WELL      = "#6ee7b7"   # soft green, dark text
BLANK_WELL_INK  = "#04231a"
SAMPLE_WELL     = "#16a34a"   # vivid green
SAMPLE_WELL_INK = "#ffffff"
ACTION     = "#3b82f6"      # the button to press next
ACTION_HOVER = "#60a5fa"
ACTION_INK  = "#ffffff"
ACTION_IDLE = "#334155"     # usable, but not the obvious next step
ACTION_IDLE_HOVER = "#415577"
ACTION_OFF = "#1b2537"      # would not do anything yet
ACTION_OFF_INK = "#64748b"
ACTION_INK = "#ffffff"

# Read from epoch_open.json beside the program; see epoch_open/config.py. Nothing
# here is tied to one lab: a different reader and a different Take3 plate need a
# config file, not a rebuild.
CONFIG = config.load()
PLATE_SERIAL = CONFIG.plate_serial
PLATE_READER_SERIAL = CONFIG.reader_serial


class App(tk.Tk):
    PROBE_MS = 3000          # how often to look for the reader

    def __init__(self, backend=None, watch: bool = False):
        super().__init__()
        self.title(f'{TEXT["title"]}  {__version__}')
        self._size_to_screen()

        self.backend = backend or MockReader()
        self.simulated = isinstance(self.backend, MockReader)

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
        self.info = (
            self.backend.connect() if self.simulated
            else ReaderInfo(model="Epoch", serial=self.backend.expected_serial or "?",
                            firmware="1.12", port=self.backend.port or "?")
        )

        self.blank_selected: set[str] = set()
        self.sample_selected: set[str] = set()
        self.blank_buttons: dict[str, tk.Button] = {}
        self.sample_buttons: dict[str, tk.Button] = {}
        self.action_buttons: dict[str, tk.Button] = {}

        self.sample_names: dict[str, str] = {}
        self.plate_serial = CONFIG.plate_serial
        self.pathlengths = CONFIG.pathlengths

        self.blank: dict | None = None
        self.results: list = []          # (read_number, QuantResult)
        self.read_number = 0

        self._style()
        self._build()
        self._refresh_state()

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

    def _size_to_screen(self) -> None:
        """Open at a sensible size for whatever screen this is, and centre it.

        A fixed 1120x720 was wider than a 1366x768 laptop can show once the
        window border and taskbar are taken off, and the column that fell off
        the right-hand edge was the one carrying the warnings.
        """
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        width = min(1180, screen_w - 80)
        height = min(980, screen_h - 70)
        self.minsize(min(900, width), min(600, height))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Readable at arm's length on a roomy screen, but a cramped laptop needs
        # the space more than it needs the extra point.
        self.tiny = screen_h < 760
        self.compact = screen_h < 1000
        self.base_pt = 10 if self.compact else 11
        self.ui_font = self._pick_font()

    def _pick_font(self) -> str:
        """The platform's own interface face, falling back to Tk's default.

        Named explicitly rather than left to TkDefaultFont, which on Windows is
        still Tahoma 8 on some systems and looks a decade out of date.
        """
        from tkinter import font as tkfont

        available = {name.lower() for name in tkfont.families(self)}
        for candidate in ("Segoe UI", "SF Pro Text", "Helvetica Neue",
                          "Ubuntu", "Cantarell", "DejaVu Sans"):
            if candidate.lower() in available:
                return candidate
        return "TkDefaultFont"

    def _style(self) -> None:
        """Tk's default theme is the 1990s Motif look. 'clam' is plain but current."""
        self.configure(bg=CANVAS)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        pt = self.base_pt
        family = self.ui_font
        base = (family, pt)
        style.configure(".", background=CANVAS, foreground=INK, font=base)
        style.configure("TFrame", background=CANVAS)
        style.configure("TLabel", background=CANVAS, foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Good.TLabel", foreground=GOOD)
        style.configure("Bad.TLabel", foreground=BAD)
        style.configure("Head.TLabel", font=(family, pt + 3, "bold"))

        style.configure("Card.TLabelframe", background=PANEL,
                        bordercolor=LINE, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=PANEL,
                        foreground=MUTED, font=(family, pt, "bold"))
        style.configure("Card.TFrame", background=PANEL)
        style.configure("Card.TLabel", background=PANEL, foreground=INK)
        style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED,
                        font=(family, pt - 1))

        style.configure("TButton", padding=(10, 6), font=base,
                        background=PANEL, foreground=INK,
                        bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL,
                        focuscolor=ACTION, relief="flat")
        style.map("TButton",
                  background=[("active", "#2d3c52")],
                  foreground=[("active", INK)])

        # No vertical separators: clam draws them through the body and the
        # headings, and they fight with the numbers. Rows are told apart by
        # alternating background instead, which ttk.Treeview can actually do --
        # it has no per-row rule, so a hairline divider is not on offer.
        style.configure("Treeview",
                        background=PANEL, fieldbackground=PANEL,
                        foreground=INK, rowheight=pt * 2 + 14,
                        borderwidth=0, relief="flat", font=base)
        style.configure("Treeview.Heading", font=(family, pt, "bold"),
                        background=CANVAS, foreground=MUTED,
                        relief="flat", borderwidth=0, padding=(8, 10))
        style.map("Treeview.Heading", background=[("active", CANVAS)])
        style.map("Treeview",
                  background=[("selected", "#2d3c52")],
                  foreground=[("selected", INK)])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        style.configure("TEntry", fieldbackground=PANEL, foreground=INK,
                        bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                        insertcolor=INK, padding=4)
        style.configure("TCheckbutton", background=CANVAS, foreground=INK,
                        indicatorcolor=PANEL, font=base)
        style.map("TCheckbutton",
                  background=[("active", CANVAS)],
                  indicatorcolor=[("selected", ACTION)])
        style.configure("TCombobox", padding=4, arrowcolor=INK,
                        fieldbackground=PANEL, background=PANEL,
                        foreground=INK, bordercolor=LINE,
                        lightcolor=PANEL, darkcolor=PANEL)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", ACTION)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        style.configure("Dark.Vertical.TScrollbar",
                        background=LINE, troughcolor=CANVAS,
                        bordercolor=CANVAS, arrowcolor=MUTED,
                        lightcolor=LINE, darkcolor=LINE, relief="flat")
        style.map("Dark.Vertical.TScrollbar",
                  background=[("active", "#475569")])

    # ---------------------------------------------------------------- layout

    def _build(self) -> None:
        self._build_banner()

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

        self.status = tk.Label(
            self, text=self._idle_text(), anchor="w", justify="left",
            bg=TITLE_BAR, fg=MUTED, padx=16, pady=5 if self.compact else 8,
            font=(self.ui_font, self.base_pt - 1),
        )
        self.status.pack(fill="x", side="bottom")

    def _build_banner(self) -> None:
        """The app's own title bar, with the connection badge sitting in it."""
        bar = tk.Frame(self, bg=TITLE_BAR)
        bar.pack(fill="x")

        tk.Label(bar, text=TEXT["title"], bg=TITLE_BAR, fg=INK,
                 font=(self.ui_font, self.base_pt + 4, "bold"),
                 padx=16, pady=7 if self.compact else 12).pack(side="left")
        tk.Label(bar, text=__version__, bg=TITLE_BAR, fg=MUTED,
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
        if self.lost:
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
                    grid, text=name, width=72,
                    height=20 if self.tiny else (22 if self.compact else 28), radius=4,
                    bg=EMPTY, fg=WELL_INK, outline=WELL_LINE,
                    hover="#2d3c52", parent_bg=PANEL,
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

        controls = ttk.Frame(frame, style="Card.TFrame")
        controls.pack(fill="x", pady=(8, 0))
        if nameable:
            ttk.Button(controls, text=TEXT["all_samples"],
                       command=lambda: self._select_all(selection, buttons)).pack(
                side="left", expand=True, fill="x", padx=1)
        ttk.Button(controls, text=TEXT["clear_blank"],
                   command=lambda: self._clear(selection, buttons)).pack(
            side="left", expand=True, fill="x", padx=1)

        # On a laptop screen this line is what pushes the buttons off the
        # bottom. The short status bar says the same thing there.
        if nameable and not self.compact:
            ttk.Label(frame, text=TEXT["naming_hint"], wraplength=220,
                      style="CardMuted.TLabel").pack(pady=(6, 0))

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
                height=34 if self.compact else 42, radius=6,
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
        for column, width in zip(TEXT["columns"], (130, 115, 90, 90, 240)):
            self.table.heading(
                column, text=column,
                anchor="e" if column in numeric else "w",
            )
            self.table.column(column, width=width,
                              anchor="e" if column in numeric else "w",
                              stretch=(column == TEXT["columns"][-1]),
                              minwidth=60)
        self.table.column(TEXT["columns"][-1], anchor="w", minwidth=120)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview,
                                  style="Dark.Vertical.TScrollbar")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.tag_configure("odd", background=ZEBRA)
        self.table.tag_configure("even", background=PANEL)
        self.table.tag_configure("warn", background=WARN_ROW, foreground="#fde68a")

    # --------------------------------------------------------------- state

    def _toggle(self, name, selection, buttons) -> None:
        button = buttons[name]
        if name in selection:
            selection.discard(name)
            button.configure(bg=EMPTY, fg=WELL_INK, outline=WELL_LINE,
                             hover="#2d3c52",
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
        if self.blank:
            self.blank_label.configure(
                text=TEXT["blank_done"].format(wells=", ".join(sorted(self.blank))),
                style="Good.TLabel",
            )
        else:
            self.blank_label.configure(text=TEXT["blank_pending"], style="Bad.TLabel")

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
        if self.blank is None:
            nxt = "read_blank"
        elif not self.results:
            nxt = "read_samples"
        else:
            nxt = "end_batch"

        usable = {
            "read_blank": True,
            "read_samples": self.blank is not None,
            "end_batch": bool(self.results),
        }
        for key, button in self.action_buttons.items():
            if not usable[key]:
                button.configure(state="disabled", bg=ACTION_OFF,
                                 fg=ACTION_OFF_INK, hover=None, cursor="")
            else:
                is_next = key == nxt
                button.configure(
                    state="normal", cursor="hand2", fg=ACTION_INK,
                    bg=ACTION if is_next else ACTION_IDLE,
                    hover=ACTION_HOVER if is_next else ACTION_IDLE_HOVER,
                )

    def _idle_text(self) -> str:
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
        return self.simulated or self.lost

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
        self.info = ReaderInfo(
            model="Epoch", serial=reader.expected_serial or "?",
            firmware="1.12", port=reader.port or "?",
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
            self.blank = self._read(wells, as_blank=True)
        except (ReaderError, NotImplementedError, OSError) as exc:
            self._mark_lost()
            messagebox.showerror(TEXT["title"], TEXT["read_error"].format(error=exc))
            self._say(self._idle_text())
            return

        for warning in check_blanks(self.blank):
            messagebox.showwarning(TEXT["title"], warning.message)

        self._refresh_state()
        self._say(TEXT["blank_ok"].format(time=datetime.now().strftime("%H:%M")))

    def _read_samples(self) -> None:
        wells = sorted(self.sample_selected)
        if not wells:
            messagebox.showinfo(TEXT["title"], TEXT["no_sample_wells"])
            return
        if self.blank is None:
            messagebox.showinfo(TEXT["title"], TEXT["no_blank"])
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
                             sample_type, self.pathlengths),
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
        self.blank = None
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
    """The real instrument when it answers, the simulator when it does not.

    Falling back rather than failing matters: the technician can still look at the
    program, and the red banner makes the difference impossible to miss.
    """
    if force_simulator:
        return MockReader()

    reader = EpochReader(expected_serial=PLATE_READER_SERIAL)
    try:
        reader.connect()
        return reader
    except (ReaderError, NotImplementedError, OSError) as exc:
        print(f"No reader: {exc}\nStarting in simulation mode.", file=sys.stderr)
        return MockReader()


def main() -> int:
    force = "--sim" in sys.argv or os.environ.get("EPOCH_GUI_SIM") == "1"
    App(connect_backend(force), watch=not force).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
