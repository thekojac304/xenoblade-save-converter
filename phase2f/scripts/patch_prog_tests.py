"""Corrections of three wrong test assumptions in tests/test_phase2f_progression.py (the converter was right):
  - quest 221/287 are accepted (state 1) with objectives partly done, not completed: assert the exact known values;
  - random skill-tree states only add learned skills (a game never un-learns, and armour permission depends on them);
  - the map test iterates the Wii FLD_maplist resources (minimap.WII_MAPS is keyed by map id, not by area)."""
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests", "test_phase2f_progression.py")
s = open(P, encoding="utf-8").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''        for q in (221, 287):
            r = qc.quests()[q]
            used = [s for s, t, c, n in qc.slots(r) if t and s < 4]
            st = fm.wii_get(w, 0x220 + q)
            self.assertTrue(all(de[qc.DE_QC + 8 * q + s] == 0xFF for s in used) or st in (254, 255), q)''',
    '''        # accepted (state 1) with objectives partly done: Wii [1,1,0] / [0,1,0,0] -> DE 0xFF on exactly those
        self.assertEqual((fm.wii_get(w, 0x220 + 221), fm.wii_get(w, 0x220 + 287)), (1, 1))
        self.assertEqual(list(de[qc.DE_QC + 8 * 221:qc.DE_QC + 8 * 221 + 8]), [255, 255, 0, 0, 0, 0, 0, 0])
        self.assertEqual(list(de[qc.DE_QC + 8 * 287:qc.DE_QC + 8 * 287 + 8]), [0, 255, 0, 0, 0, 0, 0, 0])''')
rep('''                learned = [r.randint(0, 5) for _ in range(5)]''',
    '''                learned = [max(x, r.randint(0, 5)) for x in struct.unpack_from("<5I", b, o + 0x90)]''')
rep('''        import minimap
        maps = sorted(minimap.WII_MAPS)
        self.assertTrue(maps)
        w0 = U.wii01()
        for area in maps:
            word = area | 1 << 16
            b = bytearray(U.de0())
            struct.pack_into("<I", b, 0x149C00, word)
            w = de_to_wii.build(bytes(b), w0, T, lineage=True)[0]
            self.assertEqual(canon.from_wii(w, T)["shared"]["map"], word, area)
            self.assertEqual(w[0xB264:0xB269], ("%02d01f" % area).encode(), area)''',
    '''        maps = sorted(de_to_wii.wii_maps())
        self.assertEqual(len(maps), 28)
        w0 = U.wii01()
        for area, sub in maps:
            word = area | sub << 16
            b = bytearray(U.de0())
            struct.pack_into("<I", b, 0x149C00, word)
            w = de_to_wii.build(bytes(b), w0, T, lineage=True)[0]
            self.assertEqual(canon.from_wii(w, T)["shared"]["map"], word, (area, sub))
            self.assertEqual(w[0xB264:0xB269], ("%02d%02df" % (area, sub)).encode(), (area, sub))
        for area, sub in ((25, 1), (26, 1), (27, 1), (40, 1), (3, 2), (51, 1)):   # DE-only / non-existent maps
            b = bytearray(U.de0())
            struct.pack_into("<I", b, 0x149C00, area | sub << 16)
            with self.assertRaises(de_to_wii.IncompatibleError, msg=(area, sub)):
                de_to_wii.build(bytes(b), w0, T, lineage=True)''')
open(P, "w", encoding="utf-8").write(s)
print("patched")
