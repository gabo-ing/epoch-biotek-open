# What Gen5's own documentation says

Notes taken from the Gen5 1.11 help files on the lab's licensed installation,
read on 3 November 2026. Facts only -- thresholds, defaults, formulas, plate
dimensions -- written in our own words. No vendor text is reproduced here and
no part of Gen5 was disassembled: these are the manuals, read the way a
manual is meant to be read.

This matters because several things in this project were set by judgement
after concluding the evidence could not settle them. Some of those
conclusions were wrong, and this document says which.

## The blank validation rule -- we had this wrong

**Gen5 gates on CV%, against a user-configurable limit.** The setting is a
field called *Validation limit (CV%)* in the Take3 Preferences dialog. When
the blanking method is "use blank average" and two or more blank wells are
read, Gen5 computes a CV% for each wavelength **on the raw data**, and if the
**highest** of those exceeds the limit -- or cannot be computed at all -- it
warns and refuses to read samples until a valid blank exists.

Three consequences, in order of how much they cost us:

1. **There is no Gen5 constant to recover.** `docs/BLANK_THRESHOLD.md` was
   written to measure one experimentally. It cannot succeed as designed,
   because the number it was hunting is a per-protocol setting, not a
   property of Gen5. Whatever the experiment measured would have been that
   laptop's configuration.

2. **Our criterion is a different kind of thing.** `BLANK_SPREAD_LIMIT_AU` and
   `BLANK_DIVERGENCE_LIMIT_AU` are absolute, in absorbance units. Gen5's is
   relative, a coefficient of variation. They disagree in opposite directions
   at the two ends of the range: on a very clean blank a CV% limit is
   stricter than ours, and on a blank with a high background it is looser.

3. **We already compute the right number and only display it.**
   `blank_cv_percent()` in `epoch_open/quant.py` computes CV% per wavelength
   on raw absorbances -- deliberately, to match what the technician reads off
   Gen5 -- and the screen shows it. The gate is the part that diverges.

The help also confirms the mechanics we guessed at correctly: wells can be
clicked to include or discard, the statistics recompute each time, and sample
reads stay blocked until the blank passes. That is what `blank_report()` and
the disabled button already do.

**What to do about it is a decision, not a fact**, so it is written up at the
end of this file rather than acted on here.

## Confirmed: things we built correctly

| | |
|---|---|
| Reference wavelength | 320 nm is Gen5's documented default, for the stated reason that pure nucleic acid absorbs ~0 there |
| High reference warning | Gen5 compares the sample's raw reference reading against the blank's, against a configurable *Limit*, and marks affected wells **yellow** in the report. Our `high_reference` warning and amber row are the same idea and the same colour |
| Pathlength correction | Per well, from the calibrated table tied to the plate's serial number, normalising to 0.5 mm or 1 cm -- which is what `quant.py` does |
| Blank average | Requires two or more wells, averaged, subtracted from every sample |

## Gaps: capabilities we never implemented

Not bugs. Things the instrument and Gen5 can do that this project cannot,
recorded so the choice is deliberate rather than accidental.

- **"Blank on each sample well"** -- a second blanking method, where every
  well is blanked against itself rather than against an average. Gen5
  recommends it when samples sit in different buffers, and it is forced for
  cuvette reads. We only implement blank-average.
- **BioCell and cuvette positions.** The Take3 plate has three well types:
  the 16 low-volume microspots at A2-H3 that we support, plus **BioCells at
  A9 and H9** and **cuvette positions at E10 and E11**. We address none of
  the latter.
- **Curve fits beyond a straight line.** Gen5 offers 4-parameter,
  5-parameter, logit-log, point-to-point, spline-with-smoothing and
  polynomial regression, with documented minimum standard counts (4, 5, 4, 2,
  4, and degree+1). `epoch_open/curve.py` does linear regression only. For
  Salkowski within its linear range that is correct; **4-parameter logistic
  is the standard for ELISA**, so this is the gap to close first if that
  assay ever matters here.
- **Extrapolation factor.** Gen5 has a single configurable number, default
  **1.1**, range 1 to 3, which widens the usable concentration range by a
  fraction of the standards' span, symmetrically at both ends. A factor of 1
  means no extrapolation at all. It is a cleaner idea than our hard cutoff at
  the top standard, and worth stealing if the range handling is ever revised.

## A deliberate divergence, now documented as one

Gen5's minimum for a linear regression is **two** standards. `curve.py`
requires three, and should keep requiring three: two points fit a line with
r-squared exactly 1 whatever they are, so a two-standard curve reports a
perfect fit carrying no evidence. Ours is the stricter and better rule, and
it is now a choice rather than an accident.

