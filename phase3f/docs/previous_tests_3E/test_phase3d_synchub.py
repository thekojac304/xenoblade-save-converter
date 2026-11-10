"""Phase 3D Sync Hub regression with character 8 (the hub is the unchanged 3B code; the engine is 3D):
- a DE save from the story split (members away with stored gear, defect D2) blocks the sync with the exact reason and
  changes nothing (all-or-nothing, 3B design);
- the post-reunion save (291, Fiora = character 8, full party) syncs; Wii and 3DS play (synthetic hubfix rules) on it
  come back; DE-only character data survives; an unchanged re-save is in sync; rollback restores a generation."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_phase3d_characters as C  # noqa: E402
from test_phase3d_characters import H, canon, rd, shared, T  # noqa: E402

import xc3d  # noqa: E402
from xcsync import sync  # noqa: E402


def w_of_3ds(b):
    return xc3d.transcode(xc3d.unpack(b), "wii")


def sh(img):
    if img[:4] == b"!qzb":
        img = w_of_3ds(img)
    return (canon.from_wii(img, T) if len(img) == 163840 else canon.from_de(img, T))["shared"]


def party(img):
    if img[:4] == b"!qzb":
        img = w_of_3ds(img)
    return (canon.from_wii(img, T) if len(img) == 163840 else canon.from_de(img, T))["shared"]["party"]


class TestHubCharacter8(unittest.TestCase):
    def test_split_blocks_reunion_syncs(self):
        fx = H.HubFx("p3d_hub_c8")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(C.de(288)), age=600)
        with self.assertRaises(sync.Blocked) as cm:
            fx.sync()
        self.assertIn("Fiora is away from the party", str(cm.exception))   # 3E: only Fiora's stored gear is refused
        self.assertIsNone(fx.hub.current_generation()[1])          # nothing committed
        # the reunion save of the same playthrough
        fx.drop("Windows desktop", "bfsgame00.sav", rd(C.de(291)), age=500)
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        p291 = shared(C.de(291))["party"]
        self.assertEqual((party(fx.out("wii")), party(fx.out("3ds"))), (p291, p291))
        # Wii played (character 8 earns EXP), then the 3DS
        w2 = H.play_wii(fx.out("wii"), flags=4, skip=40, exp=100, char=8)
        fx.drop("Odin 2 Mini", "monado01", w2)
        r2 = fx.sync()
        self.assertTrue(r2.complete, r2.message)
        d2 = sh(fx.out("de"))
        c8 = shared(C.de(291))["characters"][8]
        self.assertEqual(d2["party"], p291)
        self.assertEqual((d2["characters"][8]["level"], d2["characters"][8]["exp"]), (c8["level"], c8["exp"] + 100))
        x3 = H.to_3ds(H.play_wii(w_of_3ds(fx.out("3ds")), flags=3, skip=60))
        fx.drop("New 3DS", "monado01", x3)
        r3 = fx.sync()
        self.assertTrue(r3.complete, r3.message)
        self.assertEqual(sh(fx.out("de"))["party"], p291)
        want = canon.from_de(rd(C.de(291)), T)["de_only"]["characters"]
        want[8] = dict(want[8], highest_level_exp=want[8]["highest_level_exp"] + 100)   # E1 (3C): tracks EXP at top level
        self.assertEqual(canon.from_de(fx.out("de"), T)["de_only"]["characters"], want)
        # unchanged re-save of the 3DS file: in sync
        fx.drop("New 3DS", "monado01", H.to_3ds(w_of_3ds(x3)))
        self.assertEqual(fx.scan().decision.kind, "in-sync")
        # rollback to the first generation restores the DE save exactly
        sync.rollback(fx.hub, 1)
        self.assertEqual(fx.out("de"), rd(C.de(291)))


if __name__ == "__main__":
    unittest.main()
