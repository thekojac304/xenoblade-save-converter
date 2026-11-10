"""pytest-qt fixtures for the Phase 2H and 3A GUI tests, run against the Phase 3B GUI (phase3b/gui). Every test gets its own settings file and output folder under
work/test_phase2h/gui/<test name>; the user's real settings (registry) and saves are never used."""
import os
import shutil
import sys

import pytest

P3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "phase3a"))   # 3A modules
ROOT = os.path.dirname(P3)
for p in (os.path.join(ROOT, "tools"), os.path.join(P3, "src"), os.path.join(ROOT, "phase3b", "src"),
          os.path.join(ROOT, "phase3b", "gui"), os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtCore import QSettings  # noqa: E402

import paths  # noqa: E402
import xcservice as svc  # noqa: E402

WORK = os.path.join(ROOT, "phase3b", "work", "tests_gui_3a")
DATA = os.path.join(ROOT, "data")


@pytest.fixture
def tmpdir_(request):
    d = os.path.join(WORK, request.node.name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


@pytest.fixture
def make_win(qtbot, tmpdir_):
    from xcgui.main_window import MainWindow
    made = []

    def make(data=True, size=(940, 820)):
        s = QSettings(os.path.join(tmpdir_, f"settings{len(made)}.ini"), QSettings.Format.IniFormat)
        s.setValue("output_parent", os.path.join(tmpdir_, "out"))
        s.setValue("data_dir", DATA if data else "")
        paths.set_data_dir(None)
        svc.reset_tables()
        w = MainWindow(settings=s)
        qtbot.addWidget(w)
        w.resize(*size)
        w.show()
        made.append(w)
        idle(qtbot, w)
        return w

    yield make
    for w in made:
        if w.running:
            idle(qtbot, w)
        w.engine.wait(60000)


def idle(qtbot, w, timeout=180000):
    """Wait until every engine task has finished and its result signal has been delivered."""
    qtbot.waitUntil(lambda: not w.engine.busy() and not w.running, timeout=timeout)
    qtbot.wait(30)
    qtbot.waitUntil(lambda: not w.engine.busy() and not getattr(w, "plan_pending", False), timeout=timeout)
    qtbot.wait(30)
