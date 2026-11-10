"""Isolated Dolphin (Wii) test runner for Phase 2E: Xenoblade Chronicles (SX4E01) with a scripted virtual pad.

Isolation:
  - Dolphin runs with `-u <run>/user` (its own config + its own Wii NAND); the user's portable User folder, the normal
    NAND root and the original Wii save folder are never written. Their save files are hashed before and after.
  - Only copies of the test save (+ banner.bin, + empty DMMY slots) are placed in the isolated NAND.
Input: a DSU ("cemuhook") server on 127.0.0.1:<port> serves one virtual pad; Dolphin's DSU client maps it to an
emulated Wii Remote + Classic Controller (WiimoteNew.ini). No keystrokes are injected into the desktop.
Captures: the pad's Share button is bound to Dolphin's "Take Screenshot" hotkey (written to <run>/user/ScreenShots).
Route lines (ms since the pad is first polled): "<ms> <BUTTONS|0> [lx ly rx ry]" with '+'-joined names
A B X Y L R ZL ZR PLUS MINUS HOME UP DOWN LEFT RIGHT SHOT; sticks -1.0..1.0; "# comment".

  python dolphin_harness.py --name <run> --wii <monado01 file> --route <route.txt> [--timeout 900] [--port 26770]
"""
import argparse
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RUNS = os.path.join(ROOT, "work", "phase2e", "dolphin")
DOLPHIN = r"E:\Launchbox\Emulators\Dolphin\Dolphin.exe"
GAME = r"E:\Launchbox\Games\ROMs\Wii\Xenoblade Chronicles [NTSC-U].rvz"
PROTECTED = [  # folders whose save files must not change during a run
    r"E:\Launchbox\Emulators\Dolphin\User\Wii\title\00010000\53583445\data",
    r"C:\Users\lawma\Proton Drive\lawmat304\My files\Video Game Stuff\Game Saves & Memory Cards\Wii\title\00010000\53583445\data",
    r"C:\Filen\Video Game Stuff\Game Saves & Memory Cards\Wii\title\00010000\53583445\data",
]
TITLE = os.path.join("Wii", "title", "00010000", "53583445", "data")
DMMY = os.path.join(ROOT, "work", "originals", "monado02")      # the user's empty slot (DMMY), as an empty slot
BANNER = os.path.join(ROOT, "work", "originals", "wii_banner.bin")

# DSU button bits: buttons1 (Share 0x01, L3 0x02, R3 0x04, Options 0x08, Up 0x10, Right 0x20, Down 0x40, Left 0x80)
#                  buttons2 (L2 0x01, R2 0x02, L1 0x04, R1 0x08, Triangle 0x10, Circle 0x20, Cross 0x40, Square 0x80)
BTN = {"SHOT": (1, 0x01), "MINUS": (1, 0x02), "STOP": (1, 0x04), "PLUS": (1, 0x08), "UP": (1, 0x10), "RIGHT": (1, 0x20),
       "DOWN": (1, 0x40), "LEFT": (1, 0x80), "ZL": (2, 0x01), "ZR": (2, 0x02), "L": (2, 0x04), "R": (2, 0x08),
       "X": (2, 0x10), "A": (2, 0x20), "B": (2, 0x40), "Y": (2, 0x80), "HOME": (3, 0x01)}


def sha_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def protected_hashes():
    out = {}
    for d in PROTECTED:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if os.path.isfile(p):
                    out[p] = sha_file(p)
    return out


# ------------------------------------------------------------------------------------------------- DSU server
class Pad:
    def __init__(self):
        self.b1 = self.b2 = self.ps = 0
        self.sticks = [128, 128, 128, 128]
        self.lock = threading.Lock()

    def set(self, names, sticks):
        b = [0, 0, 0, 0]
        for n in names:
            if n:
                i, m = BTN[n]
                b[i] |= m
        with self.lock:
            self.b1, self.b2, self.ps = b[1], b[2], b[3]
            self.sticks = [max(0, min(255, int(round(128 + 127 * v)))) for v in sticks]


