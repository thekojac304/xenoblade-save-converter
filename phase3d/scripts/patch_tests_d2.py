"""Phase 3D: adapt the four 2E/2F tests that export game-written DE saves from a story split (D2) - those saves are
now refused with the names of the members who are away; every assertion on the other saves is kept, and the C1
checks on absent members move to the story-20 save (members not joined yet, not affected by D2)."""
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


sub(os.path.join("tests", "test_phase2e.py"), [(
    '''            de = rd(p)
            out, log, deferred = de_to_wii.build(de, base, T, lineage=True)
            self.assertTrue(all(wii_save.check_crcs(out).values()))
            self.assertEqual(de_to_wii.verify(out, de, T, deferred, log["remap"]), [], rel)''',
    '''            de = rd(p)
            if "s1_story" in rel:   # Phase 3D D2: story 154, Melia alone - the others' gear is stored -> refused
                with self.assertRaises(de_to_wii.IncompatibleError) as cm:
                    de_to_wii.build(de, base, T, lineage=True)
                self.assertIn("Shulk, Reyn, Dunban, Riki left the party", str(cm.exception))   # Sharla: the base stores the same gear
                continue
            out, log, deferred = de_to_wii.build(de, base, T, lineage=True)
            self.assertTrue(all(wii_save.check_crcs(out).values()))
            self.assertEqual(de_to_wii.verify(out, de, T, deferred, log["remap"]), [], rel)''')])

sub(os.path.join("tests", "test_phase2f_progression.py"), [
    ('''    @unittest.skipUnless(REAL, "game-generated v10 fixtures not present")
    def test_temporarily_unavailable_and_rejoin(self):
        """C1 on real data: s269 (game-generated) has Shulk alone in the party. Absent members keep their progression
        both ways; their DE equipment stays empty; on the Wii, references into the regular inventory are cleared."""
        de = U.rd(next(p for p in REAL if "s269" in p))
        cd = canon.from_de(de, T)["shared"]
        self.assertEqual(cd["party"], [1])
        w, sc, dfr, log = export(de)
        cw = canon.from_wii(w, T)["shared"]
        for k in range(2, 8):''',
     '''    @unittest.skipUnless(REAL, "game-generated v10 fixtures not present")
    def test_temporarily_unavailable_and_rejoin(self):
        """C1 on real data. Phase 3D (D2): s269 (Shulk alone; the others' gear is kept in the stored-equipment table,
        which is not translated) is refused with their names. The absent-member checks run on the game-generated
        story-20 save instead (Dunban, Sharla, Riki, Melia not joined yet): absent members keep their progression
        both ways; their DE equipment stays empty; on the Wii, references into the regular inventory are cleared."""
        de269 = U.rd(next(p for p in REAL if "s269" in p))
        self.assertEqual(canon.from_de(de269, T)["shared"]["party"], [1])
        with self.assertRaises(de_to_wii.IncompatibleError) as cm:
            export(de269)
        self.assertIn("Reyn, Dunban, Sharla, Riki, Melia left the party", str(cm.exception))
        de = U.rd(next(p for p in REAL if "s020" in p))
        cd = canon.from_de(de, T)["shared"]
        self.assertEqual(cd["party"], [3, 1, 2])
        w, sc, dfr, log = export(de)
        cw = canon.from_wii(w, T)["shared"]
        for k in (4, 5, 6, 7):'''),
    ('''        m = U.Wii(w)                                      # SYNTHETIC rejoin on the Wii: Reyn back in the party
        m.img.put(wii_save.PARTY + 4, "H", 2)
        out, rl = reimport.wii_to_de_reimport(m.done(), sc, T, current_de=de)
        co = canon.from_de(out, T)["shared"]
        self.assertEqual(co["party"], [1, 2])
        self.assertEqual(co["characters"][2]["level"], cd["characters"][2]["level"])''',
     '''        m = U.Wii(w)                                      # SYNTHETIC party change on the Wii: Fiora (3) leaves
        m.img.put(wii_save.PARTY + 0, "H", 1)
        m.img.put(wii_save.PARTY + 4, "H", 2)
        m.img.put(wii_save.PARTY + 8, "H", 0)
        out, rl = reimport.wii_to_de_reimport(m.done(), sc, T, current_de=de)
        co = canon.from_de(out, T)["shared"]
        self.assertEqual(co["party"], [1, 2])
        self.assertEqual(co["characters"][3]["level"], cd["characters"][3]["level"])'''),
    ('''            name = os.path.basename(p)[:4]
            de = U.rd(p)
            cd = canon.from_de(de, T)
            problems, _ = de_to_wii.compatibility(cd, de, T)
            self.assertEqual(problems, [], name)
            w, sc, dfr, log = export(de)''',
     '''            name = os.path.basename(p)[:4]
            de = U.rd(p)
            cd = canon.from_de(de, T)
            problems, _ = de_to_wii.compatibility(cd, de, T)
            self.assertEqual(problems, [], name)
            if name == "s269":   # Phase 3D D2: members away with stored gear -> refused, nothing to round-trip
                with self.assertRaises(de_to_wii.IncompatibleError, msg=name):
                    export(de)
                rows.append({"fixture": name, "story": cd["shared"]["story"], "party": cd["shared"]["party"],
                             "refused": "D2 stored equipment of members who are away"})
                continue
            w, sc, dfr, log = export(de)'''),
])

sub(os.path.join("tests", "test_phase2f_regressions.py"), [(
    '''        for p in sorted(glob.glob(os.path.join(REALDIR, "s*_v10_monado.sav"))):
            w = de_to_wii.build(U.rd(p), U.wii01(), T, lineage=False, overflow="sidecar")[0]
            self.assertEqual(rec(w, 3), rec(w, 8), p)''',
    '''        for p in sorted(glob.glob(os.path.join(REALDIR, "s*_v10_monado.sav"))):
            if "s269" in p:   # Phase 3D D2: refused (members away with stored gear)
                with self.assertRaises(de_to_wii.IncompatibleError):
                    de_to_wii.build(U.rd(p), U.wii01(), T, lineage=False, overflow="sidecar")
                continue
            w = de_to_wii.build(U.rd(p), U.wii01(), T, lineage=False, overflow="sidecar")[0]
            self.assertEqual(rec(w, 3), rec(w, 8), p)''')])
print("ok")
