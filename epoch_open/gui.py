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
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import config, take3
from .quant import QuantError, blank_for, check_blanks, quantify, wavelengths_for
from .reader import EpochReader, MockReader, ReaderError, ReaderInfo
from .xlsx import export_results

TEXT = {
    "title": "Cuantificacion Take3 - Epoch",
    "simulated": "MODO SIMULACION - no hay lector conectado. Los numeros NO son medidas reales.",
    "connected": "Lector {model}, serie {serial}, firmware {firmware}, en {port}",
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
    "path_sheet": "Espesor de gota: medido pozo a pozo (hoja de la placa {serial})",
    "path_nominal": "Espesor de gota: 0,5 mm nominal (sin hoja de la placa)",
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
    "columns": ("Lectura:Pozo", "Conc.", "260/280", "260/230", "Unidad", "Aviso"),
    "instructions": (
        "1. Carga 2 uL de agua en los pozos del blanco y pulsa 'Leer blanco'.\n"
        "2. Limpia, carga 2 uL de cada muestra y pulsa 'Leer muestras'. "
        "Puedes repetir con mas placas; todo se acumula en el mismo lote.\n"
        "3. Cuando termines, pulsa 'Fin del lote' para guardar el Excel."
    ),
}

SAMPLE_TYPES = ("dsDNA", "ssDNA", "RNA", "protein")

# One place for colour, so the screen stays coherent. Greens mean "ready" or
# "chosen", red means "stop", amber marks a row that needs a second look.
INK        = "#1f2933"      # main text
MUTED      = "#5c6b7a"      # hints and secondary labels
LINE       = "#d4dae0"      # borders
CANVAS     = "#f4f6f8"      # window background
PANEL      = "#ffffff"      # cards
CHOSEN     = "#4f9d3a"      # a selected well
CHOSEN_INK = "#ffffff"
EMPTY      = "#fbfcfd"      # an unselected well
GOOD       = "#1b5e20"      # connected, blank done
BAD        = "#b00020"      # simulation, blank missing
WARN_ROW   = "#fff6e6"      # a result with something to say
ACTION     = "#2f6fb0"      # the three main buttons
ACTION_INK = "#ffffff"

# Read from epoch_open.json beside the program; see epoch_open/config.py. Nothing
# here is tied to one lab: a different reader and a different Take3 plate need a
# config file, not a rebuild.
CONFIG = config.load()
PLATE_SERIAL = CONFIG.plate_serial
PLATE_READER_SERIAL = CONFIG.reader_serial


