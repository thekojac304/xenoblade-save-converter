"""Phase 2F workstreams C + D: characters, EXP boundaries, Expert Mode with GAME-GENERATED saves, arts / skills / links,
story checkpoint matrix, quest state machine (incl. regressions for quests 90, 221, 287) and world state.

Real fixtures: phase2f/fixtures/real/s*_v10_monado.sav - public DE saves (story 20 ... 269; Expert Mode on with real
reserve EXP from 206) re-saved by the game in isolated Monado runs (see PROVENANCE.md); the user's monado01/monado03.
Changes applied to them are SYNTHETIC unless stated.
"""
import glob
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2f_util as U  # noqa: E402
import canon  # noqa: E402
import convert  # noqa: E402
import de_to_wii  # noqa: E402
import flagmap as fm  # noqa: E402
import quest_counters as qc  # noqa: E402
import reimport  # noqa: E402
import sidecar as scmod  # noqa: E402
import wii_save  # noqa: E402

T = None
REAL = sorted(glob.glob(os.path.join(U.ROOT, "phase2f", "fixtures", "real", "s*_v10_monado.sav")))
TOL = ("/achievements", "/quest_counters", "/clock", "/characters/1/palette2")
RESULTS = os.path.join(U.ROOT, "phase2f", "results", "d1_checkpoint_matrix.json")


def setUpModule():
    global T
    T = U.tables()


def export(de, base=None, lineage=False):
    w, log, dfr = de_to_wii.build(de, base or U.wii01(), T, lineage=lineage, overflow="sidecar")
    assert de_to_wii.verify(w, de, T, dfr, log["remap"]) == []
    sc = scmod.load(scmod.dumps(scmod.make("de_to_wii", de, w, canon.from_de(de, T), canon.from_wii(w, T),
                                           deferred=dfr)))
    return w, sc, dfr, log


def hard(a, b, drop=()):
    for box, sl in drop:
        b["inventory"][box].pop(sl, None)
    for box in b["inventory"]:
        b["inventory"][box] = canon.rerank(b["inventory"][box])
    return [d for d in canon.compare(a, b) if not d[0].startswith(TOL)]


@unittest.skipUnless(REAL, "game-generated v10 fixtures not present")
class CheckpointMatrix(unittest.TestCase):
    """D1 + C3: every game-generated checkpoint through DE -> Wii -> (Wii play) -> DE."""

    def test_matrix(self):
        rows = []
        for p in REAL:
            name = os.path.basename(p)[:4]
            de = U.rd(p)
            cd = canon.from_de(de, T)
            problems, _ = de_to_wii.compatibility(cd, de, T)
            self.assertEqual(problems, [], name)
            w, sc, dfr, log = export(de)
            self.assertEqual(wii_save.check_container(w), [], name)
            back, rl = reimport.wii_to_de_reimport(w, sc, T, current_de=de)
            self.assertEqual(back, de, name)                                       # no play: exact
            m = U.Wii(w)                                                          # Wii session: EXP, money, item
            party = cd["shared"]["party"]
            m.level_up(party[0], 1)
            m.money(500)
            m.play(900)
            if m.slot_free("collectable") is not None:
                m.pickup("collectable", U.valid_gids("collectable")[4], 1)
            w2 = m.done()
            out, rl = reimport.wii_to_de_reimport(w2, sc, T, current_de=de)
            drop = [(x[1], x[3]) for x in rl.get("deferred_restored", [])]
            co = canon.from_de(out, T)
            self.assertEqual(hard(canon.from_wii(w2, T)["shared"], co["shared"], drop), [], name)
            a, b = cd["de_only"], co["de_only"]
            for k in range(1, 8):
                x, y = a["characters"][k], b["characters"][k]
                self.assertEqual((x["reserve_exp"], x["cosmetic"]), (y["reserve_exp"], y["cosmetic"]), (name, k))
                if k != party[0]:
                    self.assertEqual((x["highest_level"], x["highest_level_exp"]),
                                     (y["highest_level"], y["highest_level_exp"]), (name, k))
            lead = party[0]
            self.assertEqual(b["characters"][lead]["highest_level"],
                             max(a["characters"][lead]["highest_level"], co["shared"]["characters"][lead]["level"]))
            for k in ("flags", "quest_counters_fc", "header"):
                if k == "header":
                    self.assertEqual(a[k][:8] + a[k][16:], b[k][:8] + b[k][16:], name)   # play time words differ
                else:
                    self.assertEqual(a[k], b[k], (name, k))
            self.assertEqual(out[0x151FF8:0x151FF8 + 0x320], de[0x151FF8:0x151FF8 + 0x320], name)  # Time Attack
            self.assertEqual(out[0x1490D5] & 1, de[0x1490D5] & 1)
            rows.append({"fixture": name, "story": cd["shared"]["story"], "party": party,
                         "expert": de[0x1490D5] & 1, "deferred_overflow": {k: len(v) for k, v in
                                                                           dfr.get("overflow_items", {}).items()},
                         "compacted_boxes": sorted(log["compacted"]), "exact_no_play": True,
                         "progress_reimport_canonical_equal": True})
        os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
        with open(RESULTS, "w") as f:
            json.dump(rows, f, indent=1)

    def test_expert_level_down_state(self):
        """C3 SYNTHETIC-on-real: a party member levelled down 2 levels in Expert Mode (level < highest, EXP moved to
        the reserve pool) - Wii EXP raises the active level, highest and reserve are not touched; repeated exports
        without play change nothing."""
        de = bytearray(U.rd(next(p for p in REAL if "s232" in p)))
        k = 2
        o = U.DE_CHAR + 0x138 * (k - 1)
        lv = struct.unpack_from("<I", de, o)[0]
        cost = sum(T["w_grow"][x]["level_exp"] for x in (lv - 1, lv))
        struct.pack_into("<II", de, o, lv - 2, 0)
        for kk in range(1, 8):            # the reserve is one party-wide pool, stored in every record
            ok = U.DE_CHAR + 0x138 * (kk - 1)
            struct.pack_into("<I", de, ok + 0xF4, struct.unpack_from("<I", de, ok + 0xF4)[0] + cost)
        de = bytes(de)
        w, sc, dfr, log = export(de)
        for _ in range(3):                # repeated exports without EXP: identical
            w_again, sc_again, _, _ = export(de)
            self.assertEqual(w_again, w)
        m = U.Wii(w)
        m.level_up(k, 1)
        out, rl = reimport.wii_to_de_reimport(m.done(), sc, T, current_de=de)
        self.assertEqual(struct.unpack_from("<I", out, o)[0], lv - 1)
        self.assertEqual(struct.unpack_from("<III", out, o + 0xEC), struct.unpack_from("<III", de, o + 0xEC))


