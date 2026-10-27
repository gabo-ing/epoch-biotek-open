"""Nucleic-acid and protein quantification from Take3 micro-volume readings.

The algorithm here is not invented: it was recovered from this lab's own Gen5 exports
for plate 243819 on reader 254717, and it reproduces their reported concentrations
exactly. See docs/QUANTIFICATION.md for the derivation.

Three facts, each confirmed against those files:

1. Every read takes a **reference wavelength at 320 nm** alongside the measurement
   wavelengths. 320 nm is subtracted from each measurement to remove background
   (scatter, fingerprints, a dirty window) that affects all wavelengths alike.

2. A blank is subtracted after that background correction. Gen5 reads one blank
   well (or a few) and applies it to every sample; it does not require a blank in
   each spot. `blank_for()` handles either arrangement.

3. The pathlength is **per well**, held in a table Gen5 defaults to 0.5 mm in every
   cell and lets the user overwrite with the values from the plate's Take3 Pathlength
   Data Sheet. It is not measured per drop: Gen5 never reads 977/900 the way a
   NanoDrop does.

   An earlier version of this file asserted a flat 0.5 mm as established fact. That
   was an overstatement. The lab's exports round raw absorbances to three decimals,
   and the wells in those files are all within 0.9% of 0.5 mm, so the data cannot
   distinguish a flat 0.5 mm from the certified values -- both reproduce every
   reported number exactly. The Gen5 plate dialog settles it: the table exists, it is
   per well, and what is in it is what gets used.

Which values to put in the table is a real choice, not a detail. The nominal 0.5 mm is
wrong by up to 2.4% on this plate (well A2 is certified at 0.5125 mm). Matching
whatever the lab used historically matters too, since results that silently disagree
with old ones look like sample problems. See docs/QUANTIFICATION.md.
"""

from dataclasses import dataclass, field

# What Gen5 puts in every cell of a new plate's pathlength table.
DEFAULT_PATHLENGTH_MM = 0.5

# Kept as the fallback for callers that pass no table.
PATHLENGTH_MM = DEFAULT_PATHLENGTH_MM

# The reference wavelength subtracted from every measurement.
REFERENCE_NM = 320

# Concentration in ng/uL that gives an absorbance of 1.0 at 260 nm over a 1 cm path.
EXTINCTION = {
    "dsDNA": 50.0,
    "ssDNA": 33.0,
    "RNA": 40.0,
}

# Protein, read as 260/280 with "1 Abs at 1 cm = 1 mg/mL", reported in mg/mL.
PROTEIN_FACTOR_MG_ML = 1.0

# The second wavelength each sample type is read against.
SECONDARY_NM = {
    "dsDNA": 280,
    "ssDNA": 280,
    "RNA": 280,
    "protein": 280,
}

PURITY_260_280 = {
    "dsDNA": (1.7, 1.9),
    "ssDNA": (1.7, 1.9),
    "RNA": (1.9, 2.1),
}
PURITY_260_230 = (2.0, 2.2)

# A reference reading far above the blank's means something is on the window or in
# the drop that is not sample. Gen5 shades these yellow and says so in the export.
HIGH_REFERENCE_MARGIN = 0.010


@dataclass(frozen=True)
class Warning_:
    """A problem worth telling the user about, as a code plus readable text.

    The code is what tests and callers match on; the message is what the
    technician reads. Keeping them separate means the wording can be changed, or
    translated, without breaking anything that depends on the meaning.
    """

    code: str
    message: str

    @property
    def short(self) -> str:
        """A few words for a narrow table cell."""
        return SHORT_MESSAGES.get(self.code, self.message)

    def __str__(self) -> str:
        return self.message


