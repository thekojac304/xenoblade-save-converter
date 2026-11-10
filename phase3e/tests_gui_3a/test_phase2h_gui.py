"""Phase 2H GUI tests (pytest-qt): the simplified three-step window driven like a user, on copied or synthetic saves.

Run from the research folder:  python -m pytest tests_gui -v
Every conversion is compared with the CLI (2G engine, same inputs) and, for first conversions, with the frozen 2F-rc1
code (phase2g/baseline_2F). Outputs go to work/test_phase2h/gui/<test>; original saves are only read.
"""
import json
import os
import shutil
import subprocess
import sys
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
from xcgui import main_window as mw
from xcgui import messages
from xcgui.widgets import tone

W01 = os.path.join(U.O, "monado01")
W02 = os.path.join(U.O, "monado02")
W03 = os.path.join(U.O, "monado03")
DE_USER = os.path.join(U.O, "user_v10_bfsgame00.sav")
DE_USER_A = os.path.join(U.O, "user_v10_bfsgame00a.sav")
DE_V7 = os.path.join(U.PUBLIC, "s206_207aed635e_bfsgame01.sav")
BASE_2F = os.path.join(ROOT, "phase2g", "baseline_2F", "tools", "xcconv.py")


def copy(src, d, name=None):
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name or os.path.basename(src))
    shutil.copyfile(src, p)
    return p


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


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


def fill(qtbot, w, src, dest=None):
    select(qtbot, w, w.src_pick, src)
    if dest:
        select(qtbot, w, w.dest_pick, dest)


def convert(qtbot, w):
    assert w.convert_btn.isEnabled(), w.missing()
    with qtbot.waitSignal(w.conversion_finished, timeout=180000) as sig:
        qtbot.mouseClick(w.convert_btn, Qt.MouseButton.LeftButton)
    idle(qtbot, w)
    return sig.args[0]


def cli(*args):
    assert xcconv.main(list(args)) == 0