class CharacterBoundaries(unittest.TestCase):
    def test_level_exp_ap_coin_boundaries_round_trip(self):
        """C2: level 1/2/50/99, EXP 0 and next-cost-1, AP 0 and 99,999,999, coins 0 and 999 survive DE -> Wii -> DE."""
        cases = [(1, 0), (2, 1), (50, T["w_grow"][51]["level_exp"] - 1), (99, 0)]
        for lv, exp in cases:
            for ap, coins in ((0, 0), (99_999_999, 999)):
                b = bytearray(U.de0())
                o = U.DE_CHAR + 0x138 * 3
                struct.pack_into("<IIII", b, o, lv, exp, ap, coins)
                struct.pack_into("<II", b, o + 0xEC, lv, exp)
                w, sc, dfr, log = export(bytes(b), lineage=True)
                c4 = canon.from_wii(w, T)["shared"]["characters"][4]
                self.assertEqual((c4["level"], c4["exp"], c4["ap"], c4["affinity_coins"]), (lv, exp, ap, coins))
                back = convert.build(w, bytes(b), T, lineage_template=True)[0]
                self.assertEqual(canon.from_de(back, T)["shared"]["characters"][4],
                                 canon.from_de(bytes(b), T)["shared"]["characters"][4])

    def test_exp_at_threshold_refused_both_ways(self):
        b = bytearray(U.de0())
        o = U.DE_CHAR + 0x138 * 3
        lv = struct.unpack_from("<I", b, o)[0]
        struct.pack_into("<I", b, o + 4, T["w_grow"][lv + 1]["level_exp"])
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T)
        m = U.Wii(U.wii01())
        m.char(4, 0x2A4, "I", T["w_grow"][lv + 1]["level_exp"])
        with self.assertRaises(convert.ConvertError):
            convert.build(m.done(), U.tpl(), T)

    def test_unsupported_party_members_refused_both_ways(self):
        """C1: Fiora's second form (8) and the guests (9-13) are refused, never half-converted."""
        for pid in (8, 9, 13):
            b = bytearray(U.de0())
            n = struct.unpack_from("<I", b, 0x1526D8 + 0x18)[0]
            struct.pack_into("<H", b, 0x1526D8 + 2 * n, pid)
            struct.pack_into("<I", b, 0x1526D8 + 0x18, n + 1)
            with self.assertRaises(de_to_wii.IncompatibleError, msg=pid):
                de_to_wii.build(bytes(b), U.wii01(), T)
            m = U.Wii(U.wii01())
            ir = wii_save.decode_bytes(m.b)
            m.img.put(wii_save.PARTY + 4 * len(ir["party"]), "H", pid)
            with self.assertRaises(convert.ConvertError, msg=pid):
                convert.build(m.done(), U.tpl(), T)

    @unittest.skipUnless(REAL, "game-generated v10 fixtures not present")
    def test_temporarily_unavailable_and_rejoin(self):
        """C1 on real data: s269 (game-generated) has Shulk alone in the party. Absent members keep their progression
        both ways; their DE equipment stays empty; on the Wii, references into the regular inventory are cleared."""
        de = U.rd(next(p for p in REAL if "s269" in p))
        cd = canon.from_de(de, T)["shared"]
        self.assertEqual(cd["party"], [1])
        w, sc, dfr, log = export(de)
        cw = canon.from_wii(w, T)["shared"]
        for k in range(2, 8):
            for f in ("level", "exp", "ap", "affinity_coins", "skill_learned", "arts", "links", "link_unlock"):
                self.assertEqual(cw["characters"][k][f], cd["characters"][k][f], (k, f))
            for e in wii_save.decode_bytes(w)["characters"][k]["equipment"].values():
                self.assertIsNone(e["box_index"], k)
        # Phase 3E: the members' gear is stored on the Wii now (staging, references keep the gear id). The 2F
        # SYNTHETIC rejoin (party list edited, Reyn back) is not a state the game can reach any more - its join routine
        # rebuilds the items - so the Wii session here is SYNTHETIC money; real rejoins are game-written tests in
        # phase3e/tests (TestGameWrittenReunions).
        m = U.Wii(w)
        m.money(500)
        out, rl = reimport.wii_to_de_reimport(m.done(), sc, T, current_de=de)
        co = canon.from_de(out, T)["shared"]
        self.assertEqual(co["party"], [1])
        self.assertEqual(co["characters"][2]["level"], cd["characters"][2]["level"])
        self.assertEqual(co["stored_gear"], cd["stored_gear"])                   # stored gear back unchanged


