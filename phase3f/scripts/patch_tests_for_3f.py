"""Phase 3F: the 3D/3E tests that pinned the Fiora-8 (story 288) refusal now pin the 3F behaviour - her stored gear is
translated exactly (DE -> Wii, DE -> 3DS, back), the Sync Hub accepts the 288 split and the 291 reunion as one
playthrough. Every other assertion is kept. Idempotent.   python patch_tests_for_3f.py"""
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


# ---- 3D characters: D2 test
sub(os.path.join("phase3d", "tests", "test_phase3d_characters.py"), [
    ('''        (269/276/283); Fiora's later form away (288) is still refused with her name, nothing written."""
        for s in TRANSLATED:''',
     '''        (269/276/283); Phase 3F: Fiora's later form away (288) is translated too (reunion played, 3F)."""
        for s in TRANSLATED + (288,):'''),
    ('''        d = fresh("d2_288")
        with self.assertRaises(xs.REFUSALS) as cm:
            to_wii(de(288), d)
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "w")))
        with self.assertRaises(xs.REFUSALS) as cm:
            s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=de(288), out=os.path.join(d, "x"),
                                          template=H.X3_USER, overflow="sidecar"))
        self.assertIn("Fiora is away from the party", str(cm.exception))
''',
     '''        d = fresh("d2_288")
        x = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=de(288), out=os.path.join(d, "x"),
                                          template=H.X3_USER, overflow="sidecar"))
        self.assertEqual(canon.jsonable(shared(x.main_output)["stored_gear"]),
                         canon.jsonable(shared(de(288))["stored_gear"]))
'''),
])

# ---- 3D Sync Hub: the 288 split now syncs; 291 (reunion, same playthrough) follows as a descendant
sub(os.path.join("phase3d", "tests", "test_phase3d_synchub.py"), [
    ('''        with self.assertRaises(sync.Blocked) as cm:
            fx.sync()
        self.assertIn("Fiora is away from the party", str(cm.exception))   # 3E: only Fiora's stored gear is refused
        self.assertIsNone(fx.hub.current_generation()[1])          # nothing committed
''',
     '''        r0 = fx.sync()                                              # 3F: Fiora's stored gear is translated
        self.assertTrue(r0.complete, r0.message)
'''),
    ('''        sync.rollback(fx.hub, 1)
        self.assertEqual(fx.out("de"), rd(C.de(291)))''',
     '''        sync.rollback(fx.hub, 2)                                    # 3F: generation 1 = the 288 split
        self.assertEqual(fx.out("de"), rd(C.de(291)))'''),
])

# ---- 3E stored gear: the Fiora refusal test becomes the Fiora translation test
sub(os.path.join("phase3e", "tests", "test_phase3e_stored_gear.py"), [
    ('''        for p in SPLIT[:-1]:            # 288 (Fiora away): refused, see test_fiora_away_is_refused''',
     '''        for p in SPLIT:                 # Phase 3F: 288 (Fiora away) included'''),
    ('''    def test_fiora_away_is_refused(self):
        d = fresh("fiora288")
        with self.assertRaises(xs.REFUSALS) as cm:
            xs.de_to_wii_convert(xs.DeToWiiRequest(de=SPLIT[-1], out=os.path.join(d, "w"), base=H.W150,
                                                   overflow="sidecar"))
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "w")))''',
     '''    def test_fiora_away_is_translated(self):
        """Phase 3F: Fiora's later form away (288) - her stored gear goes to the Wii staging slot 158 exactly."""
        d = fresh("fiora288")
        w = xs.de_to_wii_convert(xs.DeToWiiRequest(de=SPLIT[-1], out=os.path.join(d, "w"), base=H.W150,
                                                   overflow="sidecar"))
        self.assertEqual(stored(w.main_output)["8"], stored(SPLIT[-1])["8"])'''),
])

# ---- 3E Sync Hub: the 288 split syncs
sub(os.path.join("phase3e", "tests", "test_phase3e_synchub.py"), [
    ('''    def test_fiora_away_blocks_with_her_name(self):
        fx = H.HubFx("p3e_hub_288")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(os.path.join(S.F3D, "de_s288_v10_monado.sav")))
        with self.assertRaises(sync.Blocked) as cm:
            fx.sync()
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertIsNone(fx.hub.current_generation()[1])''',
     '''    def test_fiora_away_syncs(self):
        """Phase 3F (was: blocks with her name): the 288 split syncs; Fiora's stored gear reaches the Wii and 3DS."""
        fx = H.HubFx("p3e_hub_288")
        src = os.path.join(S.F3D, "de_s288_v10_monado.sav")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(src))
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        want = canon.jsonable(sh(rd(src))["stored_gear"])
        self.assertEqual(canon.jsonable(sh(fx.out("wii"))["stored_gear"]), want)'''),
])
print("patched")
