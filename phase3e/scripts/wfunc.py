"""Disassemble the whole Wii function containing an address (start = previous `stwu r1,-N(r1)`, end = `blr` after the
matching epilogue or a size limit), annotating bl targets.   python wfunc.py <hex addr> [max]"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import capstone as cs  # noqa: E402

DOL = os.path.join(ROOT, "exe", "wii", "main.dol")
d = open(DOL, "rb").read()
secs = []
for i in range(18):
    off, addr, size = (struct.unpack_from(">I", d, b + 4 * i)[0] for b in (0, 0x48, 0x90))
    if size:
        secs.append((addr, off, size))


def word(a):
    for addr, off, size in secs:
        if addr <= a < addr + size:
            return struct.unpack_from(">I", d, off + a - addr)[0], d[off + a - addr:off + a - addr + 4]
    raise KeyError(hex(a))


def start_of(a):
    while True:
        w, _ = word(a)
        if w >> 16 == 0x9421:   # stwu r1, -N(r1)
            return a
        a -= 4


md = cs.Cs(cs.CS_ARCH_PPC, cs.CS_MODE_32 | cs.CS_MODE_BIG_ENDIAN)
if __name__ == "__main__":
    a = start_of(int(sys.argv[1], 16))
    mx = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    n = 0
    while n < mx:
        w, raw = word(a)
        ins = next(md.disasm(raw, a), None)
        print(f"{a:08x}  {ins.mnemonic:8s} {ins.op_str}" if ins else f"{a:08x}  .word {w:#010x}")
        if ins and ins.mnemonic == "blr" and n > 8:
            break
        a += 4
        n += 1