# Spanish, because that is the language of the lab that uses this.
MESSAGES = {
    "high_reference": (
        "Referencia 320 nm alta ({reference:.3f} frente a {blank:.3f} del blanco): "
        "algo esta dispersando la luz. Limpia la ventana y la gota, y vuelve a leer."
    ),
    "noise_floor": (
        "La absorbancia esta en el limite de deteccion; esta concentracion es, como "
        "mucho, una estimacion. Concentra la muestra si el numero importa."
    ),
    "ratio_260_280": (
        "260/280 de {ratio:.2f} fuera del rango habitual {low}-{high} para "
        "{sample_type} (arrastre de proteina o de solvente)."
    ),
    "ratio_260_230": (
        "260/230 de {ratio:.2f} fuera del rango habitual {low}-{high} "
        "(arrastre de guanidina, fenol o EDTA)."
    ),
    "negative": (
        "Concentracion negativa: la muestra leyo por debajo de su blanco. "
        "Normalmente el pozo del blanco estaba sucio o la gota no llego a tocar "
        "las dos superficies."
    ),
    "blank_spread": (
        "Los pozos del blanco no coinciden entre si: {spread:.4f} AU de diferencia "
        "entre el mayor y el menor ({cv:.1f}% a 260 nm). Limpia la placa, vuelve a "
        "cargar el agua y repite el blanco antes de leer muestras: todos los "
        "resultados dependen de esto."
    ),
    "pathlength": (
        "{well}: camino optico de {value} mm poco creible para un pozo Take3 "
        "(son de unos 0,5 mm). Revisa el valor copiado de la hoja de la placa."
    ),
}


# Short forms for the results table, where a full sentence does not fit. The long
# message still goes to the spreadsheet, which has room for it.
SHORT_MESSAGES = {
    "high_reference": "Referencia 320 nm alta: limpia y repite",
    "noise_floor": "Cerca del limite de deteccion",
    "ratio_260_280": "260/280 fuera de rango",
    "ratio_260_230": "260/230 fuera de rango",
    "negative": "Concentracion negativa",
    "blank_spread": "Los blancos no coinciden",
    "pathlength": "Camino optico poco creible",
}


def warn(code: str, **params) -> Warning_:
    """Build a warning from its code and the numbers that go in the message."""
    return Warning_(code=code, message=MESSAGES[code].format(**params))


class QuantError(ValueError):
    """Raised when a reading cannot be turned into a defensible concentration."""


@dataclass
class RawWell:
    """One well's raw absorbances, straight off the reader, before any correction.

    `readings` maps wavelength in nm to raw absorbance and must include the
    reference wavelength (320 nm).
    """

    well: str
    readings: dict[int, float]

    def __post_init__(self):
        if REFERENCE_NM not in self.readings:
            raise QuantError(
                f"{self.well}: no {REFERENCE_NM} nm reference reading. Every read "
                "must include it, or the background cannot be removed."
            )

    def corrected(self, wavelength: int) -> float:
        """Absorbance at `wavelength` with the 320 nm background removed."""
        if wavelength not in self.readings:
            raise QuantError(
                f"{self.well}: no reading at {wavelength} nm."
            )
        return self.readings[wavelength] - self.readings[REFERENCE_NM]

    @property
    def reference(self) -> float:
        return self.readings[REFERENCE_NM]


@dataclass
class QuantResult:
    well: str
    sample_type: str
    pathlength_mm: float
    concentration: float
    unit: str
    a260: float
    a_secondary: float
    secondary_nm: int
    ratio_260_280: float | None
    ratio_260_230: float | None
    raw: dict[int, float] = field(default_factory=dict)
    warnings: list[Warning_] = field(default_factory=list)


def _ratio(numerator: float, denominator: float) -> float | None:
    """Absorbance ratio, or None when the denominator is too small to mean anything."""
    if abs(denominator) < 1e-4:
        return None
    return numerator / denominator


def default_pathlengths(wells) -> dict[str, float]:
    """A fresh table, 0.5 mm everywhere, exactly as Gen5 starts one."""
    return {well: DEFAULT_PATHLENGTH_MM for well in wells}


