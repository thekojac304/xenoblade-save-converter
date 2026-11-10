"""A1: candidate code for the DE item favourite byte (+0x11): byte stores/loads at #0x11 close to a load/store of the
presence byte (#0x10) on the same base register (the record layout present,favourite). Read-only."""
import collections
import os
import re

import capstone as cs

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
d = open(os.path.join(ROOT, "exe", "de", "main.bin"), "rb").read()
MD = cs.Cs(cs.CS_ARCH_ARM64, cs.CS_MODE_ARM)
MD.skipdata = True
mem = re.compile(r"^(w\d+|wzr), \[(x\d+), #0x([0-9a-f]+)\]$")
ins = [(i.address, i.mnemonic, i.op_str) for i in MD.disasm(d[:0x8B7F58], 0)]
res = collections.defaultdict(list)
for k, (a, m, o) in enumerate(ins):
    mm = mem.match(o)
    if not mm or m not in ("ldrb", "strb") or int(mm.group(3), 16) != 0x11:
        continue
    base = mm.group(2)
    near = [ins[j] for j in range(max(0, k - 12), min(len(ins), k + 12))]
    has10 = any(re.search(rf"\[{base}, #0x10\]", x[2]) and x[1] in ("ldrb", "strb", "ldrh", "strh") for x in near)
    has_c = any(re.search(rf"\[{base}, #0xc\]", x[2]) for x in near)
    has4 = any(re.search(rf"\[{base}, #4\]", x[2]) and x[1] == "ldrh" for x in near)
    if has10 and (has_c or has4):
        res[m].append(a)
        ctx = "\n".join(f"   {x[0]:08x} {x[1]} {x[2]}" for x in near)
        res["ctx"].append(f"{a:08x} {m} {o}\n{ctx}")
with open(os.path.join(ROOT, "phase3c", "work", "a1_fav_scan.txt"), "w") as f:
    f.write("\n\n".join(res["ctx"]))
print({k: len(v) for k, v in res.items()})
print("strb:", " ".join(f"{a:x}" for a in res["strb"]))
print("ldrb:", " ".join(f"{a:x}" for a in res["ldrb"][:80]))
