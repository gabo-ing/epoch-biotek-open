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

> **Confirmed against Gen5's own output, 19 November 2026.** "Each
> wavelength" includes the 320 nm reference. In `Gen5_LVA_NAQ_0014` the
> blanking Gen5 called VALID has CV 260: 6,05, 280: 6,8, 320: 9,9, and the
> 9,9 is both the highest of the three and the figure the screen displayed
> as the verdict. A draft that afternoon briefly concluded the opposite; see
> below for how, because the way it went wrong is worth keeping.

Three consequences, in order of how much they cost us:

1. **There is no Gen5 constant to recover.** `docs/BLANK_THRESHOLD.md` was
   written to measure one experimentally. It cannot succeed as designed,
   because the number it was hunting is a per-protocol setting, not a
   property of Gen5. Whatever the experiment measured would have been that
   laptop's configuration.

2. **Our criterion is a different kind of thing.** `BLANK_DISPERSION_LIMIT_AU`
   and `BLANK_DIVERGENCE_LIMIT_AU` are absolute, in absorbance units. Gen5's is
   relative, a coefficient of variation. They disagree in opposite directions
   at the two ends of the range: on a very clean blank a CV% limit is
   stricter than ours, and on a blank with a high background it is looser.

   `BLANK_DISPERSION_LIMIT_AU` was a highest-to-lowest range until 18 November
   2026, which made it a third kind of thing again: a statistic that grows with
   the number of wells, judged against a limit that does not. It is now a
   standard deviation, so like Gen5's CV% it means the same whether two wells
   were blanked or all of them. See `blank_dispersion()` for the whole story,
   which starts with a technician who blanks every well before using it.

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

## Gen5 reading a plain 96-well plate, 3 November 2026

It does. The question was open because this project had only ever seen Gen5
drive a Take3, and `epoch-multispectral` addresses an ordinary flat plate
that nothing had confirmed the instrument would read.

**The read step.** Detection method Absorbance, read type Endpoint, read
speed Normal, pathlength correction available but unticked. Dataset names
follow `<step label>:<wavelength>`, so a step labelled "530" reading three
wavelengths produces `530:530`, `530:560` and `530:590`.

**Wavelengths per read: six.** The selector offers 1 to 6 and stops. The
protocol's own count field holds a single digit, so nine would fit, and nine
is what `curve.SCAN_NM` asked for until this screenshot. Whether the
instrument accepts seven is untested; the software written by the people who
built it never asks, so the peak scan now asks for six as well -- 490 to 590
at 20 nm, bracketing 530 symmetrically.

**Read speed** is a setting this project does not expose at all. Noted rather
than acted on; "Normal" is what Gen5 uses and what the reader presumably
defaults to.

### The empty-plate baseline

A brand-new, unopened Jet Biofil TCP011096 read dry across all 96 wells:

| | |
|---|---|
| range | 0.045 - 0.049 AU |
| spread | 0.004 AU across the whole plate |

That is the plate's own absorbance with nothing in it, and it is flat enough
that the plate contributes no meaningful well-to-well variation. It is also a
reference number: an empty plate of this type read in `epoch-multispectral`
should land in the same place, and if it does not, the flat-plate geometry is
wrong.

## epoch-multispectral's first read, 3 November 2026

The same plate, empty, read on the same instrument minutes apart. Gen5 at
560 nm against `epoch-multispectral` at 560 nm, all 96 wells:

| | |
|---|---|
| wells identical to three decimals | **85 of 96 (89%)** |
| largest disagreement | 0.0010 AU -- one last-digit step |
| mean signed difference | -0.00005 AU |
| mean absorbance | 0.0472 both |

The eleven differing wells differ by exactly one digit, scattered in both
directions, which is what two separate reads of the same plate look like on
an instrument whose own noise is about 0.001 AU. There is no offset between
the programs.

**What this does and does not prove.** It proves the read path works end to
end against real hardware: the plate-setting command for a non-Take3
geometry, the multi-wavelength assembly, the response parsing, and the
numbers that come out. It does **not** prove the wells are addressed
correctly, because an empty plate is uniform -- a geometry off by a whole
column would read 0.047 everywhere and look perfect. That needs a pattern;
see the L-shape test in `docs/MULTISPECTRAL.md`.

It also cost 156 seconds for 96 wells at three wavelengths, which is worth
knowing before anyone waits on it with reagents developing.

### The bug it found immediately

The first attempt did not reach the carriage:

    ValueError: column 1 is not one of (2, 3)

