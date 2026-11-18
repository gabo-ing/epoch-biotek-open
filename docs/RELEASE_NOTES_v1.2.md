# v1.2 — Blank every well, and the file says what the blank was

The text below is what goes in the GitHub release body. Tag `v1.2`.

Attach two files, both rebuilt on Windows — the v1.0 binaries still say `1.0.0` in
their title bars:

    dist\EpochTake3.exe
    dist\EpochMultispectral.exe

and a `SHA256SUMS.txt`, which on Windows comes from:

    certutil -hashfile EpochTake3.exe SHA256
    certutil -hashfile EpochMultispectral.exe SHA256

No macOS `.app`, for the reasons in `docs/RELEASE_NOTES_v1.0.md`: it would be unsigned
and un-notarized, and `build_macos.sh` still has no `--target-arch`. Building on a Mac
is one command. Linux needs no binary.

---

**Blanking every well before using it now works.** If that is your habit — and it is a
better habit than blanking two — this release is the one you want.

The previous versions would refuse a blank for having too many wells in it, and paint a
different well red each time you tried. The cause was ours. The absolute check sitting
underneath Gen5's CV% rule measured the gap between the highest and lowest blank well
against a fixed limit, and that gap grows with the number of wells however clean the
plate is: the expected highest-to-lowest of n readings is about 2.85 standard
deviations at 8 wells but 3.90 at 24. So the check tightened the more carefully you
blanked. Meanwhile the error a blank actually puts into every sample is the error of
its *mean*, which gets **smaller** as you add wells — on a real eight-well blank, from
0.00031 AU at 8 wells to 0.00018 at 24. The check tightened as the thing it guards
against shrank.

It now measures how much the blank wells disagree with each other, as a standard
deviation, which means the same thing whether you blanked two wells or forty-eight.
Simulated at sixteen wells: 27 of 40 blanks refused before, 0 of 40 now. The real
eight-well blanking that Gen5 itself declared VALID sits at 0.00089 AU against the new
0.0025 AU limit.

**A red well no longer stops you reading.** One short or bubbled drop among sixteen or
twenty-four is still painted red so you can wipe or deselect that spot, but the status
stays VALID and the read button stays live. That well is a twenty-fourth of the blank:
a spot 0.003 AU out moves what gets subtracted by 0.0001 AU, which is nothing at
0.5 mm. Naming the well was useful; refusing the whole run over it was not. A genuinely
bad plate is still refused, at any number of wells.

**The screen now says which check stopped you, and by how much.** The two refusal
messages used to read "above the limit" and "do not agree with each other" — the same
sentence unless you had read the source — and neither carried a number. Both now give
the measured value and the limit it passed.

**A blank can be saved on its own.** Saving used to require samples, so a blanking
that would not pass — the one you most want a record of — could not produce a file at
all. Press **End batch** with just a blank and you get a workbook of it. The file is
named `blank_` rather than `quantification_`, and saving it does not close the batch:
the blanking stays on screen, because sending somebody the numbers should not cost you
the blank they describe.

**The workbook records the blanking.** Every concentration in the file was computed by
subtracting a blank, and the file used to say nothing about it. The summary sheet now
carries the blank wells, the CV% per wavelength, the disagreement between the wells, the
verdict, and any wells you discarded — written whether the blank passed or not, because
a blank accepted on a loosened limit is the one somebody will want to see six months
later.

**The workbook has a Blank sheet.** Every blank well's raw absorbance at every
wavelength, then the average and the CV% — Gen5's own table, with Gen5's own column
names. The aggregate tells you the wells disagreed; this tells you which one read what,
which is the difference between a drop that evaporated and one that never bridged the
gap. Wells you discarded are listed and marked rather than dropped from the record.

### If you are upgrading

**One settings key was renamed.** `blank_spread_limit_au` became
`blank_dispersion_limit_au`, because the number means something different now — a
standard deviation between the wells rather than a highest-to-lowest range. A file
still carrying the old key falls back to the new default, which is the safe direction,
but the stale line stays in your `epoch_open.json` until you open **Preferences** and
save once. Only relevant if you had edited that value by hand.

**Coming from v1.0: the interface speaks English by default now.** v1.1 made it
bilingual. A lab that works in Spanish sets `"language": "es"` in `epoch_open.json`,
or picks it in Preferences — both programs and the spreadsheet they write follow the
setting. A one-off: run with `--lang es`.

### Unchanged

Nothing here depends on Gen5 at runtime, and nothing modifies, patches or inspects it.
The blanking rule still matches Gen5's own — CV% on raw absorbances, sample standard
deviation, 10% limit, which is Gen5's default. What has been checked against the
instrument and what has not is in `docs/STATUS.md`, including the full write-up of this
fix and the one blanking case still unresolved: a blank read with no plate in the
carrier reports nonsense confidently, because a CV% divided by a near-zero mean can be
anything.

**Never put a Take3 plate in a multispectral read.** It can be damaged irreversibly.
Use ordinary transparent 96-well plates for those assays.

444 tests pass in both languages. MIT licensed. Protocol notes for anyone writing their
own driver are in `docs/PROTOCOL.md`.
