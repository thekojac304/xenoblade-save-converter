"""A1: how the Wii/3DS game orders items after real pickups. For game-written pairs (before -> after play), per box:
items kept at the same slot, stacks whose quantity grew, and whether their relative age order changed. Read-only."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3b", "tests"))
import hubfix as H  # noqa: E402
import canon  # noqa: E402
import xc3dservice as s3  # noqa: E402

T = H.T


def wii_img(p):
    b = H.rd(p)
    if b[:4] == b"USRD":
        return b
    return s3.load_3ds(p, "x")[2]


def pair(a_p, b_p, label):
    a, b = canon.from_wii(wii_img(a_p), T)["shared"]["inventory"], canon.from_wii(wii_img(b_p), T)["shared"]["inventory"]
    print("==", label)
    for box in a:
        same = [sl for sl in a[box] if sl in b[box] and b[box][sl]["gid"] == a[box][sl]["gid"]]
        grown = [sl for sl in same if b[box][sl]["qty"] > a[box][sl]["qty"]]
        shrunk = [sl for sl in same if b[box][sl]["qty"] < a[box][sl]["qty"]]
        new = [sl for sl in b[box] if sl not in same]
        gone = [sl for sl in a[box] if sl not in same]
        if not (grown or shrunk or new or gone):
            continue
        sa = sorted(same, key=lambda s: a[box][s]["order"])
        sb = sorted(same, key=lambda s: b[box][s]["order"])
        moved_up = [s for s in grown if sb.index(s) != sa.index(s)]
        newest_after = sorted(b[box], key=lambda s: -b[box][s]["order"])[:5]
        print(f"  {box}: same {len(same)} grown {len(grown)} shrunk {len(shrunk)} new {len(new)} gone {len(gone)}; "
              f"order of kept items unchanged: {sa == sb}; grown stacks that changed rank: {moved_up[:8]}; "
              f"newest after: {newest_after} new slots {new[:8]} grown {grown[:8]}")


A2 = os.path.join(ROOT, "phase3a", "runs", "azahar")
for run in sorted(os.listdir(A2)):
    print(run, os.listdir(os.path.join(A2, run)))
pair(H.W150, H.W150_LATER, "Dolphin 2E: user s150 -> played on (d6_travel)")
pair(os.path.join(ROOT, "phase3b", "runs", "azahar", "a1_gen2_3ds", "input", "monado01")
     if os.path.exists(os.path.join(ROOT, "phase3b", "runs", "azahar", "a1_gen2_3ds", "input", "monado01")) else H.X3_A1,
     os.path.join(ROOT, "phase3b", "fixtures", "x3_azahar_battle_monado01"), "Azahar 3B a1 battle")
