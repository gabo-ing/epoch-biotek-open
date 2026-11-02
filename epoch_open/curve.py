"""Colorimetric assays read against a standard curve.

The Take3 side of this project turns an absorbance into a concentration with
physics: Beer-Lambert, a known extinction coefficient, and the measured
thickness of the drop. A colorimetric assay cannot do that. The coloured
product's extinction coefficient depends on the reagent, the acid, the
temperature and how long the colour was left to develop, so nobody tabulates
it. Instead you measure known concentrations alongside the unknowns and read
the unknowns off the line they make.

That changes what the program has to be careful about:

1. **Pathlength drops out entirely.** It is the same for every well in a flat
   plate filled to the same volume, so it scales the standards and the samples
   by the same factor and cancels in the fit. There is no data sheet to copy
   and no per-well table -- but the volume really does have to be the same in
   every well, which is a pipetting discipline rather than something the
   software can check.

2. **The curve itself can be wrong.** A bad standard, a saturated top point or
   a transcription slip in the concentrations produces a confident-looking
   line and silently wrong answers for everything read against it. So the fit
   is reported with its r-squared and its residuals, and refuses rather than
   guesses when it has too little to go on.

3. **Extrapolation is not interpolation.** A sample above the top standard is
   not "high", it is unmeasured: colorimetric assays flatten off as the
   reagent is used up, so the line stops being a line exactly where the
   evidence stops. Those samples are flagged to be diluted and read again,
   never reported as a number alone.

The default assay is Salkowski for indole-3-acetic acid, read at 530 nm, but
nothing here is specific to it: the wavelength, the units and the standards
are all the caller's business.
"""

from dataclasses import dataclass, field

# Where to read the coloured product. 530 nm is the usual figure for Salkowski
# IAA work, but published protocols range over 530-540 and the true peak moves
# with the reagent formulation, so this is a default to be overridden rather
# than a constant to be trusted. The program can scan for the real peak; see
# `SCAN_NM` and `peak_wavelength`.
DEFAULT_NM = 530

# An optional second wavelength, subtracted from the measurement the way 320 nm
# is on the Take3 side. In the visible it corrects for turbidity and for marks
# on the plate bottom, which affect both wavelengths about equally while the
# coloured product absorbs at only one. Off by default: the standard protocol
# does not use it, and switching it on changes the numbers, so it has to be a
# deliberate choice applied to the standards as well.
DEFAULT_REFERENCE_NM = 650

# A spread of visible wavelengths for finding where the product actually
# absorbs. Nine because the reader takes at most nine in a single pass -- the
# wavelength count field in the 'D' assay record holds one digit -- so this
# costs exactly one read.
SCAN_NM = (490, 505, 520, 530, 545, 560, 575, 590, 605)

# Least-squares needs two points for a line and a third before r-squared says
# anything at all: with two points it is exactly 1 whatever they are, which
# would report a perfect curve for no reason. Five or more is normal practice.
MIN_STANDARDS = 3
THIN_STANDARDS = 4

# How good the fit has to look before the numbers read off it are reported
# without comment.
#
# This is a convention, not a measurement from this lab: 0.98 is the figure
# usually asked of a working standard curve, and 0.99 of a good one. It is
# worth saying plainly that it is weak evidence on its own -- r-squared is
# insensitive to exactly the failure that matters here, a top standard that
# has begun to saturate, because a gently bending curve still fits a line
# well. That is what `worst_residual` is reported for.
R_SQUARED_MIN = 0.98

# A single standard sitting this far off the line is called out by name, as a
# fraction of the full absorbance range the curve covers. A curve can keep a
# respectable r-squared with one badly placed point, and that point is usually
# a pipetting mistake worth knowing about.
RESIDUAL_LIMIT = 0.10

DEFAULT_UNIT = "ug/mL"


class CurveError(ValueError):
    """Raised when there is not enough to build a defensible curve."""


# Spanish, because that is the language of the lab that uses this.
MESSAGES = {
    "above_range": (
        "Absorbancia ({absorbance:.3f}) por encima del patron mas alto "
        "({top:.3f}). La curva no llega hasta aqui: diluye la muestra y "
        "vuelve a leerla. El numero que aparece es una extrapolacion."
    ),
    "below_range": (
        "Absorbancia ({absorbance:.3f}) por debajo del patron mas bajo. "
        "La muestra esta por debajo de lo que esta curva puede medir."
    ),
    "negative": (
        "Concentracion negativa: la muestra leyo por debajo del blanco de "
        "reactivo. Suele ser el blanco contaminado, o reactivo de mas en el "
        "pozo de la muestra."
    ),
    "turbid": (
        "Referencia {reference_nm} nm alta ({reference:.3f}): el pozo esta "
        "turbio. Centrifuga o filtra el sobrenadante y vuelve a leer; la "
        "dispersion sube la absorbancia sin que haya color."
    ),
}