## Plate geometry: our 96-well definition is corroborated

Gen5 ships `CustomPlateTypes.dat`, a plain-text table of 76 plate
definitions, 35 of them 8x12. Each carries footprint, first and last well
centres, well diameter, height, manufacturer and catalogue number, in
microns -- the same quantities our `PlateGeometry` sends in the `y` command.

Across those 35 definitions:

| | min | max | median |
|---|---|---|---|
| footprint X | 126.37 | 128.00 | 127.50 |
| footprint Y | 84.84 | 85.73 | 85.45 |
| A1 centre x | 13.61 | 14.70 | 14.22 |
| A1 centre y | 10.90 | 11.42 | 11.12 |
| **pitch x** | 8.892 | 9.045 | **9.007** |
| **pitch y** | 8.884 | 9.059 | **9.010** |

Our `PLATE_96` sits in the middle of that distribution: pitch 9.016 and
9.017 mm, A1 at (14.35, 11.22), footprint 127.88 x 85.59. It came from
PyLabRobot's worked example and had never been checked against anything.
It now has 35 independent corroborations.

**This is why one generic 96-well geometry is safe.** The whole spread of A1
positions across every manufacturer Gen5 knows is about 1.1 mm, while a
96-well's flat bottom is roughly 6.8 mm across. Being a millimetre off centre
still puts the beam well inside the well. Per-manufacturer definitions matter
for robotics and for small-well formats; for an absorbance read in a 96-well
plate they do not.

So `epoch-multispectral`'s untested flat-plate path is no longer untested in
the part that could silently aim the optics at nothing. It still has never
driven the instrument.

## What is still worth doing on the trial laptop

The blanking experiment in `docs/BLANK_THRESHOLD.md` has lost most of its
purpose. What replaces it takes a minute:

1. Open the Take3 Preferences dialog and **read the Validation limit (CV%)
   field**. Screenshot it. That is the number, and no pipetting recovers it.
2. Note the blanking method the lab actually uses, and the reference
   wavelength Limit value next to it.

Still worth doing with reagents, for different reasons than before:

- **The INVALID screenshot.** Knowing the rule is CV%-based does not tell us
  how Gen5 presents a failure, which wells it reddens, or whether it reddens
  any. Two reads -- clean water, then one spot smudged -- still answer that.
- **Part F, absolute accuracy.** Untouched by any of this. The calibration
  label still says December 2018 and the trial still expires 25 November.

## What was done about it

Settled on 3 November 2026: **behave like Gen5**, on the reasoning that
nobody changes these settings and the verdict agreeing with the software the
lab has used for years is worth more than being carefully stricter than it.

- The blank verdict is now the highest CV% against a limit defaulting to
  **10**, Gen5's number.
- The high-reference margin is **0.1 OD at 0.5 mm**, Gen5's number, up from
  0.010.
- The spread limit stays as an absolute floor under the CV% check, because a
  ratio says nothing about absolute size.
- The divergence limit now only decides which well is painted red. It names
  the spot to wipe and no longer blocks the run, which is Gen5's arrangement
  too -- it lets a well be clicked out of the average rather than refusing
  until it is.
- A one-well blank now **fails** where it used to pass. Gen5's help is
  explicit that a CV% which cannot be calculated is a failed blank, and it is
  right: a lone blank well has no evidence behind it and every sample in the
  run is divided by it.

All four numbers are in a **Preferences dialog**, laid out like Gen5's Take3
Preferences -- same grouping, same field names, same units -- because that is
where someone would go looking. `docs/img/preferences.png` shows it. They
also remain in `epoch_open.json` for anyone who prefers a file.

## The reasoning behind that decision, kept

Whether to change the blank gate from absorbance units to CV%, matching
Gen5's criterion and making the limit configurable as Gen5 does.

Arguments for: it is what the instrument's own software does; the technician
already reads CV% on this screen and in Gen5; it is one number instead of
two; and it would make our verdict comparable with Gen5's rather than merely
similar.

Argument against: a relative criterion is permissive exactly where absolute
accuracy matters most. At 0.5 mm Take3 path a dsDNA concentration in ng/uL is
its A260 deviation times 1000, so a CV% that looks modest on a high
background can still be several ng/uL of disagreement between blank wells.
The current absolute limits were set from the one blanking Gen5 is known to
have accepted and are, in that specific sense, grounded.

The honest answer is probably **both**: gate on CV% to match Gen5, keep an
absolute floor so a relative measure cannot wave through a blank that
disagrees by more than the smallest concentration anyone would report. That
is a change to make deliberately, with the Validation limit (CV%) value in
hand, not before.