def baseline_2f(*args):
    r = subprocess.run([sys.executable, BASE_2F, *args], capture_output=True, text=True,
                       env={**os.environ, "XCCONV_DATA": DATA, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, r.stderr


def same_as_2f(gui_dir, base_dir):
    """Saves and companion files byte-identical; sidecar identical apart from the converter version."""
    a, b = files_of(gui_dir), files_of(base_dir)
    assert set(a) == set(b)
    for rel in a:
        if rel.endswith(".sidecar.json"):
            x, y = json.loads(a[rel]), json.loads(b[rel])
            for d in (x, y):
                d.pop("integrity")
                d.pop("converter_version")
            assert x == y, rel
        elif rel != "manifest.json":
            assert a[rel] == b[rel], rel


def accept_question(monkeypatch, answers):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: answers.append(a[1]) or QMessageBox.StandardButton.Yes)


def pick_in_dialog(monkeypatch, match):
    """Make the 'choose the earlier conversion' dialog select the entry whose folder name contains `match`."""
    seen = []

    def exec_(self):
        seen.append([self.list.item(i).text() for i in range(self.list.count())])
        for i in range(self.list.count()):
            if match in self.list.item(i).data(Qt.ItemDataRole.UserRole):
                self.list.setCurrentRow(i)
        self.accept()
        return 1
    monkeypatch.setattr(mw.ChooseRecordDialog, "exec", exec_)
    return seen


# ================================================================================================= 1-3 conversions
def test_01_first_wii_to_de_matches_cli_and_2f(make_win, qtbot, tmpdir_):
    src = copy(W01, os.path.join(tmpdir_, "in"))
    tpl = copy(U.TPL, os.path.join(tmpdir_, "game_de"), "bfsgame00.sav")
    w = make_win()
    fill(qtbot, w, src, tpl)
    assert w.plan.mode == "first"
    assert w.dest_hint.text() == "Used as a starting template. Your existing save won't be changed."
    assert w.slot_combo.currentText() == "bfsgame01.sav"          # 00 is used next to the destination save
    assert convert(qtbot, w)
    r = w.last_result
    assert w.stack.currentIndex() == 1 and w.res_title.text() == "Conversion complete"
    assert w.res_game.text() == "Definitive Edition" and w.res_file.text() == os.path.join("save_0", "bfsgame01.sav")
    assert w.res_folder.text() == r.out_dir and w.open_btn.isVisible()
    cli("wii-to-de", "--wii", src, "--template", tpl, "--out", os.path.join(tmpdir_, "cli"), "--slot", "01")
    assert files_of(r.out_dir) == files_of(os.path.join(tmpdir_, "cli"))
    baseline_2f("wii-to-de", "--wii", src, "--template", tpl, "--out", os.path.join(tmpdir_, "f2"), "--slot", "01")
    same_as_2f(r.out_dir, os.path.join(tmpdir_, "f2"))
    assert svc.sha(U.rd(r.main_output)).startswith("1028f718")
    assert U.rd(src) == U.rd(W01) and U.rd(tpl) == U.rd(U.TPL)


def test_02_first_de_to_wii_matches_cli_and_2f(make_win, qtbot, tmpdir_):
    de = copy(DE_USER, os.path.join(tmpdir_, "in"))
    base = copy(W03, os.path.join(tmpdir_, "game_wii"), "monado01")
    w = make_win()
    fill(qtbot, w, de, base)
    assert w.plan.mode == "first" and w.slot_combo.currentText() == "monado02"
    assert convert(qtbot, w)
    r = w.last_result
    assert "later story point" in w.res_warn.body.text()           # engine warning shown on the result screen
    cli("de-to-wii", "--de", de, "--base", base, "--out", os.path.join(tmpdir_, "cli"), "--slot", "monado02")
    assert files_of(r.out_dir) == files_of(os.path.join(tmpdir_, "cli"))
    baseline_2f("de-to-wii", "--de", de, "--base", base, "--out", os.path.join(tmpdir_, "f2"), "--slot", "monado02")
    same_as_2f(r.out_dir, os.path.join(tmpdir_, "f2"))


def test_03_automatic_return_trips(make_win, qtbot, tmpdir_):
    """Wii -> DE, back to the Wii, back to DE: the history is found without the user seeing it."""
    src = copy(W01, os.path.join(tmpdir_, "wii"))
    w = make_win()
    fill(qtbot, w, src, U.TPL)
    assert convert(qtbot, w)
    r1 = w.last_result
    qtbot.mouseClick(w.again_btn, Qt.MouseButton.LeftButton)
    assert w.stack.currentIndex() == 0 and w.src_pick.path() == ""
    fill(qtbot, w, r1.main_output, src)
    assert w.plan.mode == "return" and w.plan.sidecar == r1.sidecar_path
    assert w.dest_notice.body.text().startswith("Continuing your conversion of")
    assert "latest Wii save" in w.dest_hint.text()
    assert convert(qtbot, w)
    r2 = w.last_result
    cli("de-to-wii", "--de", r1.main_output, "--sidecar", r1.sidecar_path, "--current-wii", src,
        "--slot", w.slot(), "--out", os.path.join(tmpdir_, "cli2"))
    assert files_of(r2.out_dir) == files_of(os.path.join(tmpdir_, "cli2"))
    w.back_to_form()
    fill(qtbot, w, r2.main_output, r1.main_output)
    assert w.plan.mode == "return" and w.plan.sidecar == r2.sidecar_path
    assert convert(qtbot, w)
    r3 = w.last_result
    assert U.rd(r3.main_output) == U.rd(r1.main_output)               # unchanged Wii save: DE save restored exactly
    cli("wii-to-de", "--wii", r2.main_output, "--sidecar", r2.sidecar_path, "--current-de", r1.main_output,
        "--slot", w.slot(), "--out", os.path.join(tmpdir_, "cli3"))
    assert files_of(r3.out_dir) == files_of(os.path.join(tmpdir_, "cli3"))


# ================================================================================================= 4-7 history issues
def test_04_missing_history_same_playthrough(make_win, qtbot, tmpdir_, monkeypatch):
    first = os.path.join(tmpdir_, "elsewhere", "first")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=first))
    de_copy = copy(os.path.join(first, "save_0", "bfsgame00.sav"), os.path.join(tmpdir_, "game_de"), "bfsgame04.sav")
    w = make_win()
    fill(qtbot, w, W01, de_copy)
    assert w.plan.issue == "same-playthrough"
    assert w.dest_notice.title.text() == "No record of your last conversion was found"
    assert [b.text() for b in w.dest_notice.buttons] == ["Find record…", "Start fresh…"]
    assert not w.convert_btn.isEnabled() and w.next_label.text() == "See the message in step 2."
    monkeypatch.setattr(mw.QFileDialog, "getOpenFileName",
                        lambda *a, **k: (os.path.join(first, "wii_to_de.sidecar.json"), ""))
    w.dest_notice.buttons[0].click()                                      # Find record…
    idle(qtbot, w)
    assert w.plan.issue == "chosen-invalid"                               # a Wii -> DE record cannot continue a Wii save
    answers = []
    accept_question(monkeypatch, answers)
    w.clear_record_choice()
    idle(qtbot, w)
    w.dest_notice.buttons[1].click()                                      # Start fresh… (confirmed)
    idle(qtbot, w)
    assert answers and w.plan.mode == "first" and w.convert_btn.isEnabled()


