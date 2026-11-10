# v1.0.0 — Read a BioTek Epoch without Gen5 (Take3 + 96-well)

The text below is what goes in the GitHub release body. Tag `v1.0.0`.

Attach two files, both built on Windows:

    dist\EpochTake3.exe
    dist\EpochMultispectral.exe

and a `SHA256SUMS.txt`, which on Windows comes from:

    certutil -hashfile EpochTake3.exe SHA256
    certutil -hashfile EpochMultispectral.exe SHA256

No macOS `.app` is attached, deliberately. It would be unsigned and un-notarized, and
Apple removed the Control-click override in Sequoia, so a downloaded app lands the user
in System Settings → Privacy & Security hunting for an "Open Anyway" button that is
widely reported not to appear. `build_macos.sh` also has no `--target-arch`, so a build
made on Apple Silicon will not run on an Intel Mac and two separate binaries would be
needed. Building on a Mac is one command and is known to work; that is the better
experience. Linux needs no binary at all.

---

**First release.** Free, open-source software for a BioTek Epoch microplate reader
whose Gen5 licence activations are exhausted. It talks to the instrument directly over
its serial protocol; nothing here depends on Gen5 at runtime, and nothing here modifies,
patches or inspects it.

**Two programs:**

- **EpochTake3** — RNA/DNA/protein quantification at 260/280 nm on a Take3 micro-volume
  plate.
- **EpochMultispectral** — colorimetric assays against a standard curve in ordinary
  transparent 96-well plates (IAA/Salkowski, Bradford, MTT), up to six wavelengths in
  one read.

**Validated against Gen5** on the same plate: 85 of 96 wells identical to three
decimals, largest disagreement 0.0010 AU. RNA duplicates read a minute apart agree to
0.23%. The blanking rule matches Gen5's own — CV% on raw absorbances, sample standard
deviation, 10% limit. What was checked and what was not is in `docs/STATUS.md`.

**Windows:** download the `.exe` you need and double-click. No Python, no installer, no
console window. Both are unsigned and self-built, so some antivirus will object on
heuristics alone; `build_windows.bat` rebuilds them from source if yours does.

**macOS:** run `./build_macos.sh`. A signed, notarized app is not something this project
can provide, and an unsigned one is now more trouble to open than to build.

**Linux:** `python3 run_take3.py` or `python3 run_multispectral.py`, with pyserial
installed from your distribution's packages.

**Never put a Take3 plate in a multispectral read.** It can be damaged irreversibly.
Use ordinary transparent 96-well plates for those assays.

MIT licensed. Protocol notes for anyone writing their own driver are in
`docs/PROTOCOL.md`.
