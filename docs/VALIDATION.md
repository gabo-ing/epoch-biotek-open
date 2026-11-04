# Paired validation against Gen5 — 26 October 2026

Reader Epoch 254717 (firmware 1.12), Take3 plate 243819, dsDNA. Gen5 read first on a Windows laptop, then this software on colonial-one, with the
USB cable moved between machines.

**Whether the plate was reloaded between the two reads was not recorded for this
first run.** The second run (below) definitely used fresh drops for each program. The
raw absorbances here agreed to 0.0007 AU, but the signal was only ~0.007 AU above a
~0.06 AU background, so that agreement is dominated by the background and does not
by itself prove the same drops were measured.

Gen5's numbers: `captures/Gen5_LVA_NAQ_0001.html`, `_0002.html`.
Ours: `tmp/samples.json`, blanks in `blank3.json`.

## Raw absorbances: the same

| Well | 260 Gen5 | 260 ours | diff | 320 Gen5 | 320 ours | diff |
|---|---|---|---|---|---|---|
| A2 | 0.061 | 0.0619 | +0.0009 | 0.048 | 0.0486 | +0.0006 |
| B2 | 0.060 | 0.0595 | -0.0005 | 0.047 | 0.0466 | -0.0004 |
| C2 | 0.059 | 0.0590 | +0.0000 | 0.046 | 0.0467 | +0.0007 |
| D2 | 0.063 | 0.0621 | -0.0009 | 0.050 | 0.0485 | -0.0015 |
| E2 | 0.050 | 0.0499 | -0.0001 | 0.043 | 0.0427 | -0.0003 |
| F2 | 0.052 | 0.0497 | -0.0023 | 0.045 | 0.0438 | -0.0012 |
| G2 | 0.047 | 0.0468 | -0.0002 | 0.041 | 0.0403 | -0.0007 |
| H2 | 0.049 | 0.0486 | -0.0004 | 0.041 | 0.0411 | +0.0001 |

Mean absolute difference **0.0007 AU** at both wavelengths. Gen5 rounds its raws to
three decimals, so +/-0.0005 is the export's own resolution. The optics, the
geometry we send and the way we parse the reply all agree with Gen5.

## Concentrations: means agree, single wells scatter

| | Gen5 | ours | difference |
|---|---|---|---|
| Neat (A2-D2), mean of 4 | 7.00 ng/uL | **7.04 ng/uL** | +0.6% |
| 1:10 (E2-H2), mean of 4 | 0.88 ng/uL | 0.80 ng/uL | -0.08 |

Individual wells differ by up to 1.3 ng/uL. That is **blank noise, not a
calculation difference**: each program subtracted its own blank, measured minutes
apart, and at A260 ~ 0.007 the blank (~0.006) is almost as large as the signal. A
0.001 AU difference in the blank moves the result by 1 ng/uL. The raw table above
shows the readings themselves agree.

## What this run could not test

The sample was about 7 ng/uL — the very bottom of the Take3's range. The 1:10
dilution landed at ~0.8 ng/uL, which is noise, so the linearity test failed for both
programs: Gen5's neat/diluted ratio came out **7.98** and ours **8.80**, against an
expected 10. Gen5 was further from 10 than we were.

That is a useful control. If this software were systematically wrong, Gen5 would hit
10 and we would not. Both miss, in the same direction, by a similar amount. The
limitation is the sample, not either program.

**Still untested:** accuracy at a normal working concentration (50-500 ng/uL), where
the blank is a small fraction of the signal and the dilution test is sharp. That
needs one run with a more concentrated prep.

## Conclusion

For the question that mattered -- does this software read the instrument correctly
and compute what Gen5 computes -- the answer is yes, within the resolution the
experiment allowed. The remaining uncertainty is about accuracy at higher
concentrations, not about whether the approach works.

---

# Second run — GeneRuler 100 bp ladder, 26 October 2026

Fermentas GeneRuler 100 bp, stated 0.5 ug/uL, dsDNA. A2/B2 neat, C2/D2 at 1:10.

**The two programs did NOT read the same drops.** The plate was wiped and reloaded
between our read (11:51:38) and Gen5's (11:55:09), so this compares two independent
loadings of the same material. That is a harder test than same-drop agreement: it
includes pipetting variation, two separate dilutions' worth of error, and two
separate blanks.

Blanks also differed by design: we blanked each well and used it for that well;
Gen5 blanked A3 alone and applied it to all four samples.

## Results

| Well | Gen5 ng/uL | ours ng/uL | 260/280 Gen5 | ours |
|---|---|---|---|---|
| A2 neat | 436.5 | 439.1 | 1.861 | 1.86 |
| B2 neat | 440.4 | 450.8 | 1.866 | 1.86 |
| C2 1:10 | 19.4 | 44.7 | 1.867 | 1.84 |
| D2 1:10 | 41.6 | 46.2 | 1.712 | 1.83 |

