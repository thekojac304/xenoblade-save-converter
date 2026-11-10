"""Phase 2H: GUI outputs (from the clean-directory package test) vs the Phase 2G RELEASE command line (xcconv.exe of
release_candidate_2G, run unchanged) for the same inputs. Writes only under the package-test folder.

  python phase2h\\scripts\\parity_2g.py <package-test root> <result json>
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EXE_2G = os.path.join(ROOT, "release_candidate_2G", "XCSaveConverter", "xcconv.exe")


def tree(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, d).replace("\\", "/")] = hashlib.sha256(fh.read()).hexdigest()
    return out


def job(root, name):
    with open(os.path.join(root, "jobs", name, "job.json"), encoding="utf-8") as f:
        j = json.load(f)
    with open(os.path.join(root, "jobs", name, "result.json"), encoding="utf-8") as f:
        return j, json.load(f)


def main(root, result):
    env = dict(os.environ, XCCONV_DATA=os.path.join(root, "mydata"))
    checks = []
    for name, build in (
            ("w2d", lambda j, r: ["wii-to-de", "--wii", j["source"], "--template", j["dest"]]),
            ("d2w_first", lambda j, r: ["de-to-wii", "--de", j["source"], "--base", j["dest"]]),
            ("d2w_return", lambda j, r: ["de-to-wii", "--de", j["source"], "--sidecar", r["plan"]["record"],
                                         "--current-wii", j["dest"]]),
            ("w2d_return", lambda j, r: ["wii-to-de", "--wii", j["source"], "--sidecar", r["plan"]["record"],
                                         "--current-de", j["dest"]])):
        j, r = job(root, name)
        slot = r["file_name"][7:9] if r["file_name"].startswith("bfsgame") else r["file_name"]
        out = os.path.join(root, "release_2g_cli", name)
        p = subprocess.run([EXE_2G, *build(j, r), "--slot", slot, "--out", out], env=env, capture_output=True,
                           text=True)
        ok = p.returncode == 0 and tree(out) == tree(r["out_dir"])
        checks.append({"name": f"2H GUI {name} identical to the 2G release xcconv.exe", "ok": ok, "rc": p.returncode})
        print("PASS" if ok else "FAIL", name, p.stderr[-200:] if not ok else "")
    with open(result, "w", encoding="utf-8") as f:
        json.dump({"exe": EXE_2G, "checks": checks}, f, indent=1)
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
