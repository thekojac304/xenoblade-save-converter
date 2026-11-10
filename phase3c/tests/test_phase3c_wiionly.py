"""Phase 3C: Wii-only per-item bytes on DE -> Wii returns (equipment header low bits; crystal byte +0x16) follow the
physical item, identified by its DE acquisition serial; and the unplayed DE -> 3DS -> DE return (3B finding B2).
Inputs: the user's game-written Wii save (story 150) and the DE template; DE-side mutations are synthetic edits."""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p3cfix as F  # noqa: E402
from p3cfix import H, T, rd  # noqa: E402

import canon  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402

BASELINE = os.path.join(F.P3C, "scripts", "baseline3b.py")


class TestWiiOnlyBytes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = F.fresh("wiionly")
        r = xs.wii_to_de(xs.WiiToDeRequest(wii=H.W150, out=os.path.join(cls.d, "w2d"), template=H.DE_TPL))
        cls.de = rd(r.main_output)
        cls.sc = r.sidecar_path
        w = rd(H.W150)
        cls.slots = [sl for sl in sorted(F.wii_items(w, "weapon")) if F.wii_low5(w, "weapon", sl)]

    def back(self, de, name):
        p = F.put_de(self.d, name, de)
        r = xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=os.path.join(self.d, name + "_out"), sidecar=self.sc,
                                                   current_wii=H.W150))
        return rd(r.main_output), p

    def test_same_item_keeps_wii_only_bits(self):
        w, _ = self.back(H.play_de(self.de, flags=3), "played")
        for sl in self.slots:
            self.assertEqual(F.wii_low5(w, "weapon", sl), F.wii_low5(rd(H.W150), "weapon", sl))

    def test_identical_replacement_gets_fresh_record(self):
        s = self.slots[0]
        de = F.de_rebuy(H.play_de(self.de, flags=3), "weapon", s)
        w, p = self.back(de, "rebuy")
        self.assertEqual(F.wii_low5(w, "weapon", s), 0)
        for sl in self.slots[1:]:
            self.assertEqual(F.wii_low5(w, "weapon", sl), F.wii_low5(rd(H.W150), "weapon", sl))
        r = subprocess.run([sys.executable, BASELINE, "de_to_wii", p, "-", self.sc, H.W150,
                            os.path.join(self.d, "rebuy_b3")], capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        old = rd(json.loads(r.stdout.strip().splitlines()[-1])["main_output"])
        self.assertEqual(F.wii_low5(old, "weapon", s), F.wii_low5(rd(H.W150), "weapon", s))   # 3B: stale bits
        self.assertEqual(canon.from_wii(old, T)["shared"], canon.from_wii(w, T)["shared"])      # same game state


class TestUnplayedReturns(unittest.TestCase):
    def test_de_3ds_de_unplayed_with_compaction_is_byte_identical(self):
        """3B finding B2 (refused by the slot-by-slot read-back in 3A/3B): DE s232 -> 3DS -> unchanged -> DE."""
        d = F.fresh("b2_3ds")
        r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "a"),
                                           template=H.X3_USER, overflow="sidecar"))
        r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=r1.main_output, out=os.path.join(d, "b"),
                                           record=r1.sidecar_path, current=H.DE_S232))
        self.assertEqual(rd(r2.main_output), rd(H.DE_S232))
        r = subprocess.run([sys.executable, BASELINE, "convert3", json.dumps(dict(
            direction="3ds_to_de", source=r1.main_output, out=os.path.join(d, "b3"), record=r1.sidecar_path,
            current=H.DE_S232))], capture_output=True, text=True, timeout=600)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("read-back", r.stderr)


if __name__ == "__main__":
    unittest.main()
