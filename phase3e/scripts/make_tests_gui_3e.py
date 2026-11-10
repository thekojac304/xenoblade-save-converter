"""Point the 3D GUI test suites at the 3E GUI copy (phase3e/gui): phase3e/tests_gui (Sync Hub tab) and
phase3e/tests_gui_3a (converter tab). Only paths, work folders and the version string change."""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P3E = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3E)


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


gen(os.path.join(ROOT, "phase3d", "tests_gui"), os.path.join(P3E, "tests_gui"), [
    ("run against the Phase 3D GUI (phase3d/gui)", "run against the Phase 3E GUI (phase3e/gui)"),
    ("..))   # = phase3d", "..))   # = phase3e"),
])
gen(os.path.join(ROOT, "phase3d", "tests_gui_3a"), os.path.join(P3E, "tests_gui_3a"), [
    ("run against the Phase 3D GUI (phase3d/gui)", "run against the Phase 3E GUI (phase3e/gui)"),
    ('os.path.join(ROOT, "phase3d", "gui")', 'os.path.join(ROOT, "phase3e", "gui")'),
    ('WORK = os.path.join(ROOT, "phase3d", "work", "tests_gui_3a")', 'WORK = os.path.join(ROOT, "phase3e", "work", "tests_gui_3a")'),
    ('== "XC Save Converter 3D-rc1"   # 3B/3C/3D: version bump only', '== "XC Save Converter 3E-rc1"   # 3B..3E: version bump only'),
])
print("ok")