`read_plate` converted well names with `take3.well_to_indices`, which refuses
any column but the Take3's. A flat 96-well plate was unreadable, and none of
the 345 tests saw it, because the simulator has its own `read_plate` that
never touches the conversion. Every test of the colorimetric program ran past
the broken line.

Addressing is now done by the geometry, which both plates declare as 8 x 12 --
the Take3's spots sit at ordinary 96-well positions, which is exactly why it
is addressed as a 12-column plate with two columns in use. `take3`'s own
mapping is still there and still refuses A1, because it answers a different
question: not "can the optics be pointed there" but "is there a micro-spot
there". `tests/test_plate_addressing.py` pins both.

## Measured against Gen5 itself, 19 November 2026

Everything above this line came from Gen5's help files and its exports. This
section came from running Gen5 and epoch-open against the same loaded Take3
plate, minutes apart, on the borrowed Dell in the last week of its demo
licence. Source files: `Gen5_LVA_NAQ_0010` through `0015`, which Gen5 writes
to `C:/ProgramData/BioTek/Temp/`.

### The formula, confirmed exactly

Back the blank out of Gen5's own Sample Results table, well by well:
`(260 raw − 320 raw) − Gen5's 260 column`. Across all sixteen wells of two
separate runs, spanning two waters six times apart in concentration, the answer
is one constant. So:

```
corrected   = 260 raw − 320 raw
reported    = corrected − mean(kept blank wells)
ng/uL       = corrected × 1000          (0,5 mm pathlength, 50 ng/uL per AU)
```

The ng/uL factor was checked the other way round too: Gen5's `ng/µL ÷ 1000`
matches its own printed `260` column to within 0,0005 AU, which is the rounding
of a three-decimal column. This is `quant.py` exactly.

### The verdict, matched on both sides

| | Gen5 | epoch-open |
|---|---|---|
| refused | 25,588% @ 09:33 | 26,12% @ 09:32 |
| accepted | 6,136% @ 09:59 | 6,320% @ 10:02 |

0,5 and 0,18 points apart. Two epoch-open reads of the same loaded plate four
minutes apart differ by 5,8, so the programs are closer to each other than one
program is to itself across the plate's drift.

### Gen5 has no cleanliness check at all

`Gen5_LVA_NAQ_0014`, the Blank Results table itself: blank forced onto six
wells of contaminated water, **0,0382 AU, roughly 38 ng/uL**. Gen5: **VALID**,
CV 9,902%. The sample read that used it is `0015`.

The same run reported eight spots of clean water at −31,6 ng/uL, each with a
260/280 between 1,93 and 2,05 — negative over negative. Gen5 prints those
ratios without comment, and prints −13,800 and −16,647 elsewhere in the same
file where both corrected values are near zero. We return nothing when the
denominator is under 1e-4, and we emit a "negative concentration" warning on
every well where Gen5 says nothing. Both divergences are deliberate and ours
is the better behaviour.

**Consequence for us:** `BLANK_LEVEL_WARN_AU` warns, never refuses.

### The reference wavelength is judged -- and how we briefly thought otherwise

The screen for the 09:47:48 blanking said VALID, CV 9,902%. Reading the 320 nm
values for its six kept wells out of `Gen5_LVA_NAQ_0015` gave a CV of 12,10%,
over the limit of 10. The only rule consistent with that pair is one that
excludes the reference, so `judged_cv()` was written, tested, committed and
pushed.

`0015` is the **sample** read, at 09:51:58. The blanking was read at 09:47:48
and its Blank Results table is in `0014`, which prints 320: 9,9 -- under the
limit, the highest of the three, and precisely the 9,902% on the screen. Two
different reads of the same spots. Reverted the same afternoon, as soon as the
HTML files were copied off the laptop.

Nothing about blanking follows from this. What follows is about evidence: every
Gen5 number this project had until then came off a photograph of a
three-decimal column, and in a photograph a sample table and a blank table look
identical. The reports name which is which. **Prefer the file.**

Not separately settled, and no longer interesting: whether 280 nm is judged. It
is, by the same rule.

### The blanking Gen5 accepted that we refuse

`Gen5_LVA_NAQ_0010` plus the screenshot of 09:38:28. Gen5 showed DIVERGING at
17,552%, reddened B3, C2, C3, D3 and H2, those five were discarded, the CV fell
to 9,08 and Gen5 read samples against the remaining eleven (`0011`).

Those eleven are two different waters. Corrected, A–D average **0,0070 AU** and
E–H average **0,0196** — nearly three times apart. The blank Gen5 subtracted,
0,0150, was wrong for every well on the plate, carrying about **8 ng/uL** of
error into each A–D sample.

