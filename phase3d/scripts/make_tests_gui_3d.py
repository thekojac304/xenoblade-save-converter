"""Point the 3C GUI test suites at the 3D GUI copy (phase3d/gui): phase3d/tests_gui (Sync Hub tab) and
phase3d/tests_gui_3a (converter tab, 2H + 3A GUI tests). Only paths, work folders and the version string change;
every assertion is kept."""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P3D = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3D)


def gen(src, dst, pairs):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for f in sorted(os.listdir(src)):
        if not f.endswith(".py"):
            continue
        s = open(os.path.join(src, f), encoding="utf-8").read()
        for a, b in pairs:
            s = s.replace(a, b)
        open(os.path.join(dst, f), "w", encoding="utf-8").write(s)


gen(os.path.join(ROOT, "phase3c", "tests_gui"), os.path.join(P3D, "tests_gui"), [
    ("run against the Phase 3C GUI (phase3c/gui)", "run against the Phase 3D GUI (phase3d/gui)"),
    ('P3C = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))',
     'P3C = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # = phase3d'),
])
gen(os.path.join(ROOT, "phase3c", "tests_gui_3a"), os.path.join(P3D, "tests_gui_3a"), [
    ("run against the Phase 3C GUI (phase3c/gui)", "run against the Phase 3D GUI (phase3d/gui)"),
    ('os.path.join(ROOT, "phase3c", "gui")', 'os.path.join(ROOT, "phase3d", "gui")'),
    ('WORK = os.path.join(ROOT, "phase3c", "work", "tests_gui_3a")', 'WORK = os.path.join(ROOT, "phase3d", "work", "tests_gui_3a")'),
    ('== "XC Save Converter 3C-rc1"   # 3B/3C: version bump only', '== "XC Save Converter 3D-rc1"   # 3B/3C/3D: version bump only'),
])
print("ok")