def test_05_stale_history_not_chosen_and_still_refused(make_win, qtbot, tmpdir_, monkeypatch):
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
    w2p = write(os.path.join(tmpdir_, "game_wii", "monado01"), m.done())
    svc.wii_to_de(svc.WiiToDeRequest(wii=w2p, sidecar=os.path.join(g2, "de_to_wii.sidecar.json"), current_de=de1,
                                     out=os.path.join(out, "g3")))
    w = make_win()
    fill(qtbot, w, de1, w2p)                                              # the OLD DE save
    assert w.plan.issue == "older" and w.plan.sidecar is None
    assert w.dest_notice.title.text() == "This save matches an older conversion"
    assert not w.convert_btn.isEnabled()
    seen = pick_in_dialog(monkeypatch, "g1")
    w.dest_notice.buttons[0].click()
    idle(qtbot, w)
    assert "older" in " ".join(seen[0])
    assert w.plan.mode == "return" and w.convert_btn.isEnabled()          # deliberate choice; the engine decides
    before = sorted(os.listdir(out))
    assert convert(qtbot, w) is False
    assert "Nothing was written" in w.fail_notice.body.text()
    assert sorted(os.listdir(out)) == before


def test_06_ambiguous_histories_ask(make_win, qtbot, tmpdir_, monkeypatch):
    out = os.path.join(tmpdir_, "out")
    a, b = os.path.join(out, "a"), os.path.join(out, "b")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=DE_USER, out=a))
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=DE_USER_A, out=b))
    w = make_win()
    fill(qtbot, w, os.path.join(a, "save_0", "bfsgame00.sav"), W01)
    assert w.plan.issue == "choose" and len(w.plan.choices) == 2
    assert w.dest_notice.title.text() == "More than one earlier conversion matches this save"
    assert not w.convert_btn.isEnabled()
    seen = pick_in_dialog(monkeypatch, os.sep + "a" + os.sep)
    w.dest_notice.buttons[0].click()
    idle(qtbot, w)
    assert len(seen[0]) == 2
    assert w.plan.mode == "return" and w.plan.sidecar == os.path.join(a, "wii_to_de.sidecar.json")
    assert convert(qtbot, w)
    cli("de-to-wii", "--de", os.path.join(a, "save_0", "bfsgame00.sav"), "--sidecar", w.plan.sidecar,
        "--current-wii", W01, "--slot", w.slot(), "--out", os.path.join(tmpdir_, "cli"))
    assert files_of(w.last_result.out_dir) == files_of(os.path.join(tmpdir_, "cli"))