class App(tk.Tk):
    def __init__(self, backend=None):
        super().__init__()
        self.title(TEXT["title"])
        self.minsize(1120, 720)

        self.backend = backend or MockReader()
        self.simulated = isinstance(self.backend, MockReader)
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

        self.sample_names: dict[str, str] = {}
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

    # ---------------------------------------------------------------- styling

    def _style(self) -> None:
        """Tk's default theme is the 1990s Motif look. 'clam' is plain but current."""
        self.configure(bg=CANVAS)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        base = ("TkDefaultFont", 10)
        style.configure(".", background=CANVAS, foreground=INK, font=base)
        style.configure("TFrame", background=CANVAS)
        style.configure("TLabel", background=CANVAS, foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Good.TLabel", foreground=GOOD)
        style.configure("Bad.TLabel", foreground=BAD)
        style.configure("Head.TLabel", font=("TkDefaultFont", 11, "bold"))

        style.configure("Card.TLabelframe", background=PANEL,
                        bordercolor=LINE, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=PANEL,
                        foreground=MUTED, font=("TkDefaultFont", 9, "bold"))
        style.configure("Card.TFrame", background=PANEL)
        style.configure("Card.TLabel", background=PANEL, foreground=INK)
        style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED,
                        font=("TkDefaultFont", 9))

        style.configure("TButton", padding=(10, 5))
        style.map("TButton", background=[("active", "#e8edf2")])

        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        rowheight=24, borderwidth=0)
        style.configure("Treeview.Heading", font=("TkDefaultFont", 9, "bold"),
                        padding=(4, 5))
        style.configure("TCheckbutton", background=CANVAS)
        style.configure("TCombobox", padding=3)

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
            self, text=TEXT["instructions"], anchor="w", justify="left",
            bg="#e9eef3", fg=INK, padx=14, pady=9,
            font=("TkDefaultFont", 9),
        )
        self.status.pack(fill="x", side="bottom")

    def _build_banner(self) -> None:
        if self.simulated:
            text, bg = TEXT["simulated"], BAD
        else:
            text = TEXT["connected"].format(
                model=self.info.model, serial=self.info.serial,
                firmware=self.info.firmware, port=self.info.port,
            )
            bg = GOOD
        tk.Label(self, text=text, bg=bg, fg="white", pady=9,
                 font=("TkDefaultFont", 11, "bold")).pack(fill="x")

    def _build_header(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 6))

        ttk.Label(frame, text=TEXT["plate"].format(serial=PLATE_SERIAL),
                  style="Head.TLabel").pack(anchor="w", pady=(0, 4))

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

        basis = (TEXT["path_sheet"].format(serial=PLATE_SERIAL) if self.pathlengths
                 else TEXT["path_nominal"])
        ttk.Label(frame, text=basis,
                  style="Good.TLabel" if self.pathlengths else "Muted.TLabel"
                  ).pack(anchor="w")

    def _build_grid(self, parent, title, selection, buttons, nameable) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=8,
                               style="Card.TLabelframe")
        frame.pack(side="left", fill="y", padx=(0, 8))

        ttk.Label(frame, text=(TEXT["grid_hint_sample"] if nameable
                               else TEXT["grid_hint_blank"]),
                  style="CardMuted.TLabel").pack(pady=(0, 6))

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
                button = tk.Button(
                    grid, text=name, width=7, bg=EMPTY, fg=INK,
                    relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=LINE, highlightcolor=LINE,
                    activebackground="#e8edf2", padx=0, pady=3,
                    font=("TkDefaultFont", 9),
                    command=lambda n=name, s=selection, b=buttons: self._toggle(n, s, b),
                )
                button.grid(row=row_index + 1, column=position + 1, padx=2, pady=2)
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

        if nameable:
            ttk.Label(frame, text=TEXT["naming_hint"], wraplength=220,
                      style="CardMuted.TLabel").pack(pady=(6, 0))

    def _build_buttons(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(6, 0))

        self.blank_label = ttk.Label(frame, text="", style="Bad.TLabel")
        self.blank_label.pack()
        self.batch_label = ttk.Label(frame, text="", style="Muted.TLabel")
        self.batch_label.pack(pady=(0, 8))

        for key, command in (("read_blank", self._read_blank),
                             ("read_samples", self._read_samples),
                             ("end_batch", self._end_batch)):
            tk.Button(frame, text=TEXT[key], command=command,
                      bg=ACTION, fg=ACTION_INK, activebackground="#255a91",
                      activeforeground=ACTION_INK, relief="flat", bd=0,
                      pady=11, font=("TkDefaultFont", 10, "bold"),
                      cursor="hand2").pack(fill="x", pady=3)

    def _build_results(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text="Resultados", padding=8,
                               style="Card.TLabelframe")
        frame.pack(fill="both", expand=True)

        self.table = ttk.Treeview(frame, columns=TEXT["columns"],
                                  show="headings", height=26)
        for column, width in zip(TEXT["columns"], (120, 95, 75, 75, 65, 330)):
            self.table.heading(column, text=column)
            self.table.column(column, width=width, anchor="center")
        self.table.column(TEXT["columns"][-1], anchor="w")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.tag_configure("warn", background=WARN_ROW)

    # --------------------------------------------------------------- state

    def _toggle(self, name, selection, buttons) -> None:
        button = buttons[name]
        if name in selection:
            selection.discard(name)
            button.configure(bg=EMPTY, fg=INK, font=("TkDefaultFont", 9))
        else:
            selection.add(name)
            button.configure(bg=CHOSEN, fg=CHOSEN_INK,
                             font=("TkDefaultFont", 9, "bold"))
        self._refresh_state()

    def _select_all(self, selection, buttons) -> None:
        for name in buttons:
            if name not in selection:
                self._toggle(name, selection, buttons)

    def _clear(self, selection, buttons) -> None:
        for name in list(selection):
            self._toggle(name, selection, buttons)

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

    # -------------------------------------------------------------- actions

    def _read(self, wells: list[str], as_blank: bool):
        if isinstance(self.backend, MockReader):
            # Simulation only: tell the fake instrument what is on the plate.
            self.backend.simulating_blank = as_blank
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
        except (ReaderError, NotImplementedError) as exc:
            messagebox.showerror(TEXT["title"], TEXT["read_error"].format(error=exc))
            self._say(TEXT["instructions"])
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
        except (ReaderError, NotImplementedError) as exc:
            messagebox.showerror(TEXT["title"], TEXT["read_error"].format(error=exc))
            self._say(TEXT["instructions"])
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

        for read_number, result in self.results:
            note = "; ".join(w.short for w in result.warnings)
            label = self.sample_names.get(result.well, result.well)
            self.table.insert(
                "", "end",
                values=(f"{read_number}:{label}",
                        shown(result.concentration, 1),
                        shown(result.ratio_260_280, 2),
                        shown(result.ratio_260_230, 2),
                        result.unit, note),
                tags=("warn",) if note else (),
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
            "Placa Take3": PLATE_SERIAL,
            "Espesor de gota": ("medido pozo a pozo, hoja de la placa"
                                if self.pathlengths else "0,5 mm nominal"),
            "Lector": self.info.model,
            "Numero de serie": self.info.serial,
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
    App(connect_backend(force)).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
