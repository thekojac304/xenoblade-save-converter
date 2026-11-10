"""Dump stored equipment: DE stash (0x3BB50) entries and Wii/3DS staging records (slot 150+k) with full fields, plus
the characters' equipment references.   python dump_store.py <save> <chars e.g. 1,2,4>"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "phase3a", "src")]
import de_save  # noqa: E402
import wii_save  # noqa: E402

STASH, ENTRY = 0x3BB50, 0xB4
SL = ["head", "body", "arm", "legs", "feet", "weapon", "x6"]


def de_rec(b, o, size):
    r = {"index": struct.unpack_from("<H", b, o)[0], "type": struct.unpack_from("<H", b, o + 2)[0],
         "gid": struct.unpack_from("<H", b, o + 4)[0], "gid_type": struct.unpack_from("<H", b, o + 6)[0],
         "qty": struct.unpack_from("<H", b, o + 8)[0], "u0a": struct.unpack_from("<H", b, o + 0xA)[0],
         "serial": struct.unpack_from("<I", b, o + 0xC)[0], "present": b[o + 0x10], "fav": b[o + 0x11],
         "b12": b[o + 0x12:o + 0x14].hex()}
    if size == 0x30:
        r.update(armour=b[o + 0x14], nsock=b[o + 0x15], b16=b[o + 0x16:o + 0x18].hex(),
                 sockets=[(hex(struct.unpack_from("<I", b, o + 0x18 + 8 * s)[0]),
                           struct.unpack_from("<I", b, o + 0x1C + 8 * s)[0]) for s in range(3)])
    else:
        r.update(rank=b[o + 0x16], attr=b[o + 0x17], cyl=b[o + 0x19], effect=struct.unpack_from("<H", b, o + 0x1C)[0],
                 strength=b[o + 0x1E], chance=b[o + 0x1F], rest=b[o + 0x14:o + 0x2C].hex())
    return r


def main(p, chars):
    b = open(p, "rb").read()
    if b[:4] == b"!qzb":
        import xc3d
        b = xc3d.transcode(xc3d.unpack(b), "wii")
    if b[:4] == b"USRD":
        ir = wii_save.decode_bytes(b)
        print("WII party", ir["party"])
        for k in chars:
            print(" char", k, {s: (e["gid"], e["row"], e["box_index"]) for s, e in ir["characters"][k]["equipment"].items()})
            for box in SL[:6]:
                for r in ir["items"][box]:
                    if r["index"] == 150 + k:
                        print("   ", box, r["header"], [(s["desc"], s["gem_box_ref"]) for s in r["sockets"] if s["desc"]],
                              "slots", r["slot_count"], "kind", r["kind"], "tail", r["tail"])
        t = bytes.fromhex(ir["items"]["tail"]["char_gem_records_raw"])
        nz = [(i // 8 + 1, i % 8, t[16 * i:16 * i + 16].hex()) for i in range(len(t) // 16) if any(t[16 * i:16 * i + 16])]
        print(" tail char gems nonzero:", nz[:12])
    else:
        ir = de_save.decode_bytes(b)
        print("DE party", ir["party"])
        for k in chars:
            print(" char", k, {s: (e["index"], e["type"]) for s, e in ir["characters"][k]["equipment"].items()})
            for j in range(7):
                o = STASH + ENTRY * (7 * (k - 1) + j)
                if not any(b[o:o + ENTRY]):
                    continue
                print("   ", SL[j], de_rec(b, o, 0x30))
                for g in range(3):
                    go = o + 0x30 + 0x2C * g
                    if any(b[go:go + 0x2C]):
                        print("       gem", g, de_rec(b, go, 0x2C))


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2].split(",")])