SHORT_MESSAGES = {
    "above_range": "Fuera de curva: diluir y repetir",
    "below_range": "Por debajo de la curva",
    "negative": "Concentracion negativa",
    "turbid": "Pozo turbio",
}

# Said about the curve as a whole rather than about one sample.
FIT_MESSAGES = {
    "r_squared": (
        "La curva ajusta mal (r2 = {r_squared:.4f}, por debajo de "
        "{limit:.2f}). Revisa los patrones antes de usar estos resultados."
    ),
    "thin": (
        "Solo {n} patrones. La curva se sostiene, pero con tan pocos puntos un "
        "error de pipeteo no se distingue de la pendiente real."
    ),
    "outlier": (
        "El patron {well} ({concentration:g} {unit}) se sale de la linea mas "
        "que los demas. Comprueba su dilucion, o quitalo y vuelve a ajustar."
    ),
    "slope": (
        "La curva baja en vez de subir, o es plana. Con mas color se absorbe "
        "mas, asi que algo esta al reves: patrones intercambiados, longitud "
        "de onda equivocada, o reactivo que no reacciono."
    ),
    "duplicate": (
        "Todos los patrones tienen la misma concentracion. Hacen falta al "
        "menos dos concentraciones distintas para definir una linea."
    ),
}


@dataclass(frozen=True)
class Note:
    """Something worth saying about a result or about the curve."""

    code: str
    message: str
    # Which well the note is about, when it is about one. Carried as a field
    # rather than parsed back out of the message: the message is Spanish prose
    # meant for a person, and reading a well name out of it again would make
    # the screen's colouring depend on the wording of a sentence.
    well: str = ""

    @property
    def short(self) -> str:
        return SHORT_MESSAGES.get(self.code, self.message)

    def __str__(self) -> str:
        return self.message


def note(code: str, well: str = "", **params) -> Note:
    """Build a note from its code and the numbers that go in the message.

    `well` is both a field on the note and available to the message, because
    the sentence names the well and the screen colours it: `format` ignores
    the keywords a given message does not use.
    """
    table = MESSAGES if code in MESSAGES else FIT_MESSAGES
    return Note(code=code, message=table[code].format(well=well, **params),
                well=well)


@dataclass(frozen=True)
class Standard:
    """One well of known concentration, with the absorbance it gave."""

    well: str
    concentration: float
    absorbance: float


@dataclass(frozen=True)
class Fit:
    """The line through the standards, and how much it should be trusted.

    `absorbance = slope * concentration + intercept`, with absorbances already
    corrected for the reagent blank.
    """

    slope: float
    intercept: float
    r_squared: float
    standards: tuple
    unit: str = DEFAULT_UNIT
    notes: tuple = ()

    @property
    def n(self) -> int:
        return len(self.standards)

    @property
    def top(self) -> float:
        """The highest absorbance the curve has evidence for."""
        return max(s.absorbance for s in self.standards)

    @property
    def bottom(self) -> float:
        return min(s.absorbance for s in self.standards)

    @property
    def top_concentration(self) -> float:
        return max(s.concentration for s in self.standards)

    @property
    def usable(self) -> bool:
        """Whether a concentration read off this curve means anything.

        A bad r-squared does not make the curve unusable on its own -- it makes
        it worth a second look, which is what the note is for. A curve running
        the wrong way is a different matter: it cannot be inverted into
        anything sensible, so nothing should be read off it.
        """
        return self.slope > 0 and not any(
            n.code in ("slope", "duplicate") for n in self.notes)

    def residual(self, standard: Standard) -> float:
        """How far one standard sits from the line, in absorbance."""
        return standard.absorbance - (
            self.slope * standard.concentration + self.intercept)

    def worst_residual(self) -> float:
        """The largest distance any standard sits from the line, in absorbance.

        Reported alongside r-squared because it catches what r-squared misses:
        one point in the wrong place, and a top standard that has started to
        saturate.
        """
        return max(abs(self.residual(s)) for s in self.standards)

    def concentration_for(self, absorbance: float) -> float:
        """Invert the line. Caller checks `usable` first."""
        if self.slope <= 0:
            raise CurveError(
                "the curve does not rise with concentration, so it cannot be "
                "inverted; check the standards and the wavelength")
        return (absorbance - self.intercept) / self.slope


@dataclass
class CurveResult:
    """One unknown well, read against the curve."""

    well: str
    name: str
    absorbance: float
    concentration: float
    unit: str
    raw: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def in_range(self) -> bool:
        return not any(n.code in ("above_range", "below_range")
                       for n in self.notes)


def mean(values) -> float:
    values = list(values)
    if not values:
        raise CurveError("no values to average")
    return sum(values) / len(values)


