# Gen5's blank threshold

**Answered on 3 November 2026. It is a setting, not a constant.**

    Validation limit (CV%)   10

A field in Gen5's Take3 Preferences dialog, carrying 10 on a fresh
installation, for both Nucleic Acid Quantification and Protein A280. Gen5
computes a CV% for each wavelength on the **raw** absorbances and refuses to
read samples while the highest of them exceeds that number -- or cannot be
calculated at all, which is why a one-well blank fails.

The number came from opening the dialog and looking. It took about thirty
seconds.

## What this document used to be

A six-part bench procedure for measuring that threshold experimentally: a
dilution series of ladder at 1, 2, 3, 5, 10 and 20 ng/uL, nine reads, a
spiked well moved through a column, two consecutive INVALID runs to bracket
the boundary. Roughly a day of careful pipetting.

**It would not have worked**, and the reason is worth keeping. It assumed the
threshold was a property of Gen5 waiting to be reverse-engineered. It is a
per-protocol setting. The experiment would have measured whatever that
laptop's configuration happened to be and reported it as Gen5's rule -- an
answer that looks like a measurement, is reproducible, and is wrong in a way
nothing inside the procedure could have caught.

The whole thing rested on one unexamined assumption, and no amount of care
within it would have helped. The procedure itself is in the project's history
rather than here; `git log -p docs/BLANK_THRESHOLD.md` has it if it is ever
wanted.

## What Gen5 does when a blanking fails

Photographed the same day, with two of four Take3 spots deliberately smudged:

| | |
|---|---|
| Status | **DIVERGING** |
| CV% | 29,242 |
| wells reddened | the two smudged ones; the clean pair stayed green |
| Read Samples | greyed out |
| hint beside the grid | "You can discard unnecessary / diverging blank wells" |

That hint is the useful part. Red does not mean "this well looks odd", it
means **"discard this one and the rest agree"** -- it answers the question
she is about to act on. `wells_to_discard()` in `epoch_open/quant.py` now
finds exactly that set, and a test asserts that dropping what is red really
does leave a blanking that passes.

It also caught a bug on arrival. The old rule measured each well's distance
from the median, and with the wells in two groups the median lands in the gap
between them -- so all four came out red, telling her to wipe two spots that
were fine.

## What changed in this project as a result

| | before | now |
|---|---|---|
| blank verdict | spread <= 0.004 AU and divergence <= 0.003 AU | **highest CV% <= 10**, as Gen5 |
| high reference | 0.010 AU | **0.100 OD**, as Gen5 |
| a one-well blank | passed | **fails** -- no CV% can be computed |
| red wells | distance from the median | the set you would discard |
| status word | NO VALIDO | **DIVERGENTE** when the CV% is what failed |

The old limits were about four times stricter than Gen5 in practice, and the
reference margin ten times stricter. Both would have sent the technician back
to wipe plates her own software accepts. All four numbers are now in the
Preferences dialog, and in `epoch_open.json` for anyone who prefers a file.

`docs/GEN5_NOTES.md` has the full account, including what the same
documentation says about curve fits, plate geometry, and the capabilities
this project does not implement.

## What is still worth doing with the trial

The trial expires **25 November 2026**. After that there is no licensed Gen5
in this lab and no second trial.

**Nothing about blanking remains.** The threshold is known, and both the
accepted and the rejected cases have been captured. What is left is unrelated
to this document's original subject, and does not need Gen5 at all:

**Absolute accuracy.** Everything verified so far shows this software reads
the *instrument* correctly -- it agrees with Gen5 to 0.5% on neat ladder
(`docs/VALIDATION.md`) and to 0.001 AU across a 96-well plate
(`docs/GEN5_NOTES.md`). Whether the instrument reads *true* has never been
checked, and the calibration label says December 2018.

That needs a reference material of known concentration and the reader. It
does **not** need Gen5, because the question is not whether the two programs
agree -- they do -- but whether both are offset from the truth together. So
it is not on the November clock, and it is better done properly when there is
a real standard than rushed against a deadline it does not have.

## The lesson, since it cost a week

Two limits in `quant.py` were set by judgement and documented at length *as*
judgement -- honestly labelled, with the reasoning written out, with a test
pinning what tightening them would cost. All of that was good practice and
none of it helped, because the error was not in the reasoning. It was in the
question.

Before building an experiment to recover a vendor's behaviour, read the
vendor's manual. It ships with the software, the lab owns a licence, and the
answer may simply be written down.
