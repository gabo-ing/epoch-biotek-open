"""Read Take3 spots from the command line, for validating against Gen5.

Deliberately not the GUI: this exists so a paired comparison can be run before the
interface has been seen on a screen, and so its output is easy to paste back.

    python read_cli.py --blank B2,B3 --wells C2,C3,D2 --type dsDNA
    python read_cli.py --wells C2 --type RNA --with-230
    python read_cli.py --list-ports

Close Gen5 first -- it holds the serial port open and nothing else can use it.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import take3                                    # noqa: E402
from epoch_open.quant import (                                  # noqa: E402
    blank_for, check_blanks, quantify, wavelengths_for,
)
from epoch_open.reader import EpochReader, ReaderError          # noqa: E402
from epoch_open.xlsx import export_results                      # noqa: E402

from epoch_open import config  # noqa: E402

CONFIG = config.load()
PLATE_SERIAL = CONFIG.plate_serial


def parse_wells(text: str) -> list[str]:
    wells = [w.strip().upper() for w in text.split(",") if w.strip()]
    for well in wells:
        take3.well_to_indices(well)      # raises on anything invalid
    return wells


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wells", help="sample spots, e.g. C2,C3,D2")
    parser.add_argument("--blank", help="blank spots, e.g. B2,B3")
    parser.add_argument("--type", default="dsDNA",
                        choices=["dsDNA", "ssDNA", "RNA", "protein"])
    parser.add_argument("--with-230", action="store_true",
                        help="also read 230 nm for the 260/230 ratio")
    parser.add_argument("--plate", default=PLATE_SERIAL,
                        help="Take3 serial, for its certified pathlengths")
    parser.add_argument("--nominal", action="store_true",
                        help="use 0.5 mm everywhere instead of the plate's sheet")
    parser.add_argument("--xlsx", help="also write results to this file")
    parser.add_argument("--port", help="serial port, if auto-detection fails")
    parser.add_argument("--list-ports", action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        for line in EpochReader.describe_ports() or ["(no serial ports found)"]:
            print(" ", line)
        return 0

    if not args.wells:
        parser.error("--wells is required (or use --list-ports)")

    wells = parse_wells(args.wells)
    blanks_wanted = parse_wells(args.blank) if args.blank else []
    wavelengths = wavelengths_for(args.type, with_230=args.with_230)

    pathlengths = None if args.nominal else take3.pathlengths_for_plate(args.plate)
    basis = "nominal 0.5 mm" if pathlengths is None else f"sheet for plate {args.plate}"

    reader = EpochReader(port=args.port, expected_serial=CONFIG.reader_serial)
    try:
        info = reader.connect()
        print(f"Connected: {info.model} serial {info.serial}, firmware "
              f"{info.firmware}, on {info.port}")
        print(f"Wavelengths: {', '.join(str(w) for w in wavelengths)} nm")
        print(f"Pathlengths: {basis}\n")

        blanks = {}
        if blanks_wanted:
            input(f"Load BLANK (water) in {', '.join(blanks_wanted)}, "
                  "close the carriage, then press Enter...")
            blanks = reader.read_wells(blanks_wanted, wavelengths)
            for warning in check_blanks(blanks):
                print(f"  WARNING: {warning}")
            for well in blanks_wanted:
                values = blanks[well].readings
                print(f"  blank {well}: "
                      + "  ".join(f"{w}={values[w]:.4f}" for w in sorted(values)))
            print()

        input(f"Load SAMPLES in {', '.join(wells)}, close the carriage, "
              "then press Enter...")
        raw = reader.read_wells(wells, wavelengths)
    except (ReaderError, NotImplementedError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        reader.close()

    results = []
    print(f"\n{'well':6} {'conc':>10} {'unit':6} {'260/280':>8} {'260/230':>8} "
          f"{'path':>7}   raw")
    for well in wells:
        result = quantify(raw[well], blank_for(blanks, well), args.type, pathlengths)
        results.append((1, result))

        def show(value, digits):
            return f"{value:.{digits}f}" if value is not None else "-"

        raws = "  ".join(f"{w}={raw[well].readings[w]:.4f}"
                         for w in sorted(raw[well].readings))
        print(f"{well:6} {result.concentration:10.3f} {result.unit:6} "
              f"{show(result.ratio_260_280, 3):>8} {show(result.ratio_260_230, 3):>8} "
              f"{result.pathlength_mm:7.4f}   {raws}")
        for warning in result.warnings:
            print(f"       ! {warning}")

    if args.xlsx:
        export_results(
            args.xlsx, results,
            metadata={"Placa Take3": args.plate, "Caminos opticos": basis,
                      "Tipo de muestra": args.type},
        )
        print(f"\nWrote {args.xlsx}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
