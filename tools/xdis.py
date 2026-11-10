"""Small read-only disassembly helper for the DE flat image (ARM64) and the Wii DOL (PowerPC BE).

Usage:
  python xdis.py de  <main.bin> <hex addr> [count]       disassemble ARM64 at image offset
  python xdis.py wii <main.dol> <hex vaddr> [count]      disassemble PPC at virtual address
  python xdis.py wii-sections <main.dol>                 list DOL sections
  python xdis.py de-imm <main.bin> <hex value>           find MOVZ/MOVK pairs building a 32-bit constant
  python xdis.py wii-imm <main.dol> <hex value>          find lis/ori|addi pairs building a 32-bit constant
"""
import struct
import sys

import capstone as cs


def dol_sections(d):
    secs = []
    for i in range(18):
        off = struct.unpack_from(">I", d, 0x00 + 4 * i)[0]
        addr = struct.unpack_from(">I", d, 0x48 + 4 * i)[0]
        size = struct.unpack_from(">I", d, 0x90 + 4 * i)[0]
        if size:
            secs.append(("T%d" % i if i < 7 else "D%d" % (i - 7), off, addr, size))
    return secs


def dol_read(d, vaddr, n):
    for _, off, addr, size in dol_sections(d):
        if addr <= vaddr < addr + size:
            o = off + vaddr - addr
            return d[o:o + n]
    raise ValueError("address not in DOL: %x" % vaddr)


def main(argv):
    mode = argv[0]
    d = open(argv[1], "rb").read()
    if mode == "de":
        a, n = int(argv[2], 16), int(argv[3]) if len(argv) > 3 else 40
        md = cs.Cs(cs.CS_ARCH_ARM64, cs.CS_MODE_ARM)
        for ins in md.disasm(d[a:a + 4 * n], a):
            print(f"{ins.address:08x}  {ins.mnemonic:8} {ins.op_str}")
    elif mode == "wii":
        a, n = int(argv[2], 16), int(argv[3]) if len(argv) > 3 else 40
        md = cs.Cs(cs.CS_ARCH_PPC, cs.CS_MODE_32 | cs.CS_MODE_BIG_ENDIAN)
        for ins in md.disasm(dol_read(d, a, 4 * n), a):
            print(f"{ins.address:08x}  {ins.mnemonic:8} {ins.op_str}")
    elif mode == "wii-sections":
        for s in dol_sections(d):
            print("%s file 0x%06X vaddr 0x%08X size 0x%X" % s)
    elif mode == "de-imm":
        v = int(argv[2], 16)
        lo, hi = v & 0xFFFF, v >> 16
        for off in range(0, 0x8B7F58, 4):
            w = struct.unpack_from("<I", d, off)[0]
            # MOVZ Wd, #lo  (0x52800000 | imm16<<5 | rd)
            if (w & 0xFFE00000) == 0x52800000 and (w >> 5 & 0xFFFF) == lo:
                rd = w & 31
                for k in range(1, 6):
                    w2 = struct.unpack_from("<I", d, off + 4 * k)[0]
                    # MOVK Wd, #hi, LSL #16 (0x72A00000)
                    if (w2 & 0xFFE0001F) == (0x72A00000 | rd) and (w2 >> 5 & 0xFFFF) == hi:
                        print(f"{off:08x}  movz/movk w{rd} = 0x{v:08X}")
                        break
    elif mode == "wii-imm":
        v = int(argv[2], 16)
        for _, off, addr, size in dol_sections(d):
            for o in range(off, off + size - 4, 4):
                w = struct.unpack_from(">I", d, o)[0]
                if w >> 26 == 15 and (w & 0xFFFF) in ((v >> 16) & 0xFFFF, ((v >> 16) + ((v >> 15) & 1)) & 0xFFFF):
                    rd = w >> 21 & 31
                    for k in range(1, 6):
                        w2 = struct.unpack_from(">I", d, o + 4 * k)[0]
                        op = w2 >> 26
                        if op == 24 and (w2 >> 16 & 31) == rd and (w2 & 0xFFFF) == v & 0xFFFF and (w >> 0 & 0xFFFF) == v >> 16:
                            print(f"{addr + o - off:08x}  lis/ori r{rd} = 0x{v:08X}")
                            break
                        if op == 14 and (w2 >> 16 & 31) == rd and (w2 & 0xFFFF) == v & 0xFFFF:
                            print(f"{addr + o - off:08x}  lis/addi r{rd} = 0x{v:08X}")
                            break


if __name__ == "__main__":
    main(sys.argv[1:])
