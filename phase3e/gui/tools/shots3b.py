"""Render the real Phase 3B window (Sync Hub tab) in its main states to PNG, for visual inspection.

  python phase3b\\gui\\tools\\shots3b.py <out folder> <light|dark> [scale]
Builds disposable hubs with simulated Syncthing folders under <out>\\work_<tag> (copies of fixtures only).
"""
import os
import shutil
import sys

OUT, SCHEME = sys.argv[1], sys.argv[2]
SCALE = sys.argv[3] if len(sys.argv) > 3 else "1"
os.environ["QT_SCALE_FACTOR"] = SCALE
HERE = os.path.dirname(os.path.abspath(__file__))
P3B = os.path.normpath(os.path.join(HERE, "..", ".."))
ROOT = os.path.dirname(P3B)
sys.path.insert(0, os.path.join(P3B, "gui"))
sys.path.insert(0, os.path.join(P3B, "tests"))

import hubfix as H  # noqa: E402

from PySide6.QtCore import QElapsedTimer, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from xcgui.app import make_app  # noqa: E402
from xcgui.shell import Shell  # noqa: E402
from xcgui import synchub_view as SV  # noqa: E402

app = make_app()
app.styleHints().setColorScheme(Qt.ColorScheme.Dark if SCHEME == "dark" else Qt.ColorScheme.Light)
tag = f"{SCHEME}_x{SCALE}"
os.makedirs(OUT, exist_ok=True)
H.WORK = os.path.join(OUT, f"work_{tag}")
shutil.rmtree(H.WORK, ignore_errors=True)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)


def pump(cond=lambda: False, ms=400):
    t = QElapsedTimer()
    t.start()
    while (cond() or t.elapsed() < ms) and t.elapsed() < 300000:
        app.processEvents()


def window(hub=None, size=(760, 700)):
    s = QSettings(os.path.join(H.WORK, f"s{len(os.listdir(H.WORK)) if os.path.isdir(H.WORK) else 0}.ini"),
                  QSettings.Format.IniFormat)
    s.setValue("data_dir", os.path.join(ROOT, "data"))
    s.setValue("sync_hub_folder", hub or "")
    w = Shell(settings=s)
    w.resize(*size)
    w.show()
    v = w.hub_view
    pump(lambda: v.scanning or v.running or w.engine.busy(), 600)
    return w


def shot(w, name):
    pump(ms=500)
    w.grab().save(os.path.join(OUT, f"{name}_{tag}.png"))


def dialog_shot(w, make, name, prep=None):
    def grab():
        d = next(x for x in QApplication.topLevelWidgets() if isinstance(x, QDialog) and x.isVisible())
        if prep:
            prep(d)
        pump(ms=400)
        d.grab().save(os.path.join(OUT, f"{name}_{tag}.png"))
        d.accept()
    QTimer.singleShot(700, grab)
    make()


os.makedirs(H.WORK, exist_ok=True)
w = window()
shot(w, "b01_welcome")
dialog_shot(w, lambda: w.hub_view.open_settings(first_run=True), "b02_setup_folder")
w.close()

fx = H.HubFx("shots_main")
fx.drop("Odin 2 Mini", "monado01", H.rd(H.W150))
w = window(fx.hub.root)
shot(w, "b03_first_sync_ready")
w.hub_view.start_sync(confirm=False)
pump(lambda: w.hub_view.running or w.engine.busy())
shot(w, "b04_result_all_updated")
w.close()

fx.drop("New 3DS", "monado01", H.rd(H.X3_A2))
w = window(fx.hub.root)
shot(w, "b05_new_progress_3ds")
dialog_shot(w, lambda: w.hub_view.open_settings(), "b06_settings_devices", prep=lambda d: d.tabs.setCurrentIndex(1))
pump(lambda: w.hub_view.scanning or w.engine.busy())          # Settings closes with a fresh scan
w.hub_view.start_sync(confirm=False)
pump(lambda: w.hub_view.running or w.engine.busy())
assert w.hub_view.last_sync and w.hub_view.last_sync.generation == 2, "second sync did not run"
w.close()

fx.drop("Odin 2 Mini", "monado02", H.rd(H.W150_LATER))
fx.drop("Windows desktop", "bfsgame00.sav", H.play_de(fx.out("de"), flags=4))
w = window(fx.hub.root)
shot(w, "b07_conflict")
w.hub_view.choice_group.buttons()[0].click()
shot(w, "b08_conflict_chosen")
dialog_shot(w, lambda: w.hub_view.open_history(), "b09_history")
w.close()

H.put(os.path.join(fx.dev["New 3DS"]["incoming"], "~syncthing~monado01.tmp"), b"partial")
w = window(fx.hub.root, size=(560, 520))
shot(w, "b10_waiting_small_window")
w.close()
print("shots in", OUT)
