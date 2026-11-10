"""Phase 2F API updates to tests/test_phase2e.py (each anchor asserted once). No assertion is removed:
  - re-import calls state explicitly that no newer DE save exists (no_newer_de=True), the 2F API requirement;
  - the CLI round trip passes --no-current-wii for the same reason;
  - the 2E-made W1 is now compared twice: the 2F export of DE1 must be canonically equal to DE1, and the 2E artifact
    may differ from DE1 only in item acquisition order (the 2E serial-direction defect found in Phase 2F)."""
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests", "test_phase2e.py")
s = open(P, encoding="utf-8").read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (a[:70], s.count(a))
    s = s.replace(a, b)


rep("        back, log = reimport.wii_to_de_reimport(w, sc, T)\n",
    "        back, log = reimport.wii_to_de_reimport(w, sc, T, no_newer_de=True)\n")
rep("        back, log = reimport.wii_to_de_reimport(w2, sc, T)\n",
    "        back, log = reimport.wii_to_de_reimport(w2, sc, T, no_newer_de=True)\n")
rep("            reimport.wii_to_de_reimport(rd(os.path.join(O, \"monado01\")), sc, T)\n",
    "            reimport.wii_to_de_reimport(rd(os.path.join(O, \"monado01\")), sc, T, no_newer_de=True)\n")
rep('''        de1 = rd(os.path.join(self.C, "b_de1/bfsgame00.sav"))
        self.assertEqual([d for d in canon.compare(canon.from_wii(w1, T)["shared"], canon.from_de(de1, T)["shared"])
                          if not d[0].startswith("/achievements")], [])
''', '''        de1 = rd(os.path.join(self.C, "b_de1/bfsgame00.sav"))
        # Phase 2F: the 2E converter copied serials although the games number acquisition order in opposite
        # directions; its W1 differs from DE1 in item order only. The 2F export of DE1 is exactly equal.
        diffs = [d for d in canon.compare(canon.from_wii(w1, T)["shared"], canon.from_de(de1, T)["shared"])
                 if not d[0].startswith("/achievements")]
        self.assertTrue(diffs)
        self.assertEqual([d for d in diffs if not (d[0].startswith("/inventory/") and d[0].endswith("/order"))], [])
        w1f, log, deferred = de_to_wii.build(de1, rd(os.path.join(O, "monado01")), T, lineage=True)
        self.assertEqual([d for d in canon.compare(canon.from_wii(w1f, T)["shared"], canon.from_de(de1, T)["shared"])
                          if not d[0].startswith("/achievements")], [])
''')
rep('''        rc = xcconv.main(["de-to-wii", "--de", de, "--sidecar", os.path.join(d1, "wii_to_de.sidecar.json"), "--out", d2])
''', '''        rc = xcconv.main(["de-to-wii", "--de", de, "--sidecar", os.path.join(d1, "wii_to_de.sidecar.json"), "--out", d2,
                          "--no-current-wii"])
''', 2)
open(P, "w", encoding="utf-8").write(s)
print("patched", P)
