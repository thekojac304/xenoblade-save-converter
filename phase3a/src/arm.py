"""Static-analysis helpers for the Xenoblade 3D ARM11 code.bin (research tool, read-only, Phase 3A).

Layout from the ExHeader: .text at 0x100000, .rodata at 0x479000, .data at 0x4BD000 (code.bin is the three
segments back to back, page aligned).  Uses capstone (ARM mode; the game is compiled to ARM, not Thumb).

  python arm.py dis <addr> [count]          disassemble
  python arm.py xref <value>                literal-pool words equal to value, and the instructions loading them
  python arm.py func <addr>                 disassemble the function containing addr (push..pop heuristic)
"""
import bisect
import os
import struct
import sys

import capstone

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "research", "rom", "code.bin")
BASE = 0x100000
_cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
_cs.detail = False
_data = None
_lit = None


def data():
    global _data
    if _data is None:
        _data = open(CODE, "rb").read()
    return _data


def word(a):
    return struct.unpack_from("<I", data(), a - BASE)[0]


def dis(addr, count=40):
    d = data()
    out = []
    a = addr
    for _ in range(count):
        ins = list(_cs.disasm(d[a - BASE:a - BASE + 4], a))
        if ins:
            i = ins[0]
            out.append((a, f"{i.mnemonic} {i.op_str}"))
        else:
            out.append((a, f".word 0x{word(a):08x}"))
        a += 4
    return out


def literal_loads():
    """[(insn addr, literal addr, value)] for every LDR Rx, [pc, #imm] in .text."""
    global _lit
    if _lit is None:
        d = data()
        _lit = []
        text_end = 0x479000
        for off in range(0, text_end - BASE, 4):
            w = struct.unpack_from("<I", d, off)[0]
            # LDR (immediate, literal): cond 01 0 1 U 0 0 1 1111 Rt imm12  -> mask 0x0F7F0000 == 0x051F0000
            if w & 0x0F7F0000 == 0x051F0000 and (w >> 28) != 0xF:
                imm = w & 0xFFF
                a = BASE + off
                lit = a + 8 + (imm if w & (1 << 23) else -imm)
                if BASE <= lit < BASE + len(d) - 4:
                    _lit.append((a, lit, struct.unpack_from("<I", d, lit - BASE)[0]))
    return _lit


def xref(value):
    return [(a, lit) for a, lit, v in literal_loads() if v == value]


def branch_target(a):
    w = word(a)
    if (w >> 25) & 7 == 5:
        imm = w & 0xFFFFFF
        if imm & 0x800000:
            imm -= 1 << 24
        return a + 8 + imm * 4, bool(w & (1 << 24))
    return None


def callers(target):
    d = data()
    res = []
    for off in range(0, 0x479000 - BASE, 4):
        w = struct.unpack_from("<I", d, off)[0]
        if (w >> 24) & 0xF == 0xB and (w >> 28) != 0xF:
            imm = w & 0xFFFFFF
            if imm & 0x800000:
                imm -= 1 << 24
            if BASE + off + 8 + imm * 4 == target:
                res.append(BASE + off)
    return res


def func_start(addr):
    a = addr
    while a > BASE:
        w = word(a)
        if w & 0xFFFF4000 == 0xE92D4000:   # push {..., lr}
            return a
        a -= 4
    return BASE


def func(addr, limit=600):
    s = func_start(addr)
    out = []
    for a, t in dis(s, limit):
        out.append((a, t))
        if a > s and (t.startswith("pop") and "pc" in t or t.startswith("ldm") and "pc" in t):
            # keep going if more code follows before the next push (conditional returns)
            nxt = word(a + 4)
            if nxt & 0xFFFF4000 == 0xE92D4000:
                break
    return out


def show(lines):
    for a, t in lines:
        print(f"{a:08x}  {t}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dis":
        show(dis(int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 40))
    elif cmd == "xref":
        for a, lit in xref(int(sys.argv[2], 16)):
            print(f"{a:08x} loads literal @{lit:08x}  (func {func_start(a):08x})")
    elif cmd == "func":
        show(func(int(sys.argv[2], 16)))
    elif cmd == "callers":
        for a in callers(int(sys.argv[2], 16)):
            print(f"{a:08x} (func {func_start(a):08x})")


def adr_refs(target, window=0):
    """Instructions 'add rd, pc, #imm' / 'sub rd, pc, #imm' that compute target (+-window)."""
    d = data()
    out = []
    for off in range(0, 0x479000 - BASE, 4):
        w = struct.unpack_from("<I", d, off)[0]
        if (w & 0x0FFF0000) in (0x028F0000, 0x024F0000) and (w >> 28) != 0xF:
            rot = (w >> 8) & 0xF
            imm8 = w & 0xFF
            imm = ((imm8 >> (2 * rot)) | (imm8 << (32 - 2 * rot))) & 0xFFFFFFFF
            a = BASE + off
            t = a + 8 + imm if (w & 0x0FFF0000) == 0x028F0000 else a + 8 - imm
            if abs(t - target) <= window:
                out.append((a, t))
    return out
