"""The two languages, and the ways a translation goes wrong quietly.

A missing key or a dropped placeholder does not fail at startup. It fails
later, in front of somebody, at the moment the program first needs that one
sentence -- which in practice is the moment something else has already gone
wrong. So the parity between the languages is asserted here rather than
trusted.

Everything in this file runs without a display.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open import config, curve, i18n, launch, quant, xlsx  # noqa: E402

# Importing the GUI modules is what registers their tables, and they need
# tkinter. Without it the rest of the file still has something to check.
try:
    from epoch_open import gui, gui_curve
    GUIS = [gui, gui_curve]
except ImportError:                                 # pragma: no cover
    GUIS = []


def _placeholders(value):
    """The {names} a format string will demand when it is used."""
    import re

    if not isinstance(value, str):
        return set()
    return set(re.findall(r"\{(\w+)", value))


def _tables():
    """Every per-language table in the project, by name."""
    out = {
        "xlsx.TEXT": xlsx.TEXT_BY_LANGUAGE,
        "quant.MESSAGES": quant.MESSAGES_BY_LANGUAGE,
        "quant.SHORT_MESSAGES": quant.SHORT_MESSAGES_BY_LANGUAGE,
        "curve.MESSAGES": curve.MESSAGES_BY_LANGUAGE,
        "curve.SHORT_MESSAGES": curve.SHORT_MESSAGES_BY_LANGUAGE,
        "curve.FIT_MESSAGES": curve.FIT_MESSAGES_BY_LANGUAGE,
    }
    for module in GUIS:
        out[f"{module.__name__}.TEXT"] = module.TEXT_BY_LANGUAGE
    return out


class TestTheLanguagesAgreeOnWhatTheySay:
    def test_every_table_has_both_languages(self):
        for name, table in _tables().items():
            assert set(table) == {"en", "es"}, f"{name}: {sorted(table)}"

    def test_no_key_is_missing_from_either_language(self):
        for name, table in _tables().items():
            english, spanish = set(table["en"]), set(table["es"])
            assert english == spanish, (
                f"{name}: only in en {sorted(english - spanish)}, "
                f"only in es {sorted(spanish - english)}")

    def test_the_placeholders_match(self):
        """`{well}` present in one language and absent in the other is a crash.

        This is the same class of bug as the KeyError that once came out of
        `note(code, well=...)`: the message formats fine until the day the
        other language is selected.
        """
        for name, table in _tables().items():
            for key, spanish in table["es"].items():
                assert (_placeholders(table["en"][key])
                        == _placeholders(spanish)), f"{name}[{key!r}]"

    def test_nothing_was_left_untranslated(self):
        """A key copied across rather than translated, which reads as a bug.

        Deliberate exceptions are listed: a symbol, a unit, or a word that is
        genuinely the same in both languages.
        """
        same_on_purpose = {
            "r2", "unit", "in_range_no", "role_blanco", "name_prompt",
            "name_title", "reading", "nothing_to_save", "no_sample_wells",
            "columns", "title", "connected", "wl_cancel", "prefs_cancel",
            "plate_cancel", "curve_field_r2", "no_curve_label",
            "blank_field_cv", "column_conc",
        }
        for name, table in _tables().items():
            copied = [k for k, v in table["es"].items()
                      if table["en"][k] == v and k not in same_on_purpose]
            assert not copied, f"{name}: untranslated {copied}"

    def test_the_project_has_no_third_language_by_accident(self):
        assert set(i18n.LANGUAGES) == {"en", "es"}


class TestSwitchingLanguage:
    def test_the_live_dict_follows_the_setting(self):
        was = i18n.current()
        try:
            i18n.set_language("es")
            assert xlsx.TEXT["sheet_summary"] == "Resumen"
            i18n.set_language("en")
            assert xlsx.TEXT["sheet_summary"] == "Summary"
        finally:
            i18n.set_language(was)

    def test_the_dict_is_filled_in_place_never_rebound(self):
        """Call sites hold the dict itself, so it must not be replaced."""
        was, held = i18n.current(), xlsx.TEXT
        try:
            i18n.set_language("es")
            assert xlsx.TEXT is held, "the dict was rebound, not refilled"
            assert held["sheet_summary"] == "Resumen"
        finally:
            i18n.set_language(was)

    def test_english_is_the_default(self):
        assert i18n.DEFAULT == "en"

    def test_nonsense_falls_back_instead_of_raising(self):
        """A hand-edited config will eventually contain something odd."""
        for junk in ("english", "", "fr", "  ", None, 7, [], "es-CL-x"):
            assert i18n.normalise(junk) in i18n.LANGUAGES

    def test_a_region_is_ignored_but_the_language_is_not(self):
        assert i18n.normalise("es-CL") == "es"
        assert i18n.normalise("ES_es") == "es"
        assert i18n.normalise("en-GB") == "en"

    def test_a_table_with_one_language_still_renders(self):
        """A half-finished translation must not produce a blank window."""
        live = i18n.register({}, {"es": {"only": "unico"}})
        was = i18n.current()
        try:
            i18n.set_language("en")
            assert live["only"] == "unico"
        finally:
            i18n.set_language(was)


class TestWhereTheLanguageComesFrom:
    def test_the_config_carries_it(self):
        assert config.Config().language == i18n.DEFAULT

    def test_it_survives_a_round_trip(self, tmp_path=None):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "epoch_open.json"
            cfg = config.Config()
            cfg.language = "es"
            config.save(cfg, path)
            assert config.load(path).language == "es"

    def test_a_broken_language_in_the_file_does_not_stop_the_program(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "epoch_open.json"
            path.write_text(json.dumps({"language": "Klingon"}))
            assert config.load(path).language == i18n.DEFAULT

    def test_the_command_line_wins(self):
        assert launch.language_override(["run.py", "--lang", "es"]) == "es"
        assert launch.language_override(["run.py", "--lang=en"]) == "en"

    def test_nothing_asked_is_not_the_same_as_the_default(self):
        """So the configuration is not overridden by its own absence."""
        import os

        was = os.environ.pop("EPOCH_LANG", None)
        try:
            assert launch.language_override(["run.py"]) is None
        finally:
            if was is not None:
                os.environ["EPOCH_LANG"] = was


class TestTheWorkbookFollowsTheLanguage:
    """The file is what leaves the lab, so it is what someone else reads."""

    def _export(self, language):
        import tempfile

        standards = [curve.Standard("A1", 0, 0.001),
                     curve.Standard("B1", 10, 0.102),
                     curve.Standard("C1", 20, 0.201)]
        fit = curve.fit_standards(standards, unit="ug/mL")
        was = i18n.current()
        try:
            i18n.set_language(language)
            folder = tempfile.mkdtemp()
            path = Path(folder) / f"curve-{language}.xlsx"
            xlsx.export_curve(path, [], fit, [530], unit="ug/mL")
            import zipfile
            with zipfile.ZipFile(path) as z:
                return "\n".join(
                    z.read(n).decode("utf-8", "replace")
                    for n in z.namelist() if n.endswith(".xml"))
        finally:
            i18n.set_language(was)

    def test_an_english_workbook_has_no_spanish_in_it(self):
        text = self._export("en")
        for word in ("Pozo", "Muestra", "Aviso", "Resumen", "Detalle",
                     "Pendiente", "Concentracion patron", "UTILIZABLE"):
            assert word not in text, f"{word!r} left in the English workbook"

    def test_the_english_workbook_uses_gen5_vocabulary(self):
        """So the two files can be compared column by column."""
        text = self._export("en")
        for word in ("Summary", "Curve", "Well", "Known concentration",
                     "Slope", "Residual", "USABLE"):
            assert word in text, f"{word!r} missing from the English workbook"

    def test_a_spanish_workbook_is_unchanged(self):
        text = self._export("es")
        for word in ("Resumen", "Curva", "Pozo", "Concentracion patron",
                     "Pendiente", "UTILIZABLE"):
            assert word in text, f"{word!r} missing from the Spanish workbook"
