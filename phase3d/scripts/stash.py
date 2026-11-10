"""DE stored-equipment table ("stash", Phase 3D finding): 0x3BB50, 7 entries x 0xB4 per character (k = 1..), entry =
one 0x30 equipment record (head, body, arm, legs, feet, weapon; 7th unused so far) + its 3 gem records (0x2C each).
The DE moves a departing character's equipped gear here (story split 283 -> 288: characters 1, 2, 5, 8) and back
into the inventory when the character returns (288 -> 291).
  python stash.py <de save> [...]"""
import os
import struct
import sys

STASH, ENTRY, PER_CHAR = 0x3BB50, 0xB4, 7
SLOTS = ["head", "body", "arm", "legs", "feet", "weapon", "x6"]


def entries(d, chars=range(1, 36)):
    out = {}
    for k in chars:
        for j in range(PER_CHAR):
            o = STASH + ENTRY * (PER_CHAR * (k - 1) + j)
            if o + ENTRY > 0x46900:
                return out
            e = d[o:o + ENTRY]
            if any(e):
                typ, gid = struct.unpack_from("<HH", e, 2)
                out[(k, SLOTS[j])] = {"type": typ, "gid": gid, "present": e[0x10] if len(e) > 0x10 else None,
                                      "gems": [e[0x30 + 0x2C * g:0x30 + 0x2C * (g + 1)].hex()[:16] for g in range(3)
                                               if any(e[0x30 + 0x2C * g:0x30 + 0x2C * (g + 1)])]}
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        d = open(p, "rb").read()
        e = entries(d)
        chars = sorted({k for k, _ in e})
        print(os.path.basename(os.path.dirname(p)) + "/" + os.path.basename(p), "entries", len(e), "chars", chars)
        for k in chars:
            print("   ", k, {s: v["gid"] for (kk, s), v in e.items() if kk == k})
