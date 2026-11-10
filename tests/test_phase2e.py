"""Phase 2E tests: exact Wii->DE additions, DE->Wii, sidecar re-import, divergence, CLI guards.

Read-only on originals; writes only under work/test_phase2e/. Synthetic fixtures (clearly marked) are derived from the
user's own DE save by setting DE-only fields; they are inputs for the merge logic, not evidence of in-game behaviour.

  python -m unittest discover -s tests -v
"""
import json
import os
import shutil
import struct
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import canon  # noqa: E402
import convert  # noqa: E402
import de_to_wii  # noqa: E402
import flagmap as fm  # noqa: E402
import reimport  # noqa: E402
import sidecar as scmod  # noqa: E402
import wii_save  # noqa: E402
import xcconv  # noqa: E402

O = os.path.join(ROOT, "work", "originals")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
OUT = os.path.join(ROOT, "work", "test_phase2e")
T = None


def rd(p):
    with open(p, "rb") as f:
        return f.read()


def setUpModule():
    global T
    T = convert.load_tables()
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)


def wii_progress(w):
    """Synthetic Wii progress on a Wii image: +1000 G, Shulk +1 level, quest 1 state flag, CRCs fixed."""
    img = de_to_wii.WiiImage(w)
    m = struct.unpack_from(">I", w, wii_save.ITEM + 0x120E8)[0]
    img.put(wii_save.ITEM + 0x120E8, "I", m + 1000)
    o = wii_save.CHAR_BASE + wii_save.CHAR_SIZE * 1
    lv = struct.unpack_from(">I", w, o + 0x17C)[0]
    img.put(o + 0x17C, "I", lv + 1)
    img.put(o + 0x2A4, "I", 0)
    pt = struct.unpack_from(">I", w, 0x11EB0)[0]
    img.put(0x11EB0, "I", pt + (1 << 6))   # +1 minute (packed h<<12 | m<<6 | s)
    de_to_wii.fix_crcs(img)
    return bytes(img.b)


