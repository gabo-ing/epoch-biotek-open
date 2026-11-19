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

from . import i18n

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
HIGH_REFERENCE_MARGIN = 0.100


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
_EN_MESSAGES = {
    "high_reference": (
        "High 320 nm reference ({reference:.3f} against the blank's "
        "{blank:.3f}): something is scattering the light. Clean the window "
        "and the drop, and read again."
    ),
    "noise_floor": (
        "The absorbance is at the limit of detection; this concentration is "
        "an estimate at best. Concentrate the sample if the number matters."
    ),
    "ratio_260_280": (
        "260/280 of {ratio:.2f} is outside the usual {low}-{high} range for "
        "{sample_type} (protein or solvent carryover)."
    ),
    "ratio_260_230": (
        "260/230 of {ratio:.2f} is outside the usual {low}-{high} range "
        "(guanidine, phenol or EDTA carryover)."
    ),
    "negative": (
        "Negative concentration: the sample read below its own blank. "
        "Usually the blank well was dirty, or the drop did not bridge both "
        "surfaces."
    ),
    "blank_dispersion": (
        "The blank wells do not agree with each other: a standard deviation of "
        "{sd:.4f} AU between them ({cv:.1f}% at 260 nm). Clean the "
        "plate, load the water again and repeat the blank before reading "
        "samples: every result depends on it."
    ),
    "blank_level": (
        "The blank wells agree with each other, but the blank itself absorbs "
        "{level:.4f} AU at 260 nm, about {ngul:.0f} ng/uL. Above {limit:.3f} "
        "AU that is usually contaminated water or a plate that was not wiped, "
        "and it is subtracted from every sample."
    ),
    "pathlength": (
        "{well}: a pathlength of {value} mm is not credible for a Take3 well "
        "(they are about 0.5 mm). Check the value copied from the plate's "
        "sheet."
    ),
}

_EN_SHORT_MESSAGES = {
    "high_reference": "High 320 nm reference: clean and repeat",
    "noise_floor": "Near the limit of detection",
    "ratio_260_280": "260/280 out of range",
    "ratio_260_230": "260/230 out of range",
    "negative": "Negative concentration",
    "blank_dispersion": "Blanks do not agree",
    "blank_level": "Blank is absorbing",
    "pathlength": "Implausible pathlength",
}

_ES_MESSAGES = {
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
    "blank_dispersion": (
        "Los pozos del blanco no coinciden entre si: desviacion estandar de "
        "{sd:.4f} AU entre ellos ({cv:.1f}% a 260 nm). Limpia la placa, vuelve a "
        "cargar el agua y repite el blanco antes de leer muestras: todos los "
        "resultados dependen de esto."
    ),
    "blank_level": (
        "Los pozos del blanco coinciden entre si, pero el blanco mismo absorbe "
        "{level:.4f} AU a 260 nm, unos {ngul:.0f} ng/uL. Por encima de "
        "{limit:.3f} AU suele ser agua contaminada o una placa sin limpiar, y "
        "se resta de cada muestra."
    ),
    "pathlength": (
        "{well}: camino optico de {value} mm poco creible para un pozo Take3 "
        "(son de unos 0,5 mm). Revisa el valor copiado de la hoja de la placa."
    ),
}

MESSAGES_BY_LANGUAGE = {"en": _EN_MESSAGES, "es": _ES_MESSAGES}

MESSAGES = i18n.register({}, MESSAGES_BY_LANGUAGE)


# Short forms for the results table, where a full sentence does not fit. The long
# message still goes to the spreadsheet, which has room for it.
_ES_SHORT_MESSAGES = {
    "high_reference": "Referencia 320 nm alta: limpia y repite",
    "noise_floor": "Cerca del limite de deteccion",
    "ratio_260_280": "260/280 fuera de rango",
    "ratio_260_230": "260/230 fuera de rango",
    "negative": "Concentracion negativa",
    "blank_dispersion": "Los blancos no coinciden",
    "blank_level": "El blanco absorbe",
    "pathlength": "Camino optico poco creible",
}

