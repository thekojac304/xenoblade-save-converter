"""Phase 3E: the Phase 3D tests that pinned the D2 refusal now pin the 3E behaviour - stored equipment is translated
(269/276/283 convert, round trips exact), only Fiora's later form being away (288) is still refused; the 3D-era Wii
saves of the split (exported before D2, no stored gear) import faithfully. Every other assertion is kept."""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def sub(rel, pairs):
    p = os.path.join(ROOT, rel)
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if b in s:
            continue
        assert a in s, (rel, a[:80])
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


T3D = os.path.join("phase3d", "tests")
sub(os.path.join(T3D, "test_phase3d_characters.py"), [
    ('CONVERTIBLE = (291,)          # 269-288: members away with stored gear (D2) -> refused\n'
     'DEPARTED = {269: "Reyn, Dunban, Sharla, Riki, Melia", 276: "Reyn, Dunban, Sharla, Riki, Melia",\n'
     '            283: "Dunban, Riki, Melia", 288: "Shulk, Reyn, Sharla"}\n',
     'CONVERTIBLE = (276, 283, 291)   # Phase 3E: stored equipment translated (3D: only 291); 288 (Fiora away) refused\n'
     'TRANSLATED = (269, 276, 283)\n'),
    ('''    def test_d2_members_away_with_stored_gear_are_refused(self):
        """D2: while members are away in a story event (public saves 269-288) the games keep their gear in a table the
        converter does not translate; DE -> Wii and DE -> 3DS are refused with the names, nothing written."""
        for s, names in DEPARTED.items():
            with self.subTest(story=s):
                d = fresh(f"d2_{s}")
                with self.assertRaises(xs.REFUSALS) as cm:
                    to_wii(de(s), d)
                self.assertIn(names + " left the party", str(cm.exception))
                self.assertFalse(os.path.exists(os.path.join(d, "w")))
                with self.assertRaises(xs.REFUSALS) as cm:
                    s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=de(s), out=os.path.join(d, "x"),
                                                  template=H.X3_USER, overflow="sidecar"))
                self.assertIn(names + " left the party", str(cm.exception))
''', '''    def test_d2_members_away_with_stored_gear(self):
        """D2 (3D: refused). Phase 3E: the stored equipment is translated - DE -> Wii and DE -> 3DS carry it exactly
        (269/276/283); Fiora's later form away (288) is still refused with her name, nothing written."""
        for s in TRANSLATED:
            with self.subTest(story=s):
                d = fresh(f"d2_{s}")
                w = to_wii(de(s), d)
                self.assertEqual(canon.jsonable(shared(w.main_output)["stored_gear"]),
                                 canon.jsonable(shared(de(s))["stored_gear"]))
        d = fresh("d2_288")
        with self.assertRaises(xs.REFUSALS) as cm:
            to_wii(de(288), d)
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "w")))
        with self.assertRaises(xs.REFUSALS) as cm:
            s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=de(288), out=os.path.join(d, "x"),
                                          template=H.X3_USER, overflow="sidecar"))
        self.assertIn("Fiora is away from the party", str(cm.exception))
'''),
])
sub(os.path.join(T3D, "test_phase3d_gamewritten.py"), [(
    '''    def test_first_time_import_during_the_split_is_refused(self):
        """D2: the Wii save of the split (no sidecar, a DE template from another point) would give the members the
        template's stored gear at their return: refused."""
        for s in (276, 283, 288):
            with self.subTest(story=s):
                d = C.fresh(f"gw_first_{s}")
                with self.assertRaises(xs.REFUSALS) as cm:
                    xs.wii_to_de(xs.WiiToDeRequest(wii=fx(f"wii_s{s}_dolphin_wd_game_save"), out=os.path.join(d, "o"),
                                                   template=C.H.DE_TPL))
                self.assertIn("left the party", str(cm.exception))
                self.assertFalse(os.path.exists(os.path.join(d, "o")))
''', '''    def test_first_time_import_of_the_split_is_faithful(self):
        """D2 (3D: refused). Phase 3E: these Wii files were exported before D2 and hold no stored gear for the members
        who are away (references cleared) - imported first-time, the DE gets exactly that: empty entries, nothing
        from the template's table."""
        import stored_gear as sg
        for s in (276, 283, 288):
            with self.subTest(story=s):
                d = C.fresh(f"gw_first_{s}")
                r = xs.wii_to_de(xs.WiiToDeRequest(wii=fx(f"wii_s{s}_dolphin_wd_game_save"), out=os.path.join(d, "o"),
                                                   template=C.H.DE_TPL))
                st = canon.from_de(rd(r.main_output), T)["shared"]["stored_gear"]
                self.assertTrue(st and all(not any(v["slots"].values()) for v in st.values()), st)
                self.assertEqual(st, canon.from_wii(rd(fx(f"wii_s{s}_dolphin_wd_game_save")), T)["shared"]["stored_gear"])
''')])
sub(os.path.join(T3D, "test_phase3d_synchub.py"), [
    ('self.assertIn("Shulk, Reyn, Sharla left the party", str(cm.exception))',
     'self.assertIn("Fiora is away from the party", str(cm.exception))   # 3E: only Fiora\'s stored gear is refused'),
])
print("ok")
