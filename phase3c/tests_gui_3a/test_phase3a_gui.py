"""Phase 3A GUI tests (pytest-qt): New 3DS saves in the three-step window.

  python -m pytest phase3a/tests_gui -v       (the 2H GUI tests in this folder run against the 3A window too)
"""
import os
import shutil

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

import xc3d
import xc3dservice as s3
import xcservice as svc2
from conftest import ROOT, idle

P3 = os.path.join(ROOT, "phase3a")
X3 = os.path.join(P3, "originals", "azahar_live", "00000001", "monado01")
X3_EMPTY = os.path.join(P3, "originals", "azahar_live", "00000001", "monado02")
X3_PLAYED = os.path.join(P3, "runs", "azahar", "a2_s150_gameplay", "save_after", "00000001", "monado02")
W150 = os.path.join(P3, "fixtures", "wii_user_s150.bin")
DE = os.path.join(ROOT, "work", "template", "bfsgame00.sav")


def copy(src, d, name):
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    shutil.copyfile(src, p)
    return p


def select(qtbot, w, picker, path):
    picker.set_path(path)
    idle(qtbot, w)


def convert(qtbot, w):
    assert w.convert_btn.isEnabled(), w.missing()
    with qtbot.waitSignal(w.conversion_finished, timeout=300000) as sig:
        qtbot.mouseClick(w.convert_btn, Qt.MouseButton.LeftButton)
    idle(qtbot, w)
    return sig.args[0]


def test_3a_01_3ds_source_preview_and_target_choice(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, copy(X3, os.path.join(tmpdir_, "x"), "monado01"))
    assert w.src["game"] == "3ds"
    assert w.src_info.text().startswith("New 3DS  ·  Colony 9  ·  0:12:09  ·  Shulk Lv 2")
    assert w.target_row.isVisible()
    assert [w.target_combo.itemData(i) for i in range(w.target_combo.count())] == ["wii", "de"]
    assert w.direction() == "3ds_to_wii"
    assert w.dest_pick.edit.placeholderText() == "Choose a Wii save"
    w.set_target("de")
    idle(qtbot, w)
    assert w.direction() == "3ds_to_de"
    assert w.dest_pick.edit.placeholderText() == "Choose a Definitive Edition save"
    assert w.slot_combo.currentText().startswith("bfsgame")


def test_3a_02_destination_save_decides_target(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, W150)
    assert w.direction() == "wii_to_de"                       # 2H default while step 2 is empty
    select(qtbot, w, w.dest_pick, copy(X3, os.path.join(tmpdir_, "dst"), "monado01"))
    assert w.direction() == "wii_to_3ds"
    assert not w.target_row.isVisible()                       # no selector once a destination save decides
    assert w.slot_combo.currentText() == "monado02"           # monado01 exists next to the destination save
    assert w.dest_title.text().endswith("(New 3DS)")


def test_3a_03_empty_and_damaged_3ds(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, X3_EMPTY)
    assert w.src_notice.title.text() == "Empty 3DS save slot"
    raw = bytearray(xc3d.unpack(open(X3, "rb").read()))
    raw[0xB300] ^= 1
    bad = os.path.join(tmpdir_, "bad", "monado01")
    os.makedirs(os.path.dirname(bad))
    with open(bad, "wb") as f:
        f.write(xc3d.pack(bytes(raw)))
    select(qtbot, w, w.src_pick, bad)
    assert not w.convert_btn.isEnabled()
    assert "damaged" in (w.src_notice.title.text() + w.src_notice.body.text() + w.src_notice.detail.text()).lower()


def test_3a_04_3ds_to_wii_without_destination(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, X3_PLAYED)
    assert w.missing() == ""                                  # lossless: no template needed
    assert convert(qtbot, w)
    r = w.last_result
    assert r.direction == "3ds_to_wii" and w.res_game.text() == "Wii"
    assert svc2.validate_bytes(open(r.main_output, "rb").read())["problems"] == []
    assert open(r.main_output, "rb").read() == xc3d.transcode(xc3d.unpack(open(X3_PLAYED, "rb").read()), "wii")


