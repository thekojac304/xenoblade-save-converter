"""Render the real window (Phase 2H layout) in several states, sizes, colour schemes and scale factors to PNG.

  python gui\\tools\\shots.py <out folder> <scheme light|dark> [scale]
(run once per scale: the scale factor must be set before Qt starts). Uses copied fixtures; writes only to <out>.
"""
import os
import shutil
import sys

OUT, SCHEME = sys.argv[1], sys.argv[2]
SCALE = sys.argv[3] if len(sys.argv) > 3 else "1"
os.environ["QT_SCALE_FACTOR"] = SCALE
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "gui"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from PySide6.QtCore import QElapsedTimer, QSettings, Qt  # noqa: E402

import paths  # noqa: E402
import xcservice  # noqa: E402
from xcgui.app import _wait_idle, make_app  # noqa: E402
from xcgui.main_window import MainWindow  # noqa: E402

FALLBACKS = list(paths.FALLBACKS)
app = make_app()
app.styleHints().setColorScheme(Qt.ColorScheme.Dark if SCHEME == "dark" else Qt.ColorScheme.Light)
os.makedirs(OUT, exist_ok=True)
tag = f"{SCHEME}_x{SCALE}"
O = os.path.join(ROOT, "work", "originals")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
WORK = os.path.join(OUT, f"work_{tag}")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)


def settle(ms=500):
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < ms:          # let style animations (radio buttons, hover) finish
        app.processEvents()


def shot(win, name, full=False):
    _wait_idle(app, win)
    settle()
    win.grab().save(os.path.join(OUT, f"{name}_{tag}.png"))
    if full:
        page = win.stack.currentWidget().widget()
        page.grab().save(os.path.join(OUT, f"{name}_full_{tag}.png"))


def window(size, data=True, out="converted"):
    ini = os.path.join(WORK, f"s{len(os.listdir(WORK))}.ini")
    s = QSettings(ini, QSettings.Format.IniFormat)
    s.setValue("output_parent", os.path.join(WORK, out))
    s.setValue("data_dir", os.path.join(ROOT, "data") if data else "")
    paths.FALLBACKS = FALLBACKS if data else []
    paths.set_data_dir(None)
    xcservice.reset_tables()
    w = MainWindow(settings=s)
    w.resize(*size)
    w.show()
    _wait_idle(app, w)
    return w


os.environ.pop("XCCONV_DATA", None)
w = window((700, 600), data=False)
shot(w, "01_first_run")
w.adv.show_tab("data")
settle()
w.adv.grab().save(os.path.join(OUT, f"02_advanced_game_data_{tag}.png"))
w.adv.hide()
w.close()

w = window((700, 600))
shot(w, "02_empty")
w.close()

for size in ((480, 420), (700, 600), (1280, 900)):
    w = window(size)
    w.src_pick.set_path(os.path.join(O, "monado01"))
    _wait_idle(app, w)
    w.dest_pick.set_path(TPL)
    shot(w, f"03_first_ready_{size[0]}", full=size[0] == 700)
    if size[0] == 700:
        w.convert_btn.click()
        _wait_idle(app, w)
        shot(w, "04_result_w2d")
        de1 = w.last_result.main_output
    w.close()

w = window((700, 600))                       # return trip found automatically
w.src_pick.set_path(de1)
_wait_idle(app, w)
w.dest_pick.set_path(os.path.join(O, "monado01"))
shot(w, "05_return_ready", full=True)
w.close()

w = window((700, 600), out="elsewhere")      # same playthrough, record not found
w.src_pick.set_path(os.path.join(O, "monado01"))
_wait_idle(app, w)
iso = os.path.join(WORK, "copy_of_de")
os.makedirs(iso, exist_ok=True)
shutil.copyfile(de1, os.path.join(iso, "bfsgame05.sav"))
w.dest_pick.set_path(os.path.join(iso, "bfsgame05.sav"))
shot(w, "06_no_record_same_playthrough", full=True)
w.close()

w = window((700, 600))
w.src_pick.set_path(os.path.join(O, "monado02"))
_wait_idle(app, w)
w.out_pick.set_path(r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save")
shot(w, "07_errors", full=True)
w.adv.show_tab("options")
settle()
w.adv.grab().save(os.path.join(OUT, f"08_advanced_options_{tag}.png"))
w.adv.show_tab("tools")
settle()
w.adv.grab().save(os.path.join(OUT, f"09_advanced_tools_{tag}.png"))
w.adv.hide()
w.close()
print("ok", tag)
