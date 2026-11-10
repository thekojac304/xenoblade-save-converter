"""Decompress a Switch NSO into a flat memory image (read-only on the input).

Usage: python -I nso_extract.py <main (NSO)> <out.bin>
Segments are placed at their memory offsets; bss is not materialised.
"""
import struct
import sys

import lz4.block


def main(src, out):
    d = open(src, "rb").read()
    assert d[:4] == b"NSO0", "not an NSO"
    flags = struct.unpack_from("<I", d, 0xC)[0]
    segs = []
    for i in range(3):
        foff, moff, dsize = struct.unpack_from("<III", d, 0x10 + 0x10 * i)
        csize = struct.unpack_from("<I", d, 0x60 + 4 * i)[0]
        raw = d[foff:foff + csize]
        data = lz4.block.decompress(raw, uncompressed_size=dsize) if flags >> i & 1 else raw
        assert len(data) == dsize
        segs.append((moff, data))
        print(f"segment {('text', 'rodata', 'data')[i]}: mem 0x{moff:X} size 0x{dsize:X}")
    end = max(m + len(s) for m, s in segs)
    img = bytearray(end)
    for m, s in segs:
        img[m:m + len(s)] = s
    open(out, "wb").write(img)
    print(f"build id {d[0x40:0x50].hex()} -> {out} ({len(img)} bytes)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