CV% on raw absorbance cannot see this. Most of each raw reading is the 320 nm
background, which both waters share, and it swamps the difference between them.
The sample standard deviation of the **corrected** values sees it at once:
0,0064 AU against a limit of 0,0025.

This is the first measured case of `BLANK_DISPERSION_LIMIT_AU` earning its
place rather than being argued for, and it is worth keeping in mind that the
gate's cost is real — it is the one rule that can stop a technician reading a
plate Gen5 would have read. Here, being stricter is right.

Our red set also differs: Gen5 drops the fewest wells that satisfy its single
gate, five of them, and keeps a mixture of both waters. We satisfy two gates and
drop eight, keeping one water. Neither answer is recoverable from the other and
both are defensible. Pinned in the tests so the difference stays a known one.

### Reading samples after discarding blank wells

Confirmed at the bench and in the screenshots: Gen5 leaves *Read Samples*
greyed out while any reddened well is still selected as a blank. Deselect them
and it unlocks. **The sample plate is independent** — a well dropped from the
blank can still be read as a sample, and on 19 November all sixteen were. Our
two grids behave the same way, which is why the Blank and Samples grids are
drawn side by side rather than as one selection.

### Gen5's red/green is a tie-break, not a diagnosis

With eight spots of one water and eight of another, Gen5 reddened **A–D at
09:33 and E–H at 09:47** — opposite halves, same layout, fourteen minutes
apart. In an 8-against-8 split there is no majority to appeal to and the tie
breaks on noise. Worth knowing before trying to make our red set agree with
Gen5's: on a bimodal blanking there is nothing to agree with.

## What is still worth doing on the trial laptop

**Nothing, as of the evening of 3 November 2026.** Everything the trial could
uniquely answer has been answered, and in a single afternoon rather than the
day of pipetting that was planned:

| | |
|---|---|
| the threshold | read off the Preferences dialog: CV% <= 10 |
| the reference limit | 0.1 OD at 0.5 mm, same dialog |
| how a failure looks | Status DIVERGING, CV% 29,242, the smudged wells red |
| can it read a flat 96-well plate | yes, and the numbers match ours to 0.001 AU |

What remains in `docs/BLANK_THRESHOLD.md` is the absolute-accuracy check, and
that needs a reference material rather than Gen5 -- the question is not
whether the two programs agree, which they do, but whether both are offset
from the truth together. So it is off the 25 November clock and should wait
for a proper standard.

If the trial is opened again before it lapses, the one thing worth grabbing
is whatever is cheap and cannot be recovered afterwards: screenshots of
anything this project has reasoned about without seeing.

**It was opened again, on 19 November 2026, and that paragraph was right.**
The licence turned out to have a week left on a second laptop, and the
afternoon produced the three things above that no amount of reasoning here
could have supplied: a blanking Gen5 refused, a filthy blanking Gen5 accepted,
and its sample arithmetic at full precision. One of them found a real bug in
our verdict. The remaining days are worth spending the same way.

`C:/ProgramData/BioTek/Temp/` was copied to `/home/gabo/epoch` the same
morning, fifteen reports, `0001` through `0015`. That folder is now the best
evidence this project has about Gen5 and it immediately overturned a conclusion
drawn from photographs of the same runs. Its Blank Results tables print the
kept wells plain and the discarded wells between asterisks, which is how the
red/green sets above were recovered.

### Gen5 never writes a report for a blanking

Confirmed at the bench: Gen5 produces a report only when it reads **samples**,
and it will not read samples until the blank is valid. So no Gen5 file can ever
carry a refused verdict, and asking for one is asking for something that does
not exist.

That looked for a long time like the reason this project had no Gen5 refusal to
calibrate against. It was not. **The Blank Results table inside a sample report
lists every blank well, including the discarded ones**, between asterisks. The
raw data of the refused blanking is therefore in the file; only the verdict is
on the screen. Pair the report with a screenshot of the moment its blank was
read and the refusal is fully reconstructed.

Two were recovered that way, and both are now tests:

| blank read | Gen5's screen | ours | gap |
|---|---|---|---|
| 09:38:28 (`0010`) | DIVERGING, 17,552% | 17,613% | 0,061 |
| 09:47:48 (`0012`, `0014`) | DIVERGING, 30,374% | 30,439% | 0,065 |

Both refused by both programs, on CV%, inside the rounding of a three-decimal
column. The technician's workaround is what made them exist at all: read the
blank, discard whatever Gen5 reddens so the run can proceed, then read **all
sixteen** sample wells including the ones just discarded as blanks.

Still worth grabbing before the licence lapses:

1. One read with no plate in the carrier. It has to be done as a *sample* read
   against a valid blank, since that is the only thing that writes a file.

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
