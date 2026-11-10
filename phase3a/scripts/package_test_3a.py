"""Phase 3A clean-directory test of the packaged application (all Phase 2H checks + New 3DS checks).

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
P3 = os.path.join(ROOT, "phase3a")
X3_DIR = os.path.join(P3, "originals", "azahar_live", "00000001")      # copy of the user's own 3DS save archive


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
    os.makedirs(os.path.join(inp, "3ds"))
    for n in ("monado01", "monado02", "monado03"):
        shutil.copyfile(os.path.join(X3_DIR, n), os.path.join(inp, "3ds", n))
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

    def research_cli3(*args):
        r = subprocess.run([sys.executable, os.path.join(P3, "src", "xcconv3.py"), *args], capture_output=True,
                           text=True, env=dict(os.environ, XCCONV_DATA=os.path.join(ROOT, "data")))
        return r.returncode

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

    # 1. first start without game data: no blocking dialog, set-up notice, bundled specs found
    smoke = os.path.join(root, "smoke", "smoke.json")
    os.makedirs(os.path.dirname(smoke))
    r = run([gui, "--smoke", smoke], timeout=120)
    s = json.load(open(smoke, encoding="utf-8")) if os.path.exists(smoke) else {}
    check("gui starts without Python and without game data (no blocking dialog)",
          r.returncode == 0 and s.get("frozen") and s.get("setup_notice") and s.get("spec_found"), smoke=s,
          rc=r.returncode)
    check("gui runs from the clean copy", s.get("executable", "").lower().startswith(app.lower()))
    for scale in ("1.5", "2"):
        sm = os.path.join(root, "smoke", f"smoke_{scale}.json")
        r = run([gui, "--smoke", sm], timeout=120, extra_env={"QT_SCALE_FACTOR": scale})
        si = json.load(open(sm, encoding="utf-8")) if os.path.exists(sm) else {}
        check(f"gui starts at scale {scale}", r.returncode == 0 and abs(si.get("dpr", 0) - float(scale)) < 0.01,
              smoke=si)

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

    # 3. GUI Wii -> DE (first conversion) vs research CLI
    w01 = os.path.join(inp, "monado01")
    tpl = os.path.join(inp, "template", "bfsgame00.sav")
    a = automate("w2d", source=w01, dest=tpl)
    ref = os.path.join(root, "cli_ref", "w2d")
    rc = research_cli("wii-to-de", "--wii", w01, "--template", tpl, "--out", ref, "--slot", "01")
    check("GUI Wii -> DE succeeds (first conversion detected)", a.get("ok") and a["rc"] == 0 and
          a["plan"]["mode"] == "first" and a["file_name"] == "bfsgame01.sav", result=a)
    check("GUI Wii -> DE identical to CLI (all files)", a.get("ok") and rc == 0 and tree(a["out_dir"]) == tree(ref))
    check("GUI Wii -> DE save is the validated 2F save", a.get("ok") and sha(a["main_output"]) == USER_SHA ==
          sha(RELEASE_2F_SAVE))
    check("preview shown", "Eryth Sea" in a.get("source_preview", ""), preview=a.get("source_preview"))

    # 4. GUI DE -> Wii back (history found automatically) vs packaged CLI
    if a.get("ok"):
        de1 = a["main_output"]
        b = automate("d2w_return", source=de1, dest=w01)
        ref = os.path.join(root, "cli_ref", "d2w")
        r = run([cli, "de-to-wii", "--de", de1, "--sidecar", a["sidecar"], "--current-wii", w01,
                 "--slot", b.get("file_name", "?"), "--out", ref], extra_env={"XCCONV_DATA": data})
        check("GUI DE -> Wii found the conversion history automatically",
              (b.get("plan") or {}).get("record") == a["sidecar"], plan=b.get("plan"))
        check("GUI DE -> Wii identical to packaged CLI", b.get("ok") and r.returncode == 0 and
              tree(b["out_dir"]) == tree(ref), rc=r.returncode, err=r.stderr[-300:])
        # 5. back to DE: byte-identical restore
        if b.get("ok"):
            c = automate("w2d_return", source=b["main_output"], dest=de1)
            check("GUI Wii -> DE return restores the DE save byte for byte",
                  c.get("ok") and c["plan"]["mode"] == "return" and sha(c["main_output"]) == sha(de1))

    # 6. DE-native export vs research CLI
    de = os.path.join(inp, "user_v10_bfsgame00.sav")
    base = os.path.join(inp, "monado03")
    d = automate("d2w_first", source=de, dest=base)
    ref = os.path.join(root, "cli_ref", "d2w_first")
    rc = research_cli("de-to-wii", "--de", de, "--base", base, "--out", ref, "--slot", d.get("file_name", "?"))
    check("GUI DE -> Wii (first conversion) identical to CLI", d.get("ok") and rc == 0 and
          tree(d["out_dir"]) == tree(ref))

    # 7. wrong input refused before converting: a Wii save offered as the DE destination save
    e = automate("refusal", source=w01, dest=os.path.join(inp, "monado03"))
    check("GUI refuses wrong inputs before converting", not e.get("ok") and e.get("missing"), missing=e.get("missing"))

    # 8. dry run writes nothing
    f = automate("dry", source=w01, dest=tpl, dry_run=True, output_parent=os.path.join(root, "dry_out"))
    check("GUI check-only run writes nothing", f.get("ok") and f.get("dry_run") and
          not os.path.exists(os.path.join(root, "dry_out")))

    # 3A. New 3DS
    x3 = os.path.join(inp, "3ds", "monado01")
    r = run([cli, "--help"])
    check("xcconv.exe --help lists the 3DS commands", r.returncode == 0 and "wii-to-3ds" in r.stdout and
          "3ds-to-de" in r.stdout)
    r = run([cli, "validate", x3], extra_env={"XCCONV_DATA": data})
    check("xcconv.exe validate (3DS save)", r.returncode == 0 and '"ok": true' in r.stdout, rc=r.returncode,
          err=r.stderr[-300:])
    r = run([cli, "wii-to-3ds", "--wii", w01, "--template", x3, "--out",
             os.path.join(os.environ.get("APPDATA", ""), "Azahar", "sdmc", "xcconv_test")], extra_env={"XCCONV_DATA": data})
    check("xcconv.exe refuses a live 3DS save folder", r.returncode == 2 and "nothing was written" in r.stderr,
          rc=r.returncode)
    o3 = os.path.join(root, "gui_out_3ds")                  # the 3DS jobs: first conversions in their own folder
    g = automate("w2x", source=w01, dest=x3, output_parent=o3)
    ref = os.path.join(root, "cli_ref", "w2x")
    rc = research_cli3("wii-to-3ds", "--wii", w01, "--template", x3, "--out", ref, "--slot", g.get("file_name", "?")[-1:])
    check("GUI Wii -> 3DS succeeds", g.get("ok") and g.get("direction") == "wii_to_3ds" and
          g["file_name"] == "monado02", result=g)
    check("GUI Wii -> 3DS identical to research CLI (all files)", g.get("ok") and rc == 0 and tree(g["out_dir"]) == tree(ref))
    check("Wii -> 3DS output includes a complete Checkpoint-style archive", g.get("ok") and
          any(k.startswith("checkpoint/") for k in tree(g["out_dir"])))
    if g.get("ok"):
        h = automate("x2w_return", source=g["main_output"], dest=w01, output_parent=o3)
        check("GUI 3DS -> Wii found the conversion record automatically",
              (h.get("plan") or {}).get("record") == g["sidecar"], plan=h.get("plan"))
        check("GUI 3DS -> Wii return gives the Wii save back byte for byte", h.get("ok") and
              sha(h["main_output"]) == sha(w01))
    k = automate("x2w_nodest", source=x3, target="wii", output_parent=os.path.join(root, "gui_out_3ds_b"))
    ref = os.path.join(root, "cli_ref", "x2w")
    r = run([cli, "3ds-to-wii", "--3ds", x3, "--out", ref, "--slot", k.get("file_name", "?")], extra_env={"XCCONV_DATA": data})
    check("GUI 3DS -> Wii without a destination save identical to packaged CLI", k.get("ok") and r.returncode == 0 and
          tree(k["out_dir"]) == tree(ref), rc=r.returncode, err=r.stderr[-300:])
    m = automate("d2x", source=tpl, dest=x3, output_parent=os.path.join(root, "gui_out_3ds_c"))
    if m.get("ok"):
        n = automate("x2d_return", source=m["main_output"], dest=tpl, output_parent=os.path.join(root, "gui_out_3ds_c"))
        check("GUI DE -> 3DS -> DE returns the DE save byte for byte", n.get("ok") and
              (n.get("plan") or {}).get("mode") == "return" and sha(n["main_output"]) == sha(tpl))
    else:
        check("GUI DE -> 3DS succeeds", False, result=m)
    q = automate("x2d_first", source=x3, dest=tpl, output_parent=os.path.join(root, "gui_out_3ds_d"))
    ref = os.path.join(root, "cli_ref", "x2d")
    rc = research_cli3("3ds-to-de", "--3ds", x3, "--template", tpl, "--out", ref, "--slot", q.get("file_name", "?")[7:9])
    check("GUI 3DS -> DE identical to research CLI", q.get("ok") and rc == 0 and tree(q["out_dir"]) == tree(ref))
    e3 = automate("x_empty", source=os.path.join(inp, "3ds", "monado02"), target="wii")
    check("GUI refuses an empty 3DS slot", not e3.get("ok") and e3.get("missing"), missing=e3.get("missing"))

    # 9. inputs and the app folder unchanged
    check("inputs unchanged", all(sha(os.path.join(inp, n)) == sha(os.path.join(O, n))
                                  for n in ("monado01", "monado03", "user_v10_bfsgame00.sav")) and
          all(sha(os.path.join(inp, "3ds", n)) == sha(os.path.join(X3_DIR, n)) for n in ("monado01", "monado02", "monado03")))
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