def test_07_divergent_histories_need_explicit_choice(make_win, qtbot, tmpdir_, monkeypatch):
    out = os.path.join(tmpdir_, "out")
    g1 = os.path.join(out, "g1")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=g1))
    d = U.DE(U.rd(os.path.join(g1, "save_0", "bfsgame00.sav")))
    d.play(3600)
    d.money(500)
    de_played = write(os.path.join(tmpdir_, "game_de", "bfsgame00.sav"), d.done())
    m = U.Wii(U.rd(W01))
    m.play(1200)
    m.level_up(2)
    wii_played = write(os.path.join(tmpdir_, "game_wii", "monado01"), m.done())
    w = make_win()
    fill(qtbot, w, de_played, wii_played)
    assert w.plan.mode == "return" and w.plan.dest_relation == "continues"
    assert convert(qtbot, w) is False
    assert w.fail_notice.title.text() == "Both games have new progress"
    assert [b.text() for b in w.fail_notice.buttons] == ["Keep this save's progress…"]
    assert os.listdir(out) == ["g1"]                                       # the refusal wrote nothing
    answers = []
    accept_question(monkeypatch, answers)
    with qtbot.waitSignal(w.conversion_finished, timeout=180000) as sig:
        w.fail_notice.buttons[0].click()
    idle(qtbot, w)
    assert answers and sig.args[0] is True and not w.branch                 # one conversion only
    cli("de-to-wii", "--de", de_played, "--sidecar", os.path.join(g1, "wii_to_de.sidecar.json"),
        "--current-wii", wii_played, "--branch", "de", "--slot", w.slot(), "--out", os.path.join(tmpdir_, "cli"))
    assert files_of(w.last_result.out_dir) == files_of(os.path.join(tmpdir_, "cli"))


# ================================================================================================= 8-10 inputs
def test_08_missing_destination_save(make_win, qtbot):
    w = make_win()
    assert not w.dest_pick.isEnabled() and w.dest_pick.edit.placeholderText() == "Choose your save in step 1 first"
    select(qtbot, w, w.src_pick, W01)
    assert w.dest_pick.isEnabled()
    assert w.dest_pick.edit.placeholderText() == "Choose a Definitive Edition save"
    assert not w.convert_btn.isEnabled()
    assert w.next_label.text() == "Choose a Definitive Edition save in step 2."
    select(qtbot, w, w.dest_pick, W03)                                    # wrong game
    assert w.dest_notice.title.text() == "This is not a Definitive Edition save."
    select(qtbot, w, w.dest_pick, W01)                                    # the same file as step 1
    assert w.dest_notice.title.text() == "This is the save from step 1"
    assert not w.convert_btn.isEnabled()


@pytest.mark.parametrize("case", ["junk", "record", "empty_slot", "v7_destination", "fiora"])
def test_09_unsupported_inputs(make_win, qtbot, tmpdir_, case):
    w = make_win()
    if case == "junk":
        select(qtbot, w, w.src_pick, write(os.path.join(tmpdir_, "junk.sav"), b"x" * 5000))
        assert w.src_notice.title.text() == "Not a Xenoblade Chronicles save"
    elif case == "record":
        out = os.path.join(tmpdir_, "sc")
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=out))
        select(qtbot, w, w.src_pick, os.path.join(out, "wii_to_de.sidecar.json"))
        assert w.src_notice.title.text() == "This is a conversion record, not a save"
    elif case == "empty_slot":
        if svc.detect(W02)["kind"] != "wii-empty":
            pytest.skip("monado02 is not empty here")
        select(qtbot, w, w.src_pick, W02)
        assert w.src_notice.title.text() == "Empty Wii save slot"
    elif case == "v7_destination":
        if not os.path.exists(DE_V7):
            pytest.skip("public v7 save not present")
        fill(qtbot, w, W01, DE_V7)
        assert w.dest_notice.title.text() == "Older Definitive Edition save"
    else:
        m = U.Wii(U.rd(W01))
        ir = wii_save.decode_bytes(m.b)
        m.img.put(wii_save.PARTY + 4 * len(ir["party"]), "H", 8)
        fill(qtbot, w, write(os.path.join(tmpdir_, "monado01"), m.done()), U.TPL)
        assert "temporary character form" in w.src_notice.body.text()
    assert not w.convert_btn.isEnabled()


