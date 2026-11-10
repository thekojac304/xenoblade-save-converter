"""Point the copied 3A/2H GUI tests (phase3b/tests_gui_3a) at the 3B GUI (phase3b/gui). Test bodies unchanged;
only the conftest import paths and the work folder differ."""
import os

D = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests_gui_3a"))
p = os.path.join(D, "conftest.py")
s = open(p, encoding="utf-8").read()
old = 'for p in (os.path.join(ROOT, "tools"), os.path.join(P3, "src"), os.path.join(P3, "gui"), os.path.join(ROOT, "tests")):'
new = ('for p in (os.path.join(ROOT, "tools"), os.path.join(P3, "src"), os.path.join(ROOT, "phase3b", "src"),\n'
       '          os.path.join(ROOT, "phase3b", "gui"), os.path.join(ROOT, "tests")):')
if old in s:
    s = s.replace(old, new)
s = s.replace('WORK = os.path.join(ROOT, "work", "test_phase3a", "gui")',
              'WORK = os.path.join(ROOT, "phase3b", "work", "tests_gui_3a")')
s = s.replace('"""pytest-qt fixtures for the Phase 2H GUI tests, run against the Phase 3A GUI (phase3a/gui).',
              '"""pytest-qt fixtures for the Phase 2H and 3A GUI tests, run against the Phase 3B GUI (phase3b/gui).')
assert 'os.path.join(ROOT, "phase3b", "gui")' in s and "phase3b\", \"work\"" in s.replace("'", '"')
open(p, "w", encoding="utf-8").write(s)
# the one expected difference: the application version shown in the diagnostics
t = os.path.join(D, "test_phase2h_gui.py")
s = open(t, encoding="utf-8").read()
s = s.replace('== "XC Save Converter 3A-rc1"', '== "XC Save Converter 3B-rc1"   # 3B: version bump only')
open(t, "w", encoding="utf-8").write(s)
print("ok", p)
