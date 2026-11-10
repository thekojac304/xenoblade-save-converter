"""Isolated Azahar (3DS) test runner for Xenoblade Chronicles 3D (Phase 3A).

Isolation
  * Azahar runs from a private copy, phase3a/runs/azahar_bin, in portable mode (its own user/ folder; verified: the
    live %APPDATA%/Azahar config, log and saves are not touched).  The installed Azahar, the live AppData saves and
    Citra are only hashed (before/after).
  * Before each run the copy's save archive for 000400000F700100 is emptied and only the test saves are placed in it.
  * Input, screenshots and memory reads go through Azahar's own RPC server on 127.0.0.1:45987 (no desktop input).

  python azahar_harness.py setup <name> [--slot N=<3ds save file>]...   prepare user/ and start Azahar with the game
  python azahar_harness.py press <buttons|-> <ms> [--then-ms N]          hold buttons (A, B, X, Y, L, R, START, ...)
  python azahar_harness.py stick <x> <y> <ms>                            circle pad -1..1
  python azahar_harness.py shot <name> [--bottom]                        screenshot into the run folder
  python azahar_harness.py finish <name>                                 stop Azahar, collect saves/logs, verify
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.normpath(os.path.join(HERE, ".."))
BIN = os.path.join(P3, "runs", "azahar_bin")
EXE = os.path.join(BIN, "azahar.exe")
USER = os.path.join(BIN, "user")
RUNS = os.path.join(P3, "runs", "azahar")
ROM = r"E:\Launchbox\Games\ROMs\3DS\Xenoblade Chronicles (USA).3ds"
SD_TITLE = os.path.join("sdmc", "Nintendo 3DS", "0" * 32, "0" * 32, "title", "00040000", "0f700100", "data")
LIVE_META = os.path.join(P3, "originals", "azahar_live", "00000001.metadata")
STATE = os.path.join(RUNS, "_current.json")
PROTECTED_DIRS = [
    os.path.join(os.environ.get("APPDATA", ""), "Azahar"),
    r"E:\Launchbox\Emulators\Azahar",
    r"E:\Launchbox\Emulators\Citra\user\sdmc",
]
sys.path.insert(0, os.path.join(BIN, "scripting"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def protected_hashes():
    out = {}
    for d in PROTECTED_DIRS:
        for dp, dns, fs in os.walk(d):
            if "shaders" in dp:      # Azahar shader caches are rebuilt by the user's own runs; saves/config are not
                continue
            for f in fs:
                p = os.path.join(dp, f)
                if p.lower().endswith((".dll", ".exe")) and os.path.getsize(p) > 50_000_000:
                    out[p] = os.path.getsize(p)
                    continue
                out[p] = sha(p)
    return out


def rpc():
    import AzaharRPC
    return AzaharRPC.AzaharRPC(timeout=2.0, retries=3)


def write_config():
    ini = os.path.join(USER, "config", "qt-config.ini")
    lines = open(ini, encoding="utf-8").read().splitlines()
    want = {"enable_rpc_server": "true", "check_for_update_on_start": "false", "confirmClose": "false",
            "firstStart": "false", "use_disk_shader_cache": "false",
            "graphics_api": "2"}   # Vulkan, as on the user's own Azahar (OpenGL renders this game incorrectly)
    out = []
    for ln in lines:
        k = ln.split("=", 1)[0]
        base = k.split("\\")[0]
        if base in want and "\\" not in k:
            ln = f"{base}={want[base]}"
        elif base in want and k.endswith("\\default"):
            ln = f"{base}\\default=false"
        out.append(ln)
    open(ini, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")


def setup(name, slots):
    run = os.path.join(RUNS, name)
    if os.path.exists(run):
        raise SystemExit(f"run folder exists: {run}")
    os.makedirs(os.path.join(run, "shots"))
    if not os.path.isfile(os.path.join(USER, "config", "qt-config.ini")):
        raise SystemExit("portable user/config missing; start the copy once without a game first")
    write_config()
    data = os.path.join(USER, SD_TITLE)
    if os.path.exists(data):
        shutil.rmtree(data)
    os.makedirs(os.path.join(data, "00000001"))
    shutil.copyfile(LIVE_META, os.path.join(data, "00000001.metadata"))
    inputs = {}
    for slot, path in slots.items():
        dst = os.path.join(data, "00000001", f"monado0{slot}")
        shutil.copyfile(path, dst)
        inputs[f"monado0{slot}"] = {"source": path, "sha256": sha(dst)}
    for s in (1, 2, 3):          # the game expects all three slot files (empty ones are DMMY)
        dst = os.path.join(data, "00000001", f"monado0{s}")
        if not os.path.exists(dst):
            shutil.copyfile(os.path.join(P3, "originals", "azahar_live", "00000001", "monado02"), dst)
            inputs[f"monado0{s}"] = {"source": "empty DMMY slot (user's own)", "sha256": sha(dst)}
    prot = protected_hashes()
    json.dump(prot, open(os.path.join(run, "protected_before.json"), "w"), indent=0)
    log = open(os.path.join(run, "azahar_stdout.txt"), "w")
    p = subprocess.Popen([EXE, ROM], cwd=BIN, stdout=log, stderr=subprocess.STDOUT)
    st = {"name": name, "pid": p.pid, "started": time.time(), "inputs": inputs, "data": data}
    json.dump(st, open(STATE, "w"), indent=1)
    json.dump(st, open(os.path.join(run, "run.json"), "w"), indent=1)
    print(json.dumps(st, indent=1))


def wait_rpc(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            c = rpc()
            if c.perf_stats() is not None:
                return c
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("RPC server not reachable")


def press(buttons, ms, circle=None):
    c = wait_rpc(20)
    names = [] if buttons in ("-", "", None) else buttons.split("+")
    c.set_input(buttons=tuple(names), circle_pad=circle)
    time.sleep(ms / 1000)
    c.set_input()


def shot(name, bottom=False):
    st = json.load(open(STATE))
    c = wait_rpc(20)
    path = os.path.join(RUNS, st["name"], "shots", name + ("_bottom" if bottom else "") + ".png")
    c.save_screenshot(path, secondary_window=bottom)
    print(path)


def finish(name):
    st = json.load(open(STATE))
    assert st["name"] == name
    run = os.path.join(RUNS, name)
    subprocess.run(["taskkill", "/PID", str(st["pid"]), "/F"], capture_output=True)
    time.sleep(2)
    out = os.path.join(run, "save_after")
    shutil.copytree(st["data"], out)
    res = {"outputs": {}}
    for f in sorted(os.listdir(os.path.join(out, "00000001"))):
        p = os.path.join(out, "00000001", f)
        res["outputs"][f] = sha(p)
    logs = os.path.join(USER, "log")
    if os.path.isdir(logs):
        shutil.copytree(logs, os.path.join(run, "log"))
    before = json.load(open(os.path.join(run, "protected_before.json")))
    after = protected_hashes()
    changed = [k for k in before if before[k] != after.get(k)]
    added = [k for k in after if k not in before]
    res.update({"protected_files": len(before), "protected_changed": changed, "protected_added": added,
                "inputs": st["inputs"]})
    json.dump(res, open(os.path.join(run, "result.json"), "w"), indent=1)
    os.remove(STATE)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--slot", action="append", default=[])
    ap.add_argument("--bottom", action="store_true")
    a = ap.parse_args()
    if a.cmd == "setup":
        setup(a.args[0], {int(s.split("=", 1)[0]): s.split("=", 1)[1] for s in a.slot})
    elif a.cmd == "press":
        press(a.args[0], int(a.args[1]))
    elif a.cmd == "stick":
        x, y, ms = float(a.args[0]), float(a.args[1]), int(a.args[2])
        press("-", ms, circle=(int(x * 0x9A), int(y * 0x9A)))
    elif a.cmd == "shot":
        shot(a.args[0], a.bottom)
    elif a.cmd == "finish":
        finish(a.args[0])
