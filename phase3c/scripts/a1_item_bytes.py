"""A1: which bytes of DE item records vary across real game-written DE saves, and which of them the canonical
model covers. Read-only."""
import collections
import glob
import os
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import de_save  # noqa: E402

files = sorted(glob.glob(os.path.join(ROOT, "phase2f", "fixtures", "real", "*.sav")) +
               glob.glob(os.path.join(ROOT, "phase3b", "fixtures", "*.sav")) +
               [os.path.join(ROOT, "work", "template", "bfsgame00.sav")])
for name, typ, off, size, n in de_save.BOXES:
    vals = collections.defaultdict(collections.Counter)
    count = 0
    for f in files:
        d = open(f, "rb").read()
        if len(d) != de_save.V10:
            continue
        for i in range(n):
            o = off + size * i
            if not d[o + 0x10]:
                continue
            count += 1
            for b in range(size):
                vals[b][d[o + b]] += 1
    var = [b for b in range(size) if len(vals[b]) > 1]
    print(f"{name:11s} recs={count:5d} varying offsets: " + " ".join(f"{b:02X}" for b in var))
    for b in (0x0A, 0x0B, 0x11, 0x12, 0x13):
        print(f"   +{b:02X}: {dict(vals[b].most_common(6))}")
    if size == 0x2C or size == 0x30:
        extra = [b for b in var if b >= 0x14]
        for b in extra:
            print(f"   +{b:02X}: {dict(vals[b].most_common(5))}")
