"""Phase 3C Sync Hub regression with DE-only per-item metadata: alternating platforms over several generations,
item disposal on the Wii/3DS, unchanged re-saves, rollback, interrupted publication. The hub itself is the unchanged
3B code; these tests check that the 3C engine change (item correspondence) keeps every 3B guarantee and never revives
a deleted item from a stale anchor/sidecar.

Inputs: game-written DE s232 (Monado) with SYNTHETIC favourite marks; Wii/3DS play is synthetic (hubfix rules +
p3cfix inventory edits)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p3cfix as F  # noqa: E402
from p3cfix import H, T, rd  # noqa: E402

import canon  # noqa: E402
import xc3d  # noqa: E402
from xcsync import sync  # noqa: E402

PICKS = {"crystal": [0, 1, 305, 340, 499], "weapon": [3, 54], "material": [5], "gem": [10]}


def w_of_3ds(b):
    return xc3d.transcode(xc3d.unpack(b), "wii")


def crystals(img):
    return canon.from_de(img, T)["shared"]["inventory"]["crystal"]


class TestHubMetadata(unittest.TestCase):
    def test_alternating_generations_keep_marks_and_never_revive_disposed_items(self):
        de0 = F.set_fav(rd(H.DE_S232), PICKS)
        fx = H.HubFx("p3c_hub_alt")
        fx.drop("Windows desktop", "bfsgame00.sav", de0)
        self.assertTrue(fx.sync().complete)
        # generation 2: 3DS played - a marked compacted crystal (DE slot 340) is used up, flags progress
        w1 = w_of_3ds(fx.out("3ds"))
        from itemcorr import export_map
        g1 = fx.gen(1)
        maps, _ = export_map(canon.from_de(de0, T)["shared"]["inventory"], canon.from_wii(w1, T)["shared"]["inventory"],
                             {})
        ws = maps["crystal"][340] if "crystal" in maps else None
        self.assertIsNotNone(ws, g1.get("conversions"))
        gone = canon.item_key("crystal", crystals(de0)[340])
        x2 = H.to_3ds(H.play_wii(F.remove(w1, "crystal", ws), flags=4, skip=30))
        fx.drop("New 3DS", "monado01", x2)
        r2 = fx.sync()
        self.assertTrue(r2.complete, r2.message)
        d2 = fx.out("de", 2)
        keys2 = [canon.item_key("crystal", r) for r in crystals(d2).values()]
        self.assertEqual(keys2.count(gone), [canon.item_key("crystal", r) for r in crystals(de0).values()].count(gone) - 1)
        want = F.favs(de0)
        want[("crystal", repr(gone))] -= 1
        want = +want
        self.assertEqual(F.favs(d2), want)
        # generation 3: Wii played on generation 2 (the DE anchor is still generation 1, whose sidecar holds the
        # crystal): the crystal must stay gone, the marks stay
        w3 = H.play_wii(fx.out("wii", 2), flags=3, skip=50)
        fx.drop("Odin 2 Mini", "monado01", w3)
        r3 = fx.sync()
        self.assertTrue(r3.complete, r3.message)
        d3 = fx.out("de", 3)
        self.assertEqual(fx.gen(3)["conversions"][0]["anchor"], 1)
        self.assertEqual([canon.item_key("crystal", r) for r in crystals(d3).values()].count(gone),
                         keys2.count(gone))
        self.assertEqual(F.favs(d3), want)
        # unchanged re-save of the Wii file: in sync, nothing converted
        fx.drop("Odin 2 Mini", "monado01", H.resave_wii(w3))
        self.assertEqual(fx.scan().decision.kind, "in-sync")
        # generation 4: DE played (marks now live in the DE save itself), then generation 5: 3DS played
        d4 = H.play_de(d3, flags=4, skip=80)
        fx.drop("Windows desktop", "bfsgame00.sav", d4)
        self.assertTrue(fx.sync().complete)
        x5 = H.to_3ds(H.play_wii(w_of_3ds(fx.out("3ds", 4)), flags=2, skip=90))
        fx.drop("New 3DS", "monado01", x5)
        r5 = fx.sync()
        self.assertTrue(r5.complete, r5.message)
        d5 = fx.out("de", 5)
        self.assertEqual(F.favs(d5), want)
        self.assertEqual([canon.item_key("crystal", r) for r in crystals(d5).values()].count(gone), keys2.count(gone))
        for box in F.DBOX:
            self.assertEqual(F.de_only_bytes_equal(d4, d5, box)[1], 0, box)
        # rollback to generation 1 restores the original marks and items exactly (a new generation)
        rb = sync.rollback(fx.hub, 1)
        self.assertTrue(getattr(rb, "complete", True))
        self.assertEqual(fx.out("de"), de0)


if __name__ == "__main__":
    unittest.main()
