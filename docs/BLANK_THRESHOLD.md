# Measuring Gen5's blank threshold

**Status: planned, not yet run.** Everything here is a procedure, not a result.

## Why

`blank_report()` in `epoch_open/quant.py` decides whether a blanking is usable,
and it is gated on two numbers:

    BLANK_SPREAD_LIMIT_AU     = 0.004    # how far apart the wells may read
    BLANK_DIVERGENCE_LIMIT_AU = 0.003    # how far one well may sit from the median

**Neither is Gen5's.** Gen5 displays a verdict but never says what it tests, and
the only blanking exports this lab has are runs Gen5 *passed*. There was nothing
to reverse-engineer a rejection threshold from, so both limits were set from the
one run we know Gen5 accepted — the eight wells of `Gen5_LVA_NAQ_0001`, which
span 0.002 AU with the worst well 0.0015 AU from the median — leaving a blank
that good about twice the room it needed.

That is a defensible guess. It is still a guess, and it is the last number in the
project set by judgement rather than measurement. This procedure replaces it with
a measurement, and needs the laptop that still has the Gen5 trial.

Roughly nine reads. Water and diluted ladder throughout; nothing hazardous.

## Step 0

Open Gen5 on the trial laptop and take one read **before preparing anything**. If
the trial has lapsed, the rest is wasted pipetting.

## The spikes

At Take3's 0.5 mm path, a dsDNA concentration in ng/uL *is* its A260 deviation
multiplied by 1000 (`ng/uL = A260 x 1000`; see `docs/QUANTIFICATION.md`). So a
dilution series reads out directly in the units the threshold is written in:

| Tube | Target ng/uL | 260 nm deviation | What epoch-open would say |
|---|---|---|---|
| 1 | 1 | 0.001 AU | pass |
| 2 | 2 | 0.002 AU | pass |
| 3 | 3 | 0.003 AU | exactly at the limit |
| 4 | 5 | 0.005 AU | fail |
| 5 | 10 | 0.010 AU | fail |
| 6 | 20 | 0.020 AU | fail clearly |

At least 20 uL of each, in the same ultrapure water used for the blanks.

## Part A — measure what was actually made

Pipetting 1 ng/uL accurately is not realistic and does not need to be. Read the
six dilutions as **samples** first (dsDNA). What Gen5 reports is the real
deviation that tube contributes when it stands in as a blank well, and that
measured value — not the nominal one — is what every verdict below is mapped
against.

One read, six wells.

## Part B — the control

All eight wells of column 2, ultrapure water. Read Blanks. Record Status and CV%.

This must come back VALID. If it does not, the water, the plate or the wiping is
the problem, and every run below would be measuring that instead.

## Part C — the spike series

Seven water wells plus **one spiked well, always D2**, so position cannot be
confused with concentration. For each tube in ascending order: wipe, load, Read
Blanks, record Status, CV%, and which wells Gen5 painted red. Export and
screenshot each run.

Two consecutive INVALID runs is enough — the boundary is bracketed by then.

The answer is wherever Status flips:

- between tubes 3 and 4 — our 0.003 AU is right
- at tube 5 or 6 — Gen5 is far more permissive, and our limit sends the
  technician back to wipe plates Gen5 would have accepted
- at tube 1 or 2 — we are letting bad blanks through

Note separately **at which run a red well first appears**. It need not be the run
where Status flips, and if it is not, Gen5 distinguishes "worth flagging" from
"not usable" — a distinction this program does not currently make.

## Part D — two clusters, nobody to blame

A2–D2 water, E2–H2 all from tube 4. No outlier: two groups of four.

`blank_report()` calls this invalid with `reason="spread"` and paints **nothing**
red, reasoning that no single well can be blamed and the only honest instruction
is to blank again. That reasoning is untested. If Gen5 reddens one of the two
groups, it has a notion of which cluster is "the blank" that this program lacks.

## Part E — the dirty spot

Seven water wells plus one deliberately contaminated spot: a fingerprint on the
window, or water with a trace of something faintly coloured.

This tests a **different mechanism** from Parts C and D, and it is easy to get
wrong by assuming otherwise. A smudge raises 260 nm and 320 nm roughly together,
and the 320 nm subtraction removes most of it — so `divergent_blank_wells()` is
designed *not* to flag this. The `high_reference` warning watches the reference
instead.

Record Status, CV%, red wells, and from the export **the 320 nm raw value of the
dirty well against the clean ones**.

If Gen5 passes this run, a dirty spot is being silently subtracted from every
sample, which is worth knowing about software this lab has trusted for years.

## Part F — absolute accuracy, while the laptop is there

A separate question that needs the same setup, and the only occasion both
programs will be in the room together.

Everything verified so far shows epoch-open reads the *instrument* correctly: it
agrees with Gen5 to 0.5% (`docs/VALIDATION.md`). Whether the instrument reads
*true* has never been checked, and the calibration label says December 2018.

GeneRuler at known dilutions, read in Gen5, then Gen5 closed (it holds the COM
port), epoch-open started, and **fresh drops loaded from the same tubes** — 2 uL
drops do not survive the hand-over, and a half-evaporated drop reads high.

If both programs agree with each other but sit away from the expected value, that
is the instrument drifting rather than either piece of software, and it is a
calibration conversation.

## What has to come back

- **A screenshot of the Blanking panel for every run.** The HTML export carries
  the blank table and the CV% but **not** the Status line — VALID / INVALID
  exists only on screen. Without the screenshots the session proves nothing.
- The HTML export of each run, named by run.
- Which wells Gen5 reddened, per run, noted even when the answer is none. A run
  Gen5 calls INVALID while reddening nothing is as informative as one where it
  reddens a well.

## Applying the result

Both limits are in `epoch_open.json` and move without a rebuild:

    "blank_spread_limit_au": 0.004,
    "blank_divergence_limit_au": 0.003

If Gen5's boundary sits elsewhere, move ours to match and rewrite the comment
above `BLANK_DIVERGENCE_LIMIT_AU` in `epoch_open/quant.py`, which currently
explains at length why the number is a judgement call. That comment exists
because this experiment had not been done.

`tests/test_blanking.py` pins the margins the current defaults leave on the one
known-good run. If the limits move, that test should move with them and keep
saying what the new numbers cost.
