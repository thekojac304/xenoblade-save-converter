"""A1: exact DE per-item data loss on DE -> 3DS (real game save a5 + synthetic flags) -> DE, using the unchanged
3A/2H engine. For every box: which DE record bytes differ between the original DE save and the returned one, for
items matched by identity (gid + content + serial order), and why (slot moved / record rewritten / restored).
Read-only on fixtures; outputs go to phase3c/work."""
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3b", "tests"))
import hubfix as H  # noqa: E402
import canon  # noqa: E402
import de_save  # noqa: E402
import xc3dservice as s3  # noqa: E402

T = H.T
OUT = os.path.join(ROOT, "phase3c", "work", "a1_roundtrip")


def records(img):
    out = {}
    for name, typ, off, size, n in de_save.BOXES:
        out[name] = {i: bytes(img[off + size * i:off + size * (i + 1)]) for i in range(n) if img[off + size * i + 0x10]}
    return out


def ident(name, rec, img_canon, sl):
    return canon.item_key(name, canon.strip_order(img_canon["inventory"][name][sl]))


def main(src=H.DE_S232, x3=None, tag="s232_a5"):
    d = H.fresh("p3c_" + tag)
    r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=src, out=os.path.join(d, "a"), template=H.X3_USER,
                                       overflow="sidecar"))
    x3b = x3 if x3 is not None else H.x3_a5_played()
    p = H.put(os.path.join(d, "in", "monado01"), x3b)
    r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=p, out=os.path.join(d, "b"), record=r1.sidecar_path,
                                       current=src))
    orig, back = H.rd(src), H.rd(r2.main_output)
    co, cb = canon.from_de(orig, T)["shared"], canon.from_de(back, T)["shared"]
    ro, rb = records(orig), records(back)
    rep = {}
    for name, typ, off, size, n in de_save.BOXES:
        same_slot_exact = moved_exact = same_slot_diff = moved_diff = 0
        lost_bytes = collections.Counter()
        # pair by identity, in DE serial order (oldest first) on both sides
        po = collections.defaultdict(list)
        for sl in sorted(ro[name], key=lambda s: struct.unpack_from("<I", ro[name][s], 0xC)[0]):
            po[ident(name, ro[name][sl], co, sl)].append(sl)
        pb = collections.defaultdict(list)
        for sl in sorted(rb[name], key=lambda s: struct.unpack_from("<I", rb[name][s], 0xC)[0]):
            pb[ident(name, rb[name][sl], cb, sl)].append(sl)
        for k, sls in po.items():
            for a, b in zip(sls, pb.get(k, [])):
                x, y = ro[name][a], rb[name][b]
                diff = [i for i in range(size) if x[i] != y[i] and i not in (0, 1)]   # +0 index = slot
                if not diff:
                    if a == b:
                        same_slot_exact += 1
                    else:
                        moved_exact += 1
                else:
                    if a == b:
                        same_slot_diff += 1
                    else:
                        moved_diff += 1
                    for i in diff:
                        lost_bytes[i] += 1
        rep[name] = {"orig_items": len(ro[name]), "back_items": len(rb[name]), "same_slot_exact": same_slot_exact,
                     "moved_exact": moved_exact, "same_slot_diff": same_slot_diff, "moved_diff": moved_diff,
                     "diff_offsets": {f"+0x{k:02X}": v for k, v in sorted(lost_bytes.items())},
                     "de_only_entries": [len(canon.from_de(orig, T)["de_only"]["items"].get(name, {})),
                                         len(canon.from_de(back, T)["de_only"]["items"].get(name, {}))]}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, tag + ".json"), "w") as f:
        json.dump(rep, f, indent=1)
    for k, v in rep.items():
        print(k, json.dumps(v))
    return orig, back


if __name__ == "__main__":
    main()
