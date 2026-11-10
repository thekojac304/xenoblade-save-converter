"""Phase 2D converter tests (read-only on originals; writes only under work/test_phase2d).

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
import convert  # noqa: E402
import de_save  # noqa: E402
import flagmap as fm  # noqa: E402
import wii_save  # noqa: E402

WII = os.path.join(ROOT, "work", "originals", "monado01")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
OUT = os.path.join(ROOT, "work", "test_phase2d")
RESAVE = os.path.join(ROOT, "work", "run6", "save_0", "bfsgame00.sav")  # DE's own re-save (isolated Monado run)


class Converter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(OUT, ignore_errors=True)
        cls.path = convert.main(WII, TPL, OUT, features=())  # Phase 2D baseline (no 2E steps)
        with open(cls.path, "rb") as f:
            cls.out = f.read()
        with open(TPL, "rb") as f:
            cls.tpl = f.read()
        cls.de = de_save.decode(cls.path)
        cls.ir = wii_save.decode(WII)
        cls.manifest = json.load(open(os.path.join(OUT, "manifest.json")))

    def test_refuses_output_outside_work(self):
        with self.assertRaises(convert.ConvertError):
            convert.main(WII, TPL, os.path.join(ROOT, "not_work_dir"))

    def test_baseline_output_identical_to_phase2d(self):
        import hashlib
        self.assertEqual(hashlib.sha256(self.out).hexdigest(),
                         "62c92c200f6cf5276d3fd8275c449101886f5e7763543be710b3ac68af7e5143")

    def test_readback_clean(self):
        self.assertEqual(self.manifest["verification_failures"], [])
        self.assertEqual((len(self.out), self.de["version"]), (0x153F30, 10))

    def test_story_party_money_location(self):
        self.assertEqual(self.de["story"], 150)
        self.assertEqual(self.de["party"], [1, 4, 6, 5, 2, 7])
        self.assertEqual(self.de["money"], 375150)
        self.assertEqual(struct.unpack_from("<I", self.out, 0x149C00)[0], 0x0001000A)
        self.assertEqual(struct.unpack_from("<I", self.out, 4)[0], 22 * 3600 + 60 + 57)

    def test_characters(self):
        want = {1: (52, 12295, 2832, 78), 2: (52, 9150, 6987, 78), 4: (51, 21224, 7579, 77), 5: (52, 1110, 10845, 78),
                6: (51, 29548, 8721, 77), 7: (51, 33318, 14984, 77)}
        for k, (lv, exp, ap, coins) in want.items():
            c = self.de["characters"][k]
            self.assertEqual((c["level"], c["exp"], c["ap"], c["affinity_coins"]), (lv, exp, ap, coins))
            self.assertEqual((c["highest_level"], c["highest_level_exp"]), (lv, exp))

    def test_equipment_and_gem_references_resolve(self):
        boxes = {n: {r["slot"]: r for r in recs} for n, recs in self.de["boxes"].items()}
        for cid in self.de["party"]:
            for slot, e in self.de["characters"][cid]["equipment"].items():
                if (e["index"], e["type"]) == (0, 0):
                    continue
                r = boxes[slot][e["index"]]
                self.assertEqual((r["index"], r["type"]), (e["index"], e["type"]))
                for s in r["sockets"]:
                    if s["normal"]:
                        g = boxes["gem"][s["normal"] & 0xFFFF]
                        self.assertEqual((s["normal"] >> 16, g["type"]), (3, 3))

    def test_inventory_counts_and_ids(self):
        counts = {k: len(v) for k, v in self.de["boxes"].items()}
        self.assertEqual(counts, {"weapon": 49, "head": 28, "body": 26, "arm": 24, "legs": 35, "feet": 29,
                                  "crystal": 159, "gem": 68, "collectable": 116, "material": 126, "keyitem": 13,
                                  "artmanual": 0})
        for name in ("weapon", "head", "collectable", "material", "keyitem"):
            wii = {r["index"]: r for r in self.ir["items"][name]}
            for r in self.de["boxes"][name]:
                self.assertEqual((r["gid"], r["serial"]), (wii[r["slot"]]["header"]["gid"], wii[r["slot"]]["header"]["serial"]))

    def test_crystals(self):
        for r in self.ir["items"]["crystal"]:
            o = 0x26D90 + 0x2C * r["index"]
            c = r["crystal"]
            effs = [(e, v) for e, v in zip(c["effects"], c["values"]) if e]
            self.assertEqual(struct.unpack_from("<H", self.out, o + 0x14)[0], c["source"])
            self.assertEqual((self.out[o + 0x16], self.out[o + 0x17], self.out[o + 0x19], self.out[o + 0x1A]),
                             (c["rank"], c["atr_type"], c["cylinder"], len(effs)))
            for k, (e, v) in enumerate(effs):
                self.assertEqual(struct.unpack_from("<HB", self.out, o + 0x1C + 4 * k), (e, v))
            if c["kind"] == "drop":  # DE generator: named enemy <=> values 80-100
                self.assertEqual(self.out[o + 0x18] == 2, effs[0][1] >= 80)

    def test_unknown_padding_kept_from_template(self):
        for name in ("collectable", "material", "keyitem"):
            _, off, size = convert.BOX[name]
            for r in self.de["boxes"][name]:
                self.assertEqual(r["u0a"], 0x3FFF)

    def test_bytes_outside_logged_ranges_untouched(self):
        self.assertEqual(self.manifest["verification_failures"], [])  # verify() fails on any stray byte

    @unittest.skipUnless(os.path.exists(RESAVE), "isolated in-game re-save not present")
    def test_in_game_resave_normalization(self):
        with open(RESAVE, "rb") as f:
            re = f.read()
        conv_ref = open(os.path.join(ROOT, "work", "phase2d", "save_0", "bfsgame00.sav"), "rb").read()
        diff = [i for i in range(len(re)) if re[i] != conv_ref[i]]
        # header (play time, timestamp, u32 0x4C set to 1 by DE on save), derived location words, minimap bitmaps
        allowed = lambda i: i < 0x50 or 0x149C00 <= i < 0x149C40 or 0x3B5B0 <= i < 0x148D6C
        self.assertEqual([hex(i) for i in diff if not allowed(i)], [])
        for g in range(0, 0x3720):
            self.assertEqual(fm.de_get(re, g), fm.de_get(conv_ref, g))


if __name__ == "__main__":
    unittest.main()