def test_3a_05_wii_to_3ds_and_automatic_return(make_win, qtbot, tmpdir_):
    w = make_win()
    dst = copy(X3, os.path.join(tmpdir_, "sd"), "monado01")          # a complete save archive (3 slot files)
    copy(X3_EMPTY, os.path.join(tmpdir_, "sd"), "monado02")
    copy(X3_EMPTY, os.path.join(tmpdir_, "sd"), "monado03")
    select(qtbot, w, w.src_pick, W150)
    select(qtbot, w, w.dest_pick, dst)
    assert convert(qtbot, w)
    r = w.last_result
    assert "Azahar" in w.res_guide.text() and "Checkpoint" in w.res_guide.text()
    assert os.path.isdir(os.path.join(r.out_dir, "checkpoint"))
    # bring it back: the record in the output parent is found automatically
    w.back_to_form()
    select(qtbot, w, w.src_pick, r.main_output)
    select(qtbot, w, w.dest_pick, copy(W150, os.path.join(tmpdir_, "wiinow"), "monado01"))
    assert w.direction() == "3ds_to_wii"
    assert w.plan and w.plan.mode == "return", w.plan
    assert convert(qtbot, w)
    assert open(w.last_result.main_output, "rb").read() == open(W150, "rb").read()


def test_3a_06_de_to_3ds_and_3ds_to_de(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, DE)
    select(qtbot, w, w.dest_pick, copy(X3, os.path.join(tmpdir_, "sd"), "monado01"))
    assert w.direction() == "de_to_3ds"
    assert convert(qtbot, w)
    out3 = w.last_result.main_output
    w.back_to_form()
    select(qtbot, w, w.src_pick, out3)
    select(qtbot, w, w.dest_pick, copy(DE, os.path.join(tmpdir_, "denow"), "bfsgame00.sav"))
    assert w.direction() == "3ds_to_de" and w.plan.mode == "return", w.plan
    assert convert(qtbot, w)
    assert open(w.last_result.main_output, "rb").read() == open(DE, "rb").read()


def test_3a_07_divergence_needs_choice(make_win, qtbot, tmpdir_):
    w = make_win()
    dst = copy(X3, os.path.join(tmpdir_, "sd"), "monado01")
    select(qtbot, w, w.src_pick, W150)
    select(qtbot, w, w.dest_pick, dst)
    assert convert(qtbot, w)
    rec = w.last_result.sidecar_path
    w.back_to_form()
    # the 3DS copy was played (game-written s150 save) and the Wii save was played too (Dolphin run d6_travel)
    played = copy(X3_PLAYED, os.path.dirname(w.last_result.main_output if w.last_result else rec), "monado03")
    wii_later = os.path.join(ROOT, "work", "phase2e", "dolphin", "d6_travel", "user", "Wii", "title", "00010000",
                             "53583445", "data", "monado01")
    select(qtbot, w, w.src_pick, played)
    select(qtbot, w, w.dest_pick, copy(wii_later, os.path.join(tmpdir_, "wiilater"), "monado01"))
    assert w.direction() == "3ds_to_wii"
    assert not convert(qtbot, w)
    assert "Keep this save's progress" in [b.text().replace("&", "") for b in w.fail_notice.findChildren(type(w.convert_btn).__mro__[1])] \
        or "both games" in w.fail_notice.detail.text()


def test_3a_08_drag_and_drop_3ds(make_win, qtbot, tmpdir_):
    w = make_win()
    p = copy(X3, os.path.join(tmpdir_, "dd"), "monado01")
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(p)])
    args = (Qt.DropAction.CopyAction, md, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w.drop1, QDragEnterEvent(QPoint(10, 10), args[0], md, args[2], args[3]))
    QApplication.sendEvent(w.drop1, QDropEvent(QPoint(10, 10), args[0], md, args[2], args[3]))
    idle(qtbot, w)
    assert w.src_pick.path() == p and w.src["game"] == "3ds"


def test_3a_09_live_3ds_folder_refused_as_output(make_win, qtbot, tmpdir_):
    w = make_win()
    select(qtbot, w, w.src_pick, W150)
    select(qtbot, w, w.dest_pick, copy(X3, os.path.join(tmpdir_, "sd"), "monado01"))
    live = os.path.join(tmpdir_, "Nintendo 3DS", "title", "00040000", "0f700100", "data")
    os.makedirs(live)
    w.out_pick.set_path(live)
    idle(qtbot, w)
    assert w.out_notice.kind == "error"
    assert not w.convert_btn.isEnabled()
