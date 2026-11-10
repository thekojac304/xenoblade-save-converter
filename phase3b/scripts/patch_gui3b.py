"""Phase 3B GUI patch: applied once to the copy of the 3A GUI in phase3b/gui (the 3A GUI is untouched).
Version 3B-rc1, import paths for xcsync, the Shell window (Sync Hub + converter tabs), --sync-automate."""
import os

G = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gui"))


def patch(rel, pairs):
    p = os.path.join(G, rel)
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if b in s and a not in s:
            continue                       # already applied
        assert a in s, (rel, a[:70])
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


patch("xcgui/__init__.py", [('APP_VERSION = "3A-rc1"', 'APP_VERSION = "3B-rc1"'),
                            ('(Phase 2G; three platforms since 3A)',
                             '(Phase 2G; three platforms since 3A; Sync Hub since 3B)')])
patch("version_info.txt", [("filevers=(0, 9, 0, 1), prodvers=(0, 9, 0, 1)", "filevers=(0, 9, 1, 0), prodvers=(0, 9, 1, 0)"),
                           ("New 3DS) 3A-rc1", "New 3DS) with Sync Hub 3B-rc1"),
                           ("'FileVersion', '3A-rc1'", "'FileVersion', '3B-rc1'"),
                           ("'ProductVersion', '3A-rc1'", "'ProductVersion', '3B-rc1'")])
patch("xcgui/shell.py", [("""    def closeEvent(self, e):
        self.converter.closeEvent(e)""", """    def closeEvent(self, e):
        if self.hub_view.running:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, APP_NAME, "A sync is running. Wait until it has finished: a new generation "
                                    "only becomes current after every save has been validated.")
            e.ignore()
            return
        self.converter.closeEvent(e)""")])
patch("xcgui/app.py", [
    ("""        for rel in (("..", "..", "..", "tools"), ("..", "..", "src")):      # 2H engine + Phase 3A modules""",
     """        for rel in (("..", "..", "..", "tools"), ("..", "..", "..", "phase3a", "src"),
                    ("..", "..", "src")):      # 2H engine + Phase 3A modules + Phase 3B Sync Hub (xcsync)"""),
    ("""  XCSaveConverter.exe --smoke result.json   start, show the window, capture it, close it, exit 0
""", """  XCSaveConverter.exe --smoke result.json   start, show the window, capture it, close it, exit 0
  XCSaveConverter.exe --sync-automate job.json   drive the Sync Hub view (scan, choose, Sync All) from a job
"""),
    ("""def smoke(result_path):
    from .main_window import MainWindow
    app = make_app()
    settings = QSettings(os.path.join(os.path.dirname(os.path.abspath(result_path)), "smoke.ini"),
                         QSettings.Format.IniFormat)
    win = MainWindow(settings=settings)""", '''def _pump(app, win, cond, ms):
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
    win = shell.converter'''),
    ("""    win.resize(*initial_size(app))
    win.show()
    info = {}

    def done():""", """    shell.resize(*initial_size(app))
    shell.show()
    info = {}

    def done():"""),
    ("""                    dpr=win.devicePixelRatioF(), style=app.style().name(),
                    color_scheme=str(app.styleHints().colorScheme()), size=[win.width(), win.height()])
        win.grab().save(os.path.splitext(result_path)[0] + ".png")
        win.close()""", """                    dpr=win.devicePixelRatioF(), style=app.style().name(),
                    color_scheme=str(app.styleHints().colorScheme()), size=[shell.width(), shell.height()],
                    tabs=[shell.tabs.tabText(i) for i in range(shell.tabs.count())],
                    hub_page=shell.hub_view.stack.currentIndex(), shell_title=shell.windowTitle())
        shell.grab().save(os.path.splitext(result_path)[0] + ".png")
        shell.tabs.setCurrentIndex(1)
        app.processEvents()
        shell.grab().save(os.path.splitext(result_path)[0] + "_converter.png")
        shell.close()"""),
    ("""    return min(700, int(avail.width() * 0.9)), min(600, int(avail.height() * 0.9))   # fits small laptops""",
     """    return min(760, int(avail.width() * 0.9)), min(700, int(avail.height() * 0.9))   # fits small laptops"""),
    ("""    if "--smoke" in argv:
        return smoke(argv[argv.index("--smoke") + 1])
    from .main_window import MainWindow
    app = make_app(argv[:1])
    win = MainWindow()""", """    if "--smoke" in argv:
        return smoke(argv[argv.index("--smoke") + 1])
    if "--sync-automate" in argv:
        return sync_automate(argv[argv.index("--sync-automate") + 1])
    from .shell import Shell
    app = make_app(argv[:1])
    win = Shell()"""),
])
print("patched", G)
