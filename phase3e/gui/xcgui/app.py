"""Application start-up, plus a scripted automation mode used to test the packaged build.

  XCSaveConverter.exe                       normal start
  XCSaveConverter.exe --automate job.json   drive the real window from a JSON job, write the outcome, exit
  XCSaveConverter.exe --smoke result.json   start, show the window, capture it, close it, exit 0
  XCSaveConverter.exe --sync-automate job.json   drive the Sync Hub view (scan, choose, Sync All) from a job

A job: {"source": path, "dest": path, "output_parent": path, "file_name": "bfsgame02.sav" (optional),
        "record": path (optional: choose a conversion record), "start_fresh": bool, "dry_run": bool,
        "overflow": bool, "no_current": bool, "data_dir": path, "settings": ini path, "result": path}.
The automation fills the same widgets a user fills and presses the same button; it never bypasses the window.
"""
import json
import os
import sys
import traceback


def _setup_path():
    if not getattr(sys, "frozen", False):
        here = os.path.dirname(os.path.abspath(__file__))
        for rel in (("..", "..", "..", "tools"), ("..", "..", "..", "phase3a", "src"),
                    ("..", "..", "..", "phase3b", "src")):   # engine + Phase 3A modules + Sync Hub (xcsync, 3B code)
            p = os.path.normpath(os.path.join(here, *rel))
            if p not in sys.path:
                sys.path.insert(0, p)


_setup_path()

from PySide6.QtCore import QElapsedTimer, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from . import APP_NAME, APP_VERSION  # noqa: E402