class DSUServer(threading.Thread):
    def __init__(self, pad, port):
        super().__init__(daemon=True)
        self.pad, self.port = pad, port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(0.005)
        self.clients = {}       # addr -> last data request time
        self.first_poll = None
        self.packet = 0
        self.stop = False
        self.sid = 0x5843434F   # "XCCO"

    def _send(self, addr, msg_type, payload):
        body = struct.pack("<I", msg_type) + payload
        hdr = b"DSUS" + struct.pack("<HHII", 1001, len(body), 0, self.sid)
        pkt = bytearray(hdr + body)
        struct.pack_into("<I", pkt, 8, zlib.crc32(bytes(pkt)) & 0xFFFFFFFF)
        self.sock.sendto(bytes(pkt), addr)

    @staticmethod
    def _slot_info(slot, connected):
        return struct.pack("<BBBB6sB", slot, 2 if connected else 0, 2 if connected else 0, 1 if connected else 0,
                           b"\x00\x11\x22\x33\x44\x55" if connected else bytes(6), 5 if connected else 0)

    def run(self):
        last = 0
        while not self.stop:
            try:
                data, addr = self.sock.recvfrom(1024)
                if data[:4] == b"DSUC" and len(data) >= 20:
                    mt = struct.unpack_from("<I", data, 16)[0]
                    if mt == 0x100000:
                        self._send(addr, 0x100000, struct.pack("<H", 1001))
                    elif mt == 0x100001:
                        n = struct.unpack_from("<i", data, 20)[0]
                        for i in range(max(0, min(n, 4))):
                            slot = data[24 + i]
                            self._send(addr, 0x100001, self._slot_info(slot, slot == 0) + b"\x00")
                    elif mt == 0x100002:
                        self.clients[addr] = time.time()
                        if self.first_poll is None:
                            self.first_poll = time.time()
            except socket.timeout:
                pass
            except OSError:
                pass
            now = time.time()
            if now - last >= 1 / 120:
                last = now
                with self.pad.lock:
                    b1, b2, ps, st = self.pad.b1, self.pad.b2, self.pad.ps, list(self.pad.sticks)
                self.packet += 1
                analog = bytes([0xFF if b1 & 0x80 else 0, 0xFF if b1 & 0x40 else 0, 0xFF if b1 & 0x20 else 0,
                                0xFF if b1 & 0x10 else 0, 0xFF if b2 & 0x80 else 0, 0xFF if b2 & 0x40 else 0,
                                0xFF if b2 & 0x20 else 0, 0xFF if b2 & 0x10 else 0, 0xFF if b2 & 0x08 else 0,
                                0xFF if b2 & 0x04 else 0, 0xFF if b2 & 0x02 else 0, 0xFF if b2 & 0x01 else 0])
                payload = self._slot_info(0, True) + struct.pack("<BIBBBB", 1, self.packet, b1, b2, ps, 0) + \
                    bytes(st) + analog + bytes(12) + struct.pack("<Q", int(now * 1e6)) + struct.pack("<6f", 0, 1, 0, 0, 0, 0)
                for addr, t in list(self.clients.items()):
                    if now - t < 6:
                        self._send(addr, 0x100002, payload)


