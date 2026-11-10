"""Find Wii code that reads/writes a character-object byte at +0x118 (save record +0x118). Read-only."""
import os, re, sys
ROOT = r"C:\Dev\XC_Wii_to_DE_Research"
sys.path.insert(0, os.path.join(ROOT, "tools"))
import capstone as cs
from xdis import dol_sections, dol_read
d = open(os.path.join(ROOT, "exe", "wii", "main.dol"), "rb").read()
md = cs.Cs(cs.CS_ARCH_PPC, cs.CS_MODE_32 | cs.CS_MODE_BIG_ENDIAN | cs.CS_MODE_PS)
md.skipdata = True
hits = []
for name, off, addr, size in dol_sections(d):
    if not name.startswith("T"):
        continue
    code = d[off:off + size]
    for i in md.disasm(code, addr):
        if i.mnemonic in ("lbz", "stb", "lbzx") and re.search(r", 0x118\(r\d+\)", i.op_str):
            hits.append((i.address, i.mnemonic, i.op_str))
print(len(hits))
for h in hits[:80]:
    print(f"{h[0]:08x} {h[1]} {h[2]}")