class ArtsSkillsLinks(unittest.TestCase):
    def test_random_valid_progression_states(self):
        """C4 (seeded): art levels / manual flags, skill-tree progress, selected tree, SP, linked skills and unlocked
        link slots (affinity coins) round trip DE -> Wii -> DE; talent pairs that share a Wii slot stay equal."""
        for seed in range(8):
            r = U.rng(500 + seed)
            b = bytearray(U.de0())
            for k in range(1, 8):
                o = U.DE_CHAR + 0x138 * (k - 1)
                learned = [max(x, r.randint(0, 5)) for x in struct.unpack_from("<5I", b, o + 0x90)]
                struct.pack_into("<I5I5I", b, o + 0x78, r.randint(0, 4), *[r.randint(0, 999) for _ in range(5)], *learned)
                others = [x for x in range(1, 8) if x != k]
                unl = list(struct.unpack_from("<8I", b, o + 0xA4))
                for src in others:
                    u = r.randint(0, 4)
                    unl[src - 1] = u
                    n_link = r.randint(0, u + 1)
                    ids = [(src - 1) * 25 + r.randint(1, 25) if e < n_link else 0 for e in range(5)]
                    b[o + 0xC4 + 5 * (src - 1):o + 0xC4 + 5 * src] = bytes(ids)
                struct.pack_into("<8I", b, o + 0xA4, *unl)
                byidx = {}
                for a in T["w_arts"].values():
                    if a["pc"] == k:
                        byidx.setdefault(a["idx"], []).append(a["id"])
                for idx, ids in byidx.items():
                    lv, fl = r.randint(0, 10), r.choice([0, 1, 2, 3])
                    for aid in ids:
                        b[0x153AA8 + 2 * (aid - 1):0x153AA8 + 2 * aid] = bytes([lv, fl])
            de = bytes(b)
            w, sc, dfr, log = export(de, lineage=True)
            self.assertEqual([d for d in canon.compare(canon.from_wii(w, T)["shared"]["characters"],
                                                       canon.from_de(de, T)["shared"]["characters"])], [], seed)
            back = convert.build(w, de, T, lineage_template=True)[0]
            self.assertEqual(canon.from_de(back, T)["shared"]["characters"], canon.from_de(de, T)["shared"]["characters"])

    def test_unlocked_empty_link_slots_reach_the_wii(self):
        """Phase 2F defect regression: slots unlocked in DE (affinity coins) but not yet linked were not unlocked on
        the Wii (2E wrote the Wii state byte only for linked slots)."""
        b = bytearray(U.de0())
        o = U.DE_CHAR
        unl = list(struct.unpack_from("<8I", b, o + 0xA4))
        unl[1] = 4                                                   # Shulk <- Reyn: 5 slots unlocked, none linked
        struct.pack_into("<8I", b, o + 0xA4, *unl)
        b[o + 0xC4 + 5:o + 0xC4 + 10] = bytes(5)
        w = export(bytes(b), lineage=True)[0]
        row = wii_save.decode_bytes(w)["characters"][1]["skill_rows"][5]          # first link row = source 2
        self.assertEqual([n[1] for n in row["nodes"]], [1, 1, 1, 1, 1])
        unl[1] = 0
        struct.pack_into("<8I", b, o + 0xA4, *unl)
        w = export(bytes(b), lineage=True)[0]
        self.assertEqual([n[1] for n in wii_save.decode_bytes(w)["characters"][1]["skill_rows"][5]["nodes"]],
                         [1, 0, 0, 0, 0])

    def test_first_export_does_not_inherit_template_link_unlocks(self):
        tpl = bytearray(U.tpl())
        struct.pack_into("<8I", tpl, U.DE_CHAR + 0xA4, *([4] * 8))
        out = convert.build(U.wii01(), bytes(tpl), T)[0]
        self.assertEqual(canon.from_de(out, T)["shared"]["characters"][1]["link_unlock"],
                         canon.from_wii(U.wii01(), T)["shared"]["characters"][1]["link_unlock"])