SHORT_MESSAGES_BY_LANGUAGE = {"en": _EN_SHORT_MESSAGES, "es": _ES_SHORT_MESSAGES}

SHORT_MESSAGES = i18n.register({}, SHORT_MESSAGES_BY_LANGUAGE)


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
    reference_limit_od: float = HIGH_REFERENCE_MARGIN,
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
    if blank is not None and sample.reference > blank.reference + reference_limit_od:
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

    Gen5 prints this next to its averaged blank, per wavelength, on the [AVE] row
    of the "Blank Results" table. It is the cheapest warning that something is
    wrong before any sample is read: blanks that disagree mean a dirty spot, a
    bubble, or a drop that did not bridge the gap, and every concentration
    computed from them inherits the problem.

    Gen5 uses the **sample** standard deviation, n-1, which is what is used
    here. Settled on 4 November 2026, having been written down as unsettlable.

    The eight-well blank in Gen5_LVA_NAQ_0001 could not decide it. Gen5
    printed 4,32 / 4,22 / 4,23 at 260 / 280 / 320 nm; recomputing gives
    4,60 / 4,33 / 4,32 with n-1 and 4,31 / 4,05 / 4,04 with n. Neither matched
    throughout and neither could, because the printed absorbances are rounded
    to three decimals, and on a ~0,045 blank that rounding moves the CV by
    more than the gap between the two conventions.

    What broke the tie was a blank with only **two** wells, in
    Gen5_LVA_NAQ_0008 from the RNA run. The two estimators differ by a factor
    of sqrt(2) at n=2 -- far wider than the rounding can hide. A2 and A3 read
    0,058 and 0,053 at 260 nm, and Gen5 printed 6,35:

        n-1  ->  6,37      n  ->  4,50

    The remaining tenths at 280 and 320 nm are the rounding, as before. The
    choice of convention is not.

    The number is computed the way Gen5 reports it in other respects too: on
    the **raw** absorbances at one wavelength, not the 320 nm-corrected ones.
    It is also what the verdict gates on -- see BLANK_CV_LIMIT_PERCENT.
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


def blank_dispersion(blanks: dict[str, RawWell]) -> float:
    """How far the background-corrected blank wells disagree, in absorbance units.

    The sample standard deviation (n-1) of (260 - 320) across the wells. That
    quantity, not the raw absorbance, is what matters: the raw readings differ
    well to well by a few percent, but most of that is background the 320 nm
    reference removes, and what gets subtracted from every sample is
    (260 - 320).

    This was `max - min` until 18 November 2026, which was a mistake, and one
    that stayed hidden until somebody blanked every well before using it. A
    range grows with the number of wells however good the blanking is: the
    expected max-min of n draws is about 2.85 standard deviations at n=8 but
    3.90 at n=24, so a fixed limit on it got steadily harder to meet the more
    wells were blanked. Worse, it ran opposite to its own purpose. What a blank
    injects into every sample is the error of the *mean* blank, and that shrinks
    as 1/sqrt(n) -- on the real eight-well blank, from 0.00031 AU at n=8 to
    0.00018 AU at n=24. The gate tightened as the thing it guards against got
    smaller, and a technician blanking a whole plate was refused for having been
    more careful rather than less.

    A standard deviation has no such drift. It estimates the same per-well
    disagreement whether two wells were blanked or forty-eight, which is what
    "do these wells agree with each other?" ought to mean. It is also exactly
    the absolute counterpart of the CV% -- CV% is this divided by the mean --
    and that is the role this number plays; see BLANK_DISPERSION_LIMIT_AU.

    One consequence is deliberate: a single bad drop among twenty-four now
    passes, where it used to fail. It should pass. That well contributes a
    twenty-fourth of the blank, so a well 0.003 AU out moves the subtracted
    blank by 0.0001 AU, which is nothing at 0.5 mm. It is still painted red by
    `divergent_blank_wells` so the spot can be wiped or dropped. Naming it is
    useful; refusing to read because of it was not.
    """
    deltas = [b.corrected(260) for b in blanks.values() if 260 in b.readings]
    if len(deltas) < 2:
        return 0.0
    mean = sum(deltas) / len(deltas)
    variance = sum((d - mean) ** 2 for d in deltas) / (len(deltas) - 1)
    return variance ** 0.5


