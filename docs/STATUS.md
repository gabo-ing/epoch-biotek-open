# Where this project stands — close-out, 9 November 2026

The instrument has been moved to its definitive lab, and the software was installed
there on a new computer straight from this repository, with no problems. This file is
the record of what is finished, what was proven on real hardware, and what is still
open, so that whoever picks the project up next — including a future me — does not have
to re-derive it.

## What exists

Two programs on one driver (`epoch_open/reader.py`), one look (`epoch_open/ui.py`),
one Excel writer (`epoch_open/xlsx.py`):

| Program | Arithmetic | Plate |
|---|---|---|
| **epoch-take3** (`run_take3.py`) | concentration from physics (Beer–Lambert at a known pathlength) | Take3 micro-volume, 16 spots A2–H3 |
| **epoch-multispectral** (`run_multispectral.py`) | concentration interpolated from standards measured in the same run | ordinary transparent 96-well |

Both talk to the Epoch over its RDOP22 serial protocol through the FTDI bridge, finding
the port by USB **serial number** rather than device path, so a replug does not break
the run. Up to six wavelengths per read, taken in one carriage pass each, chosen in a
separate preferences-style window.

**Never put a Take3 plate in a multispectral read.** It can be damaged irreversibly;
the warning is in the UI for that reason.

## Intellectual property

Nothing here modifies, patches, bypasses or disassembles the vendor software, and
nothing depends on it at runtime. Where this software matches Gen5's behaviour, the
behaviour was read out of Gen5's own help files and its shipped plate definition files
— documentation, not code. The purpose is lawful use of an instrument the lab owns
whose licence activations were exhausted. Keep it that way.

The Gen5 trial used for cross-checking **expires 25 November 2026**. After that date
the comparisons below cannot be repeated, which is why they are written down here.

## What was proven on real hardware

- **Read path against Gen5.** A full 96-well plate read by both programs: 85 of 96
  wells identical to three decimals, largest disagreement 0.0010 AU.
- **Well addressing.** An L-shaped pattern of loaded wells: 17 loaded, 17 detected, in
  the right places, +0.1218 AU separation from the empties.
- **Plate geometry.** `PLATE_96` corroborated against 35 of Gen5's own plate
  definition files.
- **Gen5's blanking rule**, recovered from its help files and reproduced here: CV% on
  **raw** absorbances, **sample** standard deviation (n−1), against a user-set
  validation limit of 10%; high-reference margin 0.100 OD at 0.5 mm. The n−1 question
  was settled from a two-well Gen5 blank, where the two estimators differ by √2 —
  Gen5 printed 6,35 against 6.37 (n−1) and 4.50 (n). This finding invalidated a week of
  planned bench work; see `docs/BLANK_THRESHOLD.md`.
- **RNA quantification, twice a minute apart** (`cuantificacion_20261105_115*.xlsx`):
  C2 at 149.2 / 148.8 ng/µL, C3 at 163.0 / 162.2 ng/µL — agreement of 0.23% and 0.45%,
  raw repeatability around 0.0005 AU on a 0.26 AU signal. The 260/230 ratio of 1.48 on
  C2 indicates guanidine or phenol carryover, which inhibits reverse transcription;
  that is a sample problem, not an instrument one.
- **macOS, end to end**, including a plate read, after `build_macos.sh` was fixed for
  Homebrew Python's PEP 668 externally-managed environment.
- **The first real calibration curve** — see below. Until it existed, every curve test
  had been checking arithmetic against data generated to satisfy it.

## The first real calibration curve

`multispectral-20261105-1309.xlsx`, a Salkowski series at 530 nm with three standards,
blank 0.0406 AU:

```
B1   10 µg/mL   0.0679   residual +0.0081
C1   20 µg/mL   0.0981   residual -0.0108
D1   50 µg/mL   0.2589   residual +0.0027

absorbance = 0.00491 × concentration + 0.0107      r² = 0.99101
```

Everything behaved as designed on data it had not seen:

- the r² gate at 0.98 passed the curve and marked it `UTILIZABLE`;
- the three-standard warning fired — with so few points a pipetting error cannot be
  told from the real slope;
- the worst residual, 0.0108, stayed well inside the 0.10 limit;
- six of nine samples were correctly refused as out of range, their absorbance lying
  above the top standard, instead of being quietly extrapolated.

Two honest wrinkles, both small and both still open:

