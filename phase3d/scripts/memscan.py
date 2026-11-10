"""Search a Monado guest-memory dump for position triples (x, y, z little-endian floats) inside a box, e.g. the guest
room floor of Whitewing Palace (y ~ 154.6). Prints the addresses and values, grouped by object (32-byte proximity).
  python memscan.py <dump.bin> <base hex> [ylo yhi xlo xhi zlo zhi]"""
import struct
import sys

p, base = sys.argv[1], int(sys.argv[2], 16)
yl, yh, xl, xh, zl, zh = (float(v) for v in (sys.argv[3:9] or (154.0, 155.2, 40, 220, 380, 540)))
d = open(p, "rb").read()
hits = []
for o in range(0, len(d) - 12, 4):
    y = struct.unpack_from("<f", d, o + 4)[0]
    if not (yl <= y <= yh):
        continue
    x, z = struct.unpack_from("<f", d, o)[0], struct.unpack_from("<f", d, o + 8)[0]
    if xl <= x <= xh and zl <= z <= zh:
        hits.append((base + o, round(x, 2), round(y, 3), round(z, 2)))
seen = {}
for a, x, y, z in hits:
    key = (round(x, 1), round(z, 1))
    seen.setdefault(key, []).append(hex(a))
for (x, z), addrs in sorted(seen.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    print(f"x {x:8.1f} z {z:8.1f}  copies {len(addrs):3d}  first {addrs[0]}")