def pathlength_for(
    well: str, pathlengths: dict[str, float] | float | None = None
) -> float:
    """The pathlength to use for one well, in millimetres."""
    if pathlengths is None:
        return DEFAULT_PATHLENGTH_MM
    if isinstance(pathlengths, (int, float)):
        return float(pathlengths)
    value = pathlengths.get(well)
    if value is None:
        return DEFAULT_PATHLENGTH_MM
    if not 0.2 <= value <= 1.2:
        raise QuantError(MESSAGES["pathlength"].format(well=well, value=value))
    return value


def unit_for(sample_type: str) -> str:
    """What a concentration of this sample type is measured in.

    The screen needs this before anything has been read, to label the column.
    Defined once here so the heading can never disagree with the number under it.
    """
    return "mg/mL" if sample_type == "protein" else "ng/uL"


def to_1cm(absorbance: float, pathlength_mm: float = DEFAULT_PATHLENGTH_MM) -> float:
    """Scale a Take3 absorbance to what a 1 cm cuvette would have shown."""
    return absorbance / (pathlength_mm / 10.0)


def quantify(
    sample: RawWell,
    blank: RawWell | None = None,
    sample_type: str = "dsDNA",
    pathlengths: dict[str, float] | float | None = None,
) -> QuantResult:
    """Turn one well into a concentration, the way Gen5 does it.

    `pathlengths` is the per-well table in millimetres, as entered in Gen5's Take3
    plate dialog. Omitted, every well is taken as the 0.5 mm nominal.
    """
    if sample_type not in EXTINCTION and sample_type != "protein":
        raise QuantError(
            f"Unknown sample type {sample_type!r}; expected protein or one of "
            f"{', '.join(sorted(EXTINCTION))}."
        )

    warnings: list[Warning_] = []
    secondary_nm = SECONDARY_NM[sample_type]

    def corrected(wavelength: int) -> float:
        value = sample.corrected(wavelength)
        if blank is not None:
            value -= blank.corrected(wavelength)
        return value

    a260 = corrected(260)
    a_secondary = corrected(secondary_nm)
    a230 = corrected(230) if 230 in sample.readings else None

    path_mm = pathlength_for(sample.well, pathlengths)

    if sample_type == "protein":
        concentration = to_1cm(a260, path_mm) * PROTEIN_FACTOR_MG_ML
    else:
        concentration = to_1cm(a260, path_mm) * EXTINCTION[sample_type]
    unit = unit_for(sample_type)

    ratio_280 = _ratio(a260, corrected(280)) if 280 in sample.readings else None
    ratio_230 = _ratio(a260, a230) if a230 is not None else None

    # A high reference reading means background, not sample. Gen5 flags these.
    if blank is not None and sample.reference > blank.reference + HIGH_REFERENCE_MARGIN:
        warnings.append(
            warn("high_reference", reference=sample.reference, blank=blank.reference)
        )

    if a260 < 0.005:
        warnings.append(warn("noise_floor"))
    elif ratio_280 is not None and sample_type in PURITY_260_280:
        low, high = PURITY_260_280[sample_type]
        if not low <= ratio_280 <= high:
            warnings.append(
                warn("ratio_260_280", ratio=ratio_280, low=low, high=high,
                     sample_type=sample_type)
            )

    if ratio_230 is not None and a260 >= 0.005:
        low, high = PURITY_260_230
        if not low <= ratio_230 <= high:
            warnings.append(
                warn("ratio_260_230", ratio=ratio_230, low=low, high=high)
            )

    if concentration < 0:
        warnings.append(warn("negative"))

    return QuantResult(
        well=sample.well,
        sample_type=sample_type,
        pathlength_mm=path_mm,
        concentration=concentration,
        unit=unit,
        a260=a260,
        a_secondary=a_secondary,
        secondary_nm=secondary_nm,
        ratio_260_280=ratio_280,
        ratio_260_230=ratio_230,
        raw=dict(sample.readings),
        warnings=warnings,
    )


