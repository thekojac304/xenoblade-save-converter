"""Isolated Monado (XC1 DE recompilation) test runner for Phase 2E gameplay validation.

Every run gets its own folder under work/phase2e/monado/<name>/ holding a *copy* of the save to test, the game's
stderr, captures and a run manifest. The live profile is never used:
  - LARECOMP_SAVE_DIR points at the run folder, XCDE_SAVE_JOURNAL_OFF=1, XCDE_SAVE_BACKUPS=0;
  - XCDE_INI points at a copy of the user's xcde.ini (mouse look off) so the launcher's settings file is not touched;
  - the stderr log is watched: the first "[fs] mounted host directory" line must name <run>/save_0, otherwise the
    game is killed at once and the run is reported as an isolation failure;
  - the live save_0 folder is hashed before and after; any change is reported loudly.

  python monado_harness.py --name <run> --save <dir with bfsgame00.sav[,.tmb,bfssystem.sav]> --route <route.txt>
                           [--shots 3000,3600,...] [--tour <file>] [--env K=V ...] [--timeout 900]

Routes use the Monado input-replay format: "<frame> <buttons hex> <lx> <ly> <rx> <ry>" (A=1 B=2 X=4 Y=8 L=40 R=80
ZL=100 ZR=200 Plus=400 Minus=800 Left=1000 Up=2000 Right=4000 Down=8000).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RUNS = os.path.join(ROOT, "work", "phase2e", "monado")
INSTALL = r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado"
EXE = os.path.join(INSTALL, "build", "xcde.exe")
LIVE = os.path.join(INSTALL, "save", "save_0")
SAVE_FILES = ("bfsgame00.sav", "bfsgame00.tmb", "bfssystem.sav")


class IsolationError(Exception):
    pass


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def hash_dir(d):
    return {f: sha(os.path.join(d, f)) for f in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, f))}


def test_ini():
    """Copy of the user's xcde.ini with mouse look off (replayed input must be the only input)."""
    os.makedirs(RUNS, exist_ok=True)
    dst = os.path.join(RUNS, "xcde_test.ini")
    lines = open(os.path.join(INSTALL, "xcde.ini"), encoding="utf-8").read().splitlines()
    out = []
    for ln in lines:
        k = ln.split("=")[0].strip()
        if k == "mouse_look":
            ln = "mouse_look = 0"
        elif k == "show_fps":
            ln = "show_fps = 1"
        out.append(ln)
    open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return dst


def run(name, save, route=None, shots=(), tour=None, env_extra=(), timeout=900, exit_after_shots=True):
    run_dir = os.path.join(RUNS, name)
    if os.path.exists(run_dir):
        raise SystemExit(f"run folder exists: {run_dir}")
    save_dir = os.path.join(run_dir, "save_0")
    shot_dir = os.path.join(run_dir, "shots")
    os.makedirs(save_dir)
    os.makedirs(shot_dir)
    src_dir = save if os.path.isdir(save) else os.path.dirname(save)
    for f in SAVE_FILES:
        p = os.path.join(src_dir, f) if os.path.isdir(save) or f != "bfsgame00.sav" else save
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(save_dir, f))
    if not os.path.exists(os.path.join(save_dir, "bfsgame00.sav")):
        raise SystemExit("no bfsgame00.sav to test")
    live_before = hash_dir(LIVE)
    env = dict(os.environ)
    env.update(LARECOMP_SAVE_DIR=run_dir, XCDE_SAVE_JOURNAL_OFF="1", XCDE_SAVE_BACKUPS="0", XCDE_INI=test_ini())
    if route:
        env["XCDE_INPUT_REPLAY"] = os.path.abspath(route)
    if shots:
        env["XCDE_SHOTS"] = ",".join(f"{f}:{os.path.join(shot_dir, f'f{f}.png')}" for f in shots)
        if exit_after_shots:
            env["XCDE_EXIT_AFTER_SHOTS"] = "1"
    if tour:
        env["XCDE_TOUR"] = os.path.abspath(tour)
    for kv in env_extra:
        k, v = kv.split("=", 1)
        env[k] = v
    manifest = {"name": name, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "save_in": {f: sha(os.path.join(save_dir, f))
                for f in os.listdir(save_dir)}, "route": route and [route, sha(route)], "tour": tour and [tour, sha(tour)],
                "shots": list(shots), "env": {k: env[k] for k in env if k.startswith(("XCDE_", "LARECOMP_"))}}
    log_path = os.path.join(run_dir, "stderr.log")
    t0 = time.time()
    with open(log_path, "wb") as log:
        p = subprocess.Popen([EXE, "targets"], cwd=INSTALL, env=env, stdout=log, stderr=subprocess.STDOUT)
        mounted, status = None, "running"
        try:
            while True:
                rc = p.poll()
                txt = open(log_path, "rb").read().decode("utf-8", "replace")
                for ln in txt.splitlines():
                    if ln.startswith("[fs] mounted host directory"):
                        path = ln.split("directory", 1)[1].strip()
                        if mounted is None:
                            mounted = path
                        if os.path.normcase(os.path.normpath(path.replace("/", os.sep))) != os.path.normcase(save_dir):
                            p.kill()
                            raise IsolationError(f"game mounted {path}, expected {save_dir}")
                if rc is not None:
                    status = f"exited rc={rc}"
                    break
                if mounted is None and time.time() - t0 > 120:
                    p.kill()
                    status = "killed: no mount line within 120 s"
                    break
                if time.time() - t0 > timeout:
                    p.kill()
                    status = f"killed: timeout {timeout} s"
                    break
                time.sleep(2)
        except IsolationError as e:
            status = f"ISOLATION FAILURE: {e}"
        finally:
            if p.poll() is None:
                p.kill()
            p.wait(30)
    live_after = hash_dir(LIVE)
    manifest.update(status=status, seconds=round(time.time() - t0), mounted=mounted,
                    live_unchanged=live_before == live_after, live_hashes=live_after,
                    save_out={f: sha(os.path.join(save_dir, f)) for f in os.listdir(save_dir)},
                    shots_written=sorted(os.listdir(shot_dir)))
    manifest["save_changed"] = manifest["save_out"].get("bfsgame00.sav") != manifest["save_in"].get("bfsgame00.sav")
    json.dump(manifest, open(os.path.join(run_dir, "run_manifest.json"), "w"), indent=1)
    if not manifest["live_unchanged"]:
        print("!!! LIVE SAVE FOLDER CHANGED during the run !!!", file=sys.stderr)
    print(json.dumps({k: manifest[k] for k in ("name", "status", "seconds", "mounted", "live_unchanged", "save_changed",
                                               "shots_written")}, indent=1))
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--save", required=True)
    ap.add_argument("--route")
    ap.add_argument("--tour")
    ap.add_argument("--shots", default="")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--no-exit-after-shots", action="store_true")
    a = ap.parse_args()
    shots = [int(x) for x in a.shots.split(",") if x]
    m = run(a.name, a.save, a.route, shots, a.tour, a.env, a.timeout, not a.no_exit_after_shots)
    sys.exit(0 if m["live_unchanged"] and not m["status"].startswith(("ISOLATION", "killed: no mount")) else 2)


if __name__ == "__main__":
    main()
