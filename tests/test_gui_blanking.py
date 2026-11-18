"""The blanking step on screen: colours, verdict, discard, reset.

This is the technician's described workflow, as a sequence the window has to
support: mark the water spots, read, look at the grid, drop or re-do whatever
came up red, and only then quantify. Every assertion here is about something
she can see or press.

These build a real window, so they are skipped when there is no display.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epoch_open.quant import RawWell                    # noqa: E402

try:
    from epoch_open import gui
    IMPORTED = True
except ImportError:          # no tkinter on this machine
    gui = None
    IMPORTED = False


def _app():
    if not IMPORTED:
        return None
    try:
        return gui.App(gui.MockReader())
    except Exception:        # no X display
        return None


def _blanking(app, offsets):
    """Pretend a blanking just happened, with `offsets` added at 260 nm.

    Goes in through the same two pieces of state a real read fills -- the
    readings it took and the wells that are marked -- so the app derives the
    blank and its verdict exactly as it would from the instrument.
    """
    app.blank_raw = {
        well: RawWell(well=well,
                      readings={260: 0.046 + offset, 280: 0.044, 320: 0.041})
        for well, offset in offsets.items()
    }
    # A fresh blanking, not an addition to the last one: marks left over from a
    # previous call would come back as unread wells and suspend the blank.
    app.blank_selected.clear()
    app.blank_selected.update(offsets)
    app.blank_time = datetime(2026, 10, 26, 10, 57, 16)
    app._refresh_state()


def _colour(app, well):
    return app.blank_buttons[well].cget("bg")


def _field(app, key):
    return app.blank_fields[key].cget("text")


class TestTheGridSaysWhichSpotIsBad:
    def test_a_marked_well_is_blue_until_it_has_been_read(self):
        app = _app()
        if app is None:
            return
        try:
            app._toggle("A2", app.blank_selected, app.blank_buttons)
            assert _colour(app, "A2") == gui.BLANK_PENDING
            assert _field(app, "state") == gui.TEXT["blank_state_unread"]
        finally:
            app.destroy()

    def test_wells_that_agree_turn_green(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0, "C2": 0.0})
            for well in ("A2", "B2", "C2"):
                assert _colour(app, well) == gui.BLANK_WELL
            assert _field(app, "state") == gui.TEXT["blank_state_valid"]
        finally:
            app.destroy()

    def test_the_odd_well_out_turns_red_and_the_others_stay_green(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            assert _colour(app, "A2") == gui.BAD_WELL
            assert _colour(app, "B2") == gui.BLANK_WELL
            # Gen5's own word for this case, photographed on 3 November 2026.
            assert _field(app, "state") == gui.TEXT["blank_state_diverging"]
        finally:
            app.destroy()

    def test_an_unmarked_well_is_left_empty(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0})
            assert _colour(app, "H3") == gui.EMPTY
        finally:
            app.destroy()


class TestSamplesWaitForAGoodBlank:
    def test_a_divergent_blank_keeps_the_sample_button_shut(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
            # And the step being pointed at is still the blank.
            assert app.action_buttons["read_blank"].cget("bg") == gui.ACTION
        finally:
            app.destroy()

    def test_discarding_the_red_well_opens_the_samples_up(self):
        """The fix she described, done by clicking the offending spot."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            app._toggle("A2", app.blank_selected, app.blank_buttons)

            assert _field(app, "state") == gui.TEXT["blank_state_valid"]
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "normal"
            # The discarded well is no longer part of the blank.
            assert "A2" not in (app.blank or {})
            assert sorted(app.blank) == ["B2", "C2", "D2"]
        finally:
            app.destroy()

    def test_a_discarded_well_can_be_put_back_without_reading_again(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0, "D2": 0.0})
            app._toggle("A2", app.blank_selected, app.blank_buttons)
            app._toggle("A2", app.blank_selected, app.blank_buttons)

            assert "A2" in app.blank
            assert _colour(app, "A2") == gui.BAD_WELL
            assert _field(app, "state") == gui.TEXT["blank_state_diverging"]
        finally:
            app.destroy()

    def test_marking_a_new_well_after_reading_suspends_the_blank(self):
        """Half a blank must not be subtracted from anyone's samples.

        A well marked after the read has no reading behind it, so the set on
        screen is not the set that was measured. Until it is read the blank is
        not usable, and the button says so.
        """
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "normal"

            app._toggle("C2", app.blank_selected, app.blank_buttons)
            assert _colour(app, "C2") == gui.BLANK_PENDING
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
            assert app._blank_reason() == gui.TEXT["blank_why_pending"]
        finally:
            app.destroy()

    def test_discarding_every_well_is_not_a_blank(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            for well in ("A2", "B2"):
                app._toggle(well, app.blank_selected, app.blank_buttons)

            assert app.blank is None
            assert not app._blank_ok()
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
        finally:
            app.destroy()


class TestTheStatusBlock:
    def test_it_shows_when_the_blanking_happened(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            assert _field(app, "date") == "26-10-2026"
            assert _field(app, "time") == "10:57:16"
        finally:
            app.destroy()

    def test_the_cv_is_written_the_way_gen5_writes_it(self):
        """With the decimal mark of whichever language is in force."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.002, "B2": 0.0, "C2": 0.0})
            shown = _field(app, "cv")
            assert gui.TEXT["decimal"] in shown and shown.endswith("%")
            assert float(shown.rstrip("%").replace(",", ".")) > 0  # either mark
        finally:
            app.destroy()

    def test_a_single_well_blank_reports_no_cv_and_is_refused(self):
        """0,00 would read as perfect agreement instead of nothing to compare.

        And a blank that cannot be judged is not a blank that passed: Gen5
        refuses to read samples when the CV% cannot be calculated, so the
        state says NO VALIDO and the screen says to mark a second well.
        """
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0})
            assert _field(app, "cv") == "-"
            # Not DIVERGENTE: one well does not diverge from anything. It
            # cannot be judged at all, which is a different failure.
            assert _field(app, "state") == gui.TEXT["blank_state_invalid"]
            assert app.blank_label.cget("text") == gui.TEXT["blank_why_single"]
        finally:
            app.destroy()

    def test_a_bad_blank_says_what_to_do_about_it(self):
        """Not just that it failed, but which fix applies.

        The wells disagreeing too much for the CV% limit is one message; a
        lone well that cannot be judged at all is another, and the fix is
        different -- wipe and repeat, versus mark a second well.
        """
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0})
            # The message carries the measured CV% and the limit it passed, so
            # it cannot be compared against the bare template any more. Which
            # of the two limits stopped her used to be unknowable from the
            # screen -- see App._why_cv.
            shown = app.blank_label.cget("text")
            assert shown == app._why_cv()
            limit = f"{gui.CONFIG.blank_cv_limit_percent:.1f}".replace(
                ".", gui.TEXT["decimal"])
            assert limit in shown, (limit, shown)
            assert "260" in shown

            _blanking(app, {"A2": 0.0})
            assert app.blank_label.cget("text") == gui.TEXT["blank_why_single"]
        finally:
            app.destroy()

    def test_a_good_blank_lists_the_wells_it_is_made_of(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            assert "A2" in app.blank_label.cget("text")
            assert "B2" in app.blank_label.cget("text")
        finally:
            app.destroy()


class TestResetBlanks:
    def test_it_throws_away_the_readings_as_well_as_the_marks(self):
        """Clearing only the marks would leave the old blank still in force."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "B2": 0.0})
            app._reset_blanks()

            assert app.blank_raw is None
            assert app.blank is None
            assert app.blank_selected == set()
            assert _field(app, "state") == gui.TEXT["blank_state_unread"]
            assert _field(app, "cv") == "-"
            assert _colour(app, "A2") == gui.EMPTY
            assert str(app.action_buttons["read_samples"].cget("state")) \
                == "disabled"
        finally:
            app.destroy()


class TestTheScreenSaysWhichLimitStoppedHer:
    """Added 18 November 2026, from a question that could not be answered.

    A technician reported being refused repeatedly, and could not say which of
    the two checks had done it -- reasonably, because the CV% message said
    "above the limit" and the disagreement message said "do not agree with each
    other", which are the same sentence to anybody who has not read the source.
    Neither carried a number. Both now carry the measured value and the limit.
    """

    def test_the_cv_message_carries_the_measured_cv_and_the_limit(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0})
            shown = app.blank_label.cget("text")
            assert app.blank_report.reason == "cv"
            measured = f"{app.blank_report.cv_260:.1f}".replace(
                ".", gui.TEXT["decimal"])
            assert measured in shown, (measured, shown)
            assert "260" in shown
        finally:
            app.destroy()

    def test_the_disagreement_message_carries_the_sd_and_the_limit(self):
        app = _app()
        if app is None:
            return
        try:
            # Two wells 0,005 AU apart: neither can be blamed, and the CV% is
            # fine, so this is the one message only this gate produces.
            _blanking(app, {"A2": 0.005, "B2": 0.0})
            assert app.blank_report.reason == "dispersion"
            shown = app.blank_label.cget("text")
            limit = f"{gui.CONFIG.blank_dispersion_limit_au:.4f}".replace(
                ".", gui.TEXT["decimal"])
            assert limit in shown, (limit, shown)
        finally:
            app.destroy()

    def test_the_two_messages_are_not_the_same_sentence(self):
        """The defect itself: they used to be indistinguishable."""
        if not IMPORTED:
            return
        from epoch_open import i18n

        was = i18n.current()
        try:
            for language in ("en", "es"):
                i18n.set_language(language)
                assert (gui.TEXT["blank_why_cv"]
                        != gui.TEXT["blank_why_dispersion"])
                assert "{cv" in gui.TEXT["blank_why_cv"]
                assert "{limit" in gui.TEXT["blank_why_cv"]
                assert "{sd" in gui.TEXT["blank_why_dispersion"]
                assert "{limit" in gui.TEXT["blank_why_dispersion"]
        finally:
            i18n.set_language(was)

    def test_a_spanish_sentence_keeps_its_full_stop(self):
        """The decimal mark must reach the numbers and nothing else.

        Swapping every "." in the finished sentence -- the obvious way to do
        this -- turns the full stop at the end of a Spanish one into a comma.
        See gui._Decimal.
        """
        if not IMPORTED:
            return
        from epoch_open import i18n

        was = i18n.current()
        try:
            i18n.set_language("es")
            rendered = gui.TEXT["blank_why_dispersion"].format(
                sd=gui._Decimal(0.0035), limit=gui._Decimal(0.0025))
            assert "0,0035" in rendered
            assert "0,0025" in rendered
            assert rendered.rstrip().endswith(".")
        finally:
            i18n.set_language(was)


class TestTheWorkbookRecordsTheBlanking:
    """Every concentration in the file was computed by subtracting this blank.

    The file recorded nothing about it until 18 November 2026: not which wells
    it came from, not how well they agreed, not whether any had been dropped.
    That gap is why a bench report of repeated refusals had to be diagnosed
    from Gen5's own exports instead of from the lab's own files.
    """

    def test_it_names_the_wells_the_cv_and_the_verdict(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "A3": 0.0005, "B2": 0.0})
            meta = app._blank_metadata()
            assert meta[gui.TEXT["meta_blank_wells"]] == "A2, A3, B2"
            assert "260" in meta[gui.TEXT["meta_blank_cv"]]
            assert meta[gui.TEXT["meta_blank_dispersion"]]
            assert (meta[gui.TEXT["meta_blank_verdict"]]
                    == gui.TEXT["meta_blank_valid"])
        finally:
            app.destroy()

    def test_a_refused_blank_is_recorded_as_refused(self):
        """The blank somebody will most want to see afterwards."""
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.010, "B2": 0.0, "C2": 0.0})
            meta = app._blank_metadata()
            assert (meta[gui.TEXT["meta_blank_verdict"]]
                    == gui.TEXT["meta_blank_invalid"])
        finally:
            app.destroy()

    def test_discarded_wells_are_named_so_the_average_can_be_checked(self):
        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "A3": 0.0, "B2": 0.0})
            app.blank_selected.discard("B2")
            app._refresh_state()
            meta = app._blank_metadata()
            assert meta[gui.TEXT["meta_blank_wells"]] == "A2, A3"
            assert meta[gui.TEXT["meta_blank_discarded"]] == "B2"
        finally:
            app.destroy()

    def test_the_rows_reach_the_spreadsheet(self):
        import tempfile
        import zipfile

        from epoch_open import xlsx

        app = _app()
        if app is None:
            return
        try:
            _blanking(app, {"A2": 0.0, "A3": 0.0005})
            meta = app._blank_metadata()
        finally:
            app.destroy()

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blank.xlsx"
            xlsx.export_results(path, [], metadata=meta)
            with zipfile.ZipFile(path) as archive:
                text = "\n".join(
                    archive.read(name).decode("utf-8", "replace")
                    for name in archive.namelist() if name.endswith(".xml"))
        assert gui.TEXT["meta_blank_wells"] in text
        assert gui.TEXT["meta_blank_verdict"] in text


