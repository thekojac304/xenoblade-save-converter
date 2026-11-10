"""Phase 3F isolated emulator runs (Monado story progression; Dolphin and Azahar reverse-conversion story tests).

Isolation as in 2F/3A/3B (tools/monado_harness: own LARECOMP_SAVE_DIR, mount-path check, live save_0 hashed; Dolphin
2F wrapper: explicit NANDRootPath + watchdog). Run folders under phase3c/runs. Before every run the input save is
validated and hashed and the 3C protected manifest (1,679 files incl. every release candidate) is checked; after every
run it is checked again and the Monado installation folder listing is compared.

  python erun3c.py monado <name> <save dir> <route script> [--warp F:MAP:SUB:X:Y:Z:ANG] [--tour file]
                          [--env K=V ...] [--timeout S]
  python erun3c.py dolphin <name> <wii save file> <droute script> [--timeout S]
"""
import argparse
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
P3F = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3F)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "phase2f", "scripts"))
RUNS = os.path.join(P3F, "runs")


def protect(tag):
    chk = subprocess.run([sys.executable, os.path.join(HERE, "protect3f.py"), "check", tag], capture_output=True,
                         text=True)
    return chk.returncode == 0, chk.stdout[-2000:]


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


def summary_de(p):
    import struct
    import de_save
    d = open(p, "rb").read()
    ir = de_save.decode_bytes(d)
    return {"story": ir["story"], "party": ir["party"], "map": struct.unpack_from("<I", d, 0x149C00)[0],
            "pos": [round(v, 2) for v in struct.unpack_from("<3f", d, 0x149C10)], "play_time_s": ir["play_time_s"]}


def monado(a):
    import monado_harness as mh
    import route
    mh.RUNS = os.path.join(RUNS, "monado")
    os.makedirs(mh.RUNS, exist_ok=True)
    ok, rep = protect(f"before_{a.name}")
    if not ok:
        raise SystemExit("protected files changed BEFORE the run - stopping:\n" + rep)
    src = os.path.join(a.save, "bfsgame00.sav")
    before = summary_de(src)
    rdir = os.path.join(RUNS, "routes")
    os.makedirs(rdir, exist_ok=True)
    rt = os.path.join(rdir, a.name + ".route")
    ev, shots = route.compile_script(open(a.script, encoding="utf-8").read().splitlines())
    with open(rt, "w", newline="\n") as fo:
        fo.write("# xcde input v1\n# compiled from %s\n" % os.path.basename(a.script))
        for e in ev:
            fo.write("%d %x %d %d %d %d\n" % e)
    env = list(a.env)
    if a.warp:
        env.append("XCDE_WARP=" + a.warp)
    inst_before = listing(mh.INSTALL)
    m = mh.run(a.name, a.save, rt, [s[0] for s in shots], a.tour, env, a.timeout, True)
    inst_after = listing(mh.INSTALL)
    m["install_changes"] = {"added": sorted(set(inst_after) - set(inst_before)),
                            "removed": sorted(set(inst_before) - set(inst_after)),
                            "changed": sorted(k for k in inst_before if k in inst_after and inst_before[k] != inst_after[k])}
    m["protected_unchanged"], m["protect_report"] = protect(f"after_{a.name}")
    m["shot_labels"] = {f"f{s[0]}.png": s[1] for s in shots}
    m["input_state"] = before
    sd = os.path.join(mh.RUNS, a.name, "save_0")
    m["output_states"] = {f: summary_de(os.path.join(sd, f)) for f in sorted(os.listdir(sd))
                          if f.startswith("bfsgame") and f.endswith(".sav")}
    m["script"] = os.path.abspath(a.script)
    json.dump(m, open(os.path.join(mh.RUNS, a.name, "run_manifest.json"), "w"), indent=1)
    print(json.dumps({k: m[k] for k in ("status", "seconds", "live_unchanged", "save_changed", "protected_unchanged",
                                        "input_state", "output_states")}, indent=1))
    print("install changes:", {k: len(v) for k, v in m["install_changes"].items()})
    return 0 if m["protected_unchanged"] and m["live_unchanged"] and not m["status"].startswith("ISOLATION") else 3


def _hotkeys_without_focus(write_config):
    """Phase 3C: captures use Dolphin's screenshot hotkey (pad Share); Dolphin ignores hotkeys while its window is not
    focused unless [Interface] HotkeysRequireFocus = False. Set in the run's own (isolated) Dolphin.ini only."""
    def wc(user, port):
        write_config(user, port)
        ini = os.path.join(user, "Config", "Dolphin.ini")
        s = open(ini, encoding="utf-8").read()
        s = s.replace("[Interface]\n", "[Interface]\nHotkeysRequireFocus = False\n", 1) if "[Interface]\n" in s \
            else s + "\n[Interface]\nHotkeysRequireFocus = False\n"
        open(ini, "w", encoding="utf-8").write(s)
    return wc


