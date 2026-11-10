"""ARM64 helpers for the DE flat image (exe/de/main.bin, image base 0), read-only.

  python a64.py <main.bin> dis <hex addr> [count]
  python a64.py <main.bin> xref-addr <hex target>     ADRP+ADD/LDR materialising target
  python a64.py <main.bin> xref-call <hex target>     BL call sites
"""
import struct
import sys

import capstone as cs

MD = cs.Cs(cs.CS_ARCH_ARM64, cs.CS_MODE_ARM)
TEXT_END = 0x8B7F58  # end of .text in this build (see nso_extract output)


def dis(d, a, n):
    out = []
    for k in range(n):
        w = d[a + 4 * k:a + 4 * k + 4]
        ins = next(MD.disasm(w, a + 4 * k), None)
        out.append((a + 4 * k, ins.mnemonic if ins else ".word", ins.op_str if ins else w[::-1].hex()))
    return out


def _adrp(w, pc):
    if w & 0x9F000000 != 0x90000000:
        return None
    imm = ((w >> 29) & 3) | ((w >> 5) & 0x7FFFF) << 2
    if imm & (1 << 20):
        imm -= 1 << 21
    return w & 31, (pc & ~0xFFF) + (imm << 12)


def xref_addr(d, target, end=TEXT_END):
    res = []
    for pc in range(0, end, 4):
        w = struct.unpack_from("<I", d, pc)[0]
        a = _adrp(w, pc)
        if not a or a[1] != target & ~0xFFF:
            continue
        rd = a[0]
        for k in range(1, 8):
            w2 = struct.unpack_from("<I", d, pc + 4 * k)[0]
            if w2 & 0xFFC00000 == 0x91000000 and (w2 >> 5 & 31) == rd:  # add xD, xN, #imm
                if a[1] + (w2 >> 10 & 0xFFF) == target:
                    res.append(pc + 4 * k)
                break
    return res


def xref_call(d, target, end=TEXT_END):
    res = []
    for pc in range(0, end, 4):
        w = struct.unpack_from("<I", d, pc)[0]
        if w >> 26 == 0b100101:
            off = w & 0x3FFFFFF
            if off & (1 << 25):
                off -= 1 << 26
            if pc + 4 * off == target:
                res.append(pc)
    return res


if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    mode, a = sys.argv[2], int(sys.argv[3], 16)
    if mode == "dis":
        for pc, m, o in dis(d, a, int(sys.argv[4]) if len(sys.argv) > 4 else 40):
            print(f"{pc:08x}  {m:8} {o}")
    elif mode == "xref-addr":
        print(" ".join(f"{x:08x}" for x in xref_addr(d, a)))
    else:
        print(" ".join(f"{x:08x}" for x in xref_call(d, a)))
