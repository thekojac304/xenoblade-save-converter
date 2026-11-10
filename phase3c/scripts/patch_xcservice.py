p = r"C:\Dev\XC_Wii_to_DE_Research\tools\xcservice.py"
s = open(p, encoding="utf-8").read()
old = '''    cw = canon.from_wii(wii, T)
    hard = readback_diffs(cw["shared"], canon.from_de(out, T)["shared"], drop)   # deferred DE-only items excluded
'''
new = '''    cw = canon.from_wii(wii, T)
    if r.sidecar and log.get("result", "").startswith("Wii unchanged"):
        # Phase 3C (3B finding B2): the DE save comes back unchanged, at its own slots; compare it with the Wii state
        # through the export's compaction map (items the export moved to other Wii slots), not slot by slot
        hard = unchanged_return_diffs(wii, out, sc, T)
    else:
        hard = readback_diffs(cw["shared"], canon.from_de(out, T)["shared"], drop)   # deferred DE-only items excluded
'''
assert old in s
s = s.replace(old, new)
s = s.replace('''def manifest(inputs, outputs, extra):''', '''def unchanged_return_diffs(wii, de_out, sc, T):
    """Read-back of an unchanged return trip: the returned DE save, projected through the export (deferred items
    removed, compaction map applied, references followed), must equal the Wii save's state."""
    import itemcorr
    maps, bad = itemcorr.export_map(canon.from_de(de_out, T)["shared"]["inventory"],
                                    canon.from_wii(wii, T)["shared"]["inventory"], sc.get("deferred", {}))
    if bad:
        return [("/inventory (export map)", bad, None)]
    return [d for d in de_to_wii.verify(wii, de_out, T, sc.get("deferred", {}), maps) if not d[0].startswith(TOLERATED)]


def manifest(inputs, outputs, extra):''')
open(p, "w", encoding="utf-8").write(s)

p = r"C:\Dev\XC_Wii_to_DE_Research\phase3c\tests\test_phase3c_metadata.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''        w = F.add_copy(w, "weapon", 0, F.free_slot(w, "weapon", 140))   # and one more pickup afterwards
''', "")
s = s.replace('''        back, _ = self.back(self.w, "unchanged")
        self.assertEqual(back, self.de)''', '''        """Also 3B finding B2: an unplayed return with compacted/overflow items was refused by the slot-by-slot
        read-back; 3C compares through the export map."""
        back, _ = self.back(self.w, "unchanged")
        self.assertEqual(back, self.de)
        p = H.put(os.path.join(self.d, "unchanged_b3", "monado01"), self.w)
        with self.assertRaises(AssertionError) as cm:
            baseline_wii_to_de(p, self.sc, self.de_p, os.path.join(self.d, "unchanged_b3_out"))
        self.assertIn("read-back differs", str(cm.exception))''')
s = s.replace("scmod.load(open(self.sc).read())", "scmod.load(rd(self.sc).decode())")
open(p, "w", encoding="utf-8").write(s)
