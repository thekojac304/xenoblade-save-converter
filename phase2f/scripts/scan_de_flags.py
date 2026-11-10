"""Phase 2F D4: DE main.bin (ARM64 flat image) sites that load a flag id in [LO, HI) with MOVZ (w-reg) or build it with
ADD #imm,lsl#12 + ADD #imm, followed within 8 instructions by BL to the DE flag getter 0xB2620 / setter 0xAEB10.
Read-only."""
import os
import struct
import sys

R = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LO, HI = int(sys.argv[1], 16), int(sys.argv[2], 16)
FUN = {0xB2620: "get", 0xAEB10: "set"}
b = open(os.path.join(R, "exe", "de", "main.bin"), "rb").read()
n = len(b) // 4
W = struct.unpack_from("<%dI" % n, b)
hits = []
for i, w in enumerate(W):
    val = None
    if w & 0xFFE00000 == 0x52800000:                     # MOVZ w, #imm16 (hw 0)
        val, rd = (w >> 5) & 0xFFFF, w & 31
    elif w & 0xFFC00000 == 0x11400000 and i + 1 < n:     # ADD w, w, #imm, lsl 12 ; next ADD w, w, #imm
        hi_, rd = ((w >> 10) & 0xFFF) << 12, w & 31
        w2 = W[i + 1]
        if w2 & 0xFFC00000 == 0x11000000 and (w2 >> 5) & 31 == rd:
            val, rd = hi_ + ((w2 >> 10) & 0xFFF), w2 & 31
    if val is None or not LO <= val < HI:
        continue
    for j in range(1, 9):
        if i + j >= n:
            break
        w3 = W[i + j]
        if w3 >> 26 == 0b100101:                         # BL
            off = w3 & 0x3FFFFFF
            if off & 0x2000000:
                off -= 0x4000000
            tgt = 4 * (i + j) + 4 * off
            if tgt in FUN:
                hits.append((4 * i, val, rd, FUN[tgt]))
            break
for h in sorted(hits, key=lambda x: x[1]):
    print(f"{h[0]:08x} id=0x{h[1]:04x} w{h[2]} {h[3]}")
print(len(hits), "sites")
