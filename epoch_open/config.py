"""Settings that differ between labs, read from a file beside the program.

The software ships compiled into a single .exe, so anything an owner might need
to change cannot live in the source. It lives in `epoch_open.json`, next to the
executable, and every field is optional.

    {
      "reader_serial": null,
      "plate_serial": "243819",
      "plates": {
        "243819": {"A2": 0.5125, "A3": 0.5096},
        "999001": {"A2": 0.5044, "A3": 0.5071}
      }
    }

reader_serial   null (the default) accepts whichever Epoch answers. Set it only
                when more than one reader is attached and the right one must be
                picked.
plate_serial    which Take3 is in use now.
plates          every plate the lab has registered, keyed by serial, each with
                the values from its own Take3 Pathlength Data Sheet.

Keeping a table per serial matters. An earlier version stored a single table, so
registering a replacement plate and later switching back to the first one kept
the replacement's pathlengths under the original's serial, and the results were
quietly about 2% wrong with nothing on screen to say so.

The older single-table form (`pathlengths_mm`) is still read, and treated as
belonging to whichever plate `plate_serial` names.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "epoch_open.json"


def _program_directory() -> Path:
    """Where to look for the config: beside the .exe, or the project root."""
    if getattr(sys, "frozen", False):          # PyInstaller
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


@dataclass
class Config:
    reader_serial: str | None = None
    plate_serial: str = "243819"
    plates: dict[str, dict[str, float]] = field(default_factory=dict)
    source: str = "defaults"

    def pathlengths_for(self, serial: str | None) -> dict[str, float] | None:
        """That plate's table: registered here, else built in, else None."""
        if serial and serial in self.plates and self.plates[serial]:
            return dict(self.plates[serial])
        from . import take3

        return take3.pathlengths_for_plate(serial)

    @property
    def pathlengths(self) -> dict[str, float] | None:
        """The table for the plate in use."""
        return self.pathlengths_for(self.plate_serial)

    def set_plate(self, serial: str, table: dict[str, float] | None) -> None:
        """Select a plate, remembering its values under its own serial.

        An empty table means the plate was registered without a data sheet. It is
        stored as empty rather than dropped, so the plate stays known and the
        screen can say SIN CALIBRAR instead of silently borrowing another
        plate's numbers.
        """
        self.plate_serial = serial
        self.plates[serial] = {k.upper(): float(v) for k, v in (table or {}).items()}


def config_path() -> Path:
    """Where the settings file lives: beside the program."""
    return _program_directory() / CONFIG_NAME


def save(cfg: Config, path: Path | None = None) -> Path:
    """Write the settings back, so a new plate needs no rebuild and no text editor.

    Writes to a temporary file and replaces, so an interrupted save cannot leave
    the program with a half-written config it refuses to read.
    """
    path = path or config_path()
    data = {
        "reader_serial": cfg.reader_serial,
        "plate_serial": cfg.plate_serial,
        "plates": {
            serial: {k: round(float(v), 4) for k, v in sorted(table.items())}
            for serial, table in sorted(cfg.plates.items())
        },
    }
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    temp.replace(path)
    return path


def load(path: Path | None = None) -> Config:
    """Read the config file if there is one. A missing file is not an error."""
    path = path or (_program_directory() / CONFIG_NAME)
    if not path.exists():
        return Config()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # A broken config must not stop the program: fall back and say so.
        config = Config(source=f"{path} (unreadable: {exc}; using defaults)")
        return config

    if not isinstance(data, dict):
        return Config(source=f"{path} (not a JSON object; using defaults)")

    def clean_table(raw) -> dict[str, float]:
        out: dict[str, float] = {}
        if not isinstance(raw, dict):
            return out
        for well, value in raw.items():
            try:
                out[str(well).upper()] = float(value)
            except (TypeError, ValueError):
                continue
        return out

    serial = data.get("reader_serial")
    plate = str(data.get("plate_serial") or Config.plate_serial)

    plates: dict[str, dict[str, float]] = {}
    raw_plates = data.get("plates")
    if isinstance(raw_plates, dict):
        for plate_serial, table in raw_plates.items():
            plates[str(plate_serial)] = clean_table(table)

    # Older single-table form: it belongs to whichever plate is selected.
    legacy = clean_table(data.get("pathlengths_mm"))
    if legacy and plate not in plates:
        plates[plate] = legacy

    return Config(
        reader_serial=str(serial) if serial else None,
        plate_serial=plate,
        plates=plates,
        source=str(path),
    )
