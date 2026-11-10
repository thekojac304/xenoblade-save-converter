"""Phase 2F regressions for defects found with GAME-GENERATED evidence (Dolphin / Monado runs in phase2f/runs).

  * Fiora's skill object is mirrored in Wii record 8; the Wii game restores record 3 from it on load (run d1_s232:
    DE skill progress of Fiora reverted). Fixed: de_to_wii keeps the copy in step.
  * DE-crafted crystal cylinders (source 0) had no Wii encoding (every late-game DE save was refused).
  * Re-import of a file written by the Wii game itself (run d2_s232) is exact apart from play.
"""
import glob
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2f_util as U  # noqa: E402
import canon  # noqa: E402
import de_to_wii  # noqa: E402
import reimport  # noqa: E402
import sidecar as scmod  # noqa: E402
import wii_save  # noqa: E402

T = None
REALDIR = os.path.join(U.ROOT, "phase2f", "fixtures", "real")
CHAIN = os.path.join(REALDIR, "game_chain_s232")
SPAN = (0x1F4, 0x2A0)


def setUpModule():
    global T
    T = U.tables()


def rec(w, k):
    o = wii_save.CHAR_BASE + wii_save.CHAR_SIZE * k
    return w[o + SPAN[0]:o + SPAN[1]]


class FioraSkillCopy(unittest.TestCase):
    def test_real_saves_hold_the_copy(self):
        for w in (U.wii01(), U.wii03()):
            self.assertEqual(rec(w, 3), rec(w, 8))

    @unittest.skipUnless(os.path.isdir(CHAIN), "game chain fixtures not present")
    def test_game_reverts_record3_from_record8(self):
        """The evidence: the Wii game rewrote record 3 from the stale record 8 copy of the pre-fix export."""
        before = U.rd(os.path.join(CHAIN, "w_export_before_fix"))
        saved = U.rd(os.path.join(CHAIN, "w_saved_by_wii_game_before_fix"))
        self.assertNotEqual(rec(before, 3), rec(before, 8))
        self.assertEqual(rec(saved, 3), rec(before, 8))

    def test_export_keeps_copy_in_step(self):
        """DE progress on Fiora's skills (SYNTHETIC on the game-generated story-20 save, Fiora in the party)."""
        de = bytearray(U.rd(os.path.join(REALDIR, "s020_v10_monado.sav")))
        o = U.DE_CHAR + 0x138 * 2
        learned = list(struct.unpack_from("<5I", de, o + 0x90))
        learned[0] = min(learned[0] + 1, 5)
        struct.pack_into("<5I", de, o + 0x90, *learned)
        struct.pack_into("<I", de, o + 0x7C, 321)
        w, log, dfr = de_to_wii.build(bytes(de), U.wii03(), T, lineage=False)
        self.assertEqual(rec(w, 3), rec(w, 8))
        self.assertTrue(log.get("fiora_skill_copy_synced"))
        self.assertEqual(canon.from_wii(w, T)["shared"]["characters"][3]["skill_learned"], learned)
        for p in sorted(glob.glob(os.path.join(REALDIR, "s*_v10_monado.sav"))):
            w = de_to_wii.build(U.rd(p), U.wii01(), T, lineage=False, overflow="sidecar")[0]
            self.assertEqual(rec(w, 3), rec(w, 8), p)


class CraftedCylinders(unittest.TestCase):
    def test_de_crafted_cylinder_round_trip(self):
        """The real DE-crafted cylinder in s241/s258/s269 (source 0, leftover bytes after the effect list) goes to the
        Wii as a kind-3 cylinder and comes back as the exact original DE record."""
        p = os.path.join(REALDIR, "s241_v10_monado.sav")
        if not os.path.exists(p):
            self.skipTest("fixture missing")
        de = U.rd(p)
        off, size = 0x26D90, 0x2C
        sl = next(i for i in range(500) if de[off + size * i + 0x10] and de[off + size * i + 0x19] and
                  struct.unpack_from("<H", de, off + size * i + 0x14)[0] == 0)
        w, log, dfr = de_to_wii.build(de, U.wii01(), T, lineage=False, overflow="sidecar")
        ws = log["remap"]["crystal"].get(sl, sl)
        c = next(r for r in wii_save.decode_bytes(w)["items"]["crystal"] if r["index"] == ws)["crystal"]
        self.assertEqual((c["kind"], c["source"], c["cylinder"]), ("cylinder", 1, 1))
        sc = scmod.load(scmod.dumps(scmod.make("de_to_wii", de, w, canon.from_de(de, T), canon.from_wii(w, T),
                                               deferred=dfr)))
        m = U.Wii(w)
        m.money(1)
        out, rl = reimport.wii_to_de_reimport(m.done(), sc, T, current_de=de)
        if ws == sl:
            self.assertEqual(out[off + size * sl:off + size * (sl + 1)], de[off + size * sl:off + size * (sl + 1)])


@unittest.skipUnless(os.path.isdir(CHAIN), "game chain fixtures not present")
class GameWrittenWiiFile(unittest.TestCase):
    def test_wii_resave_reimports_exactly_apart_from_play(self):
        exp = U.rd(os.path.join(CHAIN, "w_export_2f"))
        got = U.rd(os.path.join(CHAIN, "w_saved_by_wii_game"))
        sc = scmod.load(U.rd(os.path.join(CHAIN, "de_to_wii.sidecar.json")).decode("utf-8"))
        de = U.rd(os.path.join(REALDIR, "s232_v10_monado.sav"))
        self.assertEqual([d[0] for d in canon.compare(canon.from_wii(exp, T)["shared"], canon.from_wii(got, T)["shared"])],
                         ["/clock/hour", "/clock/minute", "/play_time_s", "/position"])
        out, log = reimport.wii_to_de_reimport(got, sc, T, current_de=de)
        cd, co = canon.from_de(de, T), canon.from_de(out, T)
        self.assertEqual([d[0] for d in canon.compare(cd["shared"], co["shared"]) if not d[0].startswith("/inventory")],
                         ["/clock/hour", "/clock/minute", "/play_time_s", "/position"])
        self.assertEqual(scmod._items(cd["shared"]), scmod._items(co["shared"]))       # 1256 items incl. 46 deferred
        self.assertEqual(cd["de_only"]["characters"], co["de_only"]["characters"])      # Expert Mode data intact
        self.assertEqual(len(log["deferred_restored"]), 46)


if __name__ == "__main__":
    unittest.main()