def de_only_fixture(de):
    """SYNTHETIC: the user's DE save with DE-only state set (Expert Mode, cosmetic, reserve EXP, highest level,
    a DE-only collectable, a favourite mark, a DE-only flag, a Future Connected quest-counter byte)."""
    b = bytearray(de)
    b[0x1490D5] |= 1                                         # Expert Mode on
    o = 0x152728                                             # Shulk
    struct.pack_into("<I", b, o + 0x30, 0x1234)              # cosmetic head
    struct.pack_into("<III", b, o + 0xEC, struct.unpack_from("<I", b, o)[0] + 3, 777, 5000)  # highest lv +3, reserve
    # DE-only collectable gid 3956 in the first free collectable slot
    off, size = 0x31970, 0x14
    sl = next(i for i in range(500) if b[off + size * i + 0x10] == 0)
    struct.pack_into("<HHHHH", b, off + size * sl, sl, 10, 3956, 10, 1)
    struct.pack_into("<I", b, off + size * sl + 0xC, 9999)
    b[off + size * sl + 0x10] = 1
    # favourite mark on the first weapon
    b[0x3B10 + 0x11] = 1
    # a DE-only 1-bit flag (0x3550 block) and a Future Connected quest-counter byte (quest 1100)
    n = 0x3550 - 0xA20
    b[0x50 + 4 * (n >> 5) + (n & 31) // 8] |= 1 << ((n & 31) % 8)
    b[0x1270 + 8 * 1100] = 3
    return bytes(b), sl


class WiiToDE2E(unittest.TestCase):
    def test_canonical_equality_monado01_and_03(self):
        tpl = rd(TPL)
        for name in ("monado01", "monado03"):
            w = rd(os.path.join(O, name))
            out, log, fail = convert.build(w, tpl, T)
            self.assertEqual(fail, [])
            self.assertEqual(canon.compare(canon.from_wii(w, T)["shared"], canon.from_de(out, T)["shared"]), [], name)

    def test_clock_awards_quest_counters(self):
        w = rd(os.path.join(O, "monado01"))
        out, log, fail = convert.build(w, rd(TPL), T)
        self.assertEqual(struct.unpack_from("<HH", out, 0x149C04), (13, 13))
        self.assertEqual(struct.unpack_from("<HH", out, 0x149C24), (30, 27))
        want = {0x40: 10, 0x4A: 27, 0x89: 4, 0x8A: 4, 0x97: 5, 0xD6: 46, 0xD7: 46, 0x103: 18, 0x104: 18, 0x105: 18,
                0x107: 10}
        for g, v in want.items():
            self.assertEqual(fm.de_get(out, g), v, hex(g))
        # quests 221 / 287 objectives done on the Wii (items consumed) must be done (0xFF) in DE
        self.assertEqual(out[0x1270 + 8 * 221], 0xFF)
        self.assertEqual(out[0x1270 + 8 * 287 + 1], 0xFF)
        self.assertGreater(log["minimap"]["bytes_set"], 100000)

    def test_empty_slot_refused(self):
        with self.assertRaises(convert.ConvertError):
            convert.build(rd(os.path.join(O, "monado02")), rd(TPL), T)


class DEToWii(unittest.TestCase):
    def test_roundtrip_wii_de_wii_identical(self):
        for name in ("monado01", "monado03"):
            w = rd(os.path.join(O, name))
            de, _, _ = convert.build(w, rd(TPL), T)
            back, log, deferred = de_to_wii.build(de, w, T, lineage=True)
            self.assertEqual(back, w, name)

    def test_de_native_to_foreign_base(self):
        de, base = rd(TPL), rd(os.path.join(O, "monado03"))
        out, log, deferred = de_to_wii.build(de, base, T, lineage=False)
        self.assertTrue(all(wii_save.check_crcs(out).values()))
        self.assertEqual(de_to_wii.verify(out, de, T, deferred, log["remap"]), [])
        self.assertEqual(wii_save.decode_bytes(out)["party"], canon.from_de(de, T)["shared"]["party"])

    def test_monado_progressed_saves(self):
        base = rd(os.path.join(O, "monado01"))
        for rel in ("work/phase2e/monado/f3_travel_save/save_0/bfsgame00.sav",
                    "work/phase2e/monado/s1_story/save_0/bfsgame00a.sav"):
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                continue
            de = rd(p)
            out, log, deferred = de_to_wii.build(de, base, T, lineage=True)
            self.assertTrue(all(wii_save.check_crcs(out).values()))
            self.assertEqual(de_to_wii.verify(out, de, T, deferred, log["remap"]), [], rel)

    def test_capacity_refusal_and_overflow_sidecar(self):
        p = os.path.join(ROOT, "public/blobs/s232_207aed635e_bfsgame00.sav")
        if not os.path.exists(p):
            self.skipTest("public fixture missing")
        de, base = rd(p), rd(os.path.join(O, "monado01"))
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(de, base, T, lineage=False)
        out, log, deferred = de_to_wii.build(de, base, T, lineage=False, overflow="sidecar")
        self.assertEqual(sum(len(v) for v in deferred["overflow_items"].values()), 46)
        self.assertEqual(de_to_wii.verify(out, de, T, deferred, log["remap"]), [])

    def test_future_connected_map_refused(self):
        de = bytearray(rd(TPL))
        struct.pack_into("<I", de, 0x149C00, 0x00010032)   # ma5001 (Future Connected)
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(de), rd(os.path.join(O, "monado03")), T, lineage=False)


