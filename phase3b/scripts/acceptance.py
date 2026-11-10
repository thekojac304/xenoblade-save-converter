"""Phase 3B emulator acceptance cycle driver (Sync Hub side). Every Sync Hub step runs the real window
(xcconv_gui.py --sync-automate, or the packaged XCSaveConverter.exe with --exe) on a hub with simulated Syncthing
folders under phase3b/runs/acceptance. Emulator sessions run separately (erun3b.py, azahar_harness.py).

  python acceptance.py setup                         hub, 3 devices, DE + 3DS templates, the user's Wii save on Odin
  python acceptance.py gui <step> [--sync] [--choose TEXT] [--exe PATH]   start the window, scan, (Sync All), close
  python acceptance.py deliver <device folder> <file> [<name>]            a device's game-written save "arrives"
  python acceptance.py stage <device folder> <out dir> [extra files...]   copy a ready folder for an emulator run
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P3B = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3B)
sys.path.insert(0, os.path.join(P3B, "src"))
from xcsync import store  # noqa: E402

ACC = os.path.join(P3B, "runs", "acceptance")
HUB = os.path.join(ACC, "Xenoblade Sync")
SYNCT = os.path.join(ACC, "syncthing")
DEVICES = [("Windows desktop", "de", "windows-desktop"), ("Odin 2 Mini", "wii", "odin-2-mini"),
           ("New 3DS", "3ds", "new-3ds")]
W150 = os.path.join(ROOT, "phase3a", "fixtures", "wii_user_s150.bin")      # copy of the user's own Wii save
DE_TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
X3_TPL = os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado01")


def setup():
    if os.path.exists(ACC):
        raise SystemExit(f"{ACC} exists")
    h = store.Hub.create(HUB)
    for name, plat, folder in DEVICES:
        inc = os.path.join(SYNCT, folder)
        os.makedirs(os.path.join(inc, ".stfolder"))
        h.add_device(name, plat, incoming=inc)
    h.add_template("de", DE_TPL)
    h.add_template("3ds", X3_TPL)
    deliver("odin-2-mini", W150, "monado01")
    print(json.dumps(h.devices(), indent=1))


def deliver(folder, src, name=None):
    """As Syncthing does: write a temp file, then rename into place."""
    dst = os.path.join(SYNCT, folder, name or os.path.basename(src))
    tmp = os.path.join(SYNCT, folder, f"~syncthing~{os.path.basename(dst)}.tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    t = time.time() - 30
    os.utime(dst, (t, t))
    print(f"delivered {src} -> {dst}")


def stage(folder, out, *extra):
    os.makedirs(out)
    rd = os.path.join(HUB, "ready", folder)
    for n in os.listdir(rd):
        p = os.path.join(rd, n)
        if os.path.isfile(p) and n not in ("READY.json", "HOW_TO_INSTALL.txt"):
            shutil.copyfile(p, os.path.join(out, n))
    for e in extra:
        shutil.copyfile(e, os.path.join(out, os.path.basename(e)))
    print(sorted(os.listdir(out)))


def gui(step, sync=False, choose=None, exe=None):
    d = os.path.join(ACC, "steps", step)
    os.makedirs(d, exist_ok=False)
    job = {"hub": HUB, "data_dir": os.path.join(ROOT, "data"), "settings": os.path.join(d, "settings.ini"),
           "result": os.path.join(d, "result.json"), "sync": sync, "screenshot": os.path.join(d, "window.png")}
    if choose:
        job["choose"] = choose
    jp = os.path.join(d, "job.json")
    json.dump(job, open(jp, "w"), indent=1)
    cmd = [exe, "--sync-automate", jp] if exe else [sys.executable, os.path.join(P3B, "gui", "xcconv_gui.py"),
                                                     "--sync-automate", jp]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    r = json.load(open(job["result"]))
    r["seconds"] = round(time.time() - t0, 1)
    r["rc"] = p.returncode
    json.dump(r, open(job["result"], "w"), indent=1)
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "setup":
        setup()
    elif a[0] == "deliver":
        deliver(*a[1:4])
    elif a[0] == "stage":
        stage(*a[1:])
    elif a[0] == "gui":
        opt = lambda k: a[a.index(k) + 1] if k in a else None   # noqa: E731
        gui(a[1], sync="--sync" in a, choose=opt("--choose"), exe=opt("--exe"))
