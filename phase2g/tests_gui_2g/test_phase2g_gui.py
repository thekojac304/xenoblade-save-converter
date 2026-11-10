"""Phase 2G GUI tests (pytest-qt): the real MainWindow driven like a user, on copied or synthetic saves only.

Run from the research folder:  python -m pytest tests_gui -v
Outputs go to work/test_phase2g/gui/<test>; the user's original saves are only read.
"""
import json
import os
import shutil
import struct
import threading

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

import p2f_util as U
import paths
import safeio
import wii_save
import xcconv
import xcservice as svc
from conftest import DATA, ROOT, idle
from xcgui import messages
from xcgui.widgets import tone

W01 = os.path.join(U.O, "monado01")
W03 = os.path.join(U.O, "monado03")
DE_USER = os.path.join(U.O, "user_v10_bfsgame00.sav")
DE_V7 = os.path.join(U.PUBLIC, "s206_207aed635e_bfsgame01.sav")


def copy(src, d, name=None):
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name or os.path.basename(src))
    shutil.copyfile(src, p)
    return p


def files_of(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            out[os.path.relpath(p, d).replace("\\", "/")] = U.rd(p)
    return out


def select(qtbot, w, picker, path):
    picker.set_path(path)
    idle(qtbot, w)


def convert(qtbot, w):
    assert w.convert_btn.isEnabled(), w.missing()
    with qtbot.waitSignal(w.conversion_finished, timeout=180000) as sig:
        qtbot.mouseClick(w.convert_btn, Qt.MouseButton.LeftButton)
    idle(qtbot, w)
    return sig.args[0]


# ------------------------------------------------------------------------------------------------- launch / exit
def test_launch_and_clean_exit(make_win, qtbot):
    w = make_win()
    assert w.isVisible()
    assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == ["&Convert", "&Advanced tools", "&Game data"]
    assert not w.convert_btn.isEnabled()
    assert "choose your save" in w.ready_label.text()
    assert not w.data_banner.isVisible()            # tables configured
    w.close()
    assert not w.isVisible()
    assert not w.engine.busy()


def test_first_run_without_game_data(make_win, qtbot, tmpdir_, monkeypatch):
    monkeypatch.setattr(paths, "FALLBACKS", [])      # no fallback tables next to the code (as in the package)
    monkeypatch.delenv("XCCONV_DATA", raising=False)
    w = make_win(data=False)
    assert w.data_banner.isVisible()
    assert "set up the game data" in w.ready_label.text()
    select(qtbot, w, w.src_pick, W01)                # recognised from its header even without tables
    assert w.dir_w2d.isChecked()
    assert not w.convert_btn.isEnabled()
    assert not w.set_data_dir(tmpdir_)               # folder without tables refused
    assert w.set_data_dir(DATA)
    idle(qtbot, w)
    assert not w.data_banner.isVisible()
    assert w.pv["location"].text() == "Eryth Sea (ma1001)"


# ------------------------------------------------------------------------------------------------- selection, preview
def test_file_selection_preview_and_format_detection(make_win, qtbot):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    pv = svc.preview(W01)
    assert w.dir_w2d.isChecked()
    assert w.pv["format"].text().startswith("Wii save")
    assert w.pv["location"].text() == "Eryth Sea (ma1001)"
    assert w.pv["story"].text() == "Story scenario 150"
    assert w.pv["play_time"].text() == pv["play_time"] == "22:01:57"
    assert w.pv["party"].text() == ", ".join(f"{m['name']} Lv {m['level']}" for m in pv["party"])
    assert w.pv["money"].text() == f"{pv['money']:,} G"
    select(qtbot, w, w.src_pick, DE_USER)
    assert w.dir_d2w.isChecked()                      # direction follows the detected format
    assert w.pv["format"].text() == "Definitive Edition save, format v10"


def test_v7_preview_explains_upgrade(make_win, qtbot):
    if not os.path.exists(DE_V7):
        pytest.skip("public v7 save not present")
    w = make_win()
    select(qtbot, w, w.src_pick, DE_V7)
    assert "format v7" in w.pv["format"].text() and "upgrade it to v10" in w.pv["format"].text()
    assert w.compat_notice.isVisible()
    assert "format v10" in w.compat_notice.body.text()
    assert not w.convert_btn.isEnabled()


def test_drag_and_drop(make_win, qtbot, tmpdir_):
    w = make_win()
    p = copy(W01, os.path.join(tmpdir_, "dropped"))
    args = (Qt.DropAction.CopyAction,)
    mods = (Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    text = QMimeData()
    text.setText("not a file")
    enter = QDragEnterEvent(QPoint(10, 10), *args, text, *mods)
    QApplication.sendEvent(w.drop, enter)
    assert not enter.isAccepted()                              # only local files are accepted
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(p)])
    enter = QDragEnterEvent(QPoint(10, 10), *args, md, *mods)  # the sequence Windows delivers: enter, move, drop
    QApplication.sendEvent(w.drop, enter)
    assert enter.isAccepted()
    QApplication.sendEvent(w.drop, QDragMoveEvent(QPoint(12, 12), *args, md, *mods))
    QApplication.sendEvent(w.drop, QDropEvent(QPointF(12, 12), *args, md, *mods))
    idle(qtbot, w)
    assert w.src_pick.path() == os.path.normpath(p)
    assert w.src and w.src["story"] == 150