# ------------------------------------------------------------------------------------------------- config
def write_config(user, port):
    cfg = os.path.join(user, "Config")
    os.makedirs(cfg, exist_ok=True)
    open(os.path.join(cfg, "Dolphin.ini"), "w").write(f"""[General]
ISOPaths = 0
[Interface]
ConfirmStop = False
UsePanicHandlers = False
OnScreenDisplayMessages = True
HotkeysRequireFocus = False
PauseOnFocusLost = False
ShowActiveTitle = False
[Display]
Fullscreen = False
RenderToMain = False
RenderWindowWidth = 960
RenderWindowHeight = 540
RenderWindowAutoSize = False
[Core]
SkipIPL = True
EnableCheats = False
WiiSDCard = False
WiimoteContinuousScanning = False
CPUThread = True
[Input]
BackgroundInput = True
[Analytics]
PermissionAsked = True
Enabled = False
[AutoUpdate]
UpdateTrack =
[Movie]
PauseMovie = False
""")
    open(os.path.join(cfg, "DSUClient.ini"), "w").write(f"""[Server]
Enabled = True
Entries = xcconv:127.0.0.1:{port};
""")
    dev = "DSUClient/0/xcconv"
    open(os.path.join(cfg, "WiimoteNew.ini"), "w").write(f"""[Wiimote1]
Device = {dev}
Source = 1
Extension = Classic
Classic/Buttons/A = Circle
Classic/Buttons/B = Cross
Classic/Buttons/X = Triangle
Classic/Buttons/Y = Square
Classic/Buttons/ZL = L2
Classic/Buttons/ZR = R2
Classic/Buttons/- = L3
Classic/Buttons/+ = Options
Classic/Buttons/Home = PS
Classic/Triggers/L = L1
Classic/Triggers/R = R1
Classic/Triggers/L-Analog = L1
Classic/Triggers/R-Analog = R1
Classic/D-Pad/Up = `Pad N`
Classic/D-Pad/Down = `Pad S`
Classic/D-Pad/Left = `Pad W`
Classic/D-Pad/Right = `Pad E`
Classic/Left Stick/Up = `Left Y+`
Classic/Left Stick/Down = `Left Y-`
Classic/Left Stick/Left = `Left X-`
Classic/Left Stick/Right = `Left X+`
Classic/Right Stick/Up = `Right Y+`
Classic/Right Stick/Down = `Right Y-`
Classic/Right Stick/Left = `Right X-`
Classic/Right Stick/Right = `Right X+`
Buttons/A = Circle
Buttons/B = Cross
Buttons/1 = Square
Buttons/2 = Triangle
Buttons/- = L3
Buttons/+ = Options
Buttons/Home = PS
[Wiimote2]
Source = 0
[Wiimote3]
Source = 0
[Wiimote4]
Source = 0
[BalanceBoard]
Source = 0
""")
    open(os.path.join(cfg, "Hotkeys.ini"), "w").write(f"""[Hotkeys]
Device = {dev}
General/Take Screenshot = Share
General/Stop = R3
""")
    open(os.path.join(cfg, "GCPadNew.ini"), "w").write("[GCPad1]\nSource = 0\n[GCPad2]\nSource = 0\n[GCPad3]\nSource = 0\n[GCPad4]\nSource = 0\n")


def window_shots(pid, out_dir, tag):
    """Diagnostic capture of Dolphin's own top-level windows only (found by process id), never the whole desktop."""
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import ImageGrab
    except ImportError:
        return 0
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 100 and r.bottom - r.top > 100:
                found.append((r.left, r.top, r.right, r.bottom))
        return True
    user32.EnumWindows(cb, 0)
    os.makedirs(out_dir, exist_ok=True)
    for i, box in enumerate(found):
        try:
            ImageGrab.grab(bbox=box, all_screens=True).save(os.path.join(out_dir, f"{tag}_w{i}.png"))
        except Exception:
            pass
    return len(found)


def parse_route(path):
    ev = []
    for ln in open(path, encoding="utf-8"):
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        p = ln.split()
        t = int(p[0])
        names = [] if p[1] == "0" else p[1].upper().split("+")
        sticks = [float(x) for x in p[2:6]] + [0.0] * (4 - len(p[2:6]))
        ev.append((t, names, sticks))
    return sorted(ev, key=lambda e: e[0])