1. **H5 was flagged out of range by 0.0003 AU** (0.2592 against a top standard of
   0.2589). Technically right, practically noise. A tolerance of roughly the read
   repeatability — about 0.001 AU — before declaring extrapolation would be kinder.
2. **The Detalle sheet leaves the standards' absorbance cells empty.** Their
   blank-corrected values appear on the Curva sheet, but their raw readings are
   recorded nowhere, so a reader cannot re-derive the fit from the file alone.

## Language, added 10 November 2026

The interface was Spanish only, which is right for the lab it was written for
and wrong for a repository anyone can clone. It now speaks **English by
default and Spanish on request**: 249 strings across eleven tables, chosen at
startup from `"language"` in the configuration, the Preferences dialog, or
`--lang`.

Three things are worth knowing before changing any of it:

- **The English is Gen5's vocabulary**, taken from its help files and its
  exported result tables rather than translated back from the Spanish:
  *Validation limit (CV%)*, *Reference wavelength*, *Standard*, *Known
  concentration*, *Blank Results*, *CV (%)*, *Out-of-Range*. The point is that
  the two programs' spreadsheets line up column by column.
- **The detail sheet's headers are deliberately not translated.** They already
  copy Gen5's export exactly -- `Sample Read#`, `Location`, `260 Raw` -- in
  both languages, which is what makes that sheet recognisable.
- **The decimal mark follows the language**: `0,1` in Spanish, `0.1` in
  English. Input has always accepted either; it was the display that was
  fixed to a comma.

The mechanism is in `epoch_open/i18n.py`. Each module keeps its own `TEXT`
dict and registers per-language tables against it; switching refills every
dict **in place**, so the two hundred-odd `TEXT["key"]` call sites did not
change and nothing has to be rebound. The refactor was proved inert before any
English existed, by dumping every table to JSON and diffing it after.

`tests/test_i18n.py` asserts the two languages have the same keys and the same
`{placeholders}`, that nothing was copied across untranslated, and that an
English workbook contains no Spanish. The whole suite passes under both
languages -- `EPOCH_LANG=es python3 tests/run_tests.py` -- which is the check
worth repeating, because a test that quotes one language's words silently
stops testing anything in the other.

**Verified on screen**, not only in tests: both programs were launched on a
real display in both languages and their windows photographed or their widget
trees read back. The layout survives; the English strings were kept no longer
than the Spanish precisely so that it would.

## Still open

- **An absolute sanity check on the blank's level.** Every check we have asks whether
  the blank wells agree with *each other*; none asks whether the blank is plausible at
  all. On 18 November a water blank reached 0.105 AU corrected — 16x what Gen5 accepted
  in October, and ten times a 10 ng/uL sample — and had all sixteen spots been
  uniformly that dirty it would have passed. This is the mirror of the empty-carrier
  case below: that one is a mean near zero, this is a mean far too high. A warning
  rather than a refusal, above roughly 0.02 AU, would have caught every bad run that
  day and none of the good ones. Not built: the threshold wants one Gen5 opinion on a
  high-but-consistent blank, which the remaining trial days can supply.
- Validation **Part F**: absolute accuracy against a reference standard. It needs a
  certified standard, not Gen5, so the trial expiry does not block it.
- The two curve wrinkles above.
- Rebuild on the Mac to confirm the Retina layout fix on hardware; it was fixed and
  tested, but the last build predates the fix.
- Known capability gaps, all deliberate: a blank on each sample well, the Take3 BioCell
  (A9, H9) and cuvette (E10, E11) positions, the 4-parameter logistic fit ELISA wants,
  and Gen5's extrapolation factor.
- Cosmetic: the 230 nm checkbox ("Also read 230 nm" / "Leer tambien 230 nm")
  is oversized on macOS.
- **This lab's own machines will come up in English after the upgrade** unless
  `"language": "es"` is set in `epoch_open.json`, or chosen once in
  Preferences. That is the cost of making English the default, and it is paid
  by the people who need it least -- worth doing on each bench PC before the
  next run.
- The screenshots in the README and in `docs/img` still show the Spanish
  interface. Not wrong, but an English-speaking visitor now sees a screen that
  does not match what they will get.
- **A blank read with no plate in the carrier reports nonsense, confidently.** See
  below.
- **Blanking every well used to be refused for being too many wells.** Fixed
  18 November 2026; see below.

## The empty-carrier blank

