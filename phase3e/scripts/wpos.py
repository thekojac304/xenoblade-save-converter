"""DEBUG POSITIONING of a Wii-layout save (Wii monado01 or 3DS monado0N): set the player position (x, y, z) and facing
angle (degrees) at 0x11EE0 and fix the checksums. Nothing else changes (no story, party, flag or equipment field);
the change is reported.   python wpos.py <in> <out> <x> <y> <z> <angle_deg>"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "phase3a", "src")]
import xc3d  # noqa: E402

POS = 0x11EE0


def set_pos(data, x, y, z, ang):
    is3 = data[:4] == b"!qzb"
    w = bytearray(xc3d.transcode(xc3d.unpack(data), "wii") if is3 else data)
    before = struct.unpack_from(">4f", w, POS)
    struct.pack_into(">4f", w, POS, x, y, z, ang)
    w = xc3d.fix_wii_checksums(bytes(w))
    if is3:
        import xc3dservice as s3
        out = xc3d.pack(xc3d.transcode(w, "3ds"))
        return out, before
    return w, before


if __name__ == "__main__":
    src, dst = sys.argv[1:3]
    x, y, z, a = (float(v) for v in sys.argv[3:7])
    out, before = set_pos(open(src, "rb").read(), x, y, z, a)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, "wb").write(out)
    print("position", [round(v, 3) for v in before], "->", [x, y, z, a])
