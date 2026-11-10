"""Phase 2F D4: DE flag-block descriptors (start << 16 | count, Phase 2B: getter 0xB2620(desc, idx)) whose start lies in
[LO, HI): MOVZ wN, #start, lsl 16 followed (within 4 instructions) by MOVK wN, #count. Read-only."""
import collections
import os
import struct
import sys

R = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LO, HI = int(sys.argv[1], 16), int(sys.argv[2], 16)
b = open(os.path.join(R, "exe", "de", "main.bin"), "rb").read()
n = len(b) // 4
W = struct.unpack_from("<%dI" % n, b)
found = collections.defaultdict(list)
for i, w in enumerate(W):
    if w & 0xFFE00000 != 0x52A00000:          # MOVZ w, #imm16, lsl 16
        continue
    start, rd = (w >> 5) & 0xFFFF, w & 31
    if not LO <= start < HI:
        continue
    cnt = 0
    for j in range(1, 5):
        w2 = W[i + j] if i + j < n else 0
        if w2 & 0xFFE00000 == 0x72800000 and w2 & 31 == rd:   # MOVK w, #imm16 (hw 0)
            cnt = (w2 >> 5) & 0xFFFF
            break
    found[(start, cnt)].append(4 * i)
for (s, c), sites in sorted(found.items()):
    print(f"start=0x{s:04x} count={c} ({s + c - 1:#06x} last)  sites={len(sites)}  e.g. {[hex(x) for x in sites[:4]]}")
