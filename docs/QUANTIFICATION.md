# How concentrations are calculated, and where the method came from

Not invented here. Recovered from this lab's own Gen5 exports for Take3 plate 243819
on reader 254717 (January 2014), and it reproduces their reported numbers.

## What the exports show

Every Take3 read records three raw absorbances per well: the two measurement
wavelengths and **320 nm as a reference**. For nucleic acids that is 260/280/320, or
260/230/320 when 260/230 purity is wanted. For protein, 260/280/320 reported in mg/mL.

    Sample Read# | Location | 260 Raw | 280 Raw | 320 Raw | 260 | 280 | 260/280 | ng/uL
    1            | B2       | 0.098   | 0.074   | 0.044   | 0.045 | 0.025 | 1.825 | 45.23
    1            | B3       | 0.103   | 0.078   | 0.048   | 0.046 | 0.025 | 1.840 | 46.294
    1            | C2       | 0.055   | 0.050   | 0.042   | 0.005 | 0.003 | 1.645 | 5.059
    1            | C3       | 0.059   | 0.053   | 0.044   | 0.007 | 0.004 | 1.643 | 6.841

## The calculation

1. **Remove the background.** Subtract the 320 nm reading from each measurement
   wavelength. 320 nm is where nucleic acids and protein do not absorb, so whatever
   shows up there — scattering, a fingerprint, a dirty window — is affecting all
   wavelengths roughly equally and should come off all of them.
2. **Subtract the blank**, after that background correction. Gen5 reads **one** blank
   well and applies it to every sample; it does not need a blank in each spot. Where
   several blanks are read, they are averaged.

   (An earlier draft of this document claimed per-well blanks. That was wrong, read
   out of rounding noise in a file that omitted its blank table. The 31-3-15 export
   includes its blank and settles it.)
3. **Scale to a 1 cm path**: divide by that well's pathlength in cm (see below).
4. **Multiply by the extinction factor**: 50 for dsDNA, 33 ssDNA, 40 RNA; protein uses
   1 Abs at 1 cm = 1 mg/mL.

For dsDNA, steps 3 and 4 collapse to a clean `ng/uL = A260 x 1000`, and that
reproduces all four rows above exactly (45.23 -> A260 0.04523, 46.294 -> 0.046294,
5.059 -> 0.005059, 6.841 -> 0.006841).

## Pathlength: a per-well table, not a constant

**This section corrects an earlier claim in this document.** It previously stated as
established fact that Gen5 uses a flat 0.5 mm. That was an overstatement.

Gen5's Take3 plate dialog holds a **Pathlengths (mm) table**: 16 editable cells, rows
A-H against columns 2 and 3, pre-filled with 0.5 everywhere. The user overwrites them
with the values from the plate's Take3 Pathlength Data Sheet. Whatever is in that
table is what the concentration is divided by.

The lab's exports cannot distinguish the two, because they round raw absorbances to
three decimals and every well in them is within 0.9% of 0.5 mm:

| Well | A260 if 0.5 mm | A260 if certified | Both display |
|---|---|---|---|
| C2 | 0.005257 | 0.005300 | 0.005 |
| D2 | 0.022404 | 0.022400 | 0.022 |
| E2 | 0.011020 | 0.011000 | 0.011 |

Identical at three decimals in every case. The screenshot of the dialog is what
settles it, not the data.

It matters most at the ends of the plate. On plate 243819, well A2 is certified at
0.5125 mm, so assuming 0.5 reports a concentration **2.4% low**. Row H is within 0.4%.

This software ships the certified table for plate 243819 in
`epoch_open/take3.KNOWN_PLATES`, keyed by serial number, so the sheet never has to be
retyped. An unknown plate falls back to the 0.5 mm nominal, as Gen5 does.

### Calibration is a different thing entirely

Gen5's **Calibrate...** button runs a physical routine: it reads well A2 and derives
**X Offset and Y Offset in micrometres** — where the micro-spots sit relative to the
beam in that particular reader. It must be measured; it cannot be typed in, and it has
nothing to do with the pathlength table. The two are independent fields in the same
dialog, and neither is a prerequisite for the other.

## Two assumptions that were wrong, and how we know

This project originally implemented the **NanoDrop** method: measure each drop's
thickness from the water absorbance peak (A977 - A900) and divide by a per-drop
pathlength. That is a defensible way to quantify, and it is self-calibrating, but it
is **not what Gen5 did on this instrument**:

- Gen5 never reads 977 or 900 on a Take3. The exports only ever show 260, 280, 230
  and 320.
- The pathlength is a flat **0.5 mm**, not measured per drop. Backing it out of four
  wells gives 0.5000 mm every time, to four decimal places.
- The plate's certified per-well pathlengths (0.4973-0.5125 mm, on the Take3
  Pathlength Data Sheet) are **not** used in the concentration either. They are a QC
  document showing the plate was made within tolerance.

The lab does have a NanoDrop and exports from it look entirely different (Sample ID,
ng/ul, A260, A280, 260/280, 260/230, Constant, Cursor Pos.). The two instruments are
not expected to agree exactly, and neither is wrong.

## Why match Gen5 rather than improve on it

This lab has years of results produced the Gen5 way. Software that silently disagreed
would be worse than useless: every disagreement would look like a sample problem. So
the default reproduces Gen5.

Measuring the pathlength per drop would be a genuine improvement — it catches a drop
that did not bridge the gap, which a flat 0.5 mm assumption cannot. The Epoch can read
977 and 900. That is worth adding later as an optional check that *warns* rather than
one that changes the reported number.

