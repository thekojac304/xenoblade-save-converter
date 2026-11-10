"""Point the 3E GUI test suites at the 3F GUI copy (phase3f/gui): phase3f/tests_gui (Sync Hub tab) and
phase3f/tests_gui_3a (converter tab), plus one 3F test for the new plain-language rule. Only paths, work folders and
the version string change in the copied tests."""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P3F = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3F)


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


gen(os.path.join(ROOT, "phase3e", "tests_gui"), os.path.join(P3F, "tests_gui"), [
    ("run against the Phase 3E GUI (phase3e/gui)", "run against the Phase 3F GUI (phase3f/gui)"),
    ("..))   # = phase3e", "..))   # = phase3f"),
])
gen(os.path.join(ROOT, "phase3e", "tests_gui_3a"), os.path.join(P3F, "tests_gui_3a"), [
    ("run against the Phase 3E GUI (phase3e/gui)", "run against the Phase 3F GUI (phase3f/gui)"),
    ('os.path.join(ROOT, "phase3e", "gui")', 'os.path.join(ROOT, "phase3f", "gui")'),
    ('WORK = os.path.join(ROOT, "phase3e", "work", "tests_gui_3a")', 'WORK = os.path.join(ROOT, "phase3f", "work", "tests_gui_3a")'),
    ('== "XC Save Converter 3E-rc1"   # 3B..3E: version bump only', '== "XC Save Converter 3F-rc1"   # 3B..3F: version bump only'),
])
open(os.path.join(P3F, "tests_gui", "test_phase3f_messages.py"), "w", encoding="utf-8").write('''"""Phase 3F GUI: plain-language text for the F1 refusal and for the reunion-room capacity refusal."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gui"))
from xcgui import messages  # noqa: E402


def test_skipped_return_is_explained():
    f = messages.explain(Exception("Shulk, Reyn: back in the party, but the game has not given back the equipment it "
                                   "kept during the story separation (...)"))
    assert f.title == "Equipment not given back by the game" and "Nothing was written" in f.text


def test_reunion_room_refusal_offers_the_overflow_option():
    f = messages.explain(Exception("weapon: 140 items exceed the Wii capacity of this save (140) less the 4 slots the "
                                   "game needs free to give the stored equipment back at the party's reunion; rerun"))
    assert f.title == "Inventory too large for the Wii save"
''')
print("ok")
