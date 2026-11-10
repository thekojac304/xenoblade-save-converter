"""Phase 2F exploratory probes of the 2E-rc1 CLI (frozen copy in phase2f/snapshot_2E/source/tools).
Writes only under phase2f/probe_out. Prints one line per probe; the regression tests in tests/test_phase2f_*.py
are the authoritative versions of anything found here."""
import io
import json
import os
import shutil
import subprocess
import sys
import contextlib

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
TOOLS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P2F, "snapshot_2E", "source", "tools")
OUT = os.path.join(P2F, "probe_out")
W1 = os.path.join(ROOT, "work", "originals", "monado01")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
os.environ.setdefault("XCCONV_DATA", os.path.join(ROOT, "data"))


def run(*args):
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "xcconv.py"), *args], capture_output=True, text=True)
    return p.returncode, p.stdout[-400:], p.stderr[-600:]


def fresh(name):
    d = os.path.join(OUT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


res = {}
# P1 --slot path traversal (Wii->DE): slot is spliced into the file name
d = fresh("p1")
rc, so, se = run("wii-to-de", "--wii", W1, "--template", TPL, "--out", os.path.join(d, "o"), "--slot", "00/../../escaped")
res["P1_slot_traversal"] = (rc, se.strip()[-200:], sorted(os.listdir(d)))
# P2 partial output: pre-create the sidecar so the 2nd/3rd write is refused after the save was committed
d = fresh("p2")
o = os.path.join(d, "o")
os.makedirs(o)
open(os.path.join(o, "wii_to_de.sidecar.json"), "w").write("{}")
rc, so, se = run("wii-to-de", "--wii", W1, "--template", TPL, "--out", o)
left = [os.path.relpath(os.path.join(dp, f), o) for dp, _, fs in os.walk(o) for f in fs]
res["P2_partial_output"] = (rc, se.strip()[-160:], left)
# P3 junction into a live-looking folder (disposable tree whose path contains a live marker)
d = fresh("p3")
fake_live = os.path.join(d, "Dolphin", "User", "Wii")
os.makedirs(fake_live)
j = os.path.join(d, "innocent")
subprocess.run(["cmd", "/c", "mklink", "/J", j, fake_live], capture_output=True)
rc, so, se = run("wii-to-de", "--wii", W1, "--template", TPL, "--out", os.path.join(j, "o"))
res["P3_junction_guard"] = (rc, se.strip()[-160:], os.path.exists(os.path.join(fake_live, "o")))
# P4 truncated / malformed inputs -> controlled error?
d = fresh("p4")
w = open(W1, "rb").read()
cases = {"trunc_wii": w[:1000], "trunc_wii_half": w[:len(w) // 2], "empty": b"", "de_wrong_len": b"\0" * 0x153F31,
         "de_v10_zero": b"\0" * 0x153F30, "random": os.urandom(4096)}
for k, b in cases.items():
    p = os.path.join(d, k)
    open(p, "wb").write(b)
    for cmd in (["inspect", p], ["validate", p], ["wii-to-de", "--wii", p, "--template", TPL, "--out", os.path.join(d, k + "_o")],
                ["de-to-wii", "--de", p, "--base", W1, "--out", os.path.join(d, k + "_w")]):
        rc, so, se = run(*cmd)
        res[f"P4_{k}_{cmd[0]}"] = (rc, "Traceback" in se, se.strip().splitlines()[-1][:120] if se.strip() else "")
# P5 de-to-wii --slot absolute path
d = fresh("p5")
outw = os.path.join(d, "w")
rc, so, se = run("wii-to-de", "--wii", W1, "--template", TPL, "--out", os.path.join(d, "de"))
de = os.path.join(d, "de", "save_0", "bfsgame00.sav")
rc, so, se = run("de-to-wii", "--de", de, "--base", W1, "--out", outw, "--slot", os.path.join(d, "abs_target"))
res["P5_slot_absolute"] = (rc, os.path.exists(os.path.join(d, "abs_target")), se.strip()[-160:])
# P6 dry run writes nothing (including --report)
d = fresh("p6")
rc, so, se = run("wii-to-de", "--wii", W1, "--template", TPL, "--out", os.path.join(d, "o"), "--dry-run",
                 "--report", os.path.join(d, "rep.json"))
res["P6_dry_run_writes"] = (rc, sorted(os.listdir(d)))
for k, v in res.items():
    print(k, json.dumps(v, default=str))
