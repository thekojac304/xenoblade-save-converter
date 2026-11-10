"""Bisect a 3DS load crash: hybrid Wii-layout images = GOOD image with byte ranges taken from BAD, transcoded to 3DS
(checksums fixed), each loaded in the isolated Azahar copy with a fixed key sequence; a crash is detected from
Azahar's log (unmapped accesses). Diagnostic only - hybrids are never used as conversion output.

  python bisect3ds.py <good 3ds> <bad 3ds> <name> <ranges: start-end,start-end ...>   (hex, Wii-layout offsets)
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P3D = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3D)
sys.path.insert(0, os.path.join(ROOT, "phase3c", "tests"))
import p3cfix  # noqa: E402,F401
import xc3d  # noqa: E402

AZ = [sys.executable, os.path.join(HERE, "az3d.py")]
LOG = os.path.join(ROOT, "phase3a", "runs", "azahar_bin", "user", "log", "azahar_log.txt")


def az(*a):
    return subprocess.run(AZ + list(a), capture_output=True, text=True)


def build(good, bad, ranges, out):
    gw = bytearray(xc3d.transcode(xc3d.unpack(open(good, "rb").read()), "wii"))
    bw = xc3d.transcode(xc3d.unpack(open(bad, "rb").read()), "wii")
    for s, e in ranges:
        gw[s:e] = bw[s:e]
    import hubfix
    img = xc3d.fix_wii_checksums(bytes(gw))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(hubfix.to_3ds(img, template=good))
    return out


def run(name, save):
    az("setup", name, "--slot", f"1={save}")
    time.sleep(25)
    for k, w in (("A", 4), ("A", 4), ("A", 3), ("UP", 1), ("A", 30), ("A", 35)):
        az("press", k, "150")
        time.sleep(w)
    shot = az("shot", "field").stdout.strip()
    log = open(LOG, encoding="utf-8", errors="replace").read()
    crashed = "UnmappedAccess" in log
    open(os.path.join(P3D, "logs", f"{name}_azahar_log.txt"), "w", encoding="utf-8").write(log[-20000:])
    az("finish", name)
    return crashed, shot


if __name__ == "__main__":
    good, bad, name = sys.argv[1:4]
    ranges = [tuple(int(x, 16) for x in r.split("-")) for r in sys.argv[4].split(",")] if len(sys.argv) > 4 else []
    out = build(good, bad, ranges, os.path.join(P3D, "work", "bisect", name, "monado01"))
    crashed, shot = run(name, out)
    print(name, "CRASH" if crashed else "loads", ranges and [(hex(a), hex(b)) for a, b in ranges], shot)
