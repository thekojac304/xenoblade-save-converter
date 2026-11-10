"""pytest-qt fixtures for the Phase 3B GUI tests (phase3b/gui). Every test gets its own settings file and hub under
phase3b/work/tests_gui/<test>; the user's real settings and saves are never used."""
import os
import shutil
import sys

import pytest

P3B = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P3B)
for p in (os.path.join(ROOT, "tools"), os.path.join(ROOT, "phase3a", "src"), os.path.join(P3B, "src"),
          os.path.join(P3B, "gui"), os.path.join(P3B, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtCore import QSettings  # noqa: E402

import hubfix as H  # noqa: E402

WORK = os.path.join(P3B, "work", "tests_gui")
DATA = os.path.join(ROOT, "data")


@pytest.fixture
def tdir(request):
    d = os.path.join(WORK, request.node.name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    H.WORK = d
    return d


@pytest.fixture
def make_shell(qtbot, tdir):
    from xcgui.shell import Shell
    made = []

    def make(hub=None, size=(900, 800)):
        s = QSettings(os.path.join(tdir, f"settings{len(made)}.ini"), QSettings.Format.IniFormat)
        s.setValue("data_dir", DATA)
        s.setValue("output_parent", os.path.join(tdir, "out"))
        if hub:
            s.setValue("sync_hub_folder", hub)
        w = Shell(settings=s)
        qtbot.addWidget(w)
        w.resize(*size)
        w.show()
        made.append(w)
        idle(qtbot, w)
        return w

    yield make
    for w in made:
        try:
            idle(qtbot, w)
            w.engine.wait(60000)
        except RuntimeError:          # already closed and deleted by pytest-qt
            pass


def idle(qtbot, w, timeout=300000):
    v = w.hub_view
    qtbot.waitUntil(lambda: not w.engine.busy() and not v.scanning and not v.running, timeout=timeout)
    qtbot.wait(50)
    qtbot.waitUntil(lambda: not w.engine.busy() and not v.scanning and not v.running, timeout=timeout)