def blank_level(blanks: dict[str, RawWell]) -> float:
    """How much the blank itself absorbs: the mean of (260 - 320) across its wells.

    This is the number subtracted from every sample, so it is also the error
    put into every sample when the water is not clean. It is a different
    question from `blank_dispersion`, which asks only whether the wells agree
    with each other, and the two can disagree completely: sixteen spots of
    equally filthy water agree beautifully. CV% cannot see it either, because
    a larger mean is the denominator that makes the ratio look better.

    One well is a legitimate answer here, unlike a dispersion or a CV%, so
    there is no minimum count.
    """
    deltas = [b.corrected(260) for b in blanks.values() if 260 in b.readings]
    if not deltas:
        return 0.0
    return sum(deltas) / len(deltas)


# The blanking verdict, as Gen5 makes it.
#
# Gen5 computes a CV% for each wavelength on the RAW absorbances and refuses to
# read samples while the highest of them exceeds a limit the user sets. The
# limit is a field called "Validation limit (CV%)" in the Take3 Preferences
# dialog, and 10 is what a fresh installation ships with -- read off this lab's
# licensed copy on 3 November 2026, for both Nucleic Acid Quantification and
# Protein A280. See docs/GEN5_NOTES.md.
#
# This replaced two absolute limits of our own. They were not wrong so much as
# the wrong kind of thing: absorbance units where Gen5 uses a ratio, and about
# four times tighter in practice, which would have sent the technician back to
# wipe plates her old software would have accepted. Matching the instrument's
# own software is worth more here than being carefully stricter than it.
BLANK_CV_LIMIT_PERCENT = 10.0

# Above this disagreement between the blank wells the blank is not trustworthy.
# At 0.5 mm an error of 0.004 AU in the subtracted blank is 4 ng/uL of dsDNA:
# nothing on a 400 ng/uL sample, ruinous on a 10 ng/uL one.
#
# No longer the gate -- see BLANK_CV_LIMIT_PERCENT. It is kept because CV% is a
# ratio and so says nothing about absolute size: a blank sitting on a high
# background can hold its CV% under 10 while its wells disagree by more ng/uL
# than anyone would report. This is the floor under that case, and it is
# deliberately loose enough that in ordinary use the CV% limit is what decides.
#
# The number is set from what the four known quantities actually are, rather
# than converted from the 0.004 AU range limit it replaces. Converting is what
# a first attempt did -- 0.004 divided by the 2.85 standard deviations a range
# of eight spans, giving 0.0014 -- and it reintroduced the same bug in reverse.
# A standard deviation estimated from two wells is a very noisy estimate of
# itself: across 400 simulated two-well blanks its spread reaches 0.0021 AU
# where the same simulator at eight wells never passes 0.0014. A flat limit at
# 0.0014 would therefore have refused about one two-well blank in twelve on a
# clean plate, and two wells is this lab's commonest blanking.
#
#   0.00089 AU   the real blanking Gen5 accepted (Gen5_LVA_NAQ_0001, column 2,
#                eight wells, 26 October 2026)
#   0.00000 AU   the real two-well blanking Gen5 accepted (Gen5_LVA_NAQ_0008)
#   0.00212 AU   the worst of 400 simulated two-well blanks, none of which
#                should warn about anything
#   0.00354 AU   two wells disagreeing by 0.005 AU, which the tests require to
#                be refused and which is 5 ng/uL of dsDNA at 0.5 mm
#
# 0.0025 sits between the last two, so no number of wells raises a false alarm
# on a good plate and the disagreement that ought to be caught still is. That
# it is far out in the tail is the point: this is a floor, not the gate.
BLANK_DISPERSION_LIMIT_AU = 0.0025


