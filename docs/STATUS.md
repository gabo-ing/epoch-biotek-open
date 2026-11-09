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

## Still open

- The **Take3 workbook records nothing about the blank** — no wells, no CV%, no
  verdict. Verified absent: no "Blanco", "CV" or "VALIDO" anywhere in the file. Gen5's
  export has a "Blank Results" table. Adding ours was offered and not yet done.
- Validation **Part F**: absolute accuracy against a reference standard. It needs a
  certified standard, not Gen5, so the trial expiry does not block it.
- The two curve wrinkles above.
- Rebuild on the Mac to confirm the Retina layout fix on hardware; it was fixed and
  tested, but the last build predates the fix.
- Known capability gaps, all deliberate: a blank on each sample well, the Take3 BioCell
  (A9, H9) and cuvette (E10, E11) positions, the 4-parameter logistic fit ELISA wants,
  and Gen5's extrapolation factor.
- Cosmetic: the "Leer tambien 230 nm" checkbox is oversized on macOS.

## Running the tests

```
python3 tests/run_tests.py        # 392 passed as of this commit
```

One trap, learned the hard way: **the GUI tests return early with no display and the
run still reports every test as passed.** A green 392 from a headless machine has not
exercised a single window. `tests/test_gui_starts.py` exists to tell "no display" apart
from "broken" — run the suite where there is a real display before trusting it.