def run(name, wii, route, timeout=900, port=26770, extra_saves=None, diag_every=0):
    run_dir = os.path.join(RUNS, name)
    if os.path.exists(run_dir):
        raise SystemExit(f"run folder exists: {run_dir}")
    user = os.path.join(run_dir, "user")
    nand = os.path.join(user, TITLE)
    os.makedirs(nand)
    shutil.copyfile(wii, os.path.join(nand, "monado01"))
    shutil.copyfile(DMMY, os.path.join(nand, "monado02"))
    shutil.copyfile(DMMY, os.path.join(nand, "monado03"))
    shutil.copyfile(BANNER, os.path.join(nand, "banner.bin"))
    for slot, p in (extra_saves or {}).items():
        shutil.copyfile(p, os.path.join(nand, slot))
    write_config(user, port)
    before = protected_hashes()
    pad = Pad()
    srv = DSUServer(pad, port)
    srv.start()
    ev = parse_route(route)
    manifest = {"name": name, "wii_in": sha_file(os.path.join(nand, "monado01")), "route": [route, sha_file(route)],
                "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "user_dir": user}
    log = open(os.path.join(run_dir, "dolphin_stdout.log"), "wb")
    p = subprocess.Popen([DOLPHIN, "-u", user, "-b", "-e", GAME], stdout=log, stderr=subprocess.STDOUT)
    t0, status, i = time.time(), "running", 0
    next_diag = t0 + 8
    try:
        while True:
            if diag_every and time.time() >= next_diag:
                window_shots(p.pid, os.path.join(run_dir, "diag"), f"t{int(time.time() - t0):04d}")
                next_diag += diag_every
            if p.poll() is not None:
                status = f"exited rc={p.returncode}"
                break
            now = time.time()
            if now - t0 > timeout:
                status = f"timeout {timeout} s"
                break
            if srv.first_poll is not None:
                ms = (now - srv.first_poll) * 1000
                while i < len(ev) and ev[i][0] <= ms:
                    pad.set(ev[i][1], ev[i][2])
                    i += 1
                if i >= len(ev) and ms > ev[-1][0] + 3000:
                    status = "route finished"
                    break
            time.sleep(0.004)
    finally:
        if p.poll() is None:
            pad.set(["STOP"], [0, 0, 0, 0])   # Stop hotkey: emulation stops, -b exits Dolphin
            for _ in range(200):
                if p.poll() is not None:
                    break
                time.sleep(0.1)
        if p.poll() is None:
            p.kill()
            status += " (killed)"
        p.wait(30)
        srv.stop = True
        log.close()
    after = protected_hashes()
    shots_dir = os.path.join(user, "ScreenShots")
    shots = []
    for r_, _, fs in os.walk(shots_dir):
        shots += [os.path.join(r_, f) for f in sorted(fs)]
    out = {f: sha_file(os.path.join(nand, f)) for f in sorted(os.listdir(nand))}
    manifest.update(status=status, seconds=round(time.time() - t0), dsu_polled=srv.first_poll is not None,
                    protected_unchanged=before == after, protected_hashes=after, nand_out=out,
                    save_changed=out.get("monado01") != manifest["wii_in"], shots=shots, route_events_sent=i)
    json.dump(manifest, open(os.path.join(run_dir, "run_manifest.json"), "w"), indent=1)
    if before != after:
        print("!!! PROTECTED SAVE FOLDER CHANGED !!!", file=sys.stderr)
    print(json.dumps({k: manifest[k] for k in ("name", "status", "seconds", "dsu_polled", "protected_unchanged",
                                               "save_changed", "route_events_sent")} | {"shots": len(shots)}, indent=1))
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--wii", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--port", type=int, default=26770)
    ap.add_argument("--diag-every", type=int, default=0, help="seconds between captures of Dolphin's own windows")
    a = ap.parse_args()
    m = run(a.name, a.wii, a.route, a.timeout, a.port, diag_every=a.diag_every)
    sys.exit(0 if m["protected_unchanged"] else 2)


if __name__ == "__main__":
    main()
