"""Close files in the Phase 2F tests (ResourceWarnings interleaved with the verbose test log). No logic change."""
import os

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests")


def rep(name, a, b, n=1):
    p = os.path.join(T, name)
    s = open(p, encoding="utf-8").read()
    assert s.count(a) == n, (name, a, s.count(a))
    open(p, "w", encoding="utf-8").write(s.replace(a, b))


rep("test_phase2f_safety.py", 'json.load(open(os.path.join(o, "manifest.json")))', 'json.loads(U.rd(os.path.join(o, "manifest.json")))', 2)
rep("test_phase2f_safety.py", 'json.load(open(rep))["written"]', 'json.loads(U.rd(rep))["written"]')
rep("test_phase2f_sidecar.py", 'scmod.load(open(sc_d2w, encoding="utf-8").read())', 'scmod.load(U.rd(sc_d2w).decode("utf-8"))')
rep("test_phase2f_sidecar.py", 'scmod.load(open(sc_w2d, encoding="utf-8").read())', 'scmod.load(U.rd(sc_w2d).decode("utf-8"))')
rep("test_phase2f_sidecar.py", 'cls.sc_text = open(cls.sc_path, encoding="utf-8").read()', 'cls.sc_text = U.rd(cls.sc_path).decode("utf-8")')
rep("test_phase2f_sidecar.py", 'scmod.load(open(forged(m), encoding="utf-8").read())', 'scmod.load(U.rd(forged(m)).decode("utf-8"))')
print("ok")
