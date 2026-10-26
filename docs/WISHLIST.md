# What to capture while a Gen5 trial is running

**Read this first: none of it is required.** The Epoch is already driven end to end by
this software — connect, carriage, capability negotiation, absorbance reads. Gen5 is no
longer a dependency. Everything below either *verifies* something we inferred or
*polishes* the finished tool. If the trial window is short, work strictly top-down.

---

## 1. A USB capture of one Take3 nucleic-acid read — by far the most valuable

Procedure is in `docs/CAPTURE.md` (Wireshark + USBPcap, one normal read while
recording). What it settles, in order of importance:

**a. The plate geometry string Gen5 sends for a Take3.** This is the single most
valuable unknown left. Our driver currently sends the standard 96-well geometry
(`epoch_open/plates.py`, `TAKE3 = PLATE_96`) because the factory sheet addresses the
micro-spots as ordinary 96-well positions. That is an *inference*. The `y` command's
parameter in the capture shows what Gen5 actually declares — plate height especially,
which affects where the optics focus. If it differs, our readings could be
systematically off in a way that still looks plausible.

**b. How Gen5 sequences the wavelengths.** We issue one assay per wavelength
(260, then 280, then 320). Gen5 may batch them into a single assay record. If it does,
reads get roughly three times faster — worth having for a 96-sample day.

**c. The assay records themselves**, to diff against ours. Ours are confirmed accepted
by the instrument, but "accepted" is not "identical".

**d. Whether Gen5 does anything before or after a read** we do not: homing, extra
settling time, a second pass, re-reading the blank.

## 2. A paired validation run — the acceptance test

Worth more than any amount of code review:

1. In Gen5, read a Take3 plate with **known samples** (a standard, or any sample with a
   trustworthy concentration). Save the export.
2. Do not touch the plate. Read the same spots with this software.
3. Send both outputs.

Agreement on the same physical drops is the proof this is ready for real work. It also
settles the 2011 wavelength-accuracy FAIL noted in `docs/FINDINGS.md`.

If you can only do one thing after the capture, do this.

## 3. The Take3 plate definition as Gen5 holds it

In Gen5's plate-type list, open the Take3 entry and screenshot its dimensions —
plate height, well positions, anything numeric. This answers 1a directly even if the
capture is unreadable.

## 4. Screenshots of the technician's actual workflow

Every screen she touches, in order, from opening Gen5 to saving the file:

- The protocol/experiment she picks, and what it is called.
- The Take3 plate picker as she sees it.
- Where she enters sample type, and what the options are called in her Spanish UI.
- The blanking step, and whether she blanks one spot or all.
- The screen after a read, and the accumulation flow for more than 16 samples.
- The export dialog.

Our GUI should feel like a simpler version of what she already knows, not a different
program. These screenshots are the design brief for that.

## 5. Higher-precision numbers, if Gen5 offers them

Every export we have rounds raw absorbances to three decimals, which caps verification
at about +/-1 ng/uL. If Gen5 has a setting for more decimal places, one export with it
turned on would let us confirm the arithmetic to the digit instead of to the rounding.

## 6. Edge behaviour worth seeing once

- A spot left **empty** — what does Gen5 report, and does it warn?
- A **deliberately dirty** spot (fingerprint on the window) — does the yellow
  high-reference flag fire, and at what 320 nm value?
- A **saturated** sample — what does an overflow look like in the export?

We handle all three, but our thresholds are reasoned rather than observed.

## 7. Protein modes

We implement "1 Abs at 1 cm = 1 mg/mL" because that is what your exports show. If the
Take3 protein protocol offers other options (A280 with extinction coefficients, BCA,
Bradford), a screenshot of the list tells us whether anything is missing.

---

## Not needed

- The Gen5 installer, licence or help files.
- The reader manual.
- Anything about the serial protocol — that question is closed.
