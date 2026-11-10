import sys, struct
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\tools")
import wii_save as W
d = open(sys.argv[1], "rb").read()
print("filehdr", d[:16].hex())
for tag, hdr, s, e in W.SECTIONS:
    t = d[hdr:hdr+4]; sz, hs, z, crc = struct.unpack_from("<IIHH", d, hdr+4)
    print(tag, hex(hdr), t, hex(sz), hex(hs), z, hex(crc), "crc16 LE-data:", hex(W.crc16_arc(d[s:e])), "match" if crc == W.crc16_arc(d[s:e]) else "")
# scan for all 4-char tags
import re
for m in re.finditer(rb"[A-Z]{4}", d):
    if m.start() % 16 == 0: print(hex(m.start()), m.group(), d[m.start()+4:m.start()+16].hex())