class SidecarReimport(unittest.TestCase):
    def export(self, de, base):
        w, log, deferred = de_to_wii.build(de, base, T, lineage=False)
        sc = scmod.make("de_to_wii", de, w, canon.from_de(de, T), canon.from_wii(w, T), deferred=deferred)
        return w, scmod.load(scmod.dumps(sc)), deferred

    def test_unchanged_wii_restores_de_exactly(self):
        de = rd(TPL)
        w, sc, _ = self.export(de, rd(os.path.join(O, "monado03")))
        back, log = reimport.wii_to_de_reimport(w, sc, T, no_newer_de=True)
        self.assertEqual(back, de)

    def test_de_only_state_survives_wii_progress(self):
        de, sl = de_only_fixture(rd(TPL))
        w, sc, deferred = self.export(de, rd(os.path.join(O, "monado03")))
        self.assertIn("collectable", deferred["de_only_items"])
        self.assertIn(1100, deferred["future_connected_quest_counters"])
        w2 = wii_progress(w)
        back, log = reimport.wii_to_de_reimport(w2, sc, T, no_newer_de=True)
        o = 0x152728
        self.assertEqual(back[0x1490D5] & 1, 1)                                  # Expert Mode kept
        self.assertEqual(struct.unpack_from("<I", back, o + 0x30)[0], 0x1234)     # cosmetic kept
        lv0 = struct.unpack_from("<I", de, o)[0]
        self.assertEqual(struct.unpack_from("<I", back, o)[0], lv0 + 1)          # Wii level-up applied
        self.assertEqual(struct.unpack_from("<I", back, o + 0xEC)[0], lv0 + 3)   # highest earned level kept
        self.assertEqual(struct.unpack_from("<I", back, o + 0xF4)[0], 5000)      # reserve EXP neither lost nor duplicated
        self.assertEqual(struct.unpack_from("<I", back, 0x151B40)[0], struct.unpack_from("<I", de, 0x151B40)[0] + 1000)
        rec = back[0x31970 + 0x14 * sl:0x31970 + 0x14 * (sl + 1)]
        self.assertEqual(struct.unpack_from("<HH", rec, 4), (3956, 10))          # DE-only item restored
        self.assertEqual(back[0x3B10 + 0x11], 1)                                 # favourite kept (same weapon)
        self.assertEqual(fm.de_get(back, 0x3550), 1)                             # DE-only flag kept
        self.assertEqual(back[0x1270 + 8 * 1100], 3)                             # Future Connected byte kept
        self.assertEqual(struct.unpack_from("<I", back, 4)[0], struct.unpack_from("<I", de, 4)[0] + 60)

    def test_divergence_requires_branch(self):
        de = rd(TPL)
        w, sc, _ = self.export(de, rd(os.path.join(O, "monado03")))
        w2 = wii_progress(w)
        de2 = bytearray(de)
        struct.pack_into("<I", de2, 0x151B40, struct.unpack_from("<I", de, 0x151B40)[0] + 7)   # DE played on too
        with self.assertRaises(reimport.DivergenceError):
            reimport.wii_to_de_reimport(w2, sc, T, current_de=bytes(de2))
        back, log = reimport.wii_to_de_reimport(w2, sc, T, current_de=bytes(de2), branch="wii")
        self.assertEqual(struct.unpack_from("<I", back, 0x151B40)[0], struct.unpack_from("<I", de, 0x151B40)[0] + 1000)

    def test_tampered_and_foreign_sidecar(self):
        de = rd(TPL)
        w, sc, _ = self.export(de, rd(os.path.join(O, "monado03")))
        bad = json.loads(scmod.dumps(sc))
        bad["output"]["sha256"] = "0" * 64
        with self.assertRaises(scmod.SidecarError):
            scmod.load(json.dumps(bad))
        with self.assertRaises(scmod.SidecarError):   # a Wii save from another playthrough is not a descendant
            reimport.wii_to_de_reimport(rd(os.path.join(O, "monado01")), sc, T, no_newer_de=True)


