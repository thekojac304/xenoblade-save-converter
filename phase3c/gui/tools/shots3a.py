"""Render the 3A window in the New 3DS states to PNG (light/dark).  python gui\\tools\\shots3a.py <out> light|dark
Uses copies of fixtures; writes only to <out>."""
import os
import shutil
import sys

OUT, SCHEME = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.normpath(os.path.join(HERE, "..", ".."))
ROOT = os.path.dirname(P3)
for p in (os.path.join(P3, "gui"), os.path.join(P3, "src"), os.path.join(ROOT, "tools")):
    sys.path.insert(0, p)

from PySide6.QtCore import QElapsedTimer, QSettings, Qt  # noqa: E402

from xcgui.app import _wait_idle, make_app  # noqa: E402
from xcgui.main_window import MainWindow  # noqa: E402

app = make_app()
app.styleHints().setColorScheme(Qt.ColorScheme.Dark if SCHEME == "dark" else Qt.ColorScheme.Light)
WORK = os.path.join(OUT, f"work_{SCHEME}")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)


def cp(src, sub, name):
    d = os.path.join(WORK, sub)
    os.makedirs(d, exist_ok=True)
    shutil.copyfile(src, os.path.join(d, name))
    return os.path.join(d, name)


X3 = os.path.join(P3, "originals", "azahar_live", "00000001", "monado01")
X3E = os.path.join(P3, "originals", "azahar_live", "00000001", "monado02")
W150 = os.path.join(P3, "fixtures", "wii_user_s150.bin")


def settle(ms=500):
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < ms:
        app.processEvents()


def shot(win, name):
    _wait_idle(app, win)
    settle()
    win.grab().save(os.path.join(OUT, f"3a_{name}_{SCHEME}.png"))


def new_win():
    s = QSettings(os.path.join(WORK, f"s{len(os.listdir(WORK))}.ini"), QSettings.Format.IniFormat)
    s.setValue("data_dir", os.path.join(ROOT, "data"))
    s.setValue("output_parent", os.path.join(WORK, "out"))
    w = MainWindow(settings=s)
    w.resize(700, 600)
    w.show()
    _wait_idle(app, w)
    return w


w = new_win()
shot(w, "01_start")
w.src_pick.set_path(cp(X3, "sd", "monado01"))
shot(w, "02_3ds_source_convert_to")
w.close()
w = new_win()
cp(X3E, "sd2", "monado02")
cp(X3E, "sd2", "monado03")
w.src_pick.set_path(W150)
_wait_idle(app, w)
w.dest_pick.set_path(cp(X3, "sd2", "monado01"))
shot(w, "03_wii_to_3ds_ready")
w.convert_btn.click()
shot(w, "04_result_3ds")
w.close()
print("ok")
