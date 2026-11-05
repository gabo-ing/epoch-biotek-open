"""The look the Epoch programs share, and the window behaviour behind it.

Two programs now talk to the same reader -- Take3 quantification and the
colorimetric standard-curve reader -- and they are the same instrument on the
same bench in front of the same technician, so they have to look like one
family rather than two unrelated tools.

What lives here is only what is genuinely common: the palette, the drawn
button, the platform font, and the window fitting. Nothing about an assay.
The screen-fitting code in particular is here because duplicating it is how it
would drift, and it has already been wrong once -- the window used to open
taller than a laptop screen could show, putting the status bar under the
taskbar. Fixing that twice is not a plan.
"""

import sys
import tkinter as tk
from tkinter import ttk


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
        """The button's own keywords first, then whatever the Canvas knows.

        The membership test is the point. Written the obvious way --
        `{...}.get(key, super().cget(key))` -- Python builds the default
        before `get` decides whether it is needed, so every lookup also asked
        the Canvas, and a Canvas has no `-text` or `-font` option. Asking a
        button for its own label therefore raised TclError while the answer
        was sitting in the dict.
        """
        own = {
            "bg": self._bg, "background": self._bg,
            "fg": self._fg, "foreground": self._fg,
            "text": self._text, "state": self._state,
            "font": self._font,
        }
        if key in own:
            return own[key]
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)

# One place for colour, so the screen stays coherent. Greens mean "ready" or
# "chosen", red means "stop", amber marks a row that needs a second look.
#
# Light, and deliberately close to Gen5's own Take3 screen: pale grey chrome, a
# blue header strip, white plate grids with blue-grey wells. The technician has
# used that screen for years, so the less this one asks her to relearn the
# better -- the colours are the part she reads without thinking.
INK        = "#1f2933"      # main text
MUTED      = "#5f6b7a"      # hints and secondary labels
LINE       = "#c3ccd6"      # borders
CANVAS     = "#eef1f5"      # window background
PANEL      = "#ffffff"      # cards
CHOSEN     = "#43a047"      # a selected well
CHOSEN_INK = "#ffffff"
EMPTY      = "#ffffff"      # an unselected well
GOOD       = "#2e7d32"      # connected, blank done
BAD        = "#c62828"      # simulation, blank missing
WARN_ROW   = "#fff4dc"      # a result with something to say
WARN_INK   = "#7a4a00"
ZEBRA      = "#f5f8fb"      # every other table row
TITLE_BAR  = "#3f72b0"      # the app's own title strip, as Gen5 heads a section
TITLE_INK  = "#ffffff"
TITLE_MUTED = "#d6e4f5"
STATUS_BAR = "#e4e9ef"      # the hint strip along the bottom
WARN_BADGE = "#f5b041"      # simulation: amber badge, dark text
WARN_BADGE_INK = "#4a3000"
GOOD_BADGE = "#2e7d32"      # connected
GOOD_BADGE_INK = "#ffffff"

# The wells. A blank is water and a sample is material, so they are not the same
# green: the blank grid is a soft green that reads as "prepared", the sample grid
# a solid green that reads as "loaded". An empty well is white with a blue-grey
# outline, which is how Gen5 draws an unselected microspot.
WELL_LINE       = "#9db8d8"   # pale blue outline, unselected
WELL_INK        = "#33414f"
WELL_HOVER      = "#eaf2fb"
BLANK_WELL      = "#cfe8d6"   # soft green, dark text: read and good
# A blank well goes through three states and each needs its own colour, because
# the technician works by scanning the grid rather than by reading the status
# block: marked but not yet read is pale blue, a valid reading is the soft green
# above, and one that does not agree with the rest is red, meaning "this is the
# spot to wipe". Gen5 does the same thing with coloured dots.
BLANK_PENDING     = "#cfe0f5"   # pale blue, chosen, nothing measured yet
BLANK_PENDING_INK = "#1d3a5f"
BAD_WELL          = "#f6cfcf"   # soft red fill, dark red text
BAD_WELL_INK      = "#7f1d1d"
BAD_WELL_LINE     = "#d98a8a"
BLANK_WELL_INK  = "#14532d"
SAMPLE_WELL     = "#43a047"   # solid green
SAMPLE_WELL_INK = "#ffffff"
ACTION     = "#3f72b0"      # the button to press next
ACTION_HOVER = "#5a8bc8"
ACTION_INK  = "#ffffff"
ACTION_IDLE = "#cfdceb"     # usable, but not the obvious next step
ACTION_IDLE_HOVER = "#bccfe3"
ACTION_IDLE_INK = "#24405e"  # dark text: white on pale blue is unreadable
ACTION_OFF = "#dde3ea"      # would not do anything yet
ACTION_OFF_INK = "#9aa5b1"
ACTION_INK = "#ffffff"


