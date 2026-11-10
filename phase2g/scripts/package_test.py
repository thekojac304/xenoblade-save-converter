"""Phase 2G clean-directory test of the packaged application.

  python phase2g\\scripts\\package_test.py <portable folder> <clean test root> <result json>

The portable folder is copied to <clean test root>\\app (outside the research workspace). Inputs are COPIES of the
fixtures, in <clean test root>\\inputs; the user's tables are copied to <clean test root>\\mydata (they stand in for the
tables a user selects on first run). Every program runs with Python removed from PATH, no PYTHON* variables, no
XCCONV_DATA, and the clean root as working directory. Results are compared byte for byte with the research CLI
(python tools\\xcconv.py) given the same absolute inputs.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
O = os.path.join(ROOT, "work", "originals")
TPL_DIR = os.path.join(ROOT, "work", "template")
RELEASE_2F_SAVE = os.path.join(ROOT, "release_candidate_2F", "user_saves", "wii_to_de_monado01", "save_0",
                               "bfsgame01.sav")
USER_SHA = "1028f718c0c567e75e03184492287b20b5f78b8280b7e0d70ba1eecc943673b2"


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def tree(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            out[os.path.relpath(p, d).replace("\\", "/")] = sha(p)
    return out


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "XCCONV", "PIP", "VIRTUAL_ENV",
                                                                              "QT_"))}
    keep = [p for p in env.get("PATH", "").split(os.pathsep) if p and "python" not in p.lower()]
    env["PATH"] = os.pathsep.join(keep)
    return env


def main(portable, root, result_path):
    t0 = time.time()
    if os.path.exists(root):
        shutil.rmtree(root)
    app = os.path.join(root, "app", "XCSaveConverter")
    shutil.copytree(portable, app)
    inp = os.path.join(root, "inputs")
    os.makedirs(inp)
    for n in ("monado01", "monado03", "user_v10_bfsgame00.sav"):
        shutil.copyfile(os.path.join(O, n), os.path.join(inp, n))
    os.makedirs(os.path.join(inp, "template"))
    for n in ("bfsgame00.sav", "bfsgame00.tmb", "bfssystem.sav"):
        shutil.copyfile(os.path.join(TPL_DIR, n), os.path.join(inp, "template", n))
    data = os.path.join(root, "mydata")
    os.makedirs(data)
    for n in ("bdat_wii.json", "bdat_de.json"):
        shutil.copyfile(os.path.join(ROOT, "data", n), os.path.join(data, n))
    app_before = tree(app)
    env = clean_env()
    gui = os.path.join(app, "XCSaveConverter.exe")
    cli = os.path.join(app, "xcconv.exe")
    res = {"portable": portable, "clean_root": root, "path_has_python": any("python" in p.lower() for p in
                                                                             env["PATH"].split(os.pathsep)),
           "checks": []}

    def check(name, ok, **detail):
        res["checks"].append({"name": name, "ok": bool(ok), **detail})
        print(("PASS " if ok else "FAIL ") + name, detail if not ok else "")

    def run(args, timeout=300, extra_env=None):
        e = dict(env, **(extra_env or {}))
        return subprocess.run(args, cwd=root, env=e, capture_output=True, text=True, timeout=timeout)

    def research_cli(*args):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "xcconv.py"), *args], capture_output=True,
                           text=True, env=dict(os.environ, XCCONV_DATA=os.path.join(ROOT, "data")))
        return r.returncode

    def automate(name, **job):
        d = os.path.join(root, "jobs", name)
        os.makedirs(d, exist_ok=True)
        job.setdefault("data_dir", data)
        job.setdefault("output_parent", os.path.join(root, "gui_out"))
        job["settings"] = os.path.join(d, "settings.ini")
        job["result"] = os.path.join(d, "result.json")
        with open(os.path.join(d, "job.json"), "w", encoding="utf-8") as f:
            json.dump(job, f, indent=1)
        r = run([gui, "--automate", os.path.join(d, "job.json")])
        with open(job["result"], encoding="utf-8") as f:
            out = json.load(f)
        out["rc"] = r.returncode
        return out

    # 1. first start without game data: no blocking dialog, set-up banner, bundled specs found
    smoke = os.path.join(root, "smoke", "smoke.json")
    os.makedirs(os.path.dirname(smoke))
    r = run([gui, "--smoke", smoke], timeout=120)
    s = json.load(open(smoke, encoding="utf-8")) if os.path.exists(smoke) else {}
    check("gui starts without Python and without game data (no blocking dialog)",
          r.returncode == 0 and s.get("frozen") and s.get("data_banner") and s.get("spec_found"), smoke=s,
          rc=r.returncode)
    check("gui runs from the clean copy", s.get("executable", "").lower().startswith(app.lower()))

    # 2. CLI basics
    r = run([cli, "--help"])
    check("xcconv.exe --help", r.returncode == 0 and "wii-to-de" in r.stdout)
    r = run([cli, "validate", os.path.join(inp, "monado01")], extra_env={"XCCONV_DATA": data})
    check("xcconv.exe validate", r.returncode == 0 and '"ok": true' in r.stdout, rc=r.returncode, err=r.stderr[-300:])
    r = run([cli, "inspect", os.path.join(inp, "monado01")])
    check("xcconv.exe without tables refuses clearly", r.returncode == 2 and "game tables not found" in r.stderr,
          rc=r.returncode)
    r = run([cli, "wii-to-de", "--wii", os.path.join(inp, "monado01"), "--template",
             os.path.join(inp, "template", "bfsgame00.sav"), "--out",
             r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save\x"],
            extra_env={"XCCONV_DATA": data})
    check("xcconv.exe refuses a live output folder", r.returncode == 2 and "nothing was written" in r.stderr)

    # 3. GUI Wii -> DE (first export) vs research CLI
    w01 = os.path.join(inp, "monado01")
    tpl = os.path.join(inp, "template", "bfsgame00.sav")
    a = automate("w2d", source=w01, starting_save=tpl, slot="01")
    ref = os.path.join(root, "cli_ref", "w2d")
    rc = research_cli("wii-to-de", "--wii", w01, "--template", tpl, "--out", ref, "--slot", "01")
    check("GUI Wii -> DE succeeds", a.get("ok") and a["rc"] == 0, result=a)
    check("GUI Wii -> DE identical to CLI (all files)", a.get("ok") and rc == 0 and tree(a["out_dir"]) == tree(ref))
    check("GUI Wii -> DE save is the validated 2F save", a.get("ok") and sha(a["main_output"]) == USER_SHA ==
          sha(RELEASE_2F_SAVE))
    check("preview shown", a.get("preview", {}).get("location") == "Eryth Sea (ma1001)", preview=a.get("preview"))

    # 4. GUI DE -> Wii back (sidecar found automatically) vs packaged CLI
    if a.get("ok"):
        de1 = a["main_output"]
        b = automate("d2w_return", source=de1, returning=True, current=w01)
        ref = os.path.join(root, "cli_ref", "d2w")
        r = run([cli, "de-to-wii", "--de", de1, "--sidecar", os.path.join(a["out_dir"], "wii_to_de.sidecar.json"),
                 "--current-wii", w01, "--out", ref], extra_env={"XCCONV_DATA": data})
        check("GUI DE -> Wii found the sidecar automatically",
              b.get("sidecar_auto") == os.path.join(a["out_dir"], "wii_to_de.sidecar.json"), auto=b.get("sidecar_auto"))
        check("GUI DE -> Wii identical to packaged CLI", b.get("ok") and r.returncode == 0 and
              tree(b["out_dir"]) == tree(ref), rc=r.returncode)
        # 5. back to DE: byte-identical restore
        if b.get("ok"):
            c = automate("w2d_return", source=b["main_output"], returning=True, current=de1, slot="01")
            check("GUI Wii -> DE return restores the DE save byte for byte",
                  c.get("ok") and sha(c["main_output"]) == sha(de1))

    # 6. DE-native export vs research CLI
    de = os.path.join(inp, "user_v10_bfsgame00.sav")
    base = os.path.join(inp, "monado03")
    d = automate("d2w_first", source=de, starting_save=base)
    ref = os.path.join(root, "cli_ref", "d2w_first")
    rc = research_cli("de-to-wii", "--de", de, "--base", base, "--out", ref)
    check("GUI DE -> Wii (first export) identical to CLI", d.get("ok") and rc == 0 and tree(d["out_dir"]) == tree(ref))

    # 7. wrong input refused before converting: a Wii save offered as the DE starting save
    e = automate("refusal", source=w01, starting_save=os.path.join(inp, "monado03"))
    check("GUI refuses wrong inputs before converting", not e.get("ok") and e.get("missing"), missing=e.get("missing"))

    # 8. dry run writes nothing
    f = automate("dry", source=w01, starting_save=tpl, dry_run=True, output_parent=os.path.join(root, "dry_out"))
    check("GUI check-only run writes nothing", f.get("ok") and f.get("dry_run") and
          not os.path.exists(os.path.join(root, "dry_out")))

    # 9. inputs and the app folder unchanged
    check("inputs unchanged", all(sha(os.path.join(inp, n)) == sha(os.path.join(O, n))
                                  for n in ("monado01", "monado03", "user_v10_bfsgame00.sav")))
    check("portable folder unchanged by running it", tree(app) == app_before)
    res["seconds"] = round(time.time() - t0, 1)
    res["passed"] = sum(c["ok"] for c in res["checks"])
    res["total"] = len(res["checks"])
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(f"{res['passed']}/{res['total']} passed in {res['seconds']} s")
    return 0 if res["passed"] == res["total"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
