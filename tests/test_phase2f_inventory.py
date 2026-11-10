"""Phase 2F workstream B: inventory capacity, compaction / remapping, overflow deferral, equipment, gems, crystals,
item identity and acquisition order.

Capacities are the Wii box getter's ([C] 0x80158490, re-read in Phase 2F): types 2/4-8 (weapons, armour) and 11
(materials) hold 10 x (bits 1..11 of ITEM+0x12108) + 60 + min(ITEM+0x12110, 30) (the getter writes the clamp back);
gems (3), crystals (9) and collectables (10) 300, key items (12) 200, art manuals (13) 240; types 0, 1, > 13: 0.
Equipment boxes have 150 inventory records (+13 per-character staging records), so the converter caps them at 150.

Fixtures: the 2F conversion of the user's monado01 with SYNTHETIC inventories (valid item ids for each box).
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2f_util as U  # noqa: E402
import canon  # noqa: E402
import convert  # noqa: E402
import de_to_wii  # noqa: E402
import reimport  # noqa: E402
import sidecar as scmod  # noqa: E402
import wii_save  # noqa: E402

T = None
CAP_BOXES = ("weapon", "head", "material", "collectable", "keyitem", "artmanual", "crystal", "gem")


def setUpModule():
    global T
    T = U.tables()


def wii_with_capacity(bits, bonus):
    """monado01 with the expansion bits / bonus set (CRCs fixed); the box getter derives the capacity from them."""
    m = U.Wii(U.wii01())
    m.img.put(wii_save.ITEM + 0x12108, "I", bits)
    m.img.put(wii_save.ITEM + 0x12110, "I", bonus)
    return m.done()


def clear_de_box(de, box):
    typ, off, size = U.DBOX[box]
    b = bytearray(de)
    pat = bytes(b[off + size * 499:off + size * 500])
    assert not pat[0x10]
    for i in range(500):
        if b[off + size * i + 0x10]:
            b[off + size * i:off + size * (i + 1)] = pat
    return bytes(b)


def unequip_all(de):
    b = bytearray(de)
    for k in range(1, 8):
        o = U.DE_CHAR + 0x138 * (k - 1)
        b[o + 0x14:o + 0x2C] = bytes(0x18)
    return bytes(b)


def de_set_record(b, box, sl, gid, qty, serial, **kw):
    typ, off, size = U.DBOX[box]
    o = off + size * sl
    rec = bytearray(b[off + size * 499:off + size * 500])
    struct.pack_into("<HHHHH", rec, 0, sl, typ, gid, typ, qty)
    struct.pack_into("<I", rec, 0xC, serial)
    rec[0x10], rec[0x11] = 1, 0
    if box in U.EQUIP:
        rec[0x15] = kw.get("sockets", 0)
        for s, (kind, v) in enumerate(kw.get("socks", [])):
            if kind == "gem":
                struct.pack_into("<HH", rec, 0x18 + 8 * s, v, 3)
            elif kind == "fixed":
                struct.pack_into("<HH", rec, 0x1C + 8 * s, v, 1)
    if box == "gem":
        eff, rank, strength, chance = kw["gem"]
        rec[0x16], rec[0x17], rec[0x19] = rank, T["d_skill"][eff]["atr_type"], 0
        struct.pack_into("<HHBB", rec, 0x1A, 1, eff, strength, chance)
    b[o:o + size] = rec
    ctr = U.de_save.SERIALS + 4 * typ
    struct.pack_into("<I", b, ctr, max(struct.unpack_from("<I", b, ctr)[0], serial))


def gem(effect, rank, top=False):
    """A gem the game can produce: rank 1..6, chance from BTL_skill, strength at the low (or top) end of the rank."""
    sk = T["w_skill"][effect]
    r = "EDCBAS"[rank - 1]
    return effect, rank, sk["upper_" + r] if top else sk["lower_" + r], sk["percent_" + r]


def fill(de, box, slots, gids=None):
    src = canon.from_de(de, T)["shared"]["inventory"]["crystal"] if box == "crystal" else None
    real = [s for s in sorted(src)] if src else []
    typ, off, size = U.DBOX[box]
    orig = bytes(de)
    b = bytearray(clear_de_box(de, box))
    gids = gids or U.valid_gids(box)
    for i, sl in enumerate(slots):
        if box == "gem":
            de_set_record(b, box, sl, 0, 1, i + 1, gem=gem(1 + i % 20, 1 + i % 6))
        elif box == "crystal":          # copies of the user's real crystal records
            r = real[i % len(real)]
            rec = bytearray(orig[off + size * r:off + size * (r + 1)])
            struct.pack_into("<H", rec, 0, sl)
            struct.pack_into("<I", rec, 0xC, i + 1)
            b[off + size * sl:off + size * (sl + 1)] = rec
        else:
            de_set_record(b, box, sl, gids[i % len(gids)], 1, i + 1)
    if box == "crystal":
        struct.pack_into("<I", b, U.de_save.SERIALS + 4 * typ, len(slots))
    return bytes(b)


class Capacity(unittest.TestCase):
    def test_capacity_formula_matches_code(self):
        for bits, bonus, var in ((0, 0, 60), (1, 0, 60), (0b10, 0, 70), (0xFFE, 0, 170), (0xFFE, 30, 200),
                                 (0xFFE, 31, 200), (0xFFF, 999, 200), (0x1FE, 0, 140)):
            caps = de_to_wii.wii_capacity(wii_with_capacity(bits, bonus))
            for b in de_to_wii.EQUIP:
                self.assertEqual(caps[b], min(150, var), (bits, bonus, b))
            self.assertEqual(caps["material"], var, (bits, bonus))
            self.assertEqual((caps["gem"], caps["crystal"], caps["collectable"], caps["keyitem"], caps["artmanual"]),
                             (300, 300, 300, 200, 240))

    def test_boundaries_every_category(self):
        """0, 1, cap-1, cap fit; cap+1 and cap+50 are refused (overflow=refuse) or deferred and restored."""
        base = U.wii01()
        caps = de_to_wii.wii_capacity(base)
        de = unequip_all(U.de0())
        for box in CAP_BOXES:
            cap = caps[box]
            for n in (0, 1, cap - 1, cap, cap + 1, cap + 50):
                if n > 500:
                    continue
                d = fill(de, box, list(range(n)))
                if box == "gem":   # no equipment left, so no socket references into the refilled gem box
                    for eb in U.EQUIP:
                        d = clear_de_box(d, eb)
                if n <= cap:
                    w, log, dfr = de_to_wii.build(d, base, T, lineage=True)
                    self.assertEqual(de_to_wii.verify(w, d, T, dfr, log["remap"]), [], (box, n))
                    self.assertEqual(len(canon.from_wii(w, T)["shared"]["inventory"][box]), n, (box, n))
                else:
                    with self.assertRaises(de_to_wii.IncompatibleError, msg=(box, n)):
                        de_to_wii.build(d, base, T, lineage=True)
                    w, log, dfr = de_to_wii.build(d, base, T, lineage=True, overflow="sidecar")
                    self.assertEqual(len(dfr["overflow_items"][box]), n - cap, (box, n))
                    self.assertEqual(de_to_wii.verify(w, d, T, dfr, log["remap"]), [], (box, n))
                    sc = scmod.load(scmod.dumps(scmod.make("de_to_wii", d, w, canon.from_de(d, T),
                                                           canon.from_wii(w, T), deferred=dfr)))
                    back, rlog = reimport.wii_to_de_reimport(U.Wii(w).done() if False else w, sc, T, current_de=d)
                    self.assertEqual(back, d, (box, n))      # unchanged Wii: exact original, overflow included
                    w2 = U.Wii(w)
                    w2.money(10)
                    back2, rlog2 = reimport.wii_to_de_reimport(w2.done(), sc, T, current_de=d)
                    self.assertEqual(len(canon.from_de(back2, T)["shared"]["inventory"][box]), n, (box, n))

    def test_compaction_remaps_equipment_and_gem_references(self):
        """Equipped weapon at DE slot 300 and its socketed gem at DE gem slot 450 move into free Wii slots; every
        reference follows the moved instance (checked independently from the Wii character record)."""
        de = U.de0()
        b = bytearray(de)
        gem_sl, wpn_sl = 450, 300
        de_set_record(b, "gem", gem_sl, 0, 1, 999, gem=gem(5, 3))
        gid = U.valid_gids("weapon")[7]
        de_set_record(b, "weapon", wpn_sl, gid, 1, 999, sockets=2, socks=[("gem", gem_sl)])
        struct.pack_into("<HH", b, U.DE_CHAR + 0x14 + 4 * 5, wpn_sl, 2)    # Shulk equips it
        w, log, dfr = de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)
        self.assertEqual(de_to_wii.verify(w, bytes(b), T, dfr, log["remap"]), [])
        new_w, new_g = log["remap"]["weapon"][wpn_sl], log["remap"]["gem"][gem_sl]
        self.assertLess(new_w, 140)
        ir = wii_save.decode_bytes(w)
        eq = ir["characters"][1]["equipment"]["weapon"]
        self.assertEqual((eq["box_index"], eq["gid"]), (new_w, gid))
        rec = next(r for r in ir["items"]["weapon"] if r["index"] == new_w)
        self.assertEqual(rec["sockets"][0]["gem_box_ref"], new_g)
        g = next(r for r in ir["items"]["gem"] if r["index"] == new_g)
        self.assertEqual((g["desc"]["effect"], g["desc"]["rank"], g["desc"]["strength"], g["desc"]["chance"]), gem(5, 3))
        self.assertEqual(rec["sockets"][0]["desc"], g["desc"])        # socket descriptor mirrors the gem record

    def test_equipped_items_beyond_capacity_are_never_deferred(self):
        caps = de_to_wii.wii_capacity(U.wii01())
        d = fill(unequip_all(U.de0()), "weapon", list(range(caps["weapon"] + 5)))
        b = bytearray(d)
        party = canon.from_de(d, T)["shared"]["party"]           # absent characters hold no equipment in DE
        for k, sl in zip(party, range(caps["weapon"], caps["weapon"] + 5)):
            struct.pack_into("<HH", b, U.DE_CHAR + 0x138 * (k - 1) + 0x14 + 4 * 5, sl, 2)
        w, log, dfr = de_to_wii.build(bytes(b), U.wii01(), T, lineage=True, overflow="sidecar")
        deferred = set(dfr["overflow_items"]["weapon"])
        self.assertFalse(deferred & set(range(caps["weapon"], caps["weapon"] + 5)))
        self.assertEqual(de_to_wii.verify(w, bytes(b), T, dfr, log["remap"]), [])


class EquipmentAndGems(unittest.TestCase):
    def roundtrip(self, b):
        b = bytes(b)
        w, log, dfr = de_to_wii.build(b, U.wii01(), T, lineage=True)
        self.assertEqual(de_to_wii.verify(w, b, T, dfr, log["remap"]), [])
        back, clog, fail = convert.build(w, b, T, lineage_template=True)   # compaction moved slots: compare to Wii
        self.assertEqual(fail, [])
        diffs = [d for d in canon.compare(canon.from_wii(w, T)["shared"], canon.from_de(back, T)["shared"])
                 if not d[0].startswith(("/achievements", "/quest_counters", "/clock"))]
        self.assertEqual(diffs, [])
        return w

    def test_sockets_fixed_and_removable_gems(self):
        b = bytearray(U.de0())
        fixed = next(g for g, r in T["w_item"].items() if r["itemType"] == 3 and r["percent"])
        gs = [470, 471, 472]
        for i, sl in enumerate(gs):
            de_set_record(b, "gem", sl, 0, 1, 2000 + i, gem=gem(10 + i, 1 + i))
        wg = U.valid_gids("weapon")
        de_set_record(b, "weapon", 480, wg[1], 1, 3000, sockets=3, socks=[("gem", 470), ("gem", 471), ("gem", 472)])
        de_set_record(b, "weapon", 481, wg[1], 1, 3001, sockets=0)                    # same id, zero sockets
        de_set_record(b, "weapon", 482, wg[2], 1, 3002, sockets=1, socks=[("fixed", fixed)])
        de_set_record(b, "gem", 473, 0, 1, 2003, gem=gem(20, 6, top=True))           # loose gem, top of rank S
        de_set_record(b, "head", 490, U.valid_gids("head")[3], 1, 3003, sockets=0)
        self.roundtrip(b)

    def test_empty_equipment_slots_and_absent_characters(self):
        b = bytearray(U.de0())
        struct.pack_into("<HH", b, U.DE_CHAR + 0x14, 0, 0)                           # Shulk without head gear
        w = self.roundtrip(b)
        eq = wii_save.decode_bytes(w)["characters"][1]["equipment"]["head"]
        self.assertEqual((eq["gid"], eq["box_index"]), (0, None))
        # Fiora (3) is not in the party at scenario 150: her DE record holds no equipment, the Wii keeps staging gear
        self.assertIsNone(canon.from_de(U.de0(), T)["shared"]["characters"][3]["equipment"])

    def test_gem_values_beyond_field_widths_refused(self):
        b = bytearray(U.de0())
        de_set_record(b, "gem", 474, 0, 1, 2004, gem=(20, 8, 10, 1))                 # rank 8 > 3 bits
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)
        b = bytearray(U.de0())
        de_set_record(b, "gem", 474, 0, 1, 2004, gem=(20, 3, 10, 99))                # chance not the table's
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)
        m = U.Wii(U.wii01())                                                         # Wii gem strength 300 > DE byte
        ir = wii_save.decode_bytes(m.b)
        g = ir["items"]["gem"][0]
        o = wii_save.ITEM + U.WBOX["gem"][1] + 16 * g["index"] + 8
        w0 = struct.unpack_from(">I", m.b, o)[0]
        m.img.put(o, "I", (w0 & ~(0x7FF << 10)) | 300 << 10)
        with self.assertRaises(convert.ConvertError):
            convert.build(m.done(), U.tpl(), T)

    def test_crystals_round_trip_all_kinds(self):
        """The user's 159 crystals (list, drop, cylinder) survive Wii -> DE -> Wii byte for byte; an unmatched drop
        crystal is refused, not approximated."""
        de = U.de0()
        self.assertEqual(de_to_wii.build(de, U.wii01(), T, lineage=True)[0], U.wii01())
        kinds = {c["crystal"]["kind"] for c in wii_save.decode_bytes(U.wii01())["items"]["crystal"]}
        self.assertTrue({"list", "drop"} <= kinds)
        b = bytearray(de)
        sl = next(s for s, r in canon.from_de(de, T)["shared"]["inventory"]["crystal"].items()
                  if r["gid"] == 0 and not r["cylinder"])
        o = 0x26D90 + 0x2C * sl
        struct.pack_into("<HB", b, o + 0x1C, 97, 50)                                  # effect no drop row has
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T, lineage=False)


class Identity(unittest.TestCase):
    def test_de_only_ids_deferred_or_refused(self):
        b = bytearray(U.de0())
        de_only = U.de_only_gids("weapon")
        self.assertTrue(de_only)
        de_set_record(b, "weapon", 495, de_only[0], 1, 5000)
        w, log, dfr = de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)
        self.assertIn(495, dfr["de_only_items"]["weapon"])
        struct.pack_into("<HH", b, U.DE_CHAR + 0x14 + 4 * 5, 495, 2)                 # now equipped
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)

    def test_invalid_ids_and_quantities(self):
        for gid, qty in ((U.valid_gids("collectable")[0], 0), (U.valid_gids("collectable")[0], 100), (4000, 1)):
            b = bytearray(U.de0())
            de_set_record(b, "collectable", 498, gid, qty, 6000)
            with self.assertRaises(de_to_wii.IncompatibleError, msg=(gid, qty)):
                w, log, dfr = de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)
                if 498 in dfr.get("de_only_items", {}).get("collectable", {}):
                    raise de_to_wii.IncompatibleError("deferred as DE-only")  # an unknown id is not lost either
        b = bytearray(U.de0())
        de_set_record(b, "collectable", 498, U.valid_gids("collectable")[0], 99, 6000)   # maximum stack
        w = de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)[0]
        self.assertIn(99, [r["qty"] for r in canon.from_wii(w, T)["shared"]["inventory"]["collectable"].values()])

    def test_acquisition_order_both_directions(self):
        """B3: newest DE item = newest Wii item (age 1); DE serials after Wii -> DE are unique and the DE counter is
        above them; Wii ages after DE -> Wii are a dense 1..N."""
        de = U.de0()
        for box, ser in canon.from_de(de, T)["de_only"]["item_serials"].items():
            self.assertEqual(len(set(ser.values())), len(ser), box)
            typ = U.DBOX[box][0]
            if ser:
                self.assertGreaterEqual(struct.unpack_from("<I", de, U.de_save.SERIALS + 4 * typ)[0], max(ser.values()))
        m = U.DE(de)
        sl = m.pickup("material", U.valid_gids("material")[11], 3)
        w = de_to_wii.build(m.done(), U.wii01(), T, lineage=True)[0]
        ages = canon.from_wii(w, T)["wii_only"]["item_ages"]["material"]
        self.assertEqual(sorted(ages.values()), list(range(1, len(ages) + 1)))
        self.assertEqual(ages[sl], 1)
        # the Wii order of the user's real save is preserved by Wii -> DE (oldest Wii item = DE serial 1)
        w0 = canon.from_wii(U.wii01(), T)
        d0 = canon.from_de(de, T)
        for box in ("weapon", "material", "crystal"):
            self.assertEqual({s: r["order"] for s, r in w0["shared"]["inventory"][box].items()},
                             {s: r["order"] for s, r in d0["shared"]["inventory"][box].items()}, box)


if __name__ == "__main__":
    unittest.main()