# How absorbent the blank may be before the screen says something, measured on
# the corrected (260 - 320) mean of the blank wells themselves.
#
# This is not a gate and must never become one. Gen5 does not have it: proved
# on 19 November 2026 with its own software on this instrument, when a blank
# made of six wells of contaminated water was accepted as VALID on a CV of
# 9,902% while sitting at 0.038 AU -- about 38 ng/uL of nothing at all.
# Gen5 asks one question only, whether the blank wells agree with each other,
# and never whether they are clean. The same run then reported eight spots of
# good water at -31,6 ng/uL, each with a flawless 260/280 between 1,93 and
# 2,05, because a ratio of two negative numbers cannot warn anybody.
#
# Refusing such a blank would be stricter than the instrument's own software
# and would put the technician back where v1.2 found her, so this only warns.
#
#   0.0060 AU   the clean tube, all sixteen spots, 19 November 2026, which
#               Gen5 accepted at CV 6,136% and epoch-open at 6,320%
#   0.0063 AU   the blanking Gen5 accepted on 26 October 2026
#   0.0359 AU   the contaminated tube at 09:32 on 19 November 2026
#   0.0380 AU   the same tube at 09:47, which Gen5 called VALID
#
# 0.010 is quiet on both good blanks with better than half again to spare and
# loud on both bad ones by a factor of three and a half. There is no evidence
# anywhere in the gap, so the exact placing inside it is arbitrary; what is
# measured is that the two populations are a factor of six apart.
BLANK_LEVEL_WARN_AU = 0.010

# How far one blank well may sit from the middle of the others before it is named
# on screen as the spot to wipe.
#
# This is advice, not a verdict. It paints the well red so the technician knows
# which spot to wipe or discard; it does not by itself stop her reading samples.
# That is Gen5's arrangement too -- Gen5 lets a well be clicked out of the
# average and recomputes, rather than refusing until she does -- and the
# distinction matters, because a well that is visibly off on a blanking whose
# CV% is still fine is information, not an obstacle.
#
# The number is ours. It is set from the one blanking we know Gen5 accepted,
# whose worst well sits 0.0015 AU from the median, leaving a blank that good
# about twice the room it needed. Being tighter would redden wells on blanks
# the instrument's own software was happy with.
BLANK_DIVERGENCE_LIMIT_AU = 0.003


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def divergent_blank_wells(
    blanks: dict[str, RawWell],
    limit_au: float = BLANK_DIVERGENCE_LIMIT_AU,
) -> set[str]:
    """Which blank wells sit too far from the others to be trusted.

    Measured on the 320 nm-corrected reading, because that is what actually gets
    subtracted from every sample, and against the **median** rather than the mean,
    so that one bad spot is flagged instead of dragging the centre towards itself
    and dirtying the verdict on its neighbours.

    With two wells that disagree the median falls between them and both are
    flagged. That is the honest answer: two readings that do not match cannot say
    which of them is the wrong one.

    One well alone is never divergent -- there is nothing to diverge from. It can
    still be a bad blank, which is why a single-well blank is worth avoiding, but
    this function cannot be the thing that detects it.
    """
    deltas = {name: b.corrected(260) for name, b in blanks.items()
              if 260 in b.readings}
    if len(deltas) < 2:
        return set()

    middle = _median(list(deltas.values()))
    return {name for name, delta in deltas.items()
            if abs(delta - middle) > limit_au}


@dataclass(frozen=True)
class BlankReport:
    """The verdict on a set of blank wells, as the screen needs to show it.

    `valid` is what gates reading samples. `divergent` is what gets painted red,
    so the technician can drop those wells and re-blank rather than guess which
    spot to wipe.
    """

    wells: tuple[str, ...]
    divergent: tuple[str, ...]
    dispersion_au: float
    cv_percent: dict[int, float]
    valid: bool
    reason: str = ""
    # How absorbent the blank itself is. Never part of `valid`: Gen5 accepts a
    # filthy blank that agrees with itself, and so do we. See BLANK_LEVEL_WARN_AU.
    level_au: float = 0.0

    @property
    def cv_260(self) -> float:
        return self.cv_percent.get(260, 0.0)

    def level_is_high(
        self, limit_au: float = BLANK_LEVEL_WARN_AU
    ) -> bool:
        """Whether the blank absorbs enough to be worth a word on the screen."""
        return self.level_au > limit_au