On 9 November 2026, during the install on the new lab computer, a blank was read with
**no plate in the instrument at all**, on A2, A3, B2, B3, C2, C3. One well came back
divergent, the blanking was refused, and deselecting that one well re-enabled reading
samples. The instrument went back before any readings could be kept, so the numbers
below are a reproduction rather than that run's own data — but the behaviour they
produce matches what was seen, step for step.

Feeding air-like readings through `blank_report()` reproduces it from the arithmetic
alone:

| blank | CV% at 260 | verdict |
|---|---|---|
| air, 0 ± 0.0005 AU | 397% | failed |
| air, five at 0.0000 and one at 0.0003 | 245% | failed, **one well named** |
| air offset ~0.005 ± 0.0005 AU | 5.8% | passes |
| real water blank, ~0.050 AU | 2.1% | passes |

The cause is that **CV% is SD divided by the mean**, and with no plate the mean is
about zero. A difference of 0.0003 AU — a third of the instrument's own repeatability,
and utterly meaningless — becomes a CV of 245% and names a well. `blank_cv_percent()`
guards only `abs(mean) < 1e-9`, which a near-zero mean sails straight past.

The rest of the behaviour matches too. With all six wells in, the blanking is refused
and C3 is named; take C3 out and the remaining five pass at CV 0%; take out an innocent
well instead and it still fails and still points at C3. So `wells_to_discard` did its
job exactly right — it named the one well whose removal fixes the blanking, and would
not be talked into blaming another. The machinery is sound; it was handed an input that
means nothing.

So: **an empty-carrier blank is evidence of neither a fault nor of health.** The gate
is a relative measure and there is nothing for it to be relative to. A real water blank
on the Take3 reads about 0.045–0.058 AU raw at 260 nm and passes with CV around 2%, so
the two cases separate cleanly — which is also why a guard is possible.

**The guard is not built**, deliberately. Refusing to judge a blank whose mean sits
below, say, 0.01 AU and saying "parece que no hay placa en el lector" instead would be
a few lines. But the threshold should be set from one real empty-carrier reading, and
we have none: the numbers above are invented to probe the arithmetic, and inventing a
limit from invented data is how the old blanking rules went wrong. Take one empty read
the next time an Epoch is available, then set it.

This matters more than it looks, because reading a blank with nothing loaded is exactly
what someone does when they install this from GitHub and want to see the thing move.
The first impression should not be a red well.

## Blanking every well, 18 November 2026

The technician in the definite lab blanks **every well she is about to use** before
using it, rather than the two or eight these thresholds were set from. Doing that, she
was refused over and over, with wells painted red — and when asked which well, she said
it was a different one each time.

A different well each time is the diagnosis. A dirty spot is the same spot twice.

The cause was ours. The absolute floor under Gen5's CV% check was `max - min` of the
corrected blank wells, against a fixed 0.004 AU limit. A range grows with the number of
wells however good the blanking is — the expected highest-to-lowest of n draws is about
2.85 standard deviations at n=8 but 3.90 at n=24 — so the gate tightened the more wells
she blanked. Meanwhile the quantity that limit exists to bound, the error the blank
injects into every sample, is the error of the **mean** blank, and that shrinks as
1/sqrt(n): on the real eight-well blank, from 0.00031 AU at n=8 to 0.00018 AU at n=24.
**The gate tightened as the thing it guards against got smaller.** She was refused for
having been more careful, not less.

What it is now: the sample standard deviation of the same corrected values, which
estimates the same per-well disagreement at any number of wells, and is the absolute
counterpart of the CV% it sits under. Reproduced with the simulator at the size she was
working at, sixteen wells, before and after:

| blanking | refused before | refused now |
|---|---|---|
| whole plate, 16 wells | 27 of 40 reads | 0 of 40 |
| one column, 8 wells | 13 of 40 | 0 of 40 |
| four wells | 1 of 40 | 0 of 40 |

The limit, 0.0025 AU, is set from what the known quantities are rather than converted
from the old one. Converting was the first attempt — 0.004 divided by 2.85 — and it
reintroduced the same bug in reverse, because a standard deviation estimated from two
wells is a very noisy estimate of itself: across 400 simulated two-well blanks it
reaches 0.0021 AU where the same simulator at eight wells never passes 0.0014. A flat
0.0014 would have refused about one two-well blank in twelve on a clean plate, and two
wells is this lab's commonest blanking.

