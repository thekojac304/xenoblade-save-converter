"""A1 static analysis of the DE executable (exe/de/main.bin, build 7E1DF8E0..., read-only).

Finds code that materialises an inventory box base (mov #lo / movk #hi,lsl16 -> 0x3B10 .. 0x38EA0 relative to the
save image) or the generic record stride, and lists byte/halfword loads at the DE-only record offsets
(+0x0A, +0x11, +0x12, +0x13, +0x18 crystal 'named', +0x1B) within the same function window.
Output: phase3c/work/a1_exe_scan.txt"""
import os
import re
import struct
import sys

import capstone as cs

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
d = open(os.path.join(ROOT, "exe", "de", "main.bin"), "rb").read()
TEXT_END = 0x8B7F58
MD = cs.Cs(cs.CS_ARCH_ARM64, cs.CS_MODE_ARM)
MD.skipdata = True
BASES = {0x3B10: "weapon", 0x98D0: "head", 0xF690: "body", 0x15450: "arm", 0x1B210: "legs", 0x20FD0: "feet",
         0x26D90: "crystal", 0x2C380: "gem", 0x31970: "collectable", 0x34080: "material", 0x36790: "keyitem",
         0x38EA0: "artmanual"}
OFFS = {0xA, 0x11, 0x12, 0x13, 0x18, 0x1B}
mem = re.compile(r"\[(x\d+|sp), #0x([0-9a-f]+)\]")
ins = []
for i in MD.disasm(d[:TEXT_END], 0):
    ins.append((i.address, i.mnemonic, i.op_str))
print("decoded", len(ins))
# function starts: after ret / at stp x29,x30 with pre-index
hits = []
lo = {}
for k, (a, m, o) in enumerate(ins):
    if m == "mov" and "#0x" in o:
        try:
            lo[o.split(",")[0]] = (int(o.split("#")[1], 16), k)
        except ValueError:
            pass
        else:
            v = lo[o.split(",")[0]][0]
            for b, name in BASES.items():
                if v == b - 0x3B10 and v > 0x1000:
                    hits.append((k, name, v))
    elif m == "movk" and "lsl #16" in o:
        r = o.split(",")[0]
        if r in lo and k - lo[r][1] < 4:
            v = lo[r][0] | int(o.split("#")[1].split(",")[0], 16) << 16
            for b, name in BASES.items():
                if v == b - 0x3B10:
                    hits.append((k, name, v))
print("base materialisations", len(hits))
out = []
for k, name, v in hits:
    a0 = ins[k][0]
    lines = []
    for j in range(max(0, k - 60), min(len(ins), k + 120)):
        a, m, o = ins[j]
        mm = mem.search(o)
        if m in ("ldrb", "ldrh", "strb", "strh", "ldrsb", "ldrsh") and mm and int(mm.group(2), 16) in OFFS:
            lines.append(f"    {a:08x} {m} {o}")
    if lines:
        out.append(f"{a0:08x} {name} base 0x{v:X}\n" + "\n".join(lines))
with open(os.path.join(ROOT, "phase3c", "work", "a1_exe_scan.txt"), "w") as f:
    f.write("\n".join(out))
print("windows with hits", len(out))
