"""Phase 2C regression tests (read-only; operate on the snapshot copies in work/originals and public/blobs).

  python -m unittest discover -s tests -v        (run from the research directory)
"""
import json
import os
import struct
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import de_save  # noqa: E402
import wii_save  # noqa: E402

ORIG = os.path.join(ROOT, "work", "originals")
WII = [os.path.join(ORIG, f) for f in ("monado01", "monado03")]
DE_V10 = os.path.join(ORIG, "user_v10_bfsgame00.sav")
DE_V7 = os.path.join(ROOT, "public", "blobs", "s206_207aed635e_bfsgame01.sav")
W = json.load(open(os.path.join(ROOT, "data", "bdat_wii.json"), encoding="utf-8"))
D = json.load(open(os.path.join(ROOT, "data", "bdat_de.json"), encoding="utf-8"))
rows = lambda t, n: {r["id"]: r for r in t[n]["rows"]}
W_ITEM, D_ITEM, W_ARTS, W_SKILL, W_GROW = (rows(W, "ITM_itemlist"), rows(D, "ITM_itemlist"), rows(W, "pc_arts"),
                                           rows(W, "BTL_skilllist"), rows(W, "BTL_growlist"))


class Container(unittest.TestCase):
    def test_crcs(self):
        for p in WII:
            self.assertTrue(all(wii_save.check_crcs(wii_save.load(p)).values()), p)

    def test_char_field_table_covers_record(self):
        spans = sorted((o, n) for o, n, _, _ in wii_save.CHAR_FIELDS)
        pos = 0
        for o, n in spans:
            self.assertEqual(o, pos, f"gap/overlap at 0x{o:X}")
            pos = o + n
        self.assertEqual(pos, wii_save.CHAR_SIZE)

    def test_item_boxes_tile_item_object(self):
        spans = sorted((off, size * n) for _, _, off, size, n in wii_save.BOXES)
        pos = 0
        for o, n in spans:
            self.assertEqual(o, pos)
            pos = o + n
        self.assertEqual(pos, wii_save.ITEM_TAIL)


class RoundTrip(unittest.TestCase):
    """Decoded IR re-encodes to the identical bytes: no field is silently lost."""

    def test_characters(self):
        for p in WII:
            d = wii_save.load(p)
            for k in range(wii_save.N_CHARS):
                o = wii_save.CHAR_BASE + wii_save.CHAR_SIZE * k
                orig = d[o:o + wii_save.CHAR_SIZE]
                rec = wii_save.decode_char(d, k)
                self.assertEqual(wii_save.encode_char(rec, bytes(len(orig))), orig, f"{p} char {k}")

    def test_item_records(self):
        for p in WII:
            d = wii_save.load(p)
            items = wii_save.decode_items(d)
            rebuilt = bytearray(wii_save.ITEM_TAIL)
            for name, _, off, size, n in wii_save.BOXES:
                for r in items[name]:
                    rebuilt[off + size * r["index"]:off + size * (r["index"] + 1)] = wii_save.encode_record(name, r, size)
            self.assertEqual(bytes(rebuilt), d[wii_save.ITEM:wii_save.ITEM + wii_save.ITEM_TAIL], p)


class Semantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir = wii_save.decode(WII[0])

    def test_party_equipment_references_resolve(self):
        n = 0
        for k in self.ir["party"]:
            c = self.ir["characters"][k]
            for slot, e in c["equipment"].items():
                if e["box_index"] is None:
                    self.assertEqual(e["gid"], 0)
                    continue
                rec = next(r for r in self.ir["items"][slot] if r["index"] == e["box_index"])
                self.assertEqual((rec["header"]["gid"], rec["header"]["row"]), (e["gid"], e["row"]))
                self.assertLess(e["box_index"], wii_save.EQUIP_INVENTORY_SLOTS)
                n += 1
        self.assertEqual(n, 35)  # 6 members x 6 slots, Reyn's head empty

    def test_item_ids_identical_in_de(self):
        for box in ("head", "body", "arm", "legs", "feet", "weapon", "collectable", "material", "keyitem"):
            for r in self.ir["items"][box]:
                h = r["header"]
                w, d = W_ITEM[h["gid"]], D_ITEM[h["gid"]]
                self.assertEqual((w["itemType"], w["itemID"]), (h["type"], h["row"]))
                self.assertEqual((d["itemType"], d["itemID"]), (w["itemType"], w["itemID"]))

    def test_gem_descriptors(self):
        R = "EDCBAS"
        for r in self.ir["items"]["gem"]:
            g, sk = r["desc"], W_SKILL[r["desc"]["effect"]]
            self.assertEqual(r["header"]["row"], g["effect"])
            self.assertTrue(1 <= g["rank"] <= 6)
            self.assertEqual(g["chance"], sk["percent_" + R[g["rank"] - 1]])
            self.assertTrue(sk["lower_" + R[g["rank"] - 1]] <= g["strength"] <= sk["upper_" + R[g["rank"] - 1]])

    def test_art_levels_follow_get_lv(self):
        for k in self.ir["party"]:
            c = self.ir["characters"][k]
            for a in W_ARTS.values():
                if a["pc"] == k and a["get_type"] == 1 and a["arts_type"] == 0:
                    lv = c["art_levels"][a["idx"]][0]
                    self.assertEqual(lv == 0, a["get_lv"] > c["level"], f"char {k} art {a['id']}")
                    self.assertLessEqual(lv, 4 if c["art_levels"][a["idx"]][1] == 0 else 12)

    def test_skill_trees(self):
        psv = rows(W, "BTL_PSVskill")
        for k in self.ir["party"]:
            c = self.ir["characters"][k]
            for t in range(5):
                nodes = [n[0] for n in c["skill_rows"][t]["nodes"]]
                cnt = sum(1 for v in nodes if v)
                self.assertTrue(all(nodes[:cnt]))
                for i, v in enumerate(nodes[:cnt]):
                    self.assertEqual(v, (k - 1) * 25 + 5 * t + i + 1)
                if t == c["skill_selected_tree"] and cnt < 5:  # unspent SP below next node's cost
                    self.assertLess(c["skill_sp"][t], psv[(k - 1) * 25 + 5 * t + cnt + 1]["point_PP"] * 100)

    def test_exp_below_next_level(self):
        for k in self.ir["party"]:
            c = self.ir["characters"][k]
            self.assertLess(c["exp"], W_GROW[c["level"] + 1]["level_exp"])
            self.assertLessEqual(c["affinity_coins"], 999)


class DE(unittest.TestCase):
    def test_v10_and_v7_equipment_refs(self):
        for p in (DE_V10, DE_V7):
            ir = de_save.decode(p)
            boxes = {b: {r["slot"]: r for r in recs} for b, recs in ir["boxes"].items()}
            for cid in ir["party"]:
                for slot, e in ir["characters"][cid]["equipment"].items():
                    r = boxes[slot][e["index"]]
                    self.assertEqual((r["index"], r["type"]), (e["index"], e["type"]), p)

    def test_v10_offsets(self):
        ir = de_save.decode(DE_V10)
        self.assertEqual((ir["version"], ir["story"], ir["party"]), (10, 6, [1, 2]))
        self.assertEqual(ir["characters"][4]["level"], 27)


if __name__ == "__main__":
    unittest.main()
