"""Find direct `bl` callers of a Wii DOL function (read-only).  python wii_callers.py <main.dol> <hex target> [...]"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import xdis  # noqa: E402


def callers(d, target):
    out = []
    for i in range(7):  # text sections
        off = struct.unpack_from(">I", d, 0x00 + 4 * i)[0]
        addr = struct.unpack_from(">I", d, 0x48 + 4 * i)[0]
        size = struct.unpack_from(">I", d, 0x90 + 4 * i)[0]
        if not size:
            continue
        for j in range(0, size, 4):
            w = struct.unpack_from(">I", d, off + j)[0]
            if w >> 26 == 18 and w & 3 == 1:
                li = w & 0x03FFFFFC
                if li & 0x02000000:
                    li -= 0x04000000
                if (addr + j + li) & 0xFFFFFFFF == target:
                    out.append(addr + j)
    return out


if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    for t in sys.argv[2:]:
        print(t, [hex(x) for x in callers(d, int(t, 16))])