**Neat mean: Gen5 438.5, ours 445.0 — 1.5% apart**, across independent loadings.
The 260/280 ratios match to the second decimal.

**Our internal linearity**: neat/diluted = 9.79 against an expected 10.00, with
replicates 2.6% apart (neat) and 3.3% apart (1:10).

## C2

Gen5's C2 read 19.4 ng/uL against its own D2 at 41.6 -- its two 1:10 replicates
disagree by 73%. Ours agreed to 3.3%. Since the drops were freshly loaded for each
program, this is a loading failure in that particular drop (it did not bridge the
gap, or the dilution was not mixed), not a difference between the programs. Gen5
reported correctly what was in front of it.

An earlier draft of this document attributed C2 to a drop collapsing between the two
reads. That was wrong: it assumed the same drops were measured, which they were not.

## What this run establishes, and what it does not

**Establishes:** at a working concentration (~450 ng/uL) this software and Gen5 agree
to about 1.5% across independent loadings, produce the same 260/280, and our dilution
series is linear to about 2%.

**Does not establish:** absolute accuracy. The stated 0.5 ug/uL is the vendor's
nominal figure, not a certified standard, and both programs read about 12% below it.
Whether the ladder is really 440 ng/uL or the instrument reads low cannot be settled
without certified material.

**Does not establish anything about evaporation.** Fresh drops were loaded for each
program, so the read order carries no information here.


# Third run — RNA, 4 November 2026

Six old RNA samples, Take3 plate 243819, reader 254717 on COM4. Gen5 1.11.5
on the Dell at 10:38, this software on the same laptop at 10:42. First
comparison on RNA: the two earlier runs were both dsDNA ladder, so the
extinction-40 path had never been checked against anything.

Also the first time this software has been seen running on Windows against
the instrument: the badge came up green on COM4.

## The samples are empty, and both programs say so

| Well | Gen5 ng/uL | ours | Gen5 260/280 | ours |
|---|---|---|---|---|
| B2 | 20,857 | 21,9 | 2,286 | 2,20 |
| B3 | -2,831 | -1,7 | 1,846 | 1,77 |
| C2 | 4,840 | 6,2 | 1,119 | 1,14 |
| C3 | -4,045 | -2,0 | 1,729 | 1,81 |
| D2 | -1,760 | -1,0 | 1,128 | 1,22 |
| D3 | -3,196 | -3,3 | 1,569 | 1,80 |

Five of the six are negative or within a couple of ng/uL of zero, in both
programs. One well holds about 21 ng/uL of something.

**That agreement is the result, and it is worth more than the numbers.** At
0.5 mm path 1 ng/uL of RNA is 0.001 AU, so these samples sit at or below the
instrument's last printed digit. Two programs independently reporting
"nothing here" from the same drops is a meaningful check even though -2,8 and
-1,7 differ by 40%: a percentage of noise is noise.

## Where the systematic offset comes from

Ours reads about **+1 ng/uL higher** across the board -- +1,04 on average,
with five of six in the same direction. That is +0,001 AU, one last digit.

It is not a disagreement between the programs. **The two runs used different
blanks.** Gen5 blanked on two wells (A2, A3; mean 0,0555 at 260 nm) and this
software on six (A2, A3, G2, G3, H2, H3). A blank about 0,001 AU lower
produces concentrations about 1 ng/uL higher, which is exactly what is seen.

A clean comparison needs the same wells blanked in both, which was not done
and is easy to arrange next time. Nothing here suggests the extinction-40
path is wrong; nothing here confirms it either, because samples at the noise
floor cannot confirm a factor.

## What this does establish

**Gen5 computes CV% with the sample standard deviation, n-1.** See the
docstring of `blank_cv_percent` in `epoch_open/quant.py`: this had been
written down as unsettlable from the exports, because three-decimal rounding
on a ~0,045 blank moves the CV by more than the gap between the conventions.
A two-well blank breaks that tie -- the estimators differ by sqrt(2) at n=2 --
and Gen5 printed 6,35 where n-1 gives 6,37 and n gives 4,50.

**The blanking verdict matched.** Our six-well blank came back VALIDO at
CV 6,484%, under the limit of 10 that Gen5's own preferences carry. Under the
absolute limits this software used before 3 November it would very likely
have been rejected, and the technician sent back to wipe a plate Gen5 was
happy with.

## What to do differently with samples this dilute

Nothing in this run is a software problem. A Take3 at 0.5 mm cannot measure
RNA at a few ng/uL: blank scatter alone is ~0,003 AU, which is ~3 ng/uL, so
anything below roughly 10 ng/uL is indistinguishable from the blank. The
negative numbers are not an error -- they are what "less than the blank"
looks like when it is reported honestly instead of clipped to zero.

For samples at this level the options are a fluorometric assay, which is
specific and works far lower, or concentrating the sample. Re-reading them
here will reproduce the same noise.