def test_10_safe_output_slot(make_win, qtbot, tmpdir_):
    game = os.path.join(tmpdir_, "game_de")
    for n in ("bfsgame00.sav", "bfsgame01.sav", "bfsgame02.sav"):
        copy(U.TPL, game, n)
    w = make_win()
    fill(qtbot, w, W01, os.path.join(game, "bfsgame00.sav"))
    assert w.slot_combo.currentText() == "bfsgame03.sav"
    assert w.slot_note.text() == "Not used in your save folder."
    w.slot_combo.setCurrentText("bfsgame01.sav")
    assert w.slot_note.text().startswith("Your save folder already has this name")
    w.slot_combo.setCurrentText("bfsgame03.sav")
    w.out_pick.set_path(r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save")
    assert w.out_notice.title.text() == "Output inside a game or save folder" and not w.convert_btn.isEnabled()
    w.out_pick.set_path(os.path.join(tmpdir_, "out"))
    assert convert(qtbot, w)
    assert w.last_result.main_output.endswith(os.path.join("save_0", "bfsgame03.sav"))
    assert sorted(os.listdir(game)) == ["bfsgame00.sav", "bfsgame01.sav", "bfsgame02.sav"]      # untouched
    first = w.last_result.out_dir
    w.back_to_form()
    fill(qtbot, w, W01, os.path.join(game, "bfsgame00.sav"))
    assert convert(qtbot, w)
    assert w.last_result.out_dir != first and os.path.isdir(first)         # a new folder each time


# ================================================================================================= 11 failures
def test_11_transaction_failure_leaves_nothing(make_win, qtbot, tmpdir_, monkeypatch):
    def boom(stage, detail):
        if stage == "rename":
            raise OSError("simulated failure while installing the output folder")
    monkeypatch.setattr(safeio, "_FAULT", boom)
    w = make_win()
    fill(qtbot, w, W01, U.TPL)
    assert convert(qtbot, w) is False
    out = os.path.join(tmpdir_, "out")
    assert not os.path.isdir(out) or os.listdir(out) == []
    assert w.fail_notice.title.text() == "Unexpected problem" and "Nothing was written" in w.fail_notice.body.text()
    assert "Traceback" not in w.fail_notice.body.text() + w.fail_notice.detail.text()
    assert w.stack.currentIndex() == 0 and w.convert_btn.isEnabled()


def test_11b_worker_error_repeated_clicks_and_close(make_win, qtbot, monkeypatch):
    calls = []
    gate = threading.Event()

    def slow_broken(req, progress=None):
        calls.append(req.out)
        progress("read")
        gate.wait(60)
        raise RuntimeError("worker exploded")
    monkeypatch.setattr(svc, "convert_request", slow_broken)
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a))
    w = make_win()
    fill(qtbot, w, W01, U.TPL)
    for _ in range(4):
        w.convert_btn.click()
        w.start_conversion()
        QTest.keyClick(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: w.next_label.text() == "Reading saves…")
    assert w.convert_btn.text() == "Converting…" and not w.src_pick.isEnabled()
    w.close()
    assert w.isVisible() and shown                                      # closing waits for the conversion
    gate.set()
    idle(qtbot, w)
    assert len(calls) == 1
    assert w.fail_notice.title.text() == "Unexpected problem"
    assert "worker exploded" in json.loads(w.diagnostics())["last_error"]["traceback"]
    w.close()
    assert not w.isVisible()