def corrected(readings: dict, wavelength: int,
              reference_nm: int | None = None) -> float:
    """One well's absorbance at `wavelength`, less the reference if in use."""
    if wavelength not in readings:
        raise CurveError(f"no reading at {wavelength} nm")
    value = readings[wavelength]
    if reference_nm is not None:
        if reference_nm not in readings:
            raise CurveError(
                f"the reference at {reference_nm} nm was asked for but not read")
        value -= readings[reference_nm]
    return value


def fit_standards(standards, unit: str = DEFAULT_UNIT) -> Fit:
    """Least-squares line through the standards, with its own misgivings.

    Fitted with an intercept rather than forced through the origin. The
    reagent blank has already been subtracted, so in principle the line should
    pass through zero -- but forcing it there hides exactly the information
    that says it does not, which is usually a blank that was not representative
    of what the sample wells contain.
    """
    standards = tuple(standards)
    if len(standards) < MIN_STANDARDS:
        raise CurveError(
            f"a standard curve needs at least {MIN_STANDARDS} standards; "
            f"{len(standards)} given")

    notes = []
    xs = [s.concentration for s in standards]
    ys = [s.absorbance for s in standards]

    x_bar, y_bar = mean(xs), mean(ys)
    sxx = sum((x - x_bar) ** 2 for x in xs)
    if sxx == 0:
        # Every standard at the same concentration: no line exists. Returned
        # rather than raised so the screen can show the curve as unusable and
        # say why, instead of the program stopping.
        return Fit(slope=0.0, intercept=y_bar, r_squared=0.0,
                   standards=standards, unit=unit,
                   notes=(note("duplicate"),))

    sxy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = y_bar - slope * x_bar

    syy = sum((y - y_bar) ** 2 for y in ys)
    if syy == 0:
        # Every standard gave the same absorbance: a flat line. r-squared is
        # undefined (0/0), and the honest answer is that the curve says
        # nothing, not that it fits perfectly.
        r_squared = 0.0
    else:
        residuals = sum((y - (slope * x + intercept)) ** 2
                        for x, y in zip(xs, ys))
        r_squared = 1.0 - residuals / syy

    fit = Fit(slope=slope, intercept=intercept, r_squared=r_squared,
              standards=standards, unit=unit)

    if slope <= 0:
        notes.append(note("slope"))
    else:
        if r_squared < R_SQUARED_MIN:
            notes.append(note("r_squared", r_squared=r_squared,
                              limit=R_SQUARED_MIN))
        if len(standards) < THIN_STANDARDS:
            notes.append(note("thin", n=len(standards)))

        # Name a single badly placed standard, measured against the absorbance
        # range the curve actually spans rather than against a fixed figure:
        # 0.01 AU off a curve spanning 0.05 is a different matter from 0.01 off
        # one spanning 1.5.
        span = fit.top - fit.bottom
        if span > 0:
            worst = max(standards, key=lambda s: abs(fit.residual(s)))
            if abs(fit.residual(worst)) / span > RESIDUAL_LIMIT:
                notes.append(note("outlier", well=worst.well,
                                  concentration=worst.concentration,
                                  unit=unit))

    return Fit(slope=slope, intercept=intercept, r_squared=r_squared,
               standards=standards, unit=unit, notes=tuple(notes))


def read_against(
    well: str,
    readings: dict,
    fit: Fit,
    wavelength: int = DEFAULT_NM,
    reference_nm: int | None = None,
    blank: float = 0.0,
    name: str = "",
) -> CurveResult:
    """Turn one unknown well's readings into a concentration off the curve."""
    if not fit.usable:
        raise CurveError(
            "the curve is not usable, so nothing can be read against it")

    absorbance = corrected(readings, wavelength, reference_nm) - blank
    concentration = fit.concentration_for(absorbance)
    notes = []

    if absorbance > fit.top:
        notes.append(note("above_range", absorbance=absorbance, top=fit.top))
    elif absorbance < fit.bottom:
        notes.append(note("below_range", absorbance=absorbance))

    if concentration < 0:
        notes.append(note("negative"))

    return CurveResult(
        well=well, name=name, absorbance=absorbance,
        concentration=concentration, unit=fit.unit,
        raw=dict(readings), notes=notes,
    )


def peak_wavelength(readings: dict, candidates=SCAN_NM) -> int:
    """Which of the scanned wavelengths absorbed most.

    Used after a scan read to say where this reagent batch's product actually
    peaks, rather than inheriting a figure from a paper. The answer is only as
    fine as the scan's spacing, and a peak landing on the first or last point
    means the real one is probably outside the range that was scanned.
    """
    available = [nm for nm in candidates if nm in readings]
    if not available:
        raise CurveError("none of the scanned wavelengths were read")
    return max(available, key=lambda nm: readings[nm])
