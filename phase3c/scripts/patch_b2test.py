p = r"C:\Dev\XC_Wii_to_DE_Research\phase3b\tests\test_synchub.py"
s = open(p, encoding="utf-8").read()
old = s[s.index("    def test_b2_unplayed_return_is_never_converted(self):"):s.index("    def test_items_exp_quests_follow_the_source(self):")]
new = '''    def test_b2_unplayed_return_is_never_converted(self):
        """B2: the 3A/3B engine refused an UNPLAYED DE -> 3DS -> DE return when overflow items were set aside (slot
        renumbering in its read-back). The hub classifies such a save as in sync and never converts it.
        Phase 3C fixed the engine (read-back through the export's compaction map): the manual return now gives the
        DE save back byte for byte; the hub decision is unchanged."""
        fx = HubFx("b2_hub")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        fx.sync()
        fx.drop("New 3DS", "monado01", rd(os.path.join(fx.ready("New 3DS"), "monado01")))
        fx.drop("Odin 2 Mini", "monado01", resave_wii(fx.out("wii")))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync")
        d = H.fresh("b2_engine")
        r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "a"),
                                           template=H.X3_USER, overflow="sidecar"))
        r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=r1.main_output, out=os.path.join(d, "b"),
                                           record=r1.sidecar_path, current=H.DE_S232))
        self.assertEqual(rd(r2.main_output), rd(H.DE_S232))

'''
s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("patched")