class Quests(unittest.TestCase):
    def test_counter_encodings_round_trip_every_quest(self):
        """D2 exhaustive: for every Wii quest and objective, every valid DE value (0..num-1 / 0xFF for kills, 0/0xFF
        otherwise) survives DE -> Wii -> DE, and every Wii value survives Wii -> DE -> Wii up to the game's own
        'done' test (counter >= num is done)."""
        n_checked = 0
        for q, r in sorted(qc.quests().items()):
            if q >= qc.WII_N:
                continue
            for s, t, cnd, n in qc.slots(r):
                if not t:
                    continue
                de_vals = list(range(n)) + [0xFF] if t == 1 else [0, 0xFF]
                for v in de_vals:
                    d = bytearray(U.de0())
                    d[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8] = bytes(8)
                    d[qc.DE_QC + 8 * q + s] = v
                    wv = qc.de_to_wii(bytes(d), q)
                    w = bytearray(U.wii01())
                    w[qc.WII_QC + 8 * q:qc.WII_QC + 8 * q + 8] = wv
                    st = fm.wii_get(bytes(w), 0x220 + q)
                    if st in (254, 255):
                        continue
                    if t == 4:      # sub-quest objectives also count as done when the sub-quest is closed
                        continue
                    self.assertEqual(qc.wii_to_de(bytes(w), q)[s], v, (q, s, t, n, v))
                    n_checked += 1
        self.assertGreater(n_checked, 1000)

    def test_regression_quests_90_221_287(self):
        """Phase 2D/2E defects: quest 90 ('2+4+3' is the requirement, progress 0/0/0), quests 221 and 287 (objectives
        done, items consumed) must keep their state and counters in both directions."""
        w = U.wii01()
        de = U.de0()
        for q in (90, 221, 287):
            self.assertEqual(fm.de_get(de, 0x220 + q), fm.wii_get(w, 0x220 + q), q)
            self.assertEqual(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8], qc.wii_to_de(w, q), q)
            back = de_to_wii.build(de, w, T, lineage=True)[0]
            self.assertEqual(back[qc.WII_QC + 8 * q:qc.WII_QC + 8 * q + 8], w[qc.WII_QC + 8 * q:qc.WII_QC + 8 * q + 8])
        self.assertEqual(list(de[qc.DE_QC + 8 * 90:qc.DE_QC + 8 * 90 + 3]), [0, 0, 0])
        # accepted (state 1) with objectives partly done: Wii [1,1,0] / [0,1,0,0] -> DE 0xFF on exactly those
        self.assertEqual((fm.wii_get(w, 0x220 + 221), fm.wii_get(w, 0x220 + 287)), (1, 1))
        self.assertEqual(list(de[qc.DE_QC + 8 * 221:qc.DE_QC + 8 * 221 + 8]), [255, 255, 0, 0, 0, 0, 0, 0])
        self.assertEqual(list(de[qc.DE_QC + 8 * 287:qc.DE_QC + 8 * 287 + 8]), [0, 255, 0, 0, 0, 0, 0, 0])
        # partial kill progress on quest 90 (SYNTHETIC): 1 of 2, 3 of 4 - survives both ways
        m = U.Wii(w)
        m.quest_byte(90, 0, 1)
        m.quest_byte(90, 1, 3)
        w2 = m.done()
        d2 = convert.build(w2, U.tpl(), T)[0]
        self.assertEqual(list(d2[qc.DE_QC + 8 * 90:qc.DE_QC + 8 * 90 + 3]), [1, 3, 0])
        self.assertEqual(de_to_wii.build(d2, w2, T, lineage=True)[0], w2)

    def test_quest_states_completed_stay_completed(self):
        """Quest state flags (0x220 + q, 8-bit) move verbatim; a completed quest (254/255) is not reopened and its
        winning branch is filled the way DE fills it; an accepted quest's objectives are not marked done."""
        w = U.wii01()
        de = U.de0()
        for q in sorted(qc.quests()):
            if q >= qc.WII_N:
                continue
            sw, sd = fm.wii_get(w, 0x220 + q), fm.de_get(de, 0x220 + q)
            self.assertEqual(sw, sd, q)
            if sw in (254, 255):
                b = 0 if sw == 254 else 4
                self.assertTrue(any(x == 0xFF for x in de[qc.DE_QC + 8 * q + b:qc.DE_QC + 8 * q + b + 4]) or
                                not any(t for s, t, c, n in qc.slots(qc.quests()[q]) if b <= s < b + 4), q)
        m = U.Wii(w)
        q = next(q for q in sorted(qc.quests()) if q < qc.WII_N and fm.wii_get(w, 0x220 + q) == 0 and
                 any(t == 1 for s, t, c, n in qc.slots(qc.quests()[q])))
        m.flag(0x220 + q, 1)                                       # SYNTHETIC: accept quest q
        d2 = convert.build(m.done(), U.tpl(), T)[0]
        self.assertEqual(fm.de_get(d2, 0x220 + q), 1)
        self.assertNotIn(0xFF, d2[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8])