# ================================================================================================= 12-13 input methods
def test_12_keyboard_only(make_win, qtbot, tmpdir_):
    w = make_win()
    w.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is w, timeout=5000)
    QTest.keyClick(w, Qt.Key.Key_S, Qt.KeyboardModifier.AltModifier)             # Alt+S: "Your save"
    assert QApplication.focusWidget() is w.src_pick.edit
    QTest.keyClicks(w.src_pick.edit, W01)
    QTest.keyClick(w.src_pick.edit, Qt.Key.Key_Tab)
    idle(qtbot, w)
    QTest.keyClick(w, Qt.Key.Key_D, Qt.KeyboardModifier.AltModifier)             # Alt+D: destination save
    assert QApplication.focusWidget() is w.dest_pick.edit
    QTest.keyClicks(w.dest_pick.edit, U.TPL)
    QTest.keyClick(w.dest_pick.edit, Qt.Key.Key_Return)
    idle(qtbot, w)
    seen = set()
    w.src_pick.edit.setFocus()
    for _ in range(30):
        seen.add(QApplication.focusWidget())
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
    for ctl in (w.src_pick.browse, w.dest_pick.edit, w.out_pick.edit, w.slot_combo, w.convert_btn, w.adv_btn):
        assert ctl in seen, ctl.accessibleName() or ctl.text()
    with qtbot.waitSignal(w.conversion_finished, timeout=180000) as sig:
        QTest.keyClick(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    idle(qtbot, w)
    assert sig.args[0] and QApplication.focusWidget() is w.open_btn             # next action has the focus
    for ctl in (w.src_pick.edit, w.dest_pick.edit, w.out_pick.edit, w.slot_combo, w.res_folder):
        assert ctl.accessibleName()


def _drag(widget, path):
    args = (Qt.DropAction.CopyAction,)
    mods = (Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(path)])
    enter = QDragEnterEvent(QPoint(10, 10), *args, md, *mods)
    QApplication.sendEvent(widget, enter)
    QApplication.sendEvent(widget, QDragMoveEvent(QPoint(12, 12), *args, md, *mods))
    QApplication.sendEvent(widget, QDropEvent(QPointF(12, 12), *args, md, *mods))
    return enter.isAccepted()


def test_13_drag_and_drop_both_steps(make_win, qtbot, tmpdir_):
    w = make_win()
    text = QMimeData()
    text.setText("not a file")
    e = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, text, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w.drop1, e)
    assert not e.isAccepted()
    assert _drag(w.drop1, copy(DE_USER, os.path.join(tmpdir_, "in")))
    idle(qtbot, w)
    assert w.direction() == "de_to_wii" and w.src_info.text().startswith("Definitive Edition (v10)")
    assert _drag(w.drop2, copy(W03, os.path.join(tmpdir_, "wii"), "monado01"))
    idle(qtbot, w)
    assert w.dest_info.text().startswith("Wii") and w.plan.mode == "first" and w.convert_btn.isEnabled()
    d = os.path.join(tmpdir_, "folder_with_one_save")
    copy(W01, d)
    assert _drag(w.drop1, d)                                              # a folder with one save
    idle(qtbot, w)
    assert w.src_pick.path() == os.path.join(d, "monado01") and w.direction() == "wii_to_de"
    assert w.dest_notice.title.text() == "This is not a Definitive Edition save."    # step 2 re-checked


