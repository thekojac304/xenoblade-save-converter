"""Phase 3C: checks on GAME-WRITTEN story saves (Monado, Dolphin): the Wii game's story event after a DE -> Wii export
matches the DE game's own event; the return to DE reproduces the DE game's state, including the Expert Mode bookkeeping
pair (3C defect E1); Wii-only flags 0x352C-0x36CF are set by normal Wii play (Part D). Fixtures: phase3c/fixtures."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p3cfix as F  # noqa: E402
from p3cfix import H, T, rd  # noqa: E402

import canon  # noqa: E402
import flagmap as fm  # noqa: E402
import xcservice as xs  # noqa: E402

FX = os.path.join(F.P3C, "fixtures")


def fx(n):
    return os.path.join(FX, n)


def changed_flags(a, b):
    return {k for k in set(a["flags"]) | set(b["flags"]) if a["flags"].get(k) != b["flags"].get(k)}


class TestStoryAcrossPlatforms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s154 = canon.from_de(rd(fx("de_s154_monado_autosave.sav")), T)
        cls.de156 = canon.from_de(rd(fx("de_s156_monado_autosave.sav")), T)
        cls.wii156 = canon.from_wii(rd(fx("wii_s156_dolphin_d1_game_save")), T)

    def test_wii_event_changes_the_same_state_as_the_de_event(self):
        self.assertEqual((self.s154["shared"]["story"], self.wii156["shared"]["story"]), (154, 156))
        self.assertEqual(changed_flags(self.s154["shared"], self.wii156["shared"]),
                         changed_flags(self.s154["shared"], self.de156["shared"]))
        self.assertEqual(self.wii156["shared"]["position"], self.de156["shared"]["position"])
        diffs = {d[0].split("/")[1] for d in canon.compare(self.de156["shared"], self.wii156["shared"])}
        # Phase 3E: "stored_gear" too - the 3C export (base = the user's Wii 150) carried no stored equipment (3D D2)
        self.assertLessEqual(diffs, {"achievements", "characters", "clock", "play_time_s", "stored_gear"})

    def test_cold_reload_keeps_state(self):
        a = self.wii156["shared"]
        b = canon.from_wii(rd(fx("wii_s156_dolphin_d2_reload_save")), T)["shared"]
        self.assertEqual({d[0] for d in canon.compare(a, b)}, {"/clock/hour", "/clock/minute", "/play_time_s"})

    def test_return_to_de_reproduces_the_de_games_state_incl_expert_pair(self):
        """E1 (3C): after EXP earned on the Wii at the highest level, the DE-only highest-level EXP must move like the DE
        game moves it (3B kept the pre-export value)."""
        d = F.fresh("story_return")
        r = xs.wii_to_de(xs.WiiToDeRequest(wii=fx("wii_s156_dolphin_d1_game_save"), out=os.path.join(d, "o"),
                                           sidecar=fx("wii_s154_export_3c.de_to_wii.sidecar.json"),
                                           current_de=fx("de_s154_monado_autosave.sav")))
        b = canon.from_de(rd(r.main_output), T)
        self.assertEqual({x[0] for x in canon.compare(self.de156["shared"], b["shared"])},
                         {"/characters/1/palette", "/clock/hour", "/clock/minute", "/play_time_s"})
        self.assertEqual(b["de_only"]["characters"], self.de156["de_only"]["characters"])
        self.assertEqual(b["de_only"]["flags"], self.s154["de_only"]["flags"])

    def test_after_wii_and_back_the_de_story_continues_to_the_same_state(self):
        a = canon.from_de(rd(fx("de_s158_monado_autosave_c1.sav")), T)["shared"]
        b = canon.from_de(rd(fx("de_s158_monado_autosave_c5_after_wii.sav")), T)["shared"]
        self.assertEqual({x[0] for x in canon.compare(a, b)}, {"/clock/hour", "/clock/minute", "/play_time_s"})

    def test_3ds_event_and_return(self):
        """C2: the converted DE 154 save played 154 -> 156 by the 3DS game (Azahar x1): same flags as the DE event;
        back to DE with the conversion record: the DE game's 156 state, materials parked in the record returned."""
        import xc3d
        import xc3dservice as s3
        x = canon.from_wii(xc3d.transcode(xc3d.unpack(rd(fx("x3_s156_azahar_x1_game_save"))), "wii"), T)["shared"]
        self.assertEqual(x["story"], 156)
        self.assertEqual(changed_flags(self.s154["shared"], x), changed_flags(self.s154["shared"], self.de156["shared"]))
        d = F.fresh("story_3ds_return")
        r = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=fx("x3_s156_azahar_x1_game_save"), out=os.path.join(d, "o"),
                                           record=fx("x3_s154_export_3c.de_to_3ds.record.json"),
                                           current=fx("de_s154_monado_autosave.sav")))
        b = canon.from_de(rd(r.main_output), T)
        self.assertEqual({e[0] for e in canon.compare(self.de156["shared"], b["shared"])},
                         {"/characters/1/palette", "/clock/hour", "/clock/minute", "/play_time_s"})
        self.assertEqual(b["de_only"]["characters"], self.de156["de_only"]["characters"])

    def test_wii_only_high_flags_are_set_by_normal_wii_play(self):
        """Part D: the user's unconverted save, skip-travelled in Dolphin, gets 0x36C5/0x36C7 from the game itself."""
        before, after = rd(H.W150), rd(fx("wii_s150_dolphin_dD_travel_unconverted"))
        self.assertEqual([g for g in range(0x352C, 0x36D0) if fm.wii_get(before, g)], [])
        self.assertEqual([g for g in range(0x352C, 0x36D0) if fm.wii_get(after, g)], [0x36C5, 0x36C7])
        self.assertEqual(fm.WII_RANGE[1][1] - 1, 0x36CF)
        self.assertEqual(fm.DE_RANGE[1][1] - fm.DE_RANGE[1][0] - (fm.WII_RANGE[1][1] - fm.WII_RANGE[1][0]), 80)


if __name__ == "__main__":
    unittest.main()
