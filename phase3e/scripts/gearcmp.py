"""Equipped gear of characters (gear id, socket count, fixed gems, socketed gem contents) in any save, compared with a
reference save or with a stored-gear view.   python gearcmp.py <save> <ref save> <chars e.g. 1,2,4,5,6> [--stored]
--stored: take the reference's STORED gear (canonical stored_gear) instead of its equipped gear."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "phase3a", "src")]
import canon  # noqa: E402
import xc3d  # noqa: E402
import xcservice  # noqa: E402

SL = ("head", "body", "arm", "legs", "feet", "weapon")


def load(p, T):
    b = open(p, "rb").read()
    if b[:4] == b"!qzb":
        b = xc3d.transcode(xc3d.unpack(b), "wii")
    return (canon.from_wii(b, T) if b[:4] == b"USRD" else canon.from_de(b, T))["shared"]


def gem_key(g):
    return (g["gid"], g["effect"], g["rank"], g["strength"], g["chance"])


def equipped(sh, k):
    eq = sh["characters"][k].get("equipment") or {}
    out = {}
    for sl in SL:
        i = eq.get(sl)
        r = sh["inventory"][sl].get(i) if i is not None else None
        if r is None:
            out[sl] = None
            continue
        socks = []
        for s in r["sockets"]:
            if s is None:
                socks.append(None)
            elif s[0] == "fixed":
                socks.append(("fixed", s[1]))
            else:
                socks.append(("gem",) + gem_key(sh["inventory"]["gem"][s[1]]))
        out[sl] = (r["gid"], r["socket_count"], tuple(socks))
    return out


def stored(sh, k):
    d = (sh.get("stored_gear") or {}).get(k)
    if d is None or "slots" not in d:
        return None
    out = {}
    for sl in SL:
        r = d["slots"][sl]
        if r is None:
            out[sl] = None
            continue
        socks = []
        for s in r["sockets"]:
            if s is None:
                socks.append(None)
            elif s[0] == "fixed":
                socks.append(("fixed", s[1]))
            else:
                socks.append(("gem",) + gem_key(d["gems"][s[1]]))
        out[sl] = (r["gid"], r["socket_count"], tuple(socks))
    return out


if __name__ == "__main__":
    T = xcservice.tables()
    a, b = load(sys.argv[1], T), load(sys.argv[2], T)
    chars = [int(x) for x in sys.argv[3].split(",")]
    st = "--stored" in sys.argv
    allok = True
    for k in chars:
        x = equipped(a, k)
        y = stored(b, k) if st else equipped(b, k)
        ok = x == y
        allok &= ok
        print(f"char {k}: {'SAME' if ok else 'DIFFERENT'}")
        for sl in SL:
            if not ok or "-v" in sys.argv:
                print(f"   {sl:6s} {x.get(sl) if x else None}\n          {y.get(sl) if y else None}" if (x or {}).get(sl) != (y or {}).get(sl) else f"   {sl:6s} same")
    print("ALL SAME" if allok else "DIFFERENCES")