def judged_cv(cv_percent: dict[int, float]) -> dict[int, float]:
    """The CV% values the verdict is allowed to use: every one but the reference.

    Gen5 excludes the 320 nm reference, and this is measured rather than
    assumed. On 19 November 2026 Gen5 accepted a six-well blanking as VALID,
    showing 9,902%, whose CV% at 320 nm is 12,10% -- comfortably over the
    limit of 10 that it had just refused another blanking with. A rule taking
    the highest CV% across all wavelengths cannot produce that verdict, so
    Gen5's does not take it. (Gen5_LVA_NAQ_0015.html, wells E3/F3/G2/G3/H2/H3.)

    It is also the better rule. 320 nm is where nothing should absorb, so its
    mean is small and arbitrary, and a CV% with a near-zero denominator says
    more about the denominator than about the blanking. A speck of dust on one
    spot moves it a long way while changing the blank subtracted from a sample
    by almost nothing. That same speck is still caught, at the wavelength
    where it matters, by the 260 nm CV% and by the disagreement floor.

    Whether Gen5 judges 280 nm as well as 260 is not settled: in that blanking
    280 came to 9,77%, under the limit either way, so the run cannot tell them
    apart. Every non-reference wavelength is judged here, which is the
    stricter of the two readings and the one that keeps a 230 nm reading
    meaningful when "also read 230 nm" is ticked.
    """
    return {nm: value for nm, value in cv_percent.items()
            if nm != REFERENCE_NM}


def wells_to_discard(
    blanks: dict[str, RawWell],
    cv_limit_percent: float = BLANK_CV_LIMIT_PERCENT,
    dispersion_limit_au: float = BLANK_DISPERSION_LIMIT_AU,
) -> set[str]:
    """Which wells would have to go for the rest to agree.

    This is what Gen5 paints red, and the hint beside its grid says so: "you
    can discard unnecessary / diverging blank wells". The red set is not an
    opinion about which wells are odd-looking, it is the answer to a question
    she is about to act on -- which spots do I throw away so this blanking
    passes?

    Found by dropping the well furthest from the mean, over and over, until
    what remains is inside **both** limits. Never below two wells, since a
    single well has no CV% and discarding down to one would trade a bad blank
    for an unjudgeable one.

    Both limits, because either can refuse a blanking on its own. Checking
    only the CV% here was right while the CV% was the only thing that could
    fail a blank whose wells were individually plausible; once the
    disagreement limit became a gate of its own it left a hole, and the hole
    landed on the very case described below.

    The naive rule this replaced measured each well's distance from the
    median, which breaks on exactly the case Gabo photographed on
    3 November 2026: two clean spots and two smudged ones. The median lands in
    the gap between the groups, every well is then far from it, and all four
    were painted red -- telling her to wipe two spots that were fine. Gen5
    reddened the two smudged wells and left the clean pair green.

    Returns an empty set when no amount of discarding helps, which is the
    honest answer that nothing in particular is to blame and the plate should
    be blanked again.
    """
    if len(blanks) < 3:
        # With two wells neither can be called the wrong one, and discarding
        # either leaves a single well that cannot be judged at all.
        return set()

    kept = dict(blanks)
    discarded: set[str] = set()

    def passes(wells):
        cv = {w: blank_cv_percent(wells, w)
              for w in set.intersection(*(set(b.readings)
                                          for b in wells.values()))}
        cv = judged_cv(cv)
        if cv and max(cv.values()) > cv_limit_percent:
            return False
        return blank_dispersion(wells) <= dispersion_limit_au

    while len(kept) > 2:
        if passes(kept):
            return discarded

        values = {name: well.corrected(260) for name, well in kept.items()}
        centre = sum(values.values()) / len(values)
        worst = max(values, key=lambda n: abs(values[n] - centre))
        discarded.add(worst)
        del kept[worst]

    # Down to two wells and still failing: nothing to single out.
    if passes(kept):
        return discarded
    return set()


