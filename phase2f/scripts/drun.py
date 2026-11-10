"""Phase 2F isolated Dolphin run (wraps tools/dolphin_harness.run; RUNS = phase2f/runs/dolphin).

Isolation, in addition to the harness (own -u user dir, copies of the test save only, protected folders hashed before
and after):
  * Dolphin.ini gets an explicit NANDRootPath = <run>/user/Wii, verified before launch (else no launch);
  * a watchdog thread re-hashes the protected Wii save folders every 2 s while Dolphin runs and terminates this
    run's Dolphin process (matched by its -u path) the moment anything changes;
  * afterwards every protected file in phase2f/manifests/protected_start.json is re-checked.

  python drun.py <name> <wii save file> <route.txt (droute DSL)> [--timeout S]
"""
import json
import os
import subprocess
import sys
import threading
import time

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import dolphin_harness as dh  # noqa: E402
import droute  # noqa: E402

dh.RUNS = os.path.join(P2F, "runs", "dolphin")
_orig_write_config = dh.write_config
STATE = {"user": None, "violation": None}


def write_config(user, port):
    _orig_write_config(user, port)
    ini = os.path.join(user, "Config", "Dolphin.ini")
    s = open(ini, encoding="utf-8").read()
    nand = os.path.join(user, "Wii")
    s = s.replace("[General]\n", f"[General]\nNANDRootPath = {nand}\n", 1)
    open(ini, "w", encoding="utf-8").write(s)
    if f"NANDRootPath = {nand}" not in open(ini, encoding="utf-8").read() or not os.path.isdir(nand):
        raise SystemExit("isolation could not be established (NANDRootPath); not launching")
    STATE["user"] = user


dh.write_config = write_config


def kill_run_dolphin(user):
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='Dolphin.exe'\" | Where-Object { $_.CommandLine -like "
          f"'*{user}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


def watchdog(before, stop):
    while not stop.is_set():
        time.sleep(2)
        if dh.protected_hashes() != before:
            STATE["violation"] = time.strftime("%H:%M:%S")
            if STATE["user"]:
                kill_run_dolphin(STATE["user"])
            return


def main(name, wii, script, timeout=900):
    os.makedirs(dh.RUNS, exist_ok=True)
    rdir = os.path.join(P2F, "runs", "droutes")
    os.makedirs(rdir, exist_ok=True)
    rt = os.path.join(rdir, name + ".route")
    ev = droute.compile_script(open(script, encoding="utf-8").read().splitlines())
    with open(rt, "w", newline="\n") as fo:
        for e in ev:
            fo.write(f"{e[0]} {e[1]}\n")
    before = dh.protected_hashes()
    stop = threading.Event()
    th = threading.Thread(target=watchdog, args=(before, stop), daemon=True)
    th.start()
    try:
        m = dh.run(name, wii, rt, timeout)
    finally:
        stop.set()
    chk = subprocess.run([sys.executable, os.path.join(P2F, "scripts", "protect_manifest.py"), "check", f"after_{name}"],
                         capture_output=True, text=True)
    m["protected_all_unchanged"] = chk.returncode == 0
    m["watchdog_violation"] = STATE["violation"]
    m["nand_root"] = os.path.join(STATE["user"] or "", "Wii")
    json.dump(m, open(os.path.join(dh.RUNS, name, "run_manifest.json"), "w"), indent=1)
    print(json.dumps({"protected_all_unchanged": m["protected_all_unchanged"], "watchdog_violation": STATE["violation"],
                      "status": m["status"], "save_changed": m["save_changed"]}))
    return 0 if m["protected_all_unchanged"] and not STATE["violation"] else 3


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    t = int(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 900
    sys.exit(main(*args[:3], timeout=t))
