import sys, struct, itertools
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\tools")
import wii_save as W
d = open(sys.argv[1], "rb").read()
def crc16(data, poly, init, refin, refout, xorout):
    crc = init
    if refin:
        rp = int('{:016b}'.format(poly)[::-1], 2)
        for b in data:
            crc ^= b
            for _ in range(8): crc = (crc >> 1) ^ rp if crc & 1 else crc >> 1
    else:
        for b in data:
            crc ^= b << 8
            for _ in range(8): crc = ((crc << 1) ^ poly) & 0xffff if crc & 0x8000 else (crc << 1) & 0xffff
    return crc ^ xorout
tests = []
for tag, hdr, s, e in W.SECTIONS[3:6]:
    tests.append((tag, d[s:e], struct.unpack_from("<I", d, hdr+12)[0], d, hdr, s, e))
for tag, data, want, *_ in tests:
    print(tag, hex(want), len(data), "sum8", hex(sum(data)&0xffff), "sum16le", hex(sum(struct.unpack("<%dH"%(len(data)//2), data[:len(data)//2*2]))&0xffff))
import zlib
for tag, data, want, *_ in tests:
    print(tag, "crc32", hex(zlib.crc32(data)), hex(zlib.crc32(data)&0xffff))
for poly in [0x8005, 0x1021, 0x3d65, 0x8bb7, 0xa097, 0x0589, 0xc867, 0x5935, 0x755b, 0x1dcf]:
  for init in [0, 0xffff]:
    for ref in [False, True]:
      for xo in [0, 0xffff]:
        ok = all(crc16(data, poly, init, ref, ref, xo) == want for tag, data, want, *_ in tests)
        if ok: print("FOUND", hex(poly), hex(init), ref, hex(xo))
# byte-swapped data (as if computed on BE data?) - try CRC16 ARC on the Wii-endian? can't know widths. try per-u32 swap
for tag, data, want, *_ in tests:
    sw = b"".join(data[i:i+4][::-1] for i in range(0, len(data)//4*4, 4))
    sw2 = b"".join(data[i:i+2][::-1] for i in range(0, len(data)//2*2, 2))
    print(tag, hex(want), "arc u32swap", hex(W.crc16_arc(sw)), "arc u16swap", hex(W.crc16_arc(sw2)))