def blank_report(
    blanks: dict[str, RawWell],
    cv_limit_percent: float = BLANK_CV_LIMIT_PERCENT,
    dispersion_limit_au: float = BLANK_DISPERSION_LIMIT_AU,
    divergence_limit_au: float = BLANK_DIVERGENCE_LIMIT_AU,
) -> BlankReport:
    """Judge a set of blank wells the way Gen5 does.

    The verdict is the **highest CV% across the wavelengths read**, measured on
    raw absorbances, against `cv_limit_percent`. That is Gen5's rule and Gen5's
    default of 10; see docs/GEN5_NOTES.md for where the number comes from.

    `dispersion_limit_au` is a floor underneath it, for the case a ratio cannot
    see: a blank on a high background can keep its CV% respectable while its
    wells disagree by an absolute amount that matters at 0.5 mm. Neither limit
    depends on how many wells were blanked, so blanking every well before using
    it is judged the same way as blanking two.

    A well that sits well away from the others is still named in `divergent`
    and painted red, but that alone no longer blocks the run. It tells her
    which spot to wipe or discard; Gen5 likewise lets a well be clicked out of
    the average rather than refusing until it is. A single well off a blanking
    whose CV% is fine is information, not an obstacle.

    With fewer than two wells a CV% cannot be computed at all, which Gen5 also
    treats as a failed blank.
    """
    if not blanks:
        return BlankReport(wells=(), divergent=(), dispersion_au=0.0,
                           cv_percent={}, valid=False, reason="empty",
                           level_au=0.0)

    wavelengths = sorted(set.intersection(*(set(b.readings) for b in blanks.values())))
    cv = {w: blank_cv_percent(blanks, w) for w in wavelengths}
    dispersion = blank_dispersion(blanks)

    # Red means "discard this one and the rest agree" when the blanking has
    # failed, which is what Gen5 shows and what she is about to do about it.
    # When the CV% already passes there is nothing to discard, so the older
    # distance-from-the-median rule is left to name a well that is visibly out
    # of line anyway -- advice on a blanking that is otherwise fine.
    # "Failing" has to mean every way a blanking can be refused, not only the
    # CV%. When the disagreement limit became a gate of its own it was left
    # out of this test, which quietly handed the red paint back to the
    # distance-from-the-median rule -- the rule that reddens all four wells on
    # two clean spots and two smudged ones, which is the case it was retired
    # for. Caught on 18 November 2026 while reading a saved blank back.
    judged = judged_cv(cv)
    failing = (bool(judged) and max(judged.values()) > cv_limit_percent) \
        or dispersion > dispersion_limit_au
    if failing:
        divergent = wells_to_discard(blanks, cv_limit_percent,
                                     dispersion_limit_au)
    else:
        divergent = divergent_blank_wells(blanks, divergence_limit_au)

    if len(blanks) < 2:
        # Gen5 requires two or more wells for "use blank average", and treats a
        # CV% that cannot be calculated as a failure rather than a pass.
        reason = "single"
    elif judged and max(judged.values()) > cv_limit_percent:
        reason = "cv"
    elif dispersion > dispersion_limit_au:
        reason = "dispersion"
    else:
        reason = ""

    return BlankReport(
        wells=tuple(sorted(blanks)),
        divergent=tuple(sorted(divergent)),
        dispersion_au=dispersion,
        cv_percent=cv,
        valid=not reason,
        reason=reason,
        level_au=blank_level(blanks),
    )



def check_blanks(blanks: dict[str, RawWell]) -> list["Warning_"]:
    """Warnings about the blanks themselves, before any sample is quantified."""
    warnings: list[Warning_] = []
    if not blanks:
        return warnings

    # A dirty blank is worth saying even when a single well was blanked, so
    # this is checked before the two-well floor the disagreement needs.
    level = blank_level(blanks)
    if level > BLANK_LEVEL_WARN_AU:
        warnings.append(warn("blank_level", level=level,
                             ngul=to_1cm(level, DEFAULT_PATHLENGTH_MM) * 50,
                             limit=BLANK_LEVEL_WARN_AU))

    if len(blanks) < 2:
        return warnings

    dispersion = blank_dispersion(blanks)
    if dispersion > BLANK_DISPERSION_LIMIT_AU:
        warnings.append(warn("blank_dispersion", sd=dispersion,
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
