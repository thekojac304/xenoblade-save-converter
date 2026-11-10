"""Phase 3E Sync Hub regression with stored equipment (hub = unchanged 3B code; engine 3E): the genuine Alcamoth
sequence 154 (Melia alone) -> 156 -> 158 (Shulk alone; Melia away) -> 160 (five back) synced as DE generations -
departures and reunions are ordinary progress, never a conflict; every Wii/3DS output carries the DE's stored gear;
a Wii session on the split generation comes back with it; Fiora's later form away (288) blocks with her name;
rollback restores a split generation exactly."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_phase3e_stored_gear as S  # noqa: E402
from test_phase3e_stored_gear import H, T, canon, rd  # noqa: E402

import xc3d  # noqa: E402
from xcsync import sync  # noqa: E402

SEQ = [os.path.join(S.F3C, f) for f in ("de_s154_monado_autosave.sav", "de_s156_monado_autosave.sav",
                                         "de_s158_monado_autosave_c1.sav", "de_s160_monado_autosave_c9.sav")]


def sh(img):
    if img[:4] == b"!qzb":
        img = xc3d.transcode(xc3d.unpack(img), "wii")
    return (canon.from_wii(img, T) if img[:4] == b"USRD" else canon.from_de(img, T))["shared"]


class TestHubStoredGear(unittest.TestCase):
    def test_alcamoth_sequence(self):
        fx = H.HubFx("p3e_hub_sg")
        for n, p in enumerate(SEQ, 1):
            fx.drop("Windows desktop", "bfsgame00.sav", rd(p), age=900 - 100 * n)
            res = fx.scan()
            self.assertIn(res.decision.kind, ("start", "new-progress"), (os.path.basename(p), res.decision.message))
            r = fx.sync(res)
            self.assertTrue(r.complete, r.message)
            want = canon.jsonable(sh(rd(p)).get("stored_gear"))
            self.assertEqual(canon.jsonable(sh(fx.out("wii")).get("stored_gear")), want, p)
            self.assertEqual(canon.jsonable(sh(fx.out("3ds")).get("stored_gear")), want, p)
            if n == 3:
                split_gen = fx.hub.current_generation()[0]
        # Wii session on generation 4 (160, Melia still away): synthetic play, back to DE with her stored gear
        w = H.play_wii(fx.out("wii"), flags=3, skip=30)
        fx.drop("Odin 2 Mini", "monado01", w)
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        self.assertEqual(canon.jsonable(sh(fx.out("de")).get("stored_gear")),
                         canon.jsonable(sh(rd(SEQ[3])).get("stored_gear")))
        # rollback to the split generation (158): DE file restored exactly
        sync.rollback(fx.hub, split_gen)
        self.assertEqual(fx.out("de"), rd(SEQ[2]))

    def test_fiora_away_blocks_with_her_name(self):
        fx = H.HubFx("p3e_hub_288")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(os.path.join(S.F3D, "de_s288_v10_monado.sav")))
        with self.assertRaises(sync.Blocked) as cm:
            fx.sync()
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertIsNone(fx.hub.current_generation()[1])


if __name__ == "__main__":
    unittest.main()
