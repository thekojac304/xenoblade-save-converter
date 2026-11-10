"""Phase 3B isolated emulator runs (Monado, Dolphin) for the Sync Hub acceptance cycle.

Same isolation as 2F/3A (tools/monado_harness, tools/dolphin_harness + the 2F Dolphin NANDRootPath/watchdog wrapper),
with run folders under phase3b/runs and, after every run, the 3B protected-file manifest (1226 files: originals,
live saves, emulator executables/configs, ROM/disc images, every earlier release candidate, Syncthing config).
Monado also gets a listing of its installation folder before/after (names, sizes, times), so any file the game
writes there (logs, shader cache) is reported.

  python erun3b.py monado <name> <save dir with bfsgame00.sav[,.tmb,bfssystem.sav]> <route script> [--timeout S]
  python erun3b.py dolphin <name> <wii save file> <droute script> [--timeout S]
"""
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
P3B = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3B)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "phase2f", "scripts"))
RUNS = os.path.join(P3B, "runs")


def protect(name):
    chk = subprocess.run([sys.executable, os.path.join(HERE, "protect3b.py"), "check", f"after_{name}"],
                         capture_output=True, text=True)
    return chk.returncode == 0, chk.stdout[-3000:]


def listing(d):
    out = {}
    for dp, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
                out[os.path.relpath(p, d)] = [st.st_size, int(st.st_mtime)]
            except OSError:
                pass
    return out


def monado(name, save, script, timeout=900):
    import monado_harness as mh
    import route
    mh.RUNS = os.path.join(RUNS, "monado")
    os.makedirs(mh.RUNS, exist_ok=True)
    rdir = os.path.join(RUNS, "routes")
    os.makedirs(rdir, exist_ok=True)
    rt = os.path.join(rdir, name + ".route")
    ev, shots = route.compile_script(open(script, encoding="utf-8").read().splitlines())
    with open(rt, "w", newline="\n") as fo:
        fo.write("# xcde input v1\n# compiled from %s\n" % os.path.basename(script))
        for e in ev:
            fo.write("%d %x %d %d %d %d\n" % e)
    inst_before = listing(mh.INSTALL)
    m = mh.run(name, save, rt, [s[0] for s in shots], None, (), timeout, True)
    inst_after = listing(mh.INSTALL)
    m["install_changes"] = {"added": sorted(set(inst_after) - set(inst_before)),
                            "removed": sorted(set(inst_before) - set(inst_after)),
                            "changed": sorted(k for k in inst_before if k in inst_after and
                                              inst_before[k] != inst_after[k])}
    m["protected_unchanged"], m["protect_report"] = protect(name)
    m["shot_labels"] = {f"f{s[0]}.png": s[1] for s in shots}
    json.dump(m, open(os.path.join(mh.RUNS, name, "run_manifest.json"), "w"), indent=1)
    print(json.dumps({k: m[k] for k in ("status", "live_unchanged", "save_changed", "protected_unchanged",
                                        "install_changes")}, indent=1))
    return 0 if m["protected_unchanged"] and m["live_unchanged"] and not m["status"].startswith("ISOLATION") else 3


def dolphin(name, wii, script, timeout=900):
    import drun                                     # the 2F wrapper: NANDRootPath + watchdog
    import droute
    dh = drun.dh
    dh.RUNS = os.path.join(RUNS, "dolphin")
    os.makedirs(dh.RUNS, exist_ok=True)
    rdir = os.path.join(RUNS, "droutes")
    os.makedirs(rdir, exist_ok=True)
    rt = os.path.join(rdir, name + ".route")
    ev = droute.compile_script(open(script, encoding="utf-8").read().splitlines())
    with open(rt, "w", newline="\n") as fo:
        for e in ev:
            fo.write(f"{e[0]} {e[1]}\n")
    before = dh.protected_hashes()
    stop = threading.Event()
    th = threading.Thread(target=drun.watchdog, args=(before, stop), daemon=True)
    th.start()
    try:
        m = dh.run(name, wii, rt, timeout)
    finally:
        stop.set()
    m["protected_unchanged"], m["protect_report"] = protect(name)
    m["watchdog_violation"] = drun.STATE["violation"]
    m["nand_root"] = os.path.join(drun.STATE["user"] or "", "Wii")
    json.dump(m, open(os.path.join(dh.RUNS, name, "run_manifest.json"), "w"), indent=1)
    print(json.dumps({"protected_unchanged": m["protected_unchanged"], "watchdog_violation": m["watchdog_violation"],
                      "status": m["status"], "save_changed": m["save_changed"]}, indent=1))
    return 0 if m["protected_unchanged"] and not m["watchdog_violation"] else 3


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    t = int(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 900
    fn = {"monado": monado, "dolphin": dolphin}[args[0]]
    sys.exit(fn(*args[1:4], timeout=t))