def average_blank(blanks: dict[str, RawWell]) -> RawWell:
    """Average several blank wells into one, wavelength by wavelength.

    Only wavelengths present in every blank survive; averaging a wavelength that
    some blanks lack would quietly weight it wrong.
    """
    if not blanks:
        raise QuantError("No blank wells to average.")

    shared = set.intersection(*(set(b.readings) for b in blanks.values()))
    if REFERENCE_NM not in shared:
        raise QuantError(
            f"The blank wells do not all have a {REFERENCE_NM} nm reading."
        )

    count = len(blanks)
    averaged = {
        wavelength: sum(b.readings[wavelength] for b in blanks.values()) / count
        for wavelength in shared
    }
    return RawWell(well="blank (mean of %d)" % count, readings=averaged)


def blank_cv_percent(blanks: dict[str, RawWell], wavelength: int = 260) -> float:
    """Spread of the blank wells at one wavelength, as a coefficient of variation.

    Gen5 prints this next to its averaged blank. It is the cheapest warning that
    something is wrong before any sample is read: blanks that disagree mean a dirty
    spot, a bubble, or a drop that did not bridge the gap, and every concentration
    computed from them inherits the problem.
    """
    values = [
        b.readings[wavelength] for b in blanks.values() if wavelength in b.readings
    ]
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    if abs(mean) < 1e-9:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return (variance ** 0.5) / abs(mean) * 100.0


def blank_spread(blanks: dict[str, RawWell]) -> float:
    """Range of the background-corrected blank across wells, in absorbance units.

    This, not the CV, is what matters. The raw readings differ well to well by a
    few percent, but most of that is background that the 320 nm reference removes.
    What gets subtracted from every sample is (260 - 320), so the spread of *that*
    is the error a bad blank injects.

    A coefficient of variation on two or three wells is also wildly unstable: a
    simulated blank of two wells could exceed a 5% CV on ordinary noise and warn
    about nothing.
    """
    deltas = [b.corrected(260) for b in blanks.values() if 260 in b.readings]
    if len(deltas) < 2:
        return 0.0
    return max(deltas) - min(deltas)


# Above this spread the blank is not trustworthy. A blank is ~0.006 AU, and at
# 0.5 mm an error of 0.004 AU is 4 ng/uL of dsDNA: nothing on a 400 ng/uL sample,
# ruinous on a 10 ng/uL one.
BLANK_SPREAD_LIMIT_AU = 0.004


def check_blanks(blanks: dict[str, RawWell]) -> list["Warning_"]:
    """Warnings about the blanks themselves, before any sample is quantified."""
    warnings: list[Warning_] = []
    if len(blanks) < 2:
        return warnings

    spread = blank_spread(blanks)
    if spread > BLANK_SPREAD_LIMIT_AU:
        warnings.append(warn("blank_spread", spread=spread,
                             cv=blank_cv_percent(blanks, 260)))
    return warnings


def blank_for(
    blanks: dict[str, RawWell] | RawWell | None, well: str
) -> RawWell | None:
    """Pick the blank that applies to `well`.

    A blank read in that exact spot wins. Otherwise every blank is averaged, which
    is what Gen5 does: one or a few blank wells standing in for the whole plate.
    """
    if blanks is None:
        return None
    if isinstance(blanks, RawWell):
        return blanks
    if not blanks:
        return None
    if well in blanks:
        return blanks[well]
    if len(blanks) == 1:
        return next(iter(blanks.values()))
    return average_blank(blanks)


def wavelengths_for(sample_type: str, with_230: bool = False) -> list[int]:
    """Which wavelengths a read of this sample type needs, reference included."""
    wavelengths = [260, SECONDARY_NM[sample_type], REFERENCE_NM]
    if with_230:
        wavelengths.append(230)
    return sorted(set(wavelengths))