def test_folder_selection(make_win, qtbot, tmpdir_):
    w = make_win()
    d = os.path.join(tmpdir_, "one_save")
    copy(DE_USER, os.path.join(d, "save_0"), "bfsgame03.sav")
    select(qtbot, w, w.src_pick, d)
    assert w.src_pick.path() == os.path.join(d, "save_0", "bfsgame03.sav")
    assert w.dir_d2w.isChecked()
    select(qtbot, w, w.src_pick, os.path.join(tmpdir_, "empty_folder_missing"))
    assert w.src_status.isVisible() and w.src_status.kind == "error"


def test_not_a_save_and_sidecar_as_source(make_win, qtbot, tmpdir_):
    w = make_win()
    junk = os.path.join(tmpdir_, "junk.sav")
    with open(junk, "wb") as f:
        f.write(b"x" * 5000)
    select(qtbot, w, w.src_pick, junk)
    assert w.src_status.title.text() == "Not a Xenoblade Chronicles save"
    out = os.path.join(tmpdir_, "sc")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=out))
    select(qtbot, w, w.src_pick, os.path.join(out, "wii_to_de.sidecar.json"))
    assert "preservation file, not a save" in w.src_status.title.text()
    assert not w.convert_btn.isEnabled()


def test_direction_change_requires_matching_save(make_win, qtbot):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    assert w.convert_btn.isEnabled()
    w.dir_d2w.setChecked(True)
    idle(qtbot, w)
    assert not w.convert_btn.isEnabled()
    assert "choose a Definitive Edition save, or switch the conversion direction" in w.ready_label.text()
    assert w.tpl_pick.path() == ""                    # inputs of the other direction were cleared
    assert w.slot_combo.currentText().startswith("monado")


# ------------------------------------------------------------------------------------------------- requirements
def test_missing_and_wrong_template(make_win, qtbot):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    assert w.mode_first.isChecked()
    assert "choose a starting Definitive Edition save" in w.ready_label.text()
    select(qtbot, w, w.tpl_pick, W03)                 # a Wii save is not a DE starting save
    assert w.tpl_status.kind == "error" and not w.convert_btn.isEnabled()
    if os.path.exists(DE_V7):
        select(qtbot, w, w.tpl_pick, DE_V7)
        assert w.tpl_status.title.text() == "Older Definitive Edition save"
    select(qtbot, w, w.tpl_pick, U.TPL)
    assert w.convert_btn.isEnabled()


