"""Phase 3B GUI tests: the Sync Hub tab (setup, automatic startup scan, Scan Again, new progress, conflicts, safe
source selection, disabled Sync, successful Sync, failure recovery, history/rollback, settings persistence,
keyboard operation, light/dark). The 3A converter tab is covered by phase3a/tests_gui (run against phase3b/gui by
test_converter_tab_is_the_3a_window and the separate regression run).

  python -m pytest phase3b/tests_gui -v
"""
import json
import os
import struct

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QRadioButton

import hubfix as H
from conftest import idle
from xcsync import store, sync as syncmod


@pytest.fixture(autouse=True)
def yes(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def started(name, wii=H.W150):
    fx = H.HubFx(name)
    fx.drop("Odin 2 Mini", "monado01", H.rd(wii))
    fx.sync()
    return fx


def test_welcome_and_first_run_setup(make_shell, tdir, qtbot):
    w = make_shell()
    v = w.hub_view
    assert w.tabs.tabText(0) == "&Sync Hub" and w.tabs.currentIndex() == 0
    assert v.stack.currentIndex() == 0                          # welcome page
    assert v.setup_btn.isVisible()
    from xcgui.synchub_view import HubSettingsDialog
    dlg = HubSettingsDialog(v, v, first_run=True)
    assert not dlg.tabs.isTabEnabled(1)                          # devices need a hub first
    dlg.folder.set_path(os.path.join(tdir, "My Sync Hub"))
    dlg._use_folder()
    assert v.hub is not None and dlg.tabs.isTabEnabled(1)
    v.hub.add_device("Odin 2 Mini", "wii")
    v.hub.add_template("de", H.DE_TPL)
    dlg.refresh()
    assert dlg.dev_list.topLevelItemCount() == 1
    assert "story" in dlg.tpl_labels["de"].text()
    dlg.accept()
    assert os.path.isfile(os.path.join(tdir, "My Sync Hub", store.MARKER))


def test_settings_persist_and_startup_scan_runs(make_shell, qtbot, tdir):
    fx = started("gui_persist")
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert v.stack.currentIndex() == 1
    assert v.result is not None                                  # scanned automatically at start
    assert v.status.text() == "All available saves match the last sync."
    assert not v.sync_btn.isEnabled()
    assert w.settings.value("sync_hub_folder") == fx.hub.root


def test_new_progress_shows_source_and_enables_sync(make_shell, qtbot):
    fx = started("gui_new")
    fx.drop("New 3DS", "monado01", H.rd(H.X3_A2))
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert v.status.text() == "New progress found on New 3DS."
    assert v.src_box.isVisible()
    f = {k: lab.text() for k, lab in v.src_fields.items()}
    assert f["device"] == "New 3DS" and f["game"] == "Xenoblade 3D"
    assert "story 150" in f["location"] and f["play_time"] and "Lv" in f["level"]
    assert v.sync_btn.isEnabled()
    # nothing technical in the default view
    texts = " ".join(lab.text() for lab in v.findChildren(type(v.status)) if lab.isVisible())
    assert "sha" not in texts.lower() and "sidecar" not in texts.lower()


def test_scan_again_picks_up_new_files(make_shell, qtbot):
    fx = started("gui_scan_again")
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert not v.sync_btn.isEnabled()
    fx.drop("Odin 2 Mini", "monado02", H.play_wii(H.rd(H.W150), flags=4))
    qtbot.mouseClick(v.scan_btn, Qt.MouseButton.LeftButton)
    idle(qtbot, w)
    assert v.status.text() == "New progress found on Odin 2 Mini."
    assert v.sync_btn.isEnabled()


def test_waiting_disables_sync(make_shell, qtbot):
    fx = started("gui_waiting")
    fx.drop("New 3DS", "monado01", H.rd(H.X3_A2))
    H.put(os.path.join(fx.dev["New 3DS"]["incoming"], "~syncthing~monado01.tmp"), b"x")
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert v.status.text() == "Waiting for a complete save from New 3DS."
    assert not v.sync_btn.isEnabled()


def test_conflict_requires_explicit_choice(make_shell, qtbot):
    fx = started("gui_conflict")
    fx.drop("New 3DS", "monado01", H.rd(H.X3_A2))
    fx.drop("Windows desktop", "bfsgame00.sav", H.play_de(fx.out("de"), flags=4))
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert v.status.text().startswith("Progress was found on both the ")
    assert v.choice_box.isVisible()
    radios = v.choice_box.findChildren(QRadioButton)
    assert len(radios) == 2 and not any(r.isChecked() for r in radios)
    assert not v.sync_btn.isEnabled()                            # no silent pick
    texts = [r.text() for r in radios]
    assert any("Definitive Edition" in t for t in texts) and all("story" in t and "Lv" in t for t in texts)
    radios[[i for i, t in enumerate(texts) if "Xenoblade 3D" in t][0]].click()
    assert v.sync_btn.isEnabled()
    assert v.src_fields["device"].text() == "New 3DS"
    qtbot.mouseClick(v.sync_btn, Qt.MouseButton.LeftButton)
    idle(qtbot, w)
    assert v.stack.currentIndex() == 2
    assert v.res_title.text() == "All configured platforms updated."
    g = fx.hub.current_generation()[1]
    assert any(not s["chosen"] and s["device_name"] == "Windows desktop" for s in g["snapshots"])


def test_successful_sync_result_page_and_back(make_shell, qtbot):
    fx = started("gui_sync")
    fx.drop("Odin 2 Mini", "monado01", H.play_wii(H.rd(H.W150), flags=4))
    w = make_shell(fx.hub.root)
    v = w.hub_view
    stages = []
    v.engine  # noqa
    qtbot.keyClick(v, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)   # keyboard: Ctrl+Enter = Sync
    idle(qtbot, w)
    assert v.stack.currentIndex() == 2
    assert v.res_title.text() == "All configured platforms updated."
    assert "Generation 2." in v.res_text.text()
    assert v.res_devices.topLevelItemCount() == 3
    assert all(v.res_devices.topLevelItem(i).text(1).startswith("Ready") for i in range(3))
    v.back()
    idle(qtbot, w)
    assert v.stack.currentIndex() == 1
    assert v.status.text() == "All available saves match the last sync."


def test_duplicate_submissions_are_ignored(make_shell, qtbot):
    fx = started("gui_dup")
    fx.drop("Odin 2 Mini", "monado01", H.play_wii(H.rd(H.W150), flags=4))
    w = make_shell(fx.hub.root)
    v = w.hub_view
    v.start_sync()
    assert v.running and not v.sync_btn.isEnabled()
    v.start_sync()                                                # second click while running: ignored
    v.sync_btn.click()
    idle(qtbot, w)
    assert fx.hub.committed() == [1, 2]


def test_cancel_before_commit(make_shell, qtbot, monkeypatch):
    fx = started("gui_cancel")
    fx.drop("Odin 2 Mini", "monado01", H.play_wii(H.rd(H.W150), flags=4))
    w = make_shell(fx.hub.root)
    v = w.hub_view
    v._cancel.set()                                               # cancelled before the build starts
    real = v._cancel.clear
    monkeypatch.setattr(v._cancel, "clear", lambda: None)
    v.start_sync()
    idle(qtbot, w)
    assert v.notice.title.text() == "Sync cancelled"
    assert fx.hub.committed() == [1]
    real()


def test_blocked_platform_offers_partial_update(make_shell, qtbot):
    fx = started("gui_blocked")
    b = bytearray(H.play_de(fx.out("de"), flags=3))
    n = struct.unpack_from("<I", b, 0x1526D8 + 0x18)[0]
    struct.pack_into("<H", b, 0x1526D8 + 2 * n, 8)
    struct.pack_into("<I", b, 0x1526D8 + 0x18, n + 1)
    fx.drop("Windows desktop", "bfsgame00.sav", bytes(b))
    w = make_shell(fx.hub.root)
    v = w.hub_view
    v.start_sync()
    idle(qtbot, w)
    assert v.notice.title.text() == "Not every game version can be updated"
    assert "nothing was changed" in v.notice.body.text()
    assert fx.hub.committed() == [1]
    assert v.notice.buttons and v.notice.buttons[0].text() == "Update the others only..."
    v.notice.buttons[0].click()
    idle(qtbot, w)
    assert v.stack.currentIndex() == 2
    assert v.res_title.text() == "Partly updated"
    assert "All configured platforms updated" not in v.res_text.text()


def test_history_dialog_and_rollback(make_shell, qtbot):
    fx = started("gui_history")
    fx.drop("Odin 2 Mini", "monado01", H.play_wii(H.rd(H.W150), flags=4))
    fx.sync()
    w = make_shell(fx.hub.root)
    v = w.hub_view
    from xcgui.synchub_view import HistoryDialog
    d = HistoryDialog(v, v)
    assert d.tree.topLevelItemCount() == 2
    assert "(current)" in d.tree.topLevelItem(0).text(0)
    assert "Odin 2 Mini" in d.tree.topLevelItem(0).text(3)
    assert "check:" in d.detail.toPlainText()
    d.tree.setCurrentItem(d.tree.topLevelItem(1))
    d._rollback()
    idle(qtbot, w)
    assert fx.hub.current_generation()[0] == 3
    assert fx.hub.current_generation()[1]["rollback_of"] == 1
    assert v.res_title.text() == "Generation 1 is current again (as generation 3)."


def test_interrupted_publication_offers_finish_publishing(make_shell, qtbot):
    fx = started("gui_publish")
    fx.drop("Odin 2 Mini", "monado01", H.play_wii(H.rd(H.W150), flags=4))

    def boom(p, detail=""):
        if p == "publish" and "new-3ds" in detail:
            raise OSError("simulated")
    syncmod.FAULT = boom
    try:
        fx.sync()
    finally:
        syncmod.FAULT = None
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert v.publish_btn.isVisible()
    v.publish_btn.click()
    idle(qtbot, w)
    assert not v.publish_btn.isVisible()
    assert v.notice.title.text() == "Ready folders updated"


def test_keyboard_mnemonics_and_f5(make_shell, qtbot):
    fx = started("gui_keys")
    w = make_shell(fx.hub.root)
    v = w.hub_view
    for b in (v.sync_btn, v.scan_btn, v.settings_btn, v.history_btn, v.folder_btn):
        assert "&" in b.text(), b.text()
    fx.drop("Odin 2 Mini", "monado02", H.play_wii(H.rd(H.W150), flags=4))
    qtbot.keyClick(v, Qt.Key.Key_F5)
    idle(qtbot, w)
    assert v.status.text() == "New progress found on Odin 2 Mini."
    assert v.sync_btn.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_damaged_history_shows_error_and_blocks(make_shell, qtbot):
    fx = started("gui_damaged")
    p = os.path.join(fx.hub.gen_dir(1), "generation.json")
    with open(p, "ab") as f:
        f.write(b" ")
    w = make_shell(fx.hub.root)
    v = w.hub_view
    assert "could not be read" in v.status.text()
    assert v.notice.isVisible() and v.notice.kind == "error"
    assert not v.sync_btn.isEnabled()


def test_missing_device_folder_is_shown_not_fatal(make_shell, qtbot):
    fx = started("gui_offline")
    import shutil
    shutil.rmtree(fx.dev["New 3DS"]["incoming"])
    w = make_shell(fx.hub.root)
    v = w.hub_view
    items = {v.dev_tree.topLevelItem(i).text(0): v.dev_tree.topLevelItem(i).text(2)
             for i in range(v.dev_tree.topLevelItemCount())}
    assert items["New 3DS"].startswith("Folder not available")
    assert v.status.text() == "All available saves match the last sync."


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_light_and_dark(make_shell, qtbot, scheme, tdir):
    app = QApplication.instance()
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if scheme == "dark" else Qt.ColorScheme.Light)
    try:
        fx = started(f"gui_theme_{scheme}")
        fx.drop("Odin 2 Mini", "monado02", H.play_wii(H.rd(H.W150), flags=4))
        w = make_shell(fx.hub.root)
        qtbot.wait(300)
        img = w.grab()
        img.save(os.path.join(tdir, f"{scheme}.png"))
        pal = w.palette()
        win = pal.color(pal.ColorRole.Window).lightness()
        assert (win < 128) == (scheme == "dark")
        ss = w.hub_view.sync_btn.styleSheet()
        assert "background-color" in ss
    finally:
        app.styleHints().setColorScheme(Qt.ColorScheme.Unknown)


def test_converter_tab_is_the_3a_window(make_shell):
    w = make_shell()
    from xcgui.main_window import MainWindow
    assert isinstance(w.converter, MainWindow)
    assert w.tabs.tabText(1) == "&Convert one save"
    assert w.converter.convert_btn.text().replace("&", "") == "Convert Save"