`PATHLENGTH_MM` is a module constant so this can be revisited deliberately.

## Verified end to end

`31-3-15_DNA_APP_muestras_G_-_H_-_I__1a_y_2a_elucion.xlsx` contains both the samples
and the blank Gen5 used, so nothing has to be inferred. Blank well B3 reads
260/280/320 = 0.053 / 0.049 / 0.044, giving a background-corrected blank A260 of 0.009.

| Well | 260 raw | 320 raw | ours | Gen5 | Gen5 ng/uL |
|---|---|---|---|---|---|
| C2 | 0.058 | 0.044 | 0.005 | 0.005 | 5.257 |
| C3 | 0.052 | 0.043 | 0.000 | 0.000 | -0.297 |
| D2 | 0.087 | 0.056 | 0.022 | 0.022 | 22.404 |
| D3 | 0.059 | 0.048 | 0.002 | 0.002 | 2.497 |
| E2 | 0.072 | 0.052 | 0.011 | 0.011 | 11.020 |
| E3 | 0.051 | 0.041 | 0.001 | 0.001 | 1.402 |

Six of six exact, from one blank well. This is pinned by
`TestAgainstRealGen5WithItsOwnBlank` in `tests/test_quant.py`.

Note C3 and the other second elutions: Gen5 happily reports -0.297 ng/uL. This
software reports the same number but adds a warning, because a negative or
near-zero concentration means "nothing detectable here", not "-0.3 ng/uL of DNA".

## The two export formats

Gen5 writes both, in one workbook:

- **Sheet 1, the summary** — a matrix laid out by the technician's own sample names
  ("1a eluc" / "2a eluc" against G, H, I), with 260, 280, 260/280 and ng/uL stacked
  per row. This is the sheet a person reads.
- **Sheet 2, the detail** — one row per physical well: `Sample Read#, Location,
  260 Raw, 280 Raw, 320 Raw, 260, 280, 260/280, ng/uL`. This is the audit trail, and
  `Sample Read#` is what lets several plate loads accumulate into one file.

This software currently writes the detail sheet. The summary sheet needs the sample
names to be entered first, which is a GUI question, not a format question.

## The two blanking modes

Gen5 offers both, and so does this software:

- **Blank one spot (or a few) and apply it to everything.** The 31-3-15 DNA export
  blanks B3 alone and uses it for all six samples. The clean-RNA export blanks A2 and
  A3 and prints an `[AVE]` row with a CV% per wavelength.
- **Blank every spot you will use**, then read samples in the same spots. A blank read
  in a given spot always wins over the average.

`blank_for()` implements exactly that precedence: exact spot first, otherwise the mean
of whatever blanks were read.

### Blank spread is a warning worth having

Gen5 prints a CV% beside its averaged blank. `check_blanks()` computes the same figure
and warns above 5%. Blanks that disagree mean a dirty spot, a bubble, or a drop that
did not bridge the gap -- and every concentration computed from them inherits it. It is
the cheapest check available, and it happens before any sample is consumed.

## RNA, verified

`clean_RNA_test_SA-APA_1a_eluc-_Turboambion.xls` (May 2017, legacy .xls) blanks A2+A3
and reads four samples as RNA. Mean blank 0.0435 / 0.041 / 0.038 reproduces Gen5's
`[AVE]` row, and the concentrations follow `ng/uL = A260 x 800` -- the 0.5 mm path and
RNA's factor of 40.

| Well | Gen5 ng/uL |
|---|---|
| B2 | 9.165 |
| B3 | 34.913 |
| C2 | 7.062 |
| C3 | 38.311 |

Agreement here is only to about +/-1 ng/uL, because that export rounds its raw
absorbances to three decimals while Gen5 calculated from unrounded ones. The 31-3-15
file, whose numbers happen to be exact at three decimals, is the one that pins the
formula to the digit.

## Confirmed: Gen5 uses the plate's certified pathlengths

Settled on 26 October 2026 against a GeneRuler run where both the blank and the
sample numbers were available.

Gen5 blank A3: 260/280/320 = 0.053 / 0.050 / 0.045, so a blank delta of 0.008.

Predicting Gen5's own reported values with: subtract 320, subtract the blank,
divide by **that well's certified pathlength**, express against the 0.5 mm nominal:

| Well | path (sheet) | predicted 260 | Gen5 260 | predicted ng/uL | Gen5 ng/uL |
|---|---|---|---|---|---|
| A2 | 0.5125 | 0.4361 | 0.436 | 436.1 | 436.5 |
| B2 | 0.5063 | 0.4405 | 0.440 | 440.5 | 440.4 |
| C2 | 0.5041 | 0.0188 | 0.019 | 18.8 | 19.4 |
| D2 | 0.4999 | 0.0410 | 0.042 | 41.0 | 41.6 |

Exact to the printed precision, for all four wells across a tenfold concentration
range. This software uses the same formula and the same table, so the two agree by
construction; what is left between them is the raw absorbance of the drop itself.

This also closes the question left open earlier in this document: the pathlength
table in Gen5's Take3 plate dialog is **not** decorative, and entering the values
from the plate's data sheet changes the answer. Using the 0.5 mm nominal instead
would read ~2.4% low on well A2 of plate 243819.

### A wrong turn worth recording

While working this out, the implied blank was back-computed from the sample numbers
without accounting for the pathlength normalisation, producing an apparent 0.011 AU
discrepancy in Gen5's blank handling. There was none. The arithmetic had simply
omitted a step that Gen5 performs.