# ================================================================================================= 14-15 appearance
def test_14_light_and_dark(make_win, qtbot):
    w = make_win()
    select(qtbot, w, w.src_pick, os.path.join(ROOT, "nope.sav"))
    hints = QApplication.styleHints()
    before = hints.colorScheme()
    try:
        colours = {}
        for scheme in (Qt.ColorScheme.Dark, Qt.ColorScheme.Light):
            hints.setColorScheme(scheme)
            qtbot.wait(150)
            assert w.src_notice.title.styleSheet() == f"color: {tone(w.src_notice, 'error')};"
            colours[scheme] = w.convert_btn.styleSheet()
            pal = w.convert_btn.palette()
            assert pal.color(pal.ColorRole.Highlight).name() in colours[scheme]      # follows the theme's accent
        assert colours[Qt.ColorScheme.Dark] != colours[Qt.ColorScheme.Light]
    finally:
        hints.setColorScheme(before)


@pytest.mark.parametrize("size", [(480, 420), (700, 600), (1920, 1080)])
def test_15_small_and_large_windows(make_win, qtbot, size):
    w = make_win(size=size)
    fill(qtbot, w, W01, U.TPL)
    qtbot.wait(50)
    sa = w.stack.currentWidget()
    assert not sa.horizontalScrollBar().isVisible() or sa.horizontalScrollBar().maximum() == 0
    page = sa.widget()
    assert w.convert_btn.width() <= page.width() and w.convert_btn.isVisible()


@pytest.mark.parametrize("scale", ["1.5", "2"])
def test_15b_high_dpi_start(tmpdir_, scale):
    """A real process at a Qt scale factor: starts, lays out, renders; the capture is kept for review."""
    out = os.path.join(tmpdir_, f"smoke_{scale}.json")
    env = dict(os.environ, QT_SCALE_FACTOR=scale)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gui", "xcconv_gui.py"), "--smoke", out], env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    info = json.load(open(out))
    assert abs(info["dpr"] - float(scale)) < 0.01 and info["visible"]
    assert os.path.getsize(out.replace(".json", ".png")) > 10000


# ================================================================================================= other behaviour
def test_first_run_without_game_data(make_win, qtbot, tmpdir_, monkeypatch):
    monkeypatch.setattr(paths, "FALLBACKS", [])
    monkeypatch.delenv("XCCONV_DATA", raising=False)
    w = make_win(data=False)
    assert w.setup_notice.isVisible() and w.next_label.text() == "Set up the game data first."
    w.setup_notice.buttons[0].click()
    assert w.adv.isVisible() and w.adv.tabs.currentIndex() == 1
    assert not w.set_data_dir(tmpdir_)
    assert w.set_data_dir(DATA)
    idle(qtbot, w)
    assert not w.setup_notice.isVisible()
    w.adv.hide()


def test_main_window_text_is_short_and_plain(make_win, qtbot):
    """No technical terms or instruction paragraphs in the normal workflow."""
    from PySide6.QtWidgets import QLabel, QAbstractButton
    w = make_win()
    fill(qtbot, w, W01, U.TPL)
    texts = [x.text() for x in w.stack.widget(0).findChildren(QLabel) if x.isVisible()] + \
            [x.text() for x in w.stack.widget(0).findChildren(QAbstractButton) if x.isVisible()]
    joined = " ".join(texts).lower()
    for term in ("sidecar", "lineage", "canonical", "transplant", "template transplantation", "json"):
        assert term not in joined, term
    assert max(len(t) for t in texts) < 120
    assert "Original saves are never modified." in texts


def test_advanced_dialog_tools_and_options(make_win, qtbot, tmpdir_):
    w = make_win()
    w.adv_btn.click()
    assert w.adv.isVisible() and w.adv.tabs.currentIndex() == 0
    w.adv.opt_dry.setChecked(True)
    fill(qtbot, w, W01, U.TPL)
    assert convert(qtbot, w)
    assert w.last_result.dry_run and w.res_title.text().startswith("Check complete")
    assert not w.open_btn.isVisible() and not os.path.exists(os.path.join(tmpdir_, "out"))
    w.adv.opt_dry.setChecked(False)
    w.adv.ins_pick.set_path(W01)
    w.adv.run("inspect")
    idle(qtbot, w)
    assert json.loads(w.adv.ins_out.toPlainText())["story"] == 150
    w.adv.run("validate")
    idle(qtbot, w)
    assert json.loads(w.adv.ins_out.toPlainText())["ok"] is True
    w.adv.cc_de.set_path(DE_USER)
    w.adv.cc_base.set_path(W03)
    w.adv.run("compat")
    idle(qtbot, w)
    assert "capacity_check" in json.loads(w.adv.cc_out.toPlainText())
    w.adv.show_tab("diagnostics")
    assert json.loads(w.adv.diag_out.toPlainText())["app"] == "XC Save Converter 3E-rc1"   # 3B..3E: version bump only
    assert "convert:" in w.adv.log_view.toPlainText()
    w.adv.hide()


