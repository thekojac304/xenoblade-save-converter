"""Phase 2F workstream A: round-trip invariants and metamorphic / property tests with reproducible seeds.

Fixtures: the user's real saves (monado01 scenario 150, monado03 scenario 18) and the 2F conversion of monado01;
progress is SYNTHETIC (tests/p2f_util.py mutations, valid encodings only). On a failure the mutation list is
minimised (delta debugging) and saved under phase2f/fixtures/ before the assertion fails.

  python -m unittest tests.test_phase2f_properties -v
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

T = None
SEEDS = range(1, 13)
TOL = ("/achievements", "/quest_counters", "/clock", "/characters/1/palette2")


def setUpModule():
    global T
    T = U.tables()


def hard(a, b):
    return [d for d in canon.compare(a, b) if not d[0].startswith(TOL)]


def export_de(de, base, lineage):
    w, log, dfr = de_to_wii.build(de, base, T, lineage=lineage, overflow="sidecar")
    sc = scmod.load(scmod.dumps(scmod.make("de_to_wii", de, w, canon.from_de(de, T), canon.from_wii(w, T),
                                           deferred=dfr)))
    return w, sc, dfr


def without(shared, slots):
    for box, sl in slots:
        shared["inventory"][box].pop(sl, None)
    for box in shared["inventory"]:
        shared["inventory"][box] = canon.rerank(shared["inventory"][box])
    return shared


class Determinism(unittest.TestCase):
    def test_same_inputs_same_bytes(self):
        a = convert.build(U.wii01(), U.tpl(), T)[0]
        b = convert.build(U.wii01(), U.tpl(), T)[0]
        self.assertEqual(a, b)
        w1 = de_to_wii.build(a, U.wii01(), T, lineage=False)[0]
        w2 = de_to_wii.build(a, U.wii01(), T, lineage=False)[0]
        self.assertEqual(w1, w2)
        s1 = scmod.dumps(scmod.make("de_to_wii", a, w1, canon.from_de(a, T), canon.from_wii(w1, T)))
        s2 = scmod.dumps(scmod.make("de_to_wii", a, w2, canon.from_de(a, T), canon.from_wii(w2, T)))
        self.assertEqual(s1, s2)


class RoundTrips(unittest.TestCase):
    def test_wii_de_wii_byte_identical_for_random_wii_states(self):
        """A1: Wii -> DE -> Wii without play is byte-identical, for the real saves and 12 seeded Wii progressions."""
        cases = [("monado01", U.wii01()), ("monado03", U.wii03())]
        for seed in SEEDS:
            cases.append((f"seed{seed}", U.apply(U.wii01(), U.random_mutations(U.rng(seed), 10, "wii"), "wii")))
        for name, w in cases:
            de, log, fail = convert.build(w, U.tpl(), T)
            self.assertEqual(fail, [], name)
            self.assertEqual(hard(canon.from_wii(w, T)["shared"], canon.from_de(de, T)["shared"]), [], name)
            back = de_to_wii.build(de, w, T, lineage=True)[0]
            self.assertEqual(back, w, name)

    def test_de_wii_de_foreign_path_canonical(self):
        """A1: DE -> Wii (foreign base) -> DE (first-export path, no sidecar shortcut) keeps the shared state."""
        for seed in SEEDS:
            de = U.apply(U.de0(), U.random_mutations(U.rng(100 + seed), 10, "de"), "de")
            w = de_to_wii.build(de, U.wii01(), T, lineage=False)[0]   # foreign mode, capacity 140
            self.assertEqual(de_to_wii.verify(w, de, T), [], seed)
            back, log, fail = convert.build(w, de, T)
            self.assertEqual(fail, [], seed)
            self.assertEqual(hard(canon.from_de(de, T)["shared"], canon.from_de(back, T)["shared"]), [], seed)

    def test_repeated_conversion_is_a_fixpoint(self):
        """A1/A2: converting an unchanged state again and again changes nothing (no growth of items or money)."""
        w = U.wii01()
        de1 = convert.build(w, U.tpl(), T)[0]
        w1, sc1, _ = export_de(de1, w, True)
        self.assertEqual(w1, w)
        de2, log = reimport.wii_to_de_reimport(w1, sc1, T, current_de=de1)
        self.assertEqual(de2, de1)
        for _ in range(3):
            w1, sc1, _ = export_de(de2, w1, True)
            de2, log = reimport.wii_to_de_reimport(w1, sc1, T, current_de=de2)
        self.assertEqual((w1, de2), (w, de1))


class DeltaReimport(unittest.TestCase):
    def check_seed(self, seed, muts):
        """DE -> Wii, Wii progress (muts), re-import: the result equals the Wii state; DE-only state is unchanged."""
        de = U.de0()
        w, sc, dfr = export_de(de, U.wii01(), True)
        w2 = U.apply(w, muts, "wii")
        out, log = reimport.wii_to_de_reimport(w2, sc, T, current_de=de)
        drop = [(p[1], p[3]) for p in log.get("deferred_restored", [])]
        problems = hard(canon.from_wii(w2, T)["shared"], without(canon.from_de(out, T)["shared"], drop))
        a, b = canon.from_de(de, T)["de_only"], canon.from_de(out, T)["de_only"]
        for k in ("flags", "quest_counters_fc", "version"):
            if a[k] != b[k]:
                problems.append((f"de_only/{k}", "changed"))
        for k, ch in a["characters"].items():
            for f in ("cosmetic", "reserve_exp", "link_unlock_index", "palette2_slot0"):
                if ch[f] != b["characters"][k][f]:
                    problems.append((f"de_only/characters/{k}/{f}", ch[f], b["characters"][k][f]))
            if b["characters"][k]["highest_level"] < ch["highest_level"]:
                problems.append((f"de_only/characters/{k}/highest_level", "decreased"))
        # serial uniqueness per box after the merge
        for box, ser in canon.from_de(out, T)["de_only"]["item_serials"].items():
            if len(set(ser.values())) != len(ser):
                problems.append((f"serials/{box}", "duplicate DE acquisition serials"))
        return problems

    def test_random_wii_progress_reimports_exactly(self):
        for seed in SEEDS:
            muts = U.random_mutations(U.rng(200 + seed), 12, "wii")
            problems = self.check_seed(seed, muts)
            if problems:
                small = U.minimize(muts, lambda m: bool(self.check_seed(seed, m)))
                p = U.save_fixture(f"A_delta_reimport_seed{seed}", {"seed": seed, "mutations": muts, "minimal": small,
                                                                     "problems": problems[:20]})
                self.fail(f"seed {seed}: {problems[:3]} (minimal {small}, fixture {p})")

    def test_pickups_age_every_wii_item_and_still_reimport(self):
        """B3: a Wii pickup ages all items (game rule 0x80159080); descent and the merge must not depend on serials."""
        de = U.de0()
        w, sc, _ = export_de(de, U.wii01(), True)
        m = U.Wii(w)
        for gid in U.valid_gids("collectable")[:3]:
            m.pickup("collectable", gid, 1)
        w2 = m.done()
        ok, reasons, changed = scmod.descent(w, w2, T, "wii")
        self.assertTrue(ok, reasons)
        out, log = reimport.wii_to_de_reimport(w2, sc, T, current_de=de)
        cn, co = canon.from_de(out, T), canon.from_de(de, T)
        self.assertEqual(hard(canon.from_wii(w2, T)["shared"], cn["shared"]), [])
        ser_new, ser_old = cn["de_only"]["item_serials"], co["de_only"]["item_serials"]
        for box in ser_old:      # items present before keep their DE acquisition serial
            for sl, s in ser_old[box].items():
                if sl in ser_new[box] and co["shared"]["inventory"][box][sl]["gid"] == \
                        cn["shared"]["inventory"][box][sl]["gid"]:
                    self.assertEqual(ser_new[box][sl], s, (box, sl))
        newest = sorted(ser_new["collectable"].items(), key=lambda x: x[1])[-3:]
        self.assertTrue(all(s > max(ser_old["collectable"].values()) for _, s in newest))


class Alternation(unittest.TestCase):
    def test_four_generations_alternating_with_progress(self):
        """A1/E1: Wii -> DE -> (DE play) -> Wii -> (Wii play) -> DE ... 4 generations; lineage, money, items, levels."""
        w = U.wii01()
        de = convert.build(w, U.tpl(), T)[0]
        sc_w2d = scmod.load(scmod.dumps(scmod.make("wii_to_de", w, de, canon.from_wii(w, T), canon.from_de(de, T))))
        pid = sc_w2d["lineage"]["playthrough_id"]
        gen = 1
        for g in range(4):
            de_p = U.apply(de, U.random_mutations(U.rng(300 + g), 6, "de"), "de")
            ok, reasons, changed = scmod.descent(scmod.output_image(sc_w2d), de_p, T, "de")
            self.assertTrue(ok, reasons)
            wb, log, dfr = de_to_wii.build(de_p, scmod.source_image(sc_w2d), T, lineage=True)
            self.assertEqual(de_to_wii.verify(wb, de_p, T, dfr, log["remap"]), [], g)
            sc_d2w = scmod.load(scmod.dumps(scmod.make("de_to_wii", de_p, wb, canon.from_de(de_p, T),
                                                       canon.from_wii(wb, T), deferred=dfr, parent=sc_w2d)))
            gen += 1
            self.assertEqual((sc_d2w["lineage"]["playthrough_id"], sc_d2w["lineage"]["generation"]), (pid, gen))
            w_p = U.apply(wb, U.random_mutations(U.rng(400 + g), 6, "wii"), "wii")
            de_n, rlog = reimport.wii_to_de_reimport(w_p, sc_d2w, T, current_de=de_p)
            cw, cd = canon.from_wii(w_p, T)["shared"], canon.from_de(de_n, T)["shared"]
            self.assertEqual(hard(cw, cd), [], g)
            self.assertEqual(cd["money"], cw["money"])
            sc_w2d = scmod.load(scmod.dumps(scmod.make("wii_to_de", w_p, de_n, canon.from_wii(w_p, T),
                                                       canon.from_de(de_n, T), parent=sc_d2w)))
            gen += 1
            self.assertEqual(sc_w2d["lineage"]["generation"], gen)
            de = de_n


class Locality(unittest.TestCase):
    """A2 metamorphic: one change on one side changes exactly the corresponding canonical fields on the other."""

    def paths(self, a, b):
        return {d[0].split("[")[0] for d in canon.compare(a, b)}

    def test_single_changes_wii_to_de(self):
        w0 = U.wii01()
        base = canon.from_de(convert.build(w0, U.tpl(), T)[0], T)["shared"]
        sl_free = U.Wii(w0).slot_free("collectable")
        cases = {
            "money": [["money", 1234]],
            "quest": [["quest", 221, 0, 2, 1, 0.9]],
            "flag": [["flag", 0xA20 + 100, 1]],
            "pickup": [["pickup", "collectable", U.valid_gids("collectable")[5], 2]],
        }
        for name, muts in cases.items():
            w1 = U.apply(w0, muts, "wii")
            want = self.paths(canon.from_wii(w0, T)["shared"], canon.from_wii(w1, T)["shared"])
            got = self.paths(base, canon.from_de(convert.build(w1, U.tpl(), T)[0], T)["shared"])
            self.assertEqual(got - {p for p in got if p.startswith("/achievements")},
                             want - {p for p in want if p.startswith("/achievements")}, name)
            if name == "pickup":   # the new item is the newest; every other item keeps its relative order
                c = canon.from_de(convert.build(w1, U.tpl(), T)[0], T)["shared"]["inventory"]["collectable"]
                self.assertEqual(c[sl_free]["order"], len(c))

    def test_single_changes_de_to_wii(self):
        de0 = U.de0()
        base = canon.from_wii(de_to_wii.build(de0, U.wii01(), T, lineage=True)[0], T)["shared"]
        for name, muts in {"money": [["money", -77]], "level": [["level", 4, 1]],
                           "pickup": [["pickup", "material", U.valid_gids("material")[3], 3]],
                           "clock": [["clock", 23, 59, 31]]}.items():
            d1 = U.apply(de0, muts, "de")
            want = self.paths(canon.from_de(de0, T)["shared"], canon.from_de(d1, T)["shared"])
            got = self.paths(base, canon.from_wii(de_to_wii.build(d1, U.wii01(), T, lineage=True)[0], T)["shared"])
            self.assertEqual({p for p in got if not p.startswith("/achievements")},
                             {p for p in want if not p.startswith("/achievements")}, name)

    def test_invalid_reference_rejected_before_any_output(self):
        """A2: a DE equipment reference to an empty slot is refused (no Wii image is produced)."""
        b = bytearray(U.de0())
        struct.pack_into("<HH", b, U.DE_CHAR + 0x14 + 4 * 5, 499, 2)   # Shulk's weapon -> empty weapon slot 499
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)


if __name__ == "__main__":
    unittest.main()