def test_return_needs_sidecar_and_current_save(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    w.mode_return.setChecked(True)
    idle(qtbot, w)
    assert "choose the preservation file" in w.ready_label.text()
    assert "choose your current Definitive Edition save, or confirm" in w.ready_label.text()
    out = os.path.join(tmpdir_, "foreign")                        # a sidecar of another save history
    svc.de_to_wii_convert(svc.DeToWiiRequest(de=DE_USER, base=W03, out=out))
    select(qtbot, w, w.sc_pick, os.path.join(out, "de_to_wii.sidecar.json"))
    assert w.sc_status.title.text() == "Preservation file from a different save history"
    assert "different save history" in w.sc_status.body.text()
    assert not w.convert_btn.isEnabled()
    w.no_cur.setChecked(True)
    assert not w.cur_pick.isEnabled()
    assert not w.convert_btn.isEnabled()                         # still the wrong sidecar


def test_compatibility_error_temporary_character(make_win, qtbot, tmpdir_):
    """Fiora's second form (8) in the Wii party: refused before conversion, in plain language."""
    m = U.Wii(U.rd(W01))
    ir = wii_save.decode_bytes(m.b)
    m.img.put(wii_save.PARTY + 4 * len(ir["party"]), "H", 8)
    p = os.path.join(tmpdir_, "monado01")
    with open(p, "wb") as f:
        f.write(m.done())
    w = make_win()
    select(qtbot, w, w.src_pick, p)
    select(qtbot, w, w.tpl_pick, U.TPL)
    assert w.compat_notice.isVisible()
    assert "temporary character form" in w.compat_notice.body.text()
    assert "Unsupported char ID" not in w.compat_notice.body.text()
    assert not w.convert_btn.isEnabled()


def test_output_path_validation(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    w.out_pick.set_path(r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save")
    assert w.out_status.kind == "error"
    assert w.out_status.title.text() == "Output inside a game or save folder"
    assert not w.convert_btn.isEnabled()
    w.out_pick.set_path(os.path.join(U.ROOT, "..", "..", "..", "..", "Filen", "Video Game Stuff",
                                     "Game Saves & Memory Cards", "Wii", "title", "00010000", "53583445", "x"))
    assert w.out_status.kind == "error"
    w.out_pick.set_path(os.path.join(tmpdir_, "fine"))
    assert w.out_status.kind is None and w.convert_btn.isEnabled()
    assert w.out_example.text().startswith(os.path.join(tmpdir_, "fine", "wii_to_de_"))


# ------------------------------------------------------------------------------------------------- conversions
def test_both_directions_match_cli_byte_for_byte(make_win, qtbot, tmpdir_):
    """GUI round trip Wii -> DE -> Wii -> DE, each step compared with the CLI given the same inputs."""
    src = copy(W01, os.path.join(tmpdir_, "input"))                    # copied, non-live fixture
    w = make_win()
    # 1) Wii -> DE, first export
    select(qtbot, w, w.src_pick, src)
    select(qtbot, w, w.tpl_pick, U.TPL)
    w.slot_combo.setCurrentText("01")
    assert convert(qtbot, w) is True
    r1 = w.last_result
    assert w.result_path.text() == r1.main_output and os.path.isfile(r1.main_output)
    assert all(w.stages.state(k) == "done" for k in w.stages.order)
    cli1 = os.path.join(tmpdir_, "cli1")
    assert xcconv.main(["wii-to-de", "--wii", src, "--template", U.TPL, "--out", cli1, "--slot", "01"]) == 0
    assert files_of(r1.out_dir) == files_of(cli1)
    assert U.rd(r1.main_output) == U.rd(os.path.join(ROOT, "release_candidate_2F", "user_saves", "wii_to_de_monado01",
                                                    "save_0", "bfsgame01.sav"))
    # 2) DE -> Wii, back with the sidecar found automatically
    de1 = r1.main_output
    select(qtbot, w, w.src_pick, de1)
    assert w.dir_d2w.isChecked() and w.mode_return.isChecked()
    assert w.disc.chosen and w.disc.chosen.path == r1.sidecar_path
    select(qtbot, w, w.cur_pick, src)
    assert convert(qtbot, w) is True
    r2 = w.last_result
    cli2 = os.path.join(tmpdir_, "cli2")
    assert xcconv.main(["de-to-wii", "--de", de1, "--sidecar", r1.sidecar_path, "--current-wii", src,
                        "--out", cli2]) == 0
    assert files_of(r2.out_dir) == files_of(cli2)
    # 3) Wii -> DE again: the unchanged Wii save brings back the DE save byte for byte
    select(qtbot, w, w.src_pick, r2.main_output)
    assert w.mode_return.isChecked() and w.disc.chosen.path == r2.sidecar_path
    select(qtbot, w, w.cur_pick, de1)
    w.slot_combo.setCurrentText("01")
    assert convert(qtbot, w) is True
    r3 = w.last_result
    assert U.rd(r3.main_output) == U.rd(de1)
    cli3 = os.path.join(tmpdir_, "cli3")
    assert xcconv.main(["wii-to-de", "--wii", r2.main_output, "--sidecar", r2.sidecar_path, "--current-de", de1,
                        "--out", cli3, "--slot", "01"]) == 0
    assert files_of(r3.out_dir) == files_of(cli3)
    assert U.rd(src) == U.rd(W01)                                      # input untouched


def test_de_native_export_matches_cli(make_win, qtbot, tmpdir_):
    de = copy(DE_USER, os.path.join(tmpdir_, "input"))
    base = copy(W03, os.path.join(tmpdir_, "base"))
    w = make_win()
    select(qtbot, w, w.src_pick, de)
    assert w.mode_first.isChecked()
    select(qtbot, w, w.tpl_pick, base)
    assert w.tpl_status.kind == "ok"
    assert convert(qtbot, w) is True
    cli = os.path.join(tmpdir_, "cli")
    assert xcconv.main(["de-to-wii", "--de", de, "--base", base, "--out", cli]) == 0
    assert files_of(w.last_result.out_dir) == files_of(cli)
    assert "Note:" in w.result.body.text()            # the base-chapter warning is shown


def test_check_only_writes_nothing(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    w.opt_dry.setChecked(True)
    assert convert(qtbot, w) is True
    assert w.last_result.dry_run
    assert not os.path.exists(os.path.join(tmpdir_, "out"))
    assert w.stages.state("write") == "skipped" and w.stages.state("verify") == "done"
    assert not w.result_buttons.isVisible()


def test_stale_sidecar_needs_deliberate_choice_and_is_still_refused(make_win, qtbot, tmpdir_):
    out = os.path.join(tmpdir_, "out")
    g1 = os.path.join(out, "g1")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=g1))
    de1 = os.path.join(g1, "save_0", "bfsgame00.sav")
    g2 = os.path.join(out, "g2")
    svc.de_to_wii_convert(svc.DeToWiiRequest(de=de1, sidecar=os.path.join(g1, "wii_to_de.sidecar.json"),
                                             current_wii=W01, out=g2))
    m = U.Wii(U.rd(os.path.join(g2, "monado01")))
    m.play(1800)
    m.level_up(1)
    w2p = os.path.join(tmpdir_, "w2_played")
    with open(w2p, "wb") as f:
        f.write(m.done())
    g3 = os.path.join(out, "g3")
    svc.wii_to_de(svc.WiiToDeRequest(wii=w2p, sidecar=os.path.join(g2, "de_to_wii.sidecar.json"),
                                     current_de=de1, out=g3))
    w = make_win()
    select(qtbot, w, w.src_pick, de1)                     # the OLD DE save
    assert w.disc.chosen is None
    assert w.mode_return.isChecked()
    assert w.disc_status.title.text() == "Choose the preservation file"
    assert w.sc_pick.path() == ""
    assert not w.convert_btn.isEnabled()
    i = next(i for i in range(w.sc_combo.count()) if w.sc_combo.itemData(i) and
             os.path.dirname(w.sc_combo.itemData(i).path) == g1)
    w.sc_combo.setCurrentIndex(i)
    idle(qtbot, w)
    assert w.sc_status.title.text() == "A newer preservation file of this save history exists"
    select(qtbot, w, w.cur_pick, w2p)
    assert convert(qtbot, w) is False
    assert w.result.kind == "error"
    assert "Nothing was written" in w.result.body.text()
    assert not [n for n in os.listdir(out) if n.startswith("de_to_wii_")]


def test_transaction_failure_leaves_nothing(make_win, qtbot, tmpdir_, monkeypatch):
    def boom(stage, detail):
        if stage == "rename":
            raise OSError("simulated failure while installing the output folder")
    monkeypatch.setattr(safeio, "_FAULT", boom)
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    assert convert(qtbot, w) is False
    out = os.path.join(tmpdir_, "out")
    assert not os.path.isdir(out) or os.listdir(out) == []
    assert w.stages.state("write") == "failed"
    assert w.result.title.text() == "Unexpected problem"
    assert "Traceback" not in w.result.body.text() + w.result.detail.text()
    assert w.convert_btn.isEnabled()                       # the user can try again


def test_repeated_clicks_start_one_conversion(make_win, qtbot, tmpdir_, monkeypatch):
    calls = []
    real = svc.convert_request

    def counted(req, progress=None):
        calls.append(req.out)
        return real(req, progress)
    monkeypatch.setattr(svc, "convert_request", counted)
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    with qtbot.waitSignal(w.conversion_finished, timeout=180000):
        for _ in range(5):
            w.convert_btn.click()                          # programmatic clicks bypass the disabled state check
            w.start_conversion()
            QTest.keyClick(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    idle(qtbot, w)
    assert len(calls) == 1
    assert len(os.listdir(os.path.join(tmpdir_, "out"))) == 1


def test_background_worker_error(make_win, qtbot, monkeypatch):
    def broken(req, progress=None):
        progress("read")
        raise RuntimeError("worker exploded")
    monkeypatch.setattr(svc, "convert_request", broken)
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    assert convert(qtbot, w) is False
    assert w.result.title.text() == "Unexpected problem"
    assert "RuntimeError: worker exploded" in w.result.detail.text()
    assert "Traceback" not in w.result.body.text()
    diag = json.loads(w.diagnostics())
    assert "worker exploded" in diag["last_error"]["traceback"]
    assert w.convert_btn.isEnabled() and not w.running


def test_close_is_refused_while_converting(make_win, qtbot, monkeypatch):
    gate = threading.Event()
    real = svc.convert_request

    def slow(req, progress=None):
        gate.wait(60)
        return real(req, progress)
    monkeypatch.setattr(svc, "convert_request", slow)
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a))
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    w.convert_btn.click()
    qtbot.waitUntil(lambda: w.running)
    w.close()
    assert w.isVisible() and shown
    for widget in (w.src_pick, w.tpl_pick, w.out_pick, w.dir_d2w):
        assert not widget.isEnabled()                      # inputs are locked while the job runs
    gate.set()
    idle(qtbot, w)
    assert w.result.kind == "ok"
    w.close()
    assert not w.isVisible()


# ------------------------------------------------------------------------------------------------- keyboard, a11y
def test_keyboard_only_conversion(make_win, qtbot, tmpdir_):
    w = make_win()
    w.activateWindow()
    w.src_pick.edit.setFocus()
    QTest.keyClicks(w.src_pick.edit, W01)
    QTest.keyClick(w.src_pick.edit, Qt.Key.Key_Tab)              # leaving the field confirms it
    idle(qtbot, w)
    assert w.src and w.src["story"] == 150
    w.tpl_pick.edit.setFocus()
    QTest.keyClicks(w.tpl_pick.edit, U.TPL)
    QTest.keyClick(w.tpl_pick.edit, Qt.Key.Key_Return)
    idle(qtbot, w)
    assert w.convert_btn.isEnabled()
    with qtbot.waitSignal(w.conversion_finished, timeout=180000) as sig:
        QTest.keyClick(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    idle(qtbot, w)
    assert sig.args[0] is True


def test_tab_order_reaches_every_control(make_win, qtbot):
    w = make_win()
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    w.activateWindow()
    w.dir_w2d.setFocus()
    seen = set()
    for _ in range(80):
        seen.add(QApplication.focusWidget())
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
    for ctl in (w.src_pick.edit, w.src_pick.browse, w.mode_first, w.tpl_pick.edit, w.out_pick.edit, w.slot_combo,
                w.adv_toggle, w.convert_btn):
        assert ctl in seen, ctl.accessibleName() or ctl.objectName() or type(ctl).__name__


def test_mnemonics_and_accessible_names(make_win, qtbot):
    w = make_win()
    w.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is w, timeout=5000)
    QTest.keyClick(w, Qt.Key.Key_D, Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(w.dir_d2w.isChecked, timeout=2000)      # mnemonics use animateClick (a short timer)
    QTest.keyClick(w, Qt.Key.Key_W, Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(w.dir_w2d.isChecked, timeout=2000)
    QTest.keyClick(w, Qt.Key.Key_A, Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(lambda: w.tabs.currentIndex() == 1, timeout=2000)
    QTest.keyClick(w, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(lambda: w.tabs.currentIndex() == 0, timeout=2000)
    for ctl in (w.src_pick.edit, w.src_pick.browse, w.tpl_pick.edit, w.sc_pick.edit, w.cur_pick.edit,
                w.out_pick.edit, w.slot_combo, w.sc_combo, w.result_path):
        assert ctl.accessibleName(), ctl


def _mnemonics(win):
    import re
    from PySide6.QtWidgets import QAbstractButton, QLabel
    keys = []
    for i in range(win.tabs.count()):
        m = re.search(r"&(\w)", win.tabs.tabText(i))
        keys.append((m.group(1).lower(), f"tab {i}"))
    for wd in win.findChildren(QAbstractButton) + [x for x in win.findChildren(QLabel) if x.buddy()]:
        if wd.isVisible():
            m = re.search(r"&([^&\s])", wd.text())
            if m:
                keys.append((m.group(1).lower(), wd.text()))
    return keys


@pytest.mark.parametrize("direction", ["w2d", "d2w"])
def test_no_duplicate_mnemonics(make_win, qtbot, direction):
    """Each Alt+letter on screen does one thing (an ambiguous mnemonic only cycles focus)."""
    from collections import Counter
    w = make_win()
    (w.dir_w2d if direction == "w2d" else w.dir_d2w).setChecked(True)
    w.adv_toggle.setChecked(True)
    for mode in (w.mode_first, w.mode_return):
        mode.setChecked(True)
        for tab in range(w.tabs.count()):
            w.tabs.setCurrentIndex(tab)
            subs = [w.adv_tabs] if tab == 1 else [None]
            for sub in subs:
                for j in range(sub.count() if sub else 1):
                    if sub:
                        sub.setCurrentIndex(j)
                    qtbot.wait(5)
                    keys = _mnemonics(w)
                    dup = [k for k, n in Counter(k for k, _ in keys).items() if n > 1]
                    assert not dup, [(k, t) for k, t in keys if k in dup]


# ------------------------------------------------------------------------------------------------- advanced, misc
def test_advanced_tools(make_win, qtbot, tmpdir_):
    w = make_win()
    w.ins_pick.set_path(W01)
    w._adv_run("inspect")
    idle(qtbot, w)
    assert json.loads(w.ins_out.toPlainText())["story"] == 150
    w._adv_run("validate")
    idle(qtbot, w)
    assert json.loads(w.ins_out.toPlainText())["ok"] is True
    w.rt_src.set_path(W01)
    w.rt_other.set_path(U.TPL)
    w._adv_run("roundtrip")
    idle(qtbot, w)
    assert json.loads(w.rt_out.toPlainText())["route"] == "wii -> de -> wii"
    out = os.path.join(tmpdir_, "sc")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=out))
    w.sc_info_pick.set_path(os.path.join(out, "wii_to_de.sidecar.json"))
    w._adv_run("sidecar")
    idle(qtbot, w)
    assert json.loads(w.sc_info_out.toPlainText())["direction"] == "wii_to_de"
    w.cc_de.set_path(DE_USER)
    w.cc_base.set_path(W03)
    w._adv_run("compat")
    idle(qtbot, w)
    assert "capacity_check" in json.loads(w.cc_out.toPlainText())
    w.ins_pick.set_path(os.path.join(tmpdir_, "missing.sav"))
    w._adv_run("inspect")
    idle(qtbot, w)
    assert w.ins_out.toPlainText().startswith("File not found")
    diag = json.loads(w.diagnostics())
    assert diag["converter"] == "2G-rc1" and diag["game_data"]
    w.copy_diagnostics()
    assert json.loads(QApplication.clipboard().text())["app"].startswith("XC Save Converter")


def test_plain_language_messages():
    f = messages.explain(svc.Refused("party member(s) [8] are not supported (character 8 is Fiora's second form)"))
    assert "temporary character form" in f.text
    f = messages.explain(svc.Refused("the DE save does not continue the exported one: story went back"))
    assert f.text.startswith("The selected preservation file belongs to a different save history. Conversion has "
                             "been stopped to protect your progress.")
    f = messages.explain(KeyError("x"))
    assert f.kind == "internal" and "Nothing was written" in f.text
    for _, title, text in messages.RULES:
        assert "--" not in text and "Traceback" not in text, title


def test_theme_switch_recolours(make_win, qtbot):
    w = make_win()
    select(qtbot, w, w.src_pick, os.path.join(U.ROOT, "nope.sav"))
    assert w.src_status.kind == "error"
    hints = QApplication.styleHints()
    before = hints.colorScheme()
    try:
        for scheme in (Qt.ColorScheme.Dark, Qt.ColorScheme.Light):
            hints.setColorScheme(scheme)
            qtbot.wait(100)
            assert w.src_status.title.styleSheet() == f"color: {tone(w.src_status, 'error')};"
    finally:
        hints.setColorScheme(before)


@pytest.mark.parametrize("size", [(560, 460), (800, 600), (1920, 1080)])
def test_window_sizes_no_horizontal_scroll(make_win, qtbot, size):
    w = make_win(size=size)
    select(qtbot, w, w.src_pick, W01)
    select(qtbot, w, w.tpl_pick, U.TPL)
    qtbot.wait(50)
    sa = w.tabs.widget(0)
    assert not sa.horizontalScrollBar().isVisible() or sa.horizontalScrollBar().maximum() == 0