def make_app(argv=None):
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(argv or sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("XCSaveConverter")
    return app


def _wait_idle(app, win, timeout_ms=120000):
    """Process events until the engine is idle, no conversion runs and no history check is pending."""
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < timeout_ms:
        app.processEvents()
        if not win.engine.busy() and not win.running:
            app.processEvents()
            if not win.engine.busy() and not win.plan_pending:
                return True
        win.engine.wait(20)
    return False


def automate(job_path):
    from .main_window import MainWindow
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    app = make_app()
    settings = QSettings(job.get("settings") or os.path.join(os.path.dirname(job["result"]), "automation.ini"),
                         QSettings.Format.IniFormat)
    if job.get("data_dir"):
        settings.setValue("data_dir", job["data_dir"])
    if job.get("output_parent"):
        settings.setValue("output_parent", job["output_parent"])
    win = MainWindow(settings=settings)
    win.show()
    out = {"ok": False}
    try:
        _wait_idle(app, win)
        win.adv.opt_dry.setChecked(bool(job.get("dry_run")))
        win.adv.opt_overflow.setChecked(bool(job.get("overflow")))
        win.adv.opt_no_current.setChecked(bool(job.get("no_current")))
        win.src_pick.set_path(job["source"])
        _wait_idle(app, win)
        if job.get("target"):
            win.set_target(job["target"])
            _wait_idle(app, win)
        if job.get("dest"):
            win.dest_pick.set_path(job["dest"])
            _wait_idle(app, win)
        if job.get("keep_this_progress"):
            win.branch = True
        if job.get("record"):
            win.chosen_record = job["record"]
            win._gen += 1
            win._plan()
            _wait_idle(app, win)
        if job.get("start_fresh") and win.plan and win.plan.issue == "same-playthrough":
            win.start_fresh = True
            win._gen += 1
            win._plan()
            _wait_idle(app, win)
        if job.get("file_name"):
            win.slot_combo.setCurrentText(job["file_name"])
        win.refresh()
        p = win.plan
        out["plan"] = None if not p else {"mode": p.mode, "issue": p.issue, "record": p.sidecar,
                                          "destination": p.dest_relation}
        out["missing"] = win.missing()
        out["source_preview"] = win.src_info.text()
        out["dest_preview"] = win.dest_info.text()
        out["direction"] = win.direction()
        out["file_name"] = win.slot_combo.currentText()
        if not out["missing"]:
            win.convert_btn.click()
            _wait_idle(app, win)
        out["page"] = "result" if win.stack.currentIndex() == 1 else "form"
        out["result_title"] = win.res_title.text() if out["page"] == "result" else win.fail_notice.title.text()
        out["result_detail"] = win.fail_notice.detail.text()
        if win.last_result:
            r = win.last_result
            out.update(ok=True, out_dir=r.out_dir, main_output=r.main_output, sidecar=r.sidecar_path,
                       written=r.written, dry_run=r.dry_run)
    except Exception as e:
        out["exception"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()
    finally:
        win.close()
        app.processEvents()
    with open(job["result"], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return 0 if out.get("ok") else 1


def _pump(app, win, cond, ms):
    t = QElapsedTimer()
    t.start()
    while cond() and t.elapsed() < ms:
        app.processEvents()
        win.engine.wait(20)
    app.processEvents()


def sync_automate(job_path):
    """Sync Hub automation through the real window: {"hub": folder, "data_dir", "settings", "result",
    "choose": substring of the save to choose (optional), "allow_partial": bool, "sync": bool, "screenshot": png,
    "rollback": generation number}. The startup scan runs exactly as for a user; Sync All is pressed through the
    button; confirmation questions are answered Yes."""
    from PySide6.QtWidgets import QMessageBox
    from .shell import Shell
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    app = make_app()
    settings = QSettings(job.get("settings") or os.path.join(os.path.dirname(job["result"]), "sync_automation.ini"),
                         QSettings.Format.IniFormat)
    if job.get("data_dir"):
        settings.setValue("data_dir", job["data_dir"])
    settings.setValue("sync_hub_folder", job["hub"])
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    win = Shell(settings=settings)
    win.resize(*initial_size(app))
    win.show()
    v = win.hub_view
    out = {"ok": False}
    try:
        _pump(app, win, lambda: (not v.result and not v.last_error) or v.scanning, 180000)
        r = v.result
        out["scan"] = {"decision": r.decision.kind, "message": r.decision.message, "status": v.status.text(),
                       "generation": r.generation,
                       "devices": [{"name": d.device["name"], "status": d.status, "text": d.text,
                                    "ready": d.ready_state} for d in r.devices]} if r else None
        if job.get("choose") and r:
            for b in v.choice_group.buttons():
                if job["choose"] in b.property("key"):
                    b.click()
        app.processEvents()
        out["sync_enabled"] = v.sync_btn.isEnabled()
        out["source_shown"] = {k: lab.text() for k, lab in v.src_fields.items()} if v.src_box.isVisible() else None
        if job.get("sync") and v.sync_btn.isEnabled():
            v.sync_btn.click()
            _pump(app, win, lambda: v.running or win.engine.busy(), 600000)
            if job.get("allow_partial") and not v.last_sync and v.notice.buttons:
                v.notice.buttons[0].click()
                _pump(app, win, lambda: v.running or win.engine.busy(), 600000)
        if job.get("rollback"):
            v.run_rollback(int(job["rollback"]))
            _pump(app, win, lambda: v.running or win.engine.busy(), 600000)
        s = v.last_sync
        out["result_title"] = v.res_title.text() if v.stack.currentIndex() == 2 else None
        out["notice"] = v.notice.title.text() if v.notice.isVisible() else None
        out["notice_text"] = v.notice.body.text() if v.notice.isVisible() else None
        if s:
            out.update(generation=s.generation, complete=s.complete, partial=s.partial, published=s.published,
                       message=s.message)
        if job.get("screenshot"):
            win.grab().save(job["screenshot"])
        out["ok"] = True
    except Exception as e:
        out["exception"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()
    finally:
        win.close()
        app.processEvents()
    with open(job["result"], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return 0 if out.get("ok") else 1


def smoke(result_path):
    from .shell import Shell
    app = make_app()
    settings = QSettings(os.path.join(os.path.dirname(os.path.abspath(result_path)), "smoke.ini"),
                         QSettings.Format.IniFormat)
    shell = Shell(settings=settings)
    win = shell.converter
    shell.resize(*initial_size(app))
    shell.show()
    info = {}

    def done():
        import paths
        info.update(hub_page=shell.hub_view.stack.currentIndex(), hub_visible=shell.hub_view.isVisible(),
                    tabs=[shell.tabs.tabText(i) for i in range(shell.tabs.count())], shell_title=shell.windowTitle())
        shell.grab().save(os.path.splitext(result_path)[0] + "_synchub.png")
        shell.tabs.setCurrentIndex(1)                     # the 3A converter, measured as the 3A smoke did
        app.processEvents()
        info.update(title=win.windowTitle(), visible=win.isVisible(), setup_notice=win.setup_notice.isVisible(),
                    frozen=bool(getattr(sys, "frozen", False)), executable=sys.executable,
                    spec_found=os.path.isfile(paths.spec("wii_award_tiers.json")), next=win.next_label.text(),
                    dpr=win.devicePixelRatioF(), style=app.style().name(),
                    color_scheme=str(app.styleHints().colorScheme()), size=[shell.width(), shell.height()])
        shell.grab().save(os.path.splitext(result_path)[0] + ".png")
        shell.close()
        app.quit()

    QTimer.singleShot(1500, done)
    app.exec()
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1)
    return 0


def initial_size(app):
    avail = app.primaryScreen().availableGeometry()
    return min(760, int(avail.width() * 0.9)), min(700, int(avail.height() * 0.9))   # fits small laptops


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--automate" in argv:
        return automate(argv[argv.index("--automate") + 1])
    if "--smoke" in argv:
        return smoke(argv[argv.index("--smoke") + 1])
    if "--sync-automate" in argv:
        return sync_automate(argv[argv.index("--sync-automate") + 1])
    from .shell import Shell
    app = make_app(argv[:1])
    win = Shell()
    win.resize(*initial_size(app))
    win.show()
    return app.exec()