class RealChain(unittest.TestCase):
    """Real in-game chain (Phase 2E E2/E3): Monado-played DE1 -> Wii W1 -> Dolphin-played W2/W3 -> DE."""
    C = os.path.join(ROOT, "work", "phase2e", "chain")

    def setUp(self):
        need = ["b_de1/bfsgame00.sav", "c_w1/de_to_wii.sidecar.json", "d_w2_monado01", "f_w3_monado01"]
        if not all(os.path.exists(os.path.join(self.C, n)) for n in need):
            self.skipTest("chain artifacts not present")

    def test_dolphin_saves_reimport_exactly(self):
        sc = scmod.load(open(os.path.join(self.C, "c_w1/de_to_wii.sidecar.json"), encoding="utf-8").read())
        de1 = rd(os.path.join(self.C, "b_de1/bfsgame00.sav"))
        for w in ("d_w2_monado01", "f_w3_monado01"):
            wii = rd(os.path.join(self.C, w))
            out, log = reimport.wii_to_de_reimport(wii, sc, T, current_de=de1)
            self.assertEqual(canon.compare(canon.from_wii(wii, T)["shared"], canon.from_de(out, T)["shared"]), [], w)
            self.assertEqual(canon.from_de(out, T)["de_only"]["characters"], canon.from_de(de1, T)["de_only"]["characters"])
        # W3 carries Wii-only 1-bit flags 0x36C5/0x36C7 (set in Dolphin) - kept Wii-side, not an error
        self.assertEqual(canon.from_wii(rd(os.path.join(self.C, "f_w3_monado01")), T)["wii_only"]["high_1bit"],
                         [0x36C5, 0x36C7])

    def test_de1_to_wii_matches_exported_w1(self):
        sc = scmod.load(open(os.path.join(self.C, "c_w1/de_to_wii.sidecar.json"), encoding="utf-8").read())
        self.assertEqual(scmod.source_image(sc), rd(os.path.join(self.C, "b_de1/bfsgame00.sav")))
        w1 = scmod.output_image(sc)
        self.assertTrue(all(wii_save.check_crcs(w1).values()))
        de1 = rd(os.path.join(self.C, "b_de1/bfsgame00.sav"))
        # Phase 2F: the 2E converter copied serials although the games number acquisition order in opposite
        # directions; its W1 differs from DE1 in item order only. The 2F export of DE1 is exactly equal.
        diffs = [d for d in canon.compare(canon.from_wii(w1, T)["shared"], canon.from_de(de1, T)["shared"])
                 if not d[0].startswith("/achievements")]
        self.assertTrue(diffs)
        self.assertEqual([d for d in diffs if not (d[0].startswith("/inventory/") and d[0].endswith("/order"))], [])
        w1f, log, deferred = de_to_wii.build(de1, rd(os.path.join(O, "monado01")), T, lineage=True)
        self.assertEqual([d for d in canon.compare(canon.from_wii(w1f, T)["shared"], canon.from_de(de1, T)["shared"])
                          if not d[0].startswith("/achievements")], [])


class CLIGuards(unittest.TestCase):
    def test_refuses_live_paths_and_overwrite(self):
        with self.assertRaises(xcconv.Refused):
            xcconv.guard_out(r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save\save_0\x")
        with self.assertRaises(xcconv.Refused):
            xcconv.guard_out(r"E:\Launchbox\Emulators\Dolphin\User\Wii\title\00010000\53583445\data\monado01")
        p = os.path.join(OUT, "exists.bin")
        open(p, "wb").write(b"x")
        with self.assertRaises(xcconv.Refused):
            xcconv.atomic_write(p, b"y", False)

    def test_cli_wii_to_de_then_de_to_wii(self):
        d1 = os.path.join(OUT, "cli_w2d")
        rc = xcconv.main(["wii-to-de", "--wii", os.path.join(O, "monado01"), "--template", TPL, "--out", d1])
        self.assertEqual(rc, 0)
        de = os.path.join(d1, "save_0", "bfsgame00.sav")
        d2 = os.path.join(OUT, "cli_d2w")
        rc = xcconv.main(["de-to-wii", "--de", de, "--sidecar", os.path.join(d1, "wii_to_de.sidecar.json"), "--out", d2,
                          "--no-current-wii"])
        self.assertEqual(rc, 0)
        self.assertEqual(rd(os.path.join(d2, "monado01")), rd(os.path.join(O, "monado01")))
        rc = xcconv.main(["de-to-wii", "--de", de, "--sidecar", os.path.join(d1, "wii_to_de.sidecar.json"), "--out", d2,
                          "--no-current-wii"])
        self.assertEqual(rc, 2)   # existing outputs are never overwritten


if __name__ == "__main__":
    unittest.main()