def dolphin(a):
    import drun                                     # the 2F wrapper: NANDRootPath + watchdog
    import droute
    dh = drun.dh
    if not getattr(dh.write_config, "_p3c", False):
        dh.write_config = _hotkeys_without_focus(dh.write_config)
        dh.write_config._p3c = True
    if a.gfx:
        # Phase 3F: video backend of the run's own (isolated) Dolphin.ini only, e.g. Null while the desktop is locked
        # (a locked desktop stalls presentation; the game code runs unchanged with Null, nothing is drawn)
        base_wc = dh.write_config

        def wc(user, port, _b=base_wc):
            _b(user, port)
            ini = os.path.join(user, "Config", "Dolphin.ini")
            s = open(ini, encoding="utf-8").read().replace("[Core]\n", f"[Core]\nGFXBackend = {a.gfx}\n", 1)
            open(ini, "w", encoding="utf-8").write(s)
        dh.write_config = wc
    if a.log:
        # Phase 3F: Dolphin's own log file in the run's isolated user folder (user/Logs/dolphin.log)
        base_wc2 = dh.write_config

        def wc2(user, port, _b=base_wc2):
            _b(user, port)
            open(os.path.join(user, "Config", "Logger.ini"), "w").write(
                "[Options]\nVerbosity = 3\nWriteToFile = True\nWriteToConsole = False\nWriteToWindow = False\n"
                "[Logs]\nBOOT = True\nCORE = True\nVIDEO = True\nHOST_GPU = True\nWII_IPC_FILEIO = True\n"
                "WII_IPC_HLE = False\nCOMMON = True\n")
        dh.write_config = wc2
    if a.novsync:
        # Phase 3F: [Hardware] VSync = False in the run's isolated GFX.ini (presentation must not throttle emulation
        # while the desktop is locked)
        base_wc3 = dh.write_config

        def wc3(user, port, _b=base_wc3):
            _b(user, port)
            open(os.path.join(user, "Config", "GFX.ini"), "w").write(
                "[Hardware]\nVSync = False\n[Settings]\nShowFPS = False\n")
        dh.write_config = wc3
    dh.RUNS = os.path.join(RUNS, "dolphin")
    os.makedirs(dh.RUNS, exist_ok=True)
    ok, rep = protect(f"before_{a.name}")
    if not ok:
        raise SystemExit("protected files changed BEFORE the run - stopping:\n" + rep)
    rdir = os.path.join(RUNS, "droutes")
    os.makedirs(rdir, exist_ok=True)
    rt = os.path.join(rdir, a.name + ".route")
    ev = droute.compile_script(open(a.script, encoding="utf-8").read().splitlines())
    with open(rt, "w", newline="\n") as fo:
        for e in ev:
            fo.write(f"{e[0]} {e[1]}\n")
    before = dh.protected_hashes()
    stop = threading.Event()
    th = threading.Thread(target=drun.watchdog, args=(before, stop), daemon=True)
    th.start()
    try:
        m = dh.run(a.name, a.save, rt, a.timeout, diag_every=a.diag)
    finally:
        stop.set()
    m["protected_unchanged"], m["protect_report"] = protect(f"after_{a.name}")
    m["watchdog_violation"] = drun.STATE["violation"]
    m["nand_root"] = os.path.join(drun.STATE["user"] or "", "Wii")
    m["script"] = os.path.abspath(a.script)
    json.dump(m, open(os.path.join(dh.RUNS, a.name, "run_manifest.json"), "w"), indent=1)
    print(json.dumps({"protected_unchanged": m["protected_unchanged"], "watchdog_violation": m["watchdog_violation"],
                      "status": m["status"], "save_changed": m["save_changed"]}, indent=1))
    return 0 if m["protected_unchanged"] and not m["watchdog_violation"] else 3


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("emu", choices=("monado", "dolphin"))
    ap.add_argument("name")
    ap.add_argument("save")
    ap.add_argument("script")
    ap.add_argument("--warp")
    ap.add_argument("--tour")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--diag", type=int, default=0, help="Dolphin: window capture every N s (harness diag)")
    ap.add_argument("--gfx", help="Dolphin: GFXBackend for the isolated run (e.g. Null)")
    ap.add_argument("--log", action="store_true", help="Dolphin: write user/Logs/dolphin.log")
    ap.add_argument("--novsync", action="store_true", help="Dolphin: VSync off in the isolated GFX.ini")
    a = ap.parse_args()
    sys.exit(monado(a) if a.emu == "monado" else dolphin(a))
