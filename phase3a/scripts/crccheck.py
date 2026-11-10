import sys, struct
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\tools")
import wii_save as W
def xmodem(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8): crc = ((crc << 1) ^ 0x1021) & 0xffff if crc & 0x8000 else (crc << 1) & 0xffff
    return crc
for p in sys.argv[1:]:
    d = open(p, "rb").read()
    res = []
    for tag, hdr, s, e in W.SECTIONS:
        want = struct.unpack_from("<I", d, hdr+12)[0]
        res.append(f"{tag}:{'ok' if want == xmodem(d[s:e]) else 'BAD'}")
    # what is between sections' data end and next header?
    gaps = []
    for (tag, hdr, s, e), nxt in zip(W.SECTIONS, W.SECTIONS[1:]+[(None, 0x28000, 0, 0)]):
        g = d[e:nxt[1]]
        if any(g): gaps.append((tag, hex(e), hex(nxt[1]), g[:16].hex()))
    print(p, " ".join(res), "nonzero gaps:", gaps, "tail nonzero:", any(d[0x248F0:]))