| | corrected SD |
|---|---|
| the real blanking Gen5 accepted (`Gen5_LVA_NAQ_0001`, 8 wells) | 0.00089 AU |
| the real two-well blanking Gen5 accepted (`Gen5_LVA_NAQ_0008`) | 0.00000 AU |
| worst of 400 simulated two-well blanks, none of which should warn | 0.00212 AU |
| **the limit** | **0.0025 AU** |
| two wells disagreeing by 0.005 AU, which the tests require be refused | 0.00354 AU |

One consequence is deliberate: **a single bad drop among twenty-four now passes.** It
should. That well is a twenty-fourth of the blank, so a spot 0.003 AU out moves what
gets subtracted by 0.0001 AU, which is nothing at 0.5 mm. It is still painted red by
`divergent_blank_wells` so the spot can be wiped or dropped — the screen says VALID and
the read button stays live. Naming the well was useful; refusing the read over it was
not. Tell her that red no longer means she cannot read.

Two things came out of not being able to answer "which well?":

- **The screen could not say which limit had stopped her.** The CV% message said
  "above the limit" and the disagreement message said "do not agree with each other",
  which are the same sentence to anybody who has not read the source, and neither
  carried a number. Both now give the measured value and the limit it passed.
- **The workbook recorded nothing about the blank.** Every concentration in the file
  was computed by subtracting it, and the file did not say which wells it came from,
  how well they agreed, or whether any had been dropped. This had to be diagnosed from
  Gen5's own HTML exports instead of from the lab's own spreadsheets. The summary sheet
  now carries the wells, the CV% per wavelength, the disagreement, the verdict, and any
  discarded wells — written whether the blank passed or not, since a blank accepted on
  a loosened limit is the one somebody will want to see.

A follow-on found the same afternoon, by trying to use the fix: **a refused blank
could not be saved at all.** Exporting required results, a refused blanking produces
none by definition, and so the one run whose numbers somebody needs was the only run
that could not produce a file — the technician was left with a screen she could
photograph. Saving is now available whenever there is a blank, with or without
samples. A blank-only save is named `blanco_`/`blank_` rather than
`cuantificacion_`/`quantification_`, and it **does not close the batch**: she still
has the same plate in front of her, and pressing save to send somebody the numbers
must not cost her the blanking it records.

Two more came out of the same afternoon.

**The saved blank had no per-well numbers in it.** The footer gave the CV%, the
disagreement and the verdict, and then a blanking failed in a way none of the three
could explain — two of four wells reddened, with no way to tell from the file whether
they had read high or low. The difference matters: a drop that evaporated leaves its
salts behind and reads high, one that never bridged the 0.5 mm gap reads low. The
workbook now has a third sheet, **Blanco / Blank**, carrying every blank well's raw
absorbance at every wavelength, then `[PROM]`/`[AVE]` and `CV (%)` — Gen5's own table,
with Gen5's own column names, so the two can be read side by side. A well she discarded
is still listed and marked, because what was thrown away is part of the record.

**The red wells had stopped meaning "discard these".** `wells_to_discard` replaced a
distance-from-the-median rule precisely because the median rule reddens every well on
two clean spots and two smudged ones — the case photographed on 3 November 2026. The
test choosing between the two rules asked only whether the *CV%* had failed, so making
the disagreement limit a gate of its own quietly handed the red paint back to the
retired rule. On a four-well blanking split two and two, all four went red, which tells
her nothing. Both the chooser and `wells_to_discard` now respect both limits, and the
smudged pair alone is reddened again.

**And a valid blank with red wells said nothing.** Asked at the bench the same day:
*"if red but valid, can it be used?"* It can — that is the whole point of letting a red
well stop blocking the read — but the screen showed VALID in green, painted two wells
red, and printed nothing connecting the two, so the question was the screen's fault.
A valid blanking with wells reddened now says so and names them: *Blanco VALIDO: ya
puedes leer muestras. A2, A3 son los que mas se alejan del resto.*

Still open: the config key changed from `blank_spread_limit_au` to
`blank_dispersion_limit_au`, because the number means something different now and a
file still carrying `0.004` under the old name would have been read as a very loose
limit rather than a slightly tight one. A machine with the old key in its
`epoch_open.json` silently falls back to the new default, which is the safe direction,
but the stale key stays in the file until somebody opens Preferences and saves.

## Running the tests

```
python3 tests/run_tests.py        # 449 passed as of this commit
```

One trap, learned the hard way: **the GUI tests return early with no display and the
run still reports every test as passed.** A green 449 from a headless machine has not
exercised a single window. `tests/test_gui_starts.py` exists to tell "no display" apart
from "broken" — run the suite where there is a real display before trusting it.
