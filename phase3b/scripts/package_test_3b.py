"""Phase 3B clean-directory test of the packaged application: the Sync Hub (window automation and xcsync.exe).
The unchanged 3A package test (phase3a/scripts/package_test_3a.py) is run separately against the same build.

  python phase3b\\scripts\\package_test_3b.py <portable folder> <clean test root> <result json>

The portable folder is copied to <clean root>\\app. Inputs are COPIES of fixtures in <clean root>\\inputs; the user's
tables are copied to <clean root>\\mydata (as a user selects them on first run). Programs run with Python removed
from PATH and no PYTHON*/QT_* variables. Generations made by the packaged programs are compared byte for byte with
the same steps run from source (python phase3b/src/xcsync_cli.py).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P3B = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3B)
FX3B = os.path.join(P3B, "fixtures")
FIXTURES = {
    "wii_user_s150": os.path.join(ROOT, "phase3a", "fixtures", "wii_user_s150.bin"),
    "wii_later": os.path.join(ROOT, "work", "phase2e", "dolphin", "d6_travel", "user", "Wii", "title", "00010000",
                              "53583445", "data", "monado01"),
    "de_template": os.path.join(ROOT, "work", "template", "bfsgame00.sav"),
    "de_template_tmb": os.path.join(ROOT, "work", "template", "bfsgame00.tmb"),
    "de_template_sys": os.path.join(ROOT, "work", "template", "bfssystem.sav"),
    "x3_01": os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado01"),
    "x3_02": os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado02"),
    "x3_03": os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado03"),
    "de_walked": os.path.join(FX3B, "de_monado_walked.sav"),
    "x3_battle": os.path.join(FX3B, "x3_azahar_battle_monado01"),
}
GAME_DATA_PATTERNS = (".rvz", ".iso", ".wbfs", ".3ds", ".cia", ".nsp", ".xci", ".sav", ".tmb", "bdat_", "monado0",
                      ".bdat", "keys", "prod.keys")


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


def clean_env(data=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "XCCONV", "PIP", "VIRTUAL_ENV",
                                                                              "QT_"))}
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p and "python" not in p.lower())
    if data:
        env["XCCONV_DATA"] = data
    return env


def main(portable, root, result_path):
    t0 = time.time()
    portable, root, result_path = (os.path.abspath(p) for p in (portable, root, result_path))
    if os.path.exists(root):
        shutil.rmtree(root)
    app = os.path.join(root, "app", "XCSaveConverter")
    shutil.copytree(portable, app)
    inp = os.path.join(root, "inputs")
    os.makedirs(os.path.join(inp, "x3"))
    os.makedirs(os.path.join(inp, "de"))
    for k, p in FIXTURES.items():
        dst = {"x3_01": "x3/monado01", "x3_02": "x3/monado02", "x3_03": "x3/monado03",
               "de_template": "de/bfsgame00.sav", "de_template_tmb": "de/bfsgame00.tmb",
               "de_template_sys": "de/bfssystem.sav"}.get(k, k)
        shutil.copyfile(p, os.path.join(inp, *dst.split("/")))
    inputs_before = tree(inp)
    data = os.path.join(root, "mydata")
    os.makedirs(data)
    for n in ("bdat_wii.json", "bdat_de.json"):
        shutil.copyfile(os.path.join(ROOT, "data", n), os.path.join(data, n))
    app_before = tree(app)
    env = clean_env()
    gui = os.path.join(app, "XCSaveConverter.exe")
    xs_exe = os.path.join(app, "xcsync.exe")
    res = {"portable": portable, "clean_root": root, "checks": [],
           "path_has_python": any("python" in p.lower() for p in env["PATH"].split(os.pathsep))}

    def check(name, ok, **detail):
        res["checks"].append({"name": name, "ok": bool(ok), **detail})
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    def run(cmd, data_env=True, cwd=root, timeout=900):
        return subprocess.run(cmd, cwd=cwd, env=clean_env(data if data_env else None), capture_output=True,
                              text=True, timeout=timeout)

    # ---- start-up
    out = os.path.join(root, "smoke.json")
    r = run([gui, "--smoke", out], data_env=False)
    s = json.load(open(out)) if os.path.isfile(out) else {}
    check("window starts without Python (Sync Hub tab first, welcome page without a hub)",
          r.returncode == 0 and s.get("frozen") and s.get("tabs") == ["&Sync Hub", "&Convert one save"] and
          s.get("hub_page") == 0, smoke=s)
    for scale in ("1.5", "2"):
        o2 = os.path.join(root, f"smoke_{scale}.json")
        e = clean_env()
        e["QT_SCALE_FACTOR"] = scale
        r = subprocess.run([gui, "--smoke", o2], cwd=root, env=e, capture_output=True, text=True, timeout=300)
        si = json.load(open(o2)) if os.path.isfile(o2) else {}
        check(f"window starts at scale {scale}", r.returncode == 0 and abs(si.get("dpr", 0) - float(scale)) < 0.01,
              dpr=si.get("dpr"))
    r = run([xs_exe, "--help"])
    check("xcsync.exe --help", r.returncode == 0 and all(c in r.stdout for c in ("scan", "sync", "rollback")))

    # ---- hub made with xcsync.exe, and the same steps from source (byte parity)
    def build(hubroot, exe):
        cmd = exe if isinstance(exe, list) else [exe]
        steps = []
        steps.append(run(cmd + ["init", hubroot]))
        devs = {}
        for name, plat in (("Windows desktop", "de"), ("Odin 2 Mini", "wii"), ("New 3DS", "3ds")):
            inc = os.path.join(os.path.dirname(hubroot), "st", name.replace(" ", "_"))
            os.makedirs(inc, exist_ok=True)
            devs[name] = inc
            steps.append(run(cmd + ["device-add", hubroot, "--name", name, "--platform", plat, "--incoming", inc]))
        steps.append(run(cmd + ["template", hubroot, "de", os.path.join(inp, "de", "bfsgame00.sav")]))
        steps.append(run(cmd + ["template", hubroot, "3ds", os.path.join(inp, "x3", "monado01")]))
        shutil.copyfile(os.path.join(inp, "wii_user_s150"), os.path.join(devs["Odin 2 Mini"], "monado01"))
        old = time.time() - 60
        os.utime(os.path.join(devs["Odin 2 Mini"], "monado01"), (old, old))
        steps.append(run(cmd + ["scan", hubroot]))
        steps.append(run(cmd + ["sync", hubroot]))
        return steps, devs

    hub = os.path.join(root, "packaged", "Xenoblade Sync")
    steps, devs = build(hub, xs_exe)
    check("xcsync.exe: init, devices, templates", all(p.returncode == 0 for p in steps[:6]),
          errors=[p.stderr[-300:] for p in steps[:6] if p.returncode])
    check("xcsync.exe: startup scan finds the starting save", steps[6].returncode == 0 and
          "Ready to start syncing from Odin 2 Mini" in steps[6].stdout, out=steps[6].stdout[-500:])
    check("xcsync.exe: Sync All -> all platforms", steps[7].returncode == 0 and
          "All configured platforms updated." in steps[7].stdout, out=steps[7].stdout[-500:], err=steps[7].stderr[-500:])
    src_hub = os.path.join(root, "source", "Xenoblade Sync")
    build(src_hub, [sys.executable, os.path.join(P3B, "src", "xcsync_cli.py")])
    g_pk = os.path.join(hub, "history", "gen-000001", "outputs")
    g_sr = os.path.join(src_hub, "history", "gen-000001", "outputs")
    check("packaged generation identical to the source run (every output file)",
          os.path.isdir(g_pk) and tree(g_pk) == tree(g_sr))

    # ---- the window on that hub
    def auto(step, **job):
        d = os.path.join(root, "gui", step)
        os.makedirs(d)
        job.update(hub=hub, data_dir=data, settings=os.path.join(d, "s.ini"), result=os.path.join(d, "r.json"),
                   screenshot=os.path.join(d, "window.png"))
        jp = os.path.join(d, "job.json")
        json.dump(job, open(jp, "w"))
        p = subprocess.run([gui, "--sync-automate", jp], cwd=root, env=clean_env(), capture_output=True, text=True,
                           timeout=900)
        r_ = json.load(open(job["result"])) if os.path.isfile(job["result"]) else {}
        r_["rc"] = p.returncode
        return r_

    before = tree(os.path.join(root, "packaged"))
    a = auto("a_in_sync")
    check("window: automatic startup scan, all in sync, Sync disabled", a.get("ok") and
          a["scan"]["decision"] == "in-sync" and not a["sync_enabled"], scan=a.get("scan"))
    check("window scan is read-only (hub and device folders unchanged)", tree(os.path.join(root, "packaged")) == before)
    shutil.copyfile(os.path.join(inp, "de_walked"), os.path.join(devs["Windows desktop"], "bfsgame00.sav"))
    old = time.time() - 60
    os.utime(os.path.join(devs["Windows desktop"], "bfsgame00.sav"), (old, old))
    b = auto("b_new_progress", sync=True)
    check("window: new progress on Windows desktop (Monado-written save) -> Sync All -> all platforms",
          b.get("ok") and b["scan"]["decision"] == "new-progress" and b.get("source_shown", {}).get("device") ==
          "Windows desktop" and b.get("complete") and b.get("result_title") == "All configured platforms updated.",
          result={k: b.get(k) for k in ("scan", "source_shown", "result_title", "complete", "exception")})
    for k, n in (("wii_later", os.path.join(devs["Odin 2 Mini"], "monado02")),
                 ("x3_battle", os.path.join(devs["New 3DS"], "monado01"))):
        shutil.copyfile(os.path.join(inp, k), n)
        os.utime(n, (old, old))
    c = auto("c_conflict_no_choice", sync=True)
    check("window: two branches -> conflict, Sync stays disabled without a choice",
          c.get("ok") and c["scan"]["decision"] == "conflict" and not c["sync_enabled"] and not c.get("generation"),
          scan=c.get("scan"))
    d_ = auto("d_conflict_choose", sync=True, choose="New_3DS")
    check("window: explicit choice (New 3DS) -> Sync All -> generation 3",
          d_.get("ok") and d_.get("generation") == 3 and d_.get("complete"), result=d_.get("message"))
    e = auto("e_rollback", rollback=2)
    check("window: rollback to generation 2 -> generation 4", e.get("ok") and e.get("generation") == 4 and
          e.get("complete"), result=e.get("message"))
    r = run([xs_exe, "history", hub])
    check("xcsync.exe history lists the 4 generations", r.returncode == 0 and r.stdout.count("\n") >= 4 and
          "rollback" in r.stdout, out=r.stdout[-800:])
    gen3 = json.load(open(os.path.join(hub, "history", "gen-000003", "generation.json")))
    check("unselected branch kept as a recoverable snapshot",
          any(not s_["chosen"] and s_["device_name"] == "Odin 2 Mini" for s_ in gen3["snapshots"]))

    # ---- hygiene
    names = [n.lower() for n in tree(app)]
    bad = [n for n in names if any(p in os.path.basename(n) for p in GAME_DATA_PATTERNS)]
    check("no game data, saves or keys in the portable folder", not bad, found=bad[:10])
    check("inputs unchanged", tree(inp) == inputs_before)
    check("portable folder unchanged by running it", tree(app) == app_before)
    res["seconds"] = round(time.time() - t0)
    res["passed"] = sum(c_["ok"] for c_ in res["checks"])
    res["total"] = len(res["checks"])
    json.dump(res, open(result_path, "w"), indent=1)
    print(f"{res['passed']}/{res['total']} checks passed in {res['seconds']} s")
    return 0 if res["passed"] == res["total"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
