"""Phase 3E: restore the original 2E/2F assertions that Phase 3D replaced with D2 refusals (phase3d/scripts/
patch_tests_d2.py) - the stored equipment of those saves (2E story-154 Melia alone, 2F s269 Shulk alone) is now
translated, so the original exports must succeed again. Applies the 3D replacement pairs in reverse."""
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
src = open(os.path.join(ROOT, "phase3d", "scripts", "patch_tests_d2.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(ROOT, "phase3d", "scripts", "patch_tests_d2.py")}
code = src.split("\nsub(", 1)
exec(code[0].replace('print("ok")', ""), ns)          # defines ROOT, sub
calls = []


def collect(rel, pairs):
    calls.append((rel, pairs))


ns["sub"] = collect
exec("sub(" + code[1].replace('print("ok")', ""), ns)
for rel, pairs in calls:
    p = os.path.join(ROOT, rel)
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if a in s and b not in s:
            continue                       # already original
        assert b in s, (rel, b[:80])
        s = s.replace(b, a)
    open(p, "w", encoding="utf-8").write(s)
    print("restored", rel)