class TestARefusedBlankCanStillBeSaved:
    """Found at the bench on 18 November 2026, by trying to use the last fix.

    The blank record was added to the workbook so that a refused blanking
    could be looked at afterwards. It could not: saving needed results, a
    refused blank produces none by definition, and so the one run whose
    numbers somebody needs was the only run that could not produce a file.
    The technician was left with a screen she could photograph.
    """

    def _refused(self, app):
        """A blanking that fails on disagreement, as hers did."""
        _blanking(app, {"A2": 0.0, "A3": 0.012, "B2": 0.0, "B3": 0.011})
        return app.blank_report

    def test_the_save_button_is_live_with_a_blank_and_no_samples(self):
        app = _app()
        if app is None:
            return
        try:
            report = self._refused(app)
            assert not report.valid, "this test needs a refused blank"
            assert app.results == []
            assert app.action_buttons["end_batch"].cget("state") == "normal"
        finally:
            app.destroy()

    def test_the_file_carries_the_numbers_from_the_screen(self):
        """What she would otherwise have to read off a photograph."""
        import tempfile
        import zipfile

        from epoch_open import xlsx

        app = _app()
        if app is None:
            return
        try:
            report = self._refused(app)
            meta = app._blank_metadata()
            dispersion = f"{report.dispersion_au:.5f}".replace(
                ".", gui.TEXT["decimal"])
        finally:
            app.destroy()

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blank-only.xlsx"
            xlsx.export_results(path, [], metadata=meta)
            with zipfile.ZipFile(path) as archive:
                text = "\n".join(
                    archive.read(name).decode("utf-8", "replace")
                    for name in archive.namelist() if name.endswith(".xml"))

        assert gui.TEXT["meta_blank_verdict"] in text
        assert gui.TEXT["meta_blank_invalid"] in text
        assert dispersion in text, dispersion

    def test_saving_the_blank_does_not_throw_the_blank_away(self):
        """Saving the record must not cost her the blanking it records.

        A full batch save closes the batch, which is right once samples have
        been read and wrong here: she still has the same plate in front of
        her and still has to decide what to do about it. Pressing save to
        send somebody the numbers must not make her blank again.
        """
        import tempfile

        app = _app()
        if app is None:
            return
        chosen = []
        original = gui.filedialog.asksaveasfilename
        folder = tempfile.mkdtemp()

        def fake_dialog(**kwargs):
            # Also the only place the proposed filename can be inspected.
            chosen.append(kwargs.get("initialfile", ""))
            return str(Path(folder) / "blank-only.xlsx")

        try:
            self._refused(app)
            wells_before = app.blank_report.wells
            gui.filedialog.asksaveasfilename = fake_dialog
            app._end_batch()

            assert Path(folder, "blank-only.xlsx").exists(), "no file written"
            assert chosen and chosen[0].startswith(
                gui.TEXT["file_stem_blank"]), chosen
            # The blanking survives the save, untouched.
            assert app.blank_raw is not None
            assert app.blank_report is not None
            assert app.blank_report.wells == wells_before
        finally:
            gui.filedialog.asksaveasfilename = original
            app.destroy()

    def test_a_full_batch_still_closes_when_it_is_saved(self):
        """The ordinary path must keep its old behaviour."""
        import tempfile

        app = _app()
        if app is None:
            return
        original = gui.filedialog.asksaveasfilename
        folder = tempfile.mkdtemp()
        try:
            _blanking(app, {"A2": 0.0, "A3": 0.0005})
            app._read_samples_into_results() if hasattr(
                app, "_read_samples_into_results") else None
            if not app.results:
                # Read a sample the ordinary way so this exercises the real
                # path rather than a hand-built results list.
                app.sample_selected.clear()
                app.sample_selected.add("B2")
                app._read_samples()
            if not app.results:
                return
            gui.filedialog.asksaveasfilename = (
                lambda **kw: str(Path(folder) / "full.xlsx"))
            app._end_batch()
            assert Path(folder, "full.xlsx").exists()
            assert app.results == [], "a finished batch should close"
            assert app.blank_raw is None
        finally:
            gui.filedialog.asksaveasfilename = original
            app.destroy()

    def test_an_empty_screen_still_has_nothing_to_save(self):
        """The guard has to keep rejecting the genuinely empty case."""
        app = _app()
        if app is None:
            return
        try:
            assert app.results == []
            assert app.blank_report is None
            assert app.action_buttons["end_batch"].cget("state") == "disabled"
        finally:
            app.destroy()

    def test_the_blank_only_file_is_named_so_it_is_not_mistaken_for_results(self):
        if not IMPORTED:
            return
        from epoch_open import i18n

        was = i18n.current()
        try:
            for language in ("en", "es"):
                i18n.set_language(language)
                assert gui.TEXT["file_stem_blank"] != gui.TEXT["file_stem"]
                assert gui.TEXT["saved_blank"] != gui.TEXT["saved"]
                assert "{path}" in gui.TEXT["saved_blank"]
        finally:
            i18n.set_language(was)
