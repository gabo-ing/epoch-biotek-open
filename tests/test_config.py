"""Tests for the settings file.

The program ships as a single .exe, so a broken or missing config must never stop
it starting -- an owner cannot edit the source to recover.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import config  # noqa: E402


def write(name: str, text: str) -> Path:
    directory = Path(__file__).resolve().parent / "_out"
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class TestDefaults:
    def test_missing_file_gives_defaults(self):
        c = config.load(Path("/nonexistent/epoch_open.json"))
        assert c.reader_serial is None
        assert c.plate_serial == "243819"

    def test_any_reader_is_accepted_by_default(self):
        """The bug this guards: a hardcoded serial made the software reject every
        reader but the one it was developed on."""
        assert config.load(Path("/nonexistent/x.json")).reader_serial is None

    def test_known_plate_still_resolves_its_pathlengths(self):
        c = config.load(Path("/nonexistent/x.json"))
        assert len(c.pathlengths) == 16


class TestReading:
    def test_values_are_read(self):
        p = write("good.json", json.dumps(
            {"reader_serial": "999", "plate_serial": "111222"}))
        c = config.load(p)
        assert c.reader_serial == "999"
        assert c.plate_serial == "111222"

    def test_pathlengths_override_the_built_in_table(self):
        p = write("paths.json", json.dumps(
            {"plate_serial": "243819", "pathlengths_mm": {"a2": 0.6}}))
        c = config.load(p)
        assert c.pathlengths["A2"] == 0.6

    def test_an_unknown_plate_falls_back_to_nominal(self):
        p = write("unknown.json", json.dumps({"plate_serial": "000000"}))
        assert config.load(p).pathlengths is None


class TestBrokenFilesDoNotStopTheProgram:
    def test_invalid_json_falls_back(self):
        p = write("broken.json", "{not json at all")
        c = config.load(p)
        assert c.reader_serial is None
        assert "unreadable" in c.source

    def test_a_json_list_falls_back(self):
        p = write("list.json", "[1, 2, 3]")
        assert config.load(p).plate_serial == "243819"

    def test_nonsense_pathlength_values_are_skipped(self):
        p = write("bad_paths.json", json.dumps(
            {"pathlengths_mm": {"A2": "abc", "B2": 0.51}}))
        table = config.load(p).pathlengths
        assert "A2" not in table
        assert table["B2"] == 0.51

    def test_empty_file_falls_back(self):
        p = write("empty.json", "")
        assert config.load(p).plate_serial == "243819"


class TestSaving:
    def test_a_saved_config_reads_back(self):
        directory = Path(__file__).resolve().parent / "_out"
        directory.mkdir(exist_ok=True)
        path = directory / "roundtrip.json"

        cfg = config.Config(reader_serial=None)
        cfg.set_plate("999888", {"A2": 0.5111, "H3": 0.4982})
        config.save(cfg, path)

        back = config.load(path)
        assert back.plate_serial == "999888"
        assert back.pathlengths["A2"] == 0.5111
        assert back.pathlengths["H3"] == 0.4982

    def test_saving_leaves_no_temporary_file(self):
        directory = Path(__file__).resolve().parent / "_out"
        path = directory / "clean.json"
        config.save(config.Config(plate_serial="1"), path)
        assert not path.with_suffix(".json.tmp").exists()

    def test_saved_pathlengths_override_the_builtin_plate(self):
        directory = Path(__file__).resolve().parent / "_out"
        path = directory / "override.json"
        cfg = config.Config()
        cfg.set_plate("243819", {"A2": 0.6000})
        config.save(cfg, path)
        assert config.load(path).pathlengths["A2"] == 0.6


class TestPlatesAreKeptPerSerial:
    """The bug this guards: one stored table meant that registering a
    replacement plate and later switching back left the first plate using the
    replacement's pathlengths, about 2% wrong and invisible."""

    def path(self, name):
        directory = Path(__file__).resolve().parent / "_out"
        directory.mkdir(exist_ok=True)
        p = directory / name
        if p.exists():
            p.unlink()
        return p

    def test_switching_back_restores_the_original_sheet(self):
        p = self.path("swap.json")
        cfg = config.load(p)
        cfg.set_plate("999999", {f"{r}{c}": 0.52 for r in "ABCDEFGH" for c in (2, 3)})
        config.save(cfg, p)

        cfg = config.load(p)
        assert cfg.pathlengths["A2"] == 0.52

        cfg.set_plate("243819", None)
        config.save(cfg, p)
        assert config.load(p).pathlengths["A2"] == 0.5125   # the built-in sheet

    def test_each_plate_keeps_its_own_values(self):
        p = self.path("two.json")
        cfg = config.load(p)
        cfg.set_plate("AAA", {"A2": 0.5101})
        cfg.set_plate("BBB", {"A2": 0.4902})
        config.save(cfg, p)

        cfg = config.load(p)
        assert cfg.pathlengths_for("AAA")["A2"] == 0.5101
        assert cfg.pathlengths_for("BBB")["A2"] == 0.4902

    def test_a_plate_registered_without_a_sheet_stays_uncalibrated(self):
        p = self.path("nominal.json")
        cfg = config.load(p)
        cfg.set_plate("NOSHEET", None)
        config.save(cfg, p)
        assert config.load(p).pathlengths is None

    def test_the_old_single_table_format_still_loads(self):
        p = self.path("legacy.json")
        p.write_text(json.dumps({"plate_serial": "777", "pathlengths_mm": {"A2": 0.5}}))
        assert config.load(p).pathlengths["A2"] == 0.5


