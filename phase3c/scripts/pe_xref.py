"""Read-only: find code in Monado's xcde.exe that references a given string (RIP-relative LEA) and disassemble around
it, to learn how a debug switch is parsed.  python pe_xref.py <string> [window]"""
import re
import struct
import sys

import capstone as cs

EXE = r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\build\xcde.exe"
d = open(EXE, "rb").read()
pe = struct.unpack_from("<I", d, 0x3C)[0]
nsec = struct.unpack_from("<H", d, pe + 6)[0]
opt = struct.unpack_from("<H", d, pe + 20)[0]
base = struct.unpack_from("<Q", d, pe + 24 + 24)[0]
secs = []
for i in range(nsec):
    o = pe + 24 + opt + 40 * i
    name = d[o:o + 8].rstrip(b"\0").decode()
    vsz, va, rsz, raw = struct.unpack_from("<IIII", d, o + 8)
    secs.append((name, va, vsz, raw, rsz))


def off2rva(off):
    for n, va, vsz, raw, rsz in secs:
        if raw <= off < raw + rsz:
            return va + off - raw


target = sys.argv[1].encode() + b"\0"
win = int(sys.argv[2]) if len(sys.argv) > 2 else 60
soff = d.find(target)
srva = off2rva(soff)
print("string at rva", hex(srva))
text = next(s for s in secs if s[0] == ".text")
n, va, vsz, raw, rsz = text
code = d[raw:raw + rsz]
md = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
hits = []
for m in re.finditer(rb"\x48\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]|\x4c\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", code):
    i = m.start()
    disp = struct.unpack_from("<i", code, i + 3)[0]
    if va + i + 7 + disp == srva:
        hits.append(i)
print("xrefs", len(hits))
for i in hits[:3]:
    start = i
    for ins in md.disasm(code[start:start + win * 6], va + start):
        print(f"  {ins.address:08x} {ins.mnemonic} {ins.op_str}")
        if ins.address > va + i + win * 4:
            break
    print("---")
