"""A1: does the Wii/3DS game move items between slots? Compare the converter's exported Wii-layout image with the
game-written save that loaded it (real runs), per box: same slot+same key, moved, added, removed. Read-only."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3b", "tests"))
import hubfix as H  # noqa: E402
import canon  # noqa: E402
import sidecar as scmod  # noqa: E402
import xc3dservice as s3  # noqa: E402
import json  # noqa: E402

T = H.T


def inv(img):
    return canon.from_wii(img, T)["shared"]["inventory"]


def compare(exp, cur, label):
    a, b = inv(exp), inv(cur)
    tot = {}
    for box in a:
        same = moved = added = removed = 0
        for sl, r in a[box].items():
            k = canon.item_key(box, r)
            if sl in b[box] and canon.item_key(box, b[box][sl]) == k:
                same += 1
            else:
                removed += 1
        for sl, r in b[box].items():
            if not (sl in a[box] and canon.item_key(box, a[box][sl]) == canon.item_key(box, r)):
                added += 1
        if removed or added:
            tot[box] = {"same_slot": same, "gone_from_slot": removed, "new_in_slot": added}
    print(label, json.dumps(tot) if tot else "no slot changes")


# 2F d2: s232 export (Wii) -> Wii game re-save
G = os.path.join(ROOT, "phase2f", "fixtures", "real", "game_chain_s232")
compare(H.rd(os.path.join(G, "w_export_2f")), H.rd(os.path.join(G, "w_saved_by_wii_game")), "dolphin d2 s232")
# 3A a5: s232 -> 3DS export -> 3DS game re-save
rec_dir = os.path.join(ROOT, "phase3a", "runs", "azahar", "a5_de_s232_to_3ds_fixed")
print(os.listdir(rec_dir))
