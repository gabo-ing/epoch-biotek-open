"""Settings that differ between labs, read from a file beside the program.

The software ships compiled into a single .exe, so anything an owner might need
to change cannot live in the source. It lives in `epoch_open.json`, next to the
executable, and every field is optional.

    {
      "reader_serial": null,
      "plate_serial": "243819",
      "pathlengths_mm": {"A2": 0.5125, "A3": 0.5096}
    }

reader_serial   null (the default) accepts whichever Epoch answers. Set it only
                when more than one reader is attached and the right one must be
                picked.
plate_serial    the Take3 whose certified pathlengths to use. A plate the
                software does not know falls back to the 0.5 mm nominal.
pathlengths_mm  the values from that plate's Take3 Pathlength Data Sheet, so a
                new plate needs no rebuild. Overrides the built-in table.
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
    pathlengths_mm: dict[str, float] = field(default_factory=dict)
    source: str = "defaults"

    @property
    def pathlengths(self) -> dict[str, float] | None:
        """The table to use: the config's own, else the built-in plate, else None."""
        if self.pathlengths_mm:
            return dict(self.pathlengths_mm)
        from . import take3

        return take3.pathlengths_for_plate(self.plate_serial)


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

    serial = data.get("reader_serial")
    plate = data.get("plate_serial")
    table = data.get("pathlengths_mm") or {}
    if not isinstance(table, dict):
        table = {}

    cleaned: dict[str, float] = {}
    for well, value in table.items():
        try:
            cleaned[str(well).upper()] = float(value)
        except (TypeError, ValueError):
            continue

    return Config(
        reader_serial=str(serial) if serial else None,
        plate_serial=str(plate) if plate else Config.plate_serial,
        pathlengths_mm=cleaned,
        source=str(path),
    )
