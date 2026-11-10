"""Point the 3B GUI test suites at the 3C GUI copy (phase3c/gui): phase3c/tests_gui (Sync Hub tab, from
phase3b/tests_gui) and phase3c/tests_gui_3a (converter tab, 2H + 3A GUI tests, from phase3b/tests_gui_3a). Only paths,
work folders and the version string change; every assertion is kept."""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P3C = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3C)


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


gen(os.path.join(ROOT, "phase3b", "tests_gui"), os.path.join(P3C, "tests_gui"), [
    ('"""pytest-qt fixtures for the Phase 3B GUI tests (phase3b/gui).',
     '"""pytest-qt fixtures for the Phase 3B GUI tests, run against the Phase 3C GUI (phase3c/gui).'),
    ('P3B = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))\nROOT = os.path.dirname(P3B)',
     'P3C = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))\nROOT = os.path.dirname(P3C)\n'
     'P3B = os.path.join(ROOT, "phase3b")'),
    ('os.path.join(P3B, "gui"), os.path.join(P3B, "tests")', 'os.path.join(P3C, "gui"), os.path.join(P3B, "tests")'),
    ('WORK = os.path.join(P3B, "work", "tests_gui")', 'WORK = os.path.join(P3C, "work", "tests_gui")'),
])
gen(os.path.join(ROOT, "phase3b", "tests_gui_3a"), os.path.join(P3C, "tests_gui_3a"), [
    ("run against the Phase 3B GUI (phase3b/gui)", "run against the Phase 3C GUI (phase3c/gui)"),
    ('os.path.join(ROOT, "phase3b", "gui")', 'os.path.join(ROOT, "phase3c", "gui")'),
    ('WORK = os.path.join(ROOT, "phase3b", "work", "tests_gui_3a")', 'WORK = os.path.join(ROOT, "phase3c", "work", "tests_gui_3a")'),
    ('== "XC Save Converter 3B-rc1"   # 3B: version bump only', '== "XC Save Converter 3C-rc1"   # 3B/3C: version bump only'),
])
print("ok")
