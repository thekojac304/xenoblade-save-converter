"""Robust PowerPC (Gekko/Broadway) disassembly of the Wii main.dol, one word at a time (read-only).

Unlike xdis.py it never stops at an undecodable word (paired-single and data words print as .word).

  python ppc.py <main.dol> <hex vaddr> [count]
  python ppc.py <main.dol> xref <hex target>        list bl/b call sites of a function
"""
import struct
import sys

import capstone as cs

from xdis import dol_read, dol_sections

MD = cs.Cs(cs.CS_ARCH_PPC, cs.CS_MODE_32 | cs.CS_MODE_BIG_ENDIAN | cs.CS_MODE_PS)


def dis(d, a, n):
    raw = dol_read(d, a, 4 * n)
    out = []
    for k in range(n):
        w = raw[4 * k:4 * k + 4]
        ins = next(MD.disasm(w, a + 4 * k), None)
        out.append((a + 4 * k, ins.mnemonic if ins else ".word", ins.op_str if ins else "0x%08x" % struct.unpack(">I", w)[0]))
    return out


def xrefs(d, target):
    res = []
    for name, off, addr, size in dol_sections(d):
        if not name.startswith("T"):
            continue
        for o in range(0, size, 4):
            w = struct.unpack_from(">I", d, off + o)[0]
            if w >> 26 == 18:
                li = w & 0x03FFFFFC
                if li & 0x02000000:
                    li -= 0x04000000
                tgt = li if w & 2 else addr + o + li
                if tgt == target:
                    res.append((addr + o, "bl" if w & 1 else "b"))
    return res


DFORM = {32: "lwz", 33: "lwzu", 34: "lbz", 35: "lbzu", 36: "stw", 37: "stwu", 38: "stb", 39: "stbu", 40: "lhz",
         41: "lhzu", 42: "lha", 43: "lhau", 44: "sth", 45: "sthu", 48: "lfs", 50: "lfd", 52: "stfs", 54: "stfd",
         14: "addi"}


def disp_users(d, disps):
    """All D-form loads/stores/addi in text whose 16-bit displacement is in disps."""
    want = {x & 0xFFFF for x in disps}
    res = []
    for name, off, addr, size in dol_sections(d):
        if not name.startswith("T"):
            continue
        for o in range(0, size, 4):
            w = struct.unpack_from(">I", d, off + o)[0]
            op = w >> 26
            if op in DFORM and (w & 0xFFFF) in want and (w >> 16 & 31) not in (0, 1, 2, 13):
                res.append((addr + o, DFORM[op], w >> 21 & 31, w >> 16 & 31, w & 0xFFFF))
    return res


if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    if sys.argv[2] == "xref":
        for a, k in xrefs(d, int(sys.argv[3], 16)):
            print(f"{a:08x} {k}")
    else:
        for a, m, o in dis(d, int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 40):
            print(f"{a:08x}  {m:8} {o}")


def find_str(d, s):
    """Virtual addresses of a NUL-terminated string in data sections."""
    out = []
    pat = s.encode() + b"\0"
    for name, off, addr, size in dol_sections(d):
        blob = d[off:off + size]
        i = blob.find(pat)
        while i >= 0:
            if i == 0 or blob[i - 1] == 0:
                out.append(addr + i)
            i = blob.find(pat, i + 1)
    return out


def addr_refs(d, target, window=0x40):
    """Code that materialises target via lis rX,hi + addi/ori rY,rX,lo, or lis + later addi off a base string pool."""
    res = []
    hi, lo = (target + 0x8000) >> 16 & 0xFFFF, target & 0xFFFF
    for name, off, addr, size in dol_sections(d):
        if not name.startswith("T"):
            continue
        for o in range(0, size - 4, 4):
            w = struct.unpack_from(">I", d, off + o)[0]
            if w >> 26 == 15 and (w >> 16 & 31) == 0 and (w & 0xFFFF) == hi:
                rd = w >> 21 & 31
                for k in range(1, 12):
                    w2 = struct.unpack_from(">I", d, off + o + 4 * k)[0]
                    if w2 >> 26 == 14 and (w2 >> 16 & 31) == rd and (w2 & 0xFFFF) == lo:
                        res.append(addr + o + 4 * k)
                        break
    return res


def const_refs(d, lo=0x804F0000, hi=0x80670000):
    """Approximate constant propagation over text: value -> [code addresses] for lis/addi/ori-built pointers.

    Tracks per-register constants from lis (+addi/ori) and follow-on addi chains; resets at blr/bctr and calls.
    Good enough to find which code passes a given string (e.g. a BDAT column name) to a getter.
    """
    out = {}
    for name, off, addr, size in dol_sections(d):
        if not name.startswith("T"):
            continue
        regs = {}
        for o in range(0, size, 4):
            w = struct.unpack_from(">I", d, off + o)[0]
            op, rd, ra, imm = w >> 26, w >> 21 & 31, w >> 16 & 31, w & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            if op == 15 and ra == 0:  # lis
                regs[rd] = (imm << 16) & 0xFFFFFFFF
            elif op == 14 and ra in regs:  # addi
                v = (regs[ra] + simm) & 0xFFFFFFFF
                regs[rd] = v
                if lo <= v < hi:
                    out.setdefault(v, []).append(addr + o)
            elif op == 24 and rd in regs:  # ori rA, rS, imm  (rS = rd field)
                regs[ra] = regs[rd] | imm
            elif w in (0x4E800020, 0x4E800420) or op == 18:
                regs = {k: v for k, v in regs.items() if k >= 14} if op == 18 else {}
            elif op in (32, 34, 40, 42, 48, 50) and rd in regs:
                regs.pop(rd, None)
    return out