class WorldState(unittest.TestCase):
    def test_clock_and_day_boundaries(self):
        for h, mi, day in ((0, 0, 1), (23, 59, 1), (12, 30, 65535), (6, 0, 400)):
            d = U.DE(U.de0())
            d.clock(h, mi, day)
            w = de_to_wii.build(d.done(), U.wii01(), T, lineage=True)[0]
            self.assertEqual(canon.from_wii(w, T)["shared"]["clock"], {"hour": h, "minute": mi, "day": day})
            back = convert.build(w, d.done(), T, lineage_template=True)[0]
            self.assertEqual(canon.from_de(back, T)["shared"]["clock"], {"hour": h, "minute": mi, "day": day})

    def test_every_wii_map_round_trips(self):
        maps = sorted(de_to_wii.wii_maps())
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
                de_to_wii.build(bytes(b), w0, T, lineage=True)

    def test_world_flags_survive_two_cycles(self):
        """Landmarks / fast-travel (1-bit 0xA20+k), Collectopaedia, Colony 6 / affinity (8-bit range) changed on one
        platform survive two further conversion cycles."""
        d = U.DE(U.de0())
        for g in (0xA20 + 5, 0xA20 + 150, 0x220 + 0x2F0, 0x1D44 + 3):
            d.flag(g, 1)
        de = d.done()
        c0 = canon.from_de(de, T)["shared"]
        w, sc, dfr, log = export(de, lineage=True)
        for _ in range(2):
            de2, rl = reimport.wii_to_de_reimport(U.Wii(w).done(), sc, T, current_de=de)
            self.assertEqual(de2, de)
            w, sc, dfr, log = export(de2, lineage=True)
        self.assertEqual(canon.from_wii(w, T)["shared"]["flags"], c0["flags"])
        self.assertEqual(canon.from_wii(w, T)["shared"]["collectopaedia"], c0["collectopaedia"])


if __name__ == "__main__":
    unittest.main()
