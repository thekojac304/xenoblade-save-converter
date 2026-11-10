"""H2 clean-directory package test. Builds a throwaway copy of the 2F release (tools/build_rc_2f.py with its target
redirected) under <scratch>, then runs the documented CLI from an unrelated working directory with XCCONV_DATA unset,
so the converter must find everything through the package layout. Inputs (the user's saves) are only read.

  python package_test.py <scratch dir> -> phase2f/results/package_test.json
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_rc_2f  # noqa: E402

W1 = os.path.join(ROOT, "work", "originals", "monado01")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
RC_USER_SHA = hashlib.sha256(open(os.path.join(P2F, "rc_user", "wii_to_de_monado01", "save_0", "bfsgame01.sav"),
                                  "rb").read()).hexdigest()


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(scratch):
    base = os.path.join(scratch, "pkgtest_" + time.strftime("%H%M%S"))
    build_rc_2f.RC = os.path.join(base, "rc")
    build_rc_2f.main()
    conv = os.path.join(build_rc_2f.RC, "converter")
    cwd = os.path.join(base, "somewhere_else")
    os.makedirs(cwd)
    env = {k: v for k, v in os.environ.items() if k != "XCCONV_DATA"}
    res = {"package": conv, "cwd": cwd, "checks": []}

    def run(name, args, expect_rc, check=None, at=conv):
        p = subprocess.run([sys.executable, os.path.join(at, "tools", "xcconv.py"), *args], cwd=cwd, env=env,
                           capture_output=True, text=True)
        ok = p.returncode == expect_rc and "Traceback" not in p.stderr
        extra = None
        if ok and check:
            extra = check(p)
            ok = bool(extra)
        res["checks"].append({"name": name, "rc": p.returncode, "expected_rc": expect_rc, "pass": ok,
                              "detail": extra if extra not in (True, None) else None,
                              "stderr_tail": p.stderr.strip()[-200:]})
        return p

    o = lambda n: os.path.join(base, "out", n)  # noqa: E731
    run("help", ["--help"], 0, lambda p: "cleanup-staging" in p.stdout)
    run("inspect", ["inspect", W1], 0, lambda p: json.loads(p.stdout)["story"] == 150)
    run("validate", ["validate", W1], 0)
    run("roundtrip-check", ["roundtrip-check", "--wii", W1, "--template", TPL], 0,
        lambda p: json.loads(p.stdout)["byte_identical"])
    run("wii-to-de reproduces the release save", ["wii-to-de", "--wii", W1, "--template", TPL, "--slot", "01",
                                                  "--out", o("w2d")], 0,
        lambda p: sha(os.path.join(o("w2d"), "save_0", "bfsgame01.sav")) == RC_USER_SHA)
    run("de-to-wii with sidecar, unchanged -> original Wii file",
        ["de-to-wii", "--de", os.path.join(o("w2d"), "save_0", "bfsgame01.sav"), "--sidecar",
         os.path.join(o("w2d"), "wii_to_de.sidecar.json"), "--current-wii", W1, "--out", o("d2w")], 0,
        lambda p: sha(os.path.join(o("d2w"), "monado01")) == sha(W1))
    run("wii-to-de re-import, unchanged -> original DE file",
        ["wii-to-de", "--wii", os.path.join(o("d2w"), "monado01"), "--sidecar",
         os.path.join(o("d2w"), "de_to_wii.sidecar.json"), "--current-de",
         os.path.join(o("w2d"), "save_0", "bfsgame01.sav"), "--slot", "01", "--out", o("back")], 0,
        lambda p: sha(os.path.join(o("back"), "save_0", "bfsgame01.sav")) == RC_USER_SHA)
    run("dry run writes nothing", ["wii-to-de", "--wii", W1, "--template", TPL, "--dry-run", "--out", o("dry")], 0,
        lambda p: not os.path.exists(o("dry")))
    run("live path refused", ["wii-to-de", "--wii", W1, "--template", TPL, "--out",
                              os.path.join(base, "Dolphin", "User", "Wii", "x")], 2,
        lambda p: not os.path.exists(os.path.join(base, "Dolphin")))
    bare = os.path.join(base, "bare", "converter")
    shutil.copytree(conv, bare)
    run("no tables -> clear refusal", ["inspect", W1], 2, lambda p: "game tables not found" in p.stderr, at=bare)
    hits = []
    for dp, _, fs in os.walk(conv):
        for f in fs:
            if f.endswith((".py", ".md", ".txt", ".cmd", ".json")):
                with open(os.path.join(dp, f), encoding="utf-8", errors="replace") as fh:
                    t = fh.read()
                for needle in ("XC_Wii_to_DE_Research", "C:\\Users\\lawma", "Quiver Launcher\\Apps\\Xeno"):
                    if needle in t and not f.startswith("test_"):
                        hits.append((os.path.relpath(os.path.join(dp, f), conv), needle))
    res["research_paths_in_package_code"] = hits
    game_data = [os.path.relpath(os.path.join(dp, f), conv) for dp, _, fs in os.walk(conv) for f in fs
                 if f.endswith((".sav", ".json")) and ("bdat" in f or f.startswith(("monado", "bfs")))]
    res["game_data_or_saves_in_package"] = game_data
    res["all_pass"] = all(c["pass"] for c in res["checks"]) and not game_data
    out = os.path.join(P2F, "results", "package_test.json")
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({"all_pass": res["all_pass"], "checks": [(c["name"], c["pass"]) for c in res["checks"]],
                      "research_paths": hits, "game_data": game_data}, indent=1))
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
