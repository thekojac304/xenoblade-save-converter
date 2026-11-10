"""Canonical comparison of two saves (Wii monado01, 3DS monado0N or DE bfsgame): prints the shared-state differences.
  python ccmp.py <a> <b> [--max N]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "phase3a", "src"))
import canon  # noqa: E402
import phase2c  # noqa: E402


def canon_of(p, T):
    b = open(p, "rb").read()
    if b[:4] == b"!qzb":
        import xc3d
        b = xc3d.transcode(xc3d.unpack(b), "wii")
    if len(b) == 163840 or p.endswith(("monado01", "monado02", "monado03")) or p.endswith(".bin"):
        return canon.from_wii(b, T, p)
    return canon.from_de(b, T, p)


if __name__ == "__main__":
    import xcservice
    T = xcservice.tables()
    a, b = canon_of(sys.argv[1], T), canon_of(sys.argv[2], T)
    n = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 40
    sa, sb = a["shared"] if "shared" in a else a, b["shared"] if "shared" in b else b
    d = canon.compare(sa, sb)
    print("story", sa.get("story"), sb.get("story"), "party", sa.get("party"), sb.get("party"), "diffs", len(d))
    for x in d[:n]:
        print("  ", str(x)[:220])