def test_no_current_destination_option(make_win, qtbot, tmpdir_):
    """Return conversion when the user no longer has a destination save: explicit option, CLI --no-current-wii."""
    g1 = os.path.join(tmpdir_, "out", "g1")
    svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=g1))
    de1 = os.path.join(g1, "save_0", "bfsgame00.sav")
    w = make_win()
    select(qtbot, w, w.src_pick, de1)
    assert w.plan.mode == "return" and w.next_label.text() == "Choose a Wii save in step 2."
    w.adv.opt_no_current.setChecked(True)
    assert w.convert_btn.isEnabled()
    assert convert(qtbot, w)
    cli("de-to-wii", "--de", de1, "--sidecar", os.path.join(g1, "wii_to_de.sidecar.json"), "--no-current-wii",
        "--slot", w.slot(), "--out", os.path.join(tmpdir_, "cli"))
    assert files_of(w.last_result.out_dir) == files_of(os.path.join(tmpdir_, "cli"))


def test_no_duplicate_mnemonics(make_win, qtbot):
    import re
    from collections import Counter
    from PySide6.QtWidgets import QAbstractButton, QLabel
    w = make_win()
    fill(qtbot, w, W01, U.TPL)
    for root in (w, w.adv):
        root.show()
        keys = []
        for wd in root.findChildren(QAbstractButton) + [x for x in root.findChildren(QLabel) if x.buddy()]:
            if wd.isVisible() and wd.window() is root:
                m = re.search(r"&([^&\s])", wd.text())
                if m:
                    keys.append((m.group(1).lower(), wd.text()))
        if root is w.adv:
            for i in range(w.adv.tabs.count()):
                keys.append((re.search(r"&(\w)", w.adv.tabs.tabText(i)).group(1).lower(), w.adv.tabs.tabText(i)))
        dup = [k for k, n in Counter(k for k, _ in keys).items() if n > 1]
        assert not dup, [(k, t) for k, t in keys if k in dup]
    w.adv.hide()


def test_plain_language_messages():
    f = messages.explain(svc.Refused("party member(s) [8] are not supported (character 8 is Fiora's second form)"))
    assert "temporary character form" in f.text
    f = messages.explain(svc.Refused("the DE save does not continue the exported one: story went back"))
    assert f.text.startswith("The selected conversion record belongs to a different save history. Conversion has been stopped to protect your progress.")
    for _, title, text in messages.RULES:
        assert "--" not in text and "Traceback" not in text, title
    # 2H fix: both engine divergence messages are divergence, not "older record" / "different history"
    d2w = ("your current Wii save is not the one this sidecar exported: it changed after the export, and the DE save "
           "also progressed. Either you played on the Wii after exporting (choose --branch de to keep the DE progress "
           "and DISCARD the Wii progress made after the export), or this sidecar is older than your latest conversion "
           "(use the newest sidecar).")
    w2d = ("your current DE save is not the one this sidecar exported: it changed after the export, and the Wii save "
           "also progressed. ... No automatic merge is attempted.")
    for m in (d2w, w2d):
        assert messages.explain(svc.Refused(m)).title == "Both games have new progress"
    assert messages.explain(svc.Refused("this sidecar looks older than your latest Wii -> DE conversion: 90%")).title \
        == "Older conversion record selected"