class ScreenFit:
    """Window sizing for a tk.Tk that must fit on whatever screen it finds.

    Mixed into a Tk subclass, which supplies the window methods used here.
    Call `_size_to_screen()` before building, and `_shrink_to_content()` after:
    the first picks a size against the screen, the second pulls it in to what
    the layout turned out to need.

    Also sets `scale`, `tiny`, `compact`, `base_pt` and `ui_font`, which the
    rest of a screen's measurements are written in terms of.
    """

    def _size_to_screen(self) -> None:
        """Open at a sensible size for whatever screen this is, and centre it.

        A fixed 1120x720 was wider than a 1366x768 laptop can show once the
        window border and taskbar are taken off, and the column that fell off
        the right-hand edge was the one carrying the warnings.
        """
        # How many real pixels the system puts in an inch. 96 is 100%; a laptop
        # at 150% reports 144. Points are handled by Tk once it is told the
        # scaling, but every hand-written pixel size has to be multiplied.
        dpi = self.winfo_fpixels("1i")
        self.scale = max(1.0, dpi / 96.0)
        self.tk.call("tk", "scaling", dpi / 72.0)

        work_w, work_h = self._work_area()

        # Decide the layout against logical space, not raw pixels: a 1920x1080
        # screen at 150% has the usable room of a 1280x720 one.
        logical_h = work_h / self.scale

        width = min(self.px(1180), work_w - self.px(40))
        height = min(self.px(980), work_h - self.px(40))
        self.minsize(min(self.px(900), width), min(self.px(600), height))

        self._place(width, height)

        # Readable at arm's length on a roomy screen, but a cramped laptop needs
        # the space more than it needs the extra point.
        # Decided from the whole screen, not the work area, and with the
        # threshold above 768.
        #
        # Both of those are the same bug, found on a 1366x768 laptop on
        # 4 November 2026. The tier came from the work area, so hiding the
        # taskbar moved it from 728 to 768 and across the old threshold of
        # 760 -- the program answered 40 px of extra screen by switching to a
        # layout about 100 px taller, and the save button went further off the
        # bottom than before. A toggling taskbar must not change which layout
        # is drawn, and a 768-tall screen is a short screen either way.
        panel_h = self.winfo_screenheight() / self.scale
        self.tiny = panel_h < 800
        self.compact = panel_h < 1000
        self.base_pt = 10 if self.compact else 11
        self.ui_font = self._pick_font()

    def _work_area(self) -> tuple[int, int]:
        """The part of the screen a window can actually occupy.

        winfo_screenheight() is the whole panel, taskbar and all, so sizing
        against it puts the bottom of the window underneath the taskbar --
        which is exactly where the status bar lives. Tk already knows better:
        on Windows wm maxsize is the work area, and on macOS it leaves out the
        menu bar. X11 usually just repeats the screen size, so the answer is
        sanity-checked and falls back rather than being trusted blindly.
        """
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        try:
            max_w, max_h = self.wm_maxsize()
        except tk.TclError:
            return screen_w, screen_h
        # Bigger than the screen, or implausibly small, means Tk is guessing.
        if not 0 < max_w <= screen_w or not 0 < max_h <= screen_h:
            return screen_w, screen_h
        if max_h < screen_h // 2:
            return screen_w, screen_h
        return max_w, max_h

    def _place(self, width: int, height: int) -> None:
        """Size the window and put it where the whole of it is on the screen."""
        work_w, work_h = self._work_area()
        width = min(width, work_w)
        height = min(height, work_h)
        # A third of the way down sits better than dead centre, but never so
        # far that the bottom edge -- the status bar -- leaves the screen.
        x = max(0, min((work_w - width) // 2, work_w - width))
        y = max(0, min((work_h - height) // 3, work_h - height))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _step_down_a_tier(self) -> bool:
        """Move to the next smaller layout, or report that there is none.

        `tiny` and `compact` are chosen from the screen's height before any
        widget exists, which can only ever be a guess: the same number of
        pixels holds a different amount of layout depending on the platform's
        font metrics. Tk on macOS draws this roughly two hundred pixels
        taller than Tk on Linux at the same nominal point size, so a Retina
        MacBook -- a large screen by any measure -- got the roomy layout and
        lost the action buttons off the bottom of the window.
        """
        if self.tiny:
            return False
        self.tiny = True
        self.compact = True
        self.base_pt = 10
        return True

    def _fit_to_screen(self, rebuild) -> None:
        """Draw it, and if it does not fit, draw it smaller.

        Called once after the first build with the method that builds the
        screen. The guess above is checked against the thing it was guessing
        about, which is the only way to be right on a platform nobody has
        measured.

        Only ever steps down, and only while nothing has been measured, so
        there is no reading to lose. A screen that still does not fit at the
        smallest layout is left alone: the window can be resized, and a
        further rebuild would only churn.
        """
        for _attempt in range(2):
            self.update_idletasks()
            _width, work_h = self._work_area()
            if self.winfo_reqheight() <= work_h - self.px(40):
                break
            if not self._step_down_a_tier():
                break
            for child in self.winfo_children():
                child.destroy()
            self._style()
            rebuild()
        self._shrink_to_content()

    def _shrink_to_content(self) -> None:
        """Pull the window in to what the layout actually asked for.

        The opening size is chosen before anything is built, so it is a guess
        made against the screen rather than against the contents. Once the
        widgets exist they can say how much room they want, and on a cramped
        laptop that difference is what decides whether the status bar lands
        above the taskbar or under it.

        Only ever shrinks. Growing here could push the window back off the
        screen it was just fitted to.
        """
        self.update_idletasks()
        want_w, want_h = self.winfo_reqwidth(), self.winfo_reqheight()
        if want_w < 100 or want_h < 100:      # not laid out yet; leave it be
            return
        try:
            now_w, now_h = (int(n) for n in
                            self.geometry().split("+")[0].split("x"))
        except ValueError:
            return
        min_w, min_h = self.minsize()
        width = max(min_w, min(now_w, want_w))
        height = max(min_h, min(now_h, want_h))
        if (width, height) != (now_w, now_h):
            self._place(width, height)

    def px(self, logical: int) -> int:
        """A hand-written pixel size, in this screen's real pixels."""
        return int(round(logical * getattr(self, "scale", 1.0)))

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
        style.configure("CardGood.TLabel", background=PANEL, foreground=GOOD)
        style.configure("CardBad.TLabel", background=PANEL, foreground=BAD)
        style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED,
                        font=(family, pt - 1))

        style.configure("TButton", padding=(10, 6), font=base,
                        background=PANEL, foreground=INK,
                        bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL,
                        focuscolor=ACTION, relief="flat")
        style.map("TButton",
                  background=[("active", "#dde6ef")],
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
                  background=[("selected", "#cfe0f3")],
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
                  background=[("active", "#aab6c4")])

    # ---------------------------------------------------------------- layout


def enable_dpi_awareness() -> None:
    """Stop Windows bitmap-stretching the window, which blurs every glyph.

    A process that does not declare itself DPI-aware is rendered at 96 dpi and
    then scaled up by the compositor, so on a laptop running at 125% or 150%
    the text is visibly soft. Declaring awareness means Tk draws at the real
    pixel size and the glyphs stay sharp; the layout then has to do its own
    scaling, which is what App.scale is for.

    Must be called before the first Tk window exists. A no-op anywhere but
    Windows, and harmless if the call is unavailable.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            # Per-monitor aware: correct when the laptop is docked to a second
            # screen at a different scaling.
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:          # pragma: no cover - older Windows
        pass