class TestBlankLimits:
    """The two thresholds the blanking verdict uses, which labs may move.

    They are this project's own numbers rather than anything recovered from
    Gen5, so they have to be reachable without a rebuild -- which means the
    config file has to carry them, survive a save, and refuse nonsense.
    """

    def path(self, name):
        directory = Path(__file__).resolve().parent / "_out"
        directory.mkdir(exist_ok=True)
        p = directory / name
        if p.exists():
            p.unlink()
        return p

    def test_the_defaults_are_the_ones_the_quant_module_decided(self):
        from epoch_open import quant

        cfg = config.Config()
        assert cfg.blank_spread_limit_au == quant.BLANK_SPREAD_LIMIT_AU
        assert cfg.blank_divergence_limit_au == quant.BLANK_DIVERGENCE_LIMIT_AU

    def test_a_lab_can_loosen_them_in_the_file(self):
        p = self.path("limits.json")
        p.write_text(json.dumps({"blank_spread_limit_au": 0.010,
                                 "blank_divergence_limit_au": 0.008}))
        cfg = config.load(p)
        assert cfg.blank_spread_limit_au == 0.010
        assert cfg.blank_divergence_limit_au == 0.008

    def test_they_survive_a_save(self):
        """Registering a plate must not quietly reset them to the defaults."""
        p = self.path("limits-roundtrip.json")
        p.write_text(json.dumps({"blank_spread_limit_au": 0.010,
                                 "blank_divergence_limit_au": 0.008}))
        cfg = config.load(p)
        cfg.set_plate("243819", {"A2": 0.5})
        config.save(cfg, p)

        reloaded = config.load(p)
        assert reloaded.blank_spread_limit_au == 0.010
        assert reloaded.blank_divergence_limit_au == 0.008

    def test_a_limit_of_zero_is_ignored_rather_than_obeyed(self):
        """Zero would reject every blank ever read, including perfect ones."""
        p = self.path("zero.json")
        p.write_text(json.dumps({"blank_spread_limit_au": 0,
                                 "blank_divergence_limit_au": -1}))
        cfg = config.load(p)
        assert cfg.blank_spread_limit_au > 0
        assert cfg.blank_divergence_limit_au > 0

    def test_rubbish_falls_back_instead_of_stopping_the_program(self):
        p = self.path("rubbish.json")
        p.write_text(json.dumps({"blank_spread_limit_au": "mucho"}))
        from epoch_open import quant

        assert config.load(p).blank_spread_limit_au \
            == quant.BLANK_SPREAD_LIMIT_AU

    def test_the_example_file_matches_the_built_in_defaults(self):
        """A shipped example that disagrees with the code teaches a wrong number."""
        from epoch_open import quant

        root = Path(__file__).resolve().parent.parent
        example = json.loads((root / "epoch_open.example.json").read_text())
        assert example["blank_spread_limit_au"] == quant.BLANK_SPREAD_LIMIT_AU
        assert example["blank_divergence_limit_au"] \
            == quant.BLANK_DIVERGENCE_LIMIT_AU
