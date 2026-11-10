"""Phase 2F D4: every Wii main.dol site that computes a flag id in 0x3424..0x36CF (addi/li rD, ..., imm) shortly before
calling a flag getter/setter. Read-only. Prints (site, immediate, base register form, callee)."""
import os
import struct
import sys

R = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(R, "tools"))
import capstone as cs  # noqa: E402
from xdis import dol_sections  # noqa: E402

FLAG_FUNCS = {0x8009D964: "get", 0x8009D9F0: "set", 0x8009DBD0: "get_raw", 0x8009DCA0: "set_raw"}
LO, HI = 0x3424, 0x36D0
d = open(os.path.join(R, "exe", "wii", "main.dol"), "rb").read()
md = cs.Cs(cs.CS_ARCH_PPC, cs.CS_MODE_32 | cs.CS_MODE_BIG_ENDIAN)
hits = []
for name, off, addr, size in dol_sections(d):
    if not size or not name.startswith("T"):
        continue
    words = [struct.unpack_from(">I", d, off + 4 * i)[0] for i in range(size // 4)]
    for i, w in enumerate(words):
        op = w >> 26
        if op != 14:            # addi / li
            continue
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if not LO <= imm < HI:
            continue
        for j in range(1, 6):
            if i + j >= len(words):
                break
            w2 = words[i + j]
            if w2 >> 26 == 18 and w2 & 1:          # bl
                li = w2 & 0x03FFFFFC
                if li & 0x02000000:
                    li -= 0x04000000
                tgt = (addr + 4 * (i + j) + li) & 0xFFFFFFFF
                if tgt in FLAG_FUNCS and rd == 3:
                    hits.append((addr + 4 * i, imm, "li" if ra == 0 else f"r{ra}+", FLAG_FUNCS[tgt]))
                break
for h in sorted(hits, key=lambda x: x[1]):
    print(f"{h[0]:08x} imm=0x{h[1]:04x} ({h[2]}) {h[3]}")
print(len(hits), "sites")
