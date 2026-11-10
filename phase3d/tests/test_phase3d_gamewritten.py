"""Phase 3D: GAME-WRITTEN post-rejoin saves (character 8 in the party). The Wii game (Dolphin wd_s276..291_save) and
the 3DS game (Azahar x5_s291_save: party, equipment and skill screens viewed, in-game save) loaded the converted saves
and saved them; the returns to DE must reproduce the DE save apart from what the session itself changed and the
documented limitations (6: compacted items keep their Wii slot; 5: games raise link unlocks)."""
import collections
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_phase3d_characters as C  # noqa: E402
from test_phase3d_characters import T, canon, fx, rd, shared, s3, xs  # noqa: E402

SESSION = {"/clock/hour", "/clock/minute", "/play_time_s", "/position"}


def item_multisets(c):
    return {box: collections.Counter(json.dumps(canon.strip_order(r), sort_keys=True) for r in recs.values())
            for box, recs in c["inventory"].items()}


class TestWiiGameSessions(unittest.TestCase):
    def test_wii_game_keeps_the_converted_state(self):
        for s in C.POST:
            with self.subTest(story=s):
                a, b = shared(fx(f"wii_s{s}_export_3d")), shared(fx(f"wii_s{s}_dolphin_wd_game_save"))
                self.assertLessEqual(C.diff_keys(a, b), SESSION)
                self.assertEqual(b["party"], shared(C.de(s))["party"])

    def test_wii_game_keeps_record_8_skill_ids_and_the_mirror(self):
        from de_to_wii import CHAR_BASE, CHAR_SIZE
        for s in C.POST:
            w = rd(fx(f"wii_s{s}_dolphin_wd_game_save"))
            o3, o8 = CHAR_BASE + CHAR_SIZE * 3 + 0x1F4, CHAR_BASE + CHAR_SIZE * 8 + 0x1F4
            ids = [w[o8 + 13 * t + 2 + 2 * e] for t in range(5) for e in range(5)]
            self.assertTrue(any(ids) and all(v == 0 or 175 < v <= 200 for v in ids), (s, ids))
            self.assertEqual(w[o3:o3 + 0xAC], w[o8:o8 + 0xAC])

    def test_return_to_de(self):
        for s in C.POST:
            with self.subTest(story=s):
                d = C.fresh(f"gw_ret_{s}")
                r = xs.wii_to_de(xs.WiiToDeRequest(wii=fx(f"wii_s{s}_dolphin_wd_game_save"), out=os.path.join(d, "o"),
                                                   sidecar=fx(f"wii_s{s}_export_3d.de_to_wii.sidecar.json"),
                                                   current_de=C.de(s)))
                a, b = shared(C.de(s)), shared(r.main_output)
                self.assertEqual(C.core_diffs(a, b) - SESSION, set())
                self.assertTrue(C.equipment_same(a, b))
                self.assertEqual(item_multisets(a), item_multisets(b))
                self.assertEqual(canon.from_de(rd(r.main_output), T)["de_only"]["characters"],
                                 canon.from_de(rd(C.de(s)), T)["de_only"]["characters"])
                # D2: the DE's own stored gear of members who are away comes back unchanged
                import stored_gear as sg
                self.assertEqual(rd(r.main_output)[sg.STASH:sg.STASH_END], rd(C.de(s))[sg.STASH:sg.STASH_END])

    def test_first_time_import_of_the_split_is_faithful(self):
        """D2 (3D: refused). Phase 3E: these Wii files were exported before D2 and hold no stored gear for the members
        who are away (references cleared) - imported first-time, the DE gets exactly that: empty entries, nothing
        from the template's table."""
        import stored_gear as sg
        d = C.fresh("gw_first_288")
        with self.assertRaises(xs.REFUSALS):     # 288: Fiora's references name base gear no staging record holds
            xs.wii_to_de(xs.WiiToDeRequest(wii=fx("wii_s288_dolphin_wd_game_save"), out=os.path.join(d, "o"),
                                           template=C.H.DE_TPL))
        for s in (276, 283):
            with self.subTest(story=s):
                d = C.fresh(f"gw_first_{s}")
                r = xs.wii_to_de(xs.WiiToDeRequest(wii=fx(f"wii_s{s}_dolphin_wd_game_save"), out=os.path.join(d, "o"),
                                                   template=C.H.DE_TPL))
                st = canon.from_de(rd(r.main_output), T)["shared"]["stored_gear"]
                self.assertTrue(st and all(not any(v["slots"].values()) for v in st.values()), st)
                self.assertEqual(st, canon.from_wii(rd(fx(f"wii_s{s}_dolphin_wd_game_save")), T)["shared"]["stored_gear"])


class Test3dsGameSession(unittest.TestCase):
    def test_3ds_game_keeps_the_converted_state_except_derived_link_unlocks(self):
        a, b = shared(fx("x3_s291_export_3d")), shared(fx("x3_s291_azahar_x5_game_save"))
        diffs = C.diff_keys(a, b)
        unl = {k for k in diffs if "/link_unlock/" in k}
        self.assertEqual(diffs - unl, SESSION)
        for k in unl:          # limitation 5: the game only ever raises unlocks
            _, _, ch, _, src = k.split("/")
            self.assertGreater(b["characters"][int(ch)]["link_unlock"][int(src)],
                               a["characters"][int(ch)]["link_unlock"][int(src)])

    def test_return_to_de(self):
        d = C.fresh("gw_ret3")
        r = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=fx("x3_s291_azahar_x5_game_save"), out=os.path.join(d, "o"),
                                          record=fx("x3_s291_export_3d.de_to_3ds.record.json"), current=C.de(291)))
        a, b = shared(C.de(291)), shared(r.main_output)
        rest = {k for k in C.core_diffs(a, b) if "/link_unlock/" not in k}
        self.assertEqual(rest - SESSION, set())
        self.assertTrue(C.equipment_same(a, b))
        self.assertEqual(item_multisets(a), item_multisets(b))
        x = shared(fx("x3_s291_azahar_x5_game_save"))
        for k, c in b["characters"].items():          # the DE receives exactly the unlocks the 3DS game derived
            self.assertEqual(c["link_unlock"], x["characters"][k]["link_unlock"], k)


if __name__ == "__main__":
    unittest.main()
