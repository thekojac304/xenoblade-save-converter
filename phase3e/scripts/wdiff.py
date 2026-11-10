"""Compare two Wii-layout saves (Wii monado01 or 3DS via xc3d): header story/party, character records byte diffs
(per record, ranges), other region diffs summarised.
  python wdiff.py <a> <b> [--chars 1,2,3,8]"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "phase3a", "src"))
import canon  # noqa: E402
from de_to_wii import CHAR_BASE, CHAR_SIZE  # noqa: E402


def load(p):
    b = open(p, "rb").read()
    if b[:4] == b"!qzb":
        import xc3d
        b = xc3d.transcode(xc3d.unpack(b), "wii")
    return b


def ranges(a, b, lo, hi):
    out, s = [], None
    for i in range(lo, hi):
        if a[i] != b[i]:
            if s is None:
                s = i
        elif s is not None:
            out.append((s, i))
            s = None
    if s is not None:
        out.append((s, hi))
    return out


if __name__ == "__main__":
    a, b = load(sys.argv[1]), load(sys.argv[2])
    chars = [int(x) for x in sys.argv[sys.argv.index("--chars") + 1].split(",")] if "--chars" in sys.argv else range(1, 14)
    for k in chars:
        o = CHAR_BASE + CHAR_SIZE * k
        r = ranges(a, b, o, o + CHAR_SIZE)
        if r:
            print(f"char {k}: lv {struct.unpack_from('>I', a, o + 0x17C)[0]}->{struct.unpack_from('>I', b, o + 0x17C)[0]}"
                  f" exp {struct.unpack_from('>I', a, o + 0x2A4)[0]}->{struct.unpack_from('>I', b, o + 0x2A4)[0]}")
            for s, e in r:
                print(f"   +{s - o:#05x}..+{e - o:#05x}  {a[s:e].hex()} -> {b[s:e].hex()}"[:200])
    lo, hi = CHAR_BASE + CHAR_SIZE, CHAR_BASE + CHAR_SIZE * 14
    other = [x for x in ranges(a, b, 0, len(a)) if not (lo <= x[0] < hi)]
    print("other ranges:", len(other), [(hex(s), e - s) for s, e in other[:40]])
