"""Phase 3D: Fiora's later form (character 8), the era rule, guests, defect D1 and the post-rejoin saves in every
direction. Fixtures (phase3d/fixtures, see PROVENANCE.md): genuine DE saves of one public playthrough (story 269 before
the rejoin; 276, 283, 291 with character 8; 288 = temporary split without Fiora) re-saved by Monado (v10), and the Wii
and 3DS games' own re-saves of the converted saves (Dolphin / Azahar runs). No synthetic party edits except where a
test says so (adversarial inputs)."""
import os
import shutil
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
P3D = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3D)
sys.path.insert(0, os.path.join(ROOT, "phase3c", "tests"))
import p3cfix as F  # noqa: E402,F401  (paths)
from p3cfix import H, T, rd  # noqa: E402

import canon  # noqa: E402
import flagmap as fm  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402
from de_to_wii import CHAR_BASE, CHAR_SIZE  # noqa: E402

FX = os.path.join(P3D, "fixtures")
WORK = os.path.join(P3D, "work", "tests")
POST = (276, 283, 288, 291)
CONVERTIBLE = (276, 283, 291)   # Phase 3E: stored equipment translated (3D: only 291); 288 (Fiora away) refused
TRANSLATED = (269, 276, 283)


def fx(n):
    return os.path.join(FX, n)


def de(s):
    return fx(f"de_s{s}_v10_monado.sav")


def fresh(name):
    d = os.path.join(WORK, name)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def wii_of(p):
    b = rd(p)
    return xc3d.transcode(xc3d.unpack(b), "wii") if b[:4] == b"!qzb" else b


def shared(p):
    b = rd(p)
    if b[:4] == b"!qzb" or len(b) == 163840:
        return canon.from_wii(wii_of(p), T)["shared"]
    return canon.from_de(b, T)["shared"]


def diff_keys(a, b):
    return {d[0] for d in canon.compare(a, b)}


def core_diffs(a, b):
    """Differences outside the documented lossy parts of a first-time (no sidecar/record) DE hop: award counters
    (limitation 8), inventory slots/overflow (limitations 6 and 2) and the equipment slot references that follow
    compaction (checked by content with equipment_same)."""
    import re
    return {k for k in diff_keys(a, b) if not re.match(r"/(achievements|inventory)/|/characters/\d+/equipment/", k)}


def equipment_same(a, b):
    """Every character wears an item with the same content (slot may differ: compaction)."""
    for k, c in a["characters"].items():
        for sl, i in (c.get("equipment") or {}).items():
            j = (b["characters"][k].get("equipment") or {}).get(sl)
            ra = a["inventory"][sl].get(i) if i is not None else None
            rb = b["inventory"][sl].get(j) if j is not None else None
            if (ra is None) != (rb is None) or (ra is not None and canon.strip_order(ra) != canon.strip_order(rb)):
                return False
    return True


def to_wii(de_path, d, base=H.W150, **kw):
    return xs.de_to_wii_convert(xs.DeToWiiRequest(de=de_path, out=os.path.join(d, "w"), base=base,
                                                  overflow="sidecar", **kw))


def rec(img, k):
    o = CHAR_BASE + CHAR_SIZE * k
    return img[o:o + CHAR_SIZE]


class TestEraRule(unittest.TestCase):
    def test_boundary_from_the_party_journal(self):
        self.assertEqual([canon.fiora(s) for s in (11, 269, 274, 275, 276, 400)], [3, 3, 3, 8, 8, 8])
        self.assertEqual(canon.main_chars(274), (1, 2, 3, 4, 5, 6, 7))
        self.assertEqual(canon.main_chars(275), (1, 2, 8, 4, 5, 6, 7))

    def test_party_checks(self):
        u = canon.unsupported_party
        self.assertEqual(u({"story": 276, "party": [8, 1]}), [])
        self.assertEqual(u({"story": 269, "party": [8, 1]}), [8])     # character 8 before the rejoin
        self.assertEqual(u({"story": 276, "party": [3, 1]}), [3])     # never substitute 3 for 8 (or back)
        for g in range(9, 14):                                       # guests are never converted
            self.assertEqual(u({"story": 276, "party": [1, g]}), [g])
            self.assertEqual(u({"story": 100, "party": [1, g]}), [g])

    def test_genuine_saves_follow_the_rule(self):
        self.assertEqual(shared(de(269))["party"], [1])
        self.assertEqual([shared(de(s))["party"] for s in POST], [[8, 1], [8, 2, 1, 5], [4, 6, 7], [8, 6, 5, 7, 2, 1, 4]])


class TestPostRejoinConversions(unittest.TestCase):
    def test_de_to_wii_and_back_unchanged_is_byte_identical(self):
        for s in CONVERTIBLE:
            with self.subTest(story=s):
                d = fresh(f"rt_{s}")
                r = to_wii(de(s), d)
                back = xs.wii_to_de(xs.WiiToDeRequest(wii=r.main_output, out=os.path.join(d, "b"),
                                                      sidecar=r.sidecar_path, current_de=de(s)))
                self.assertEqual(rd(back.main_output), rd(de(s)))

    def test_de_to_3ds_and_back_unchanged_is_byte_identical(self):
        for s in CONVERTIBLE:
            with self.subTest(story=s):
                d = fresh(f"rt3_{s}")
                r = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=de(s), out=os.path.join(d, "x"),
                                                  template=H.X3_USER, overflow="sidecar"))
                b = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=r.main_output, out=os.path.join(d, "b"),
                                                  record=r.sidecar_path, current=de(s)))
                self.assertEqual(rd(b.main_output), rd(de(s)))

    def test_wii_records_after_the_rejoin(self):
        """Record 8 = the DE's record 8 (level, AP, coins, gear, own skill ids 176+); record 3 receives record 8's skill
        object (the Wii mirror); character 8's six link rows exclude character 3."""
        d = fresh("recs")
        w = rd(to_wii(de(291), d).main_output)
        c = canon.from_de(rd(de(291)), T)["shared"]["characters"]
        self.assertEqual(struct.unpack_from(">I", w, CHAR_BASE + CHAR_SIZE * 8 + 0x17C)[0], c[8]["level"])
        o3, o8 = CHAR_BASE + CHAR_SIZE * 3, CHAR_BASE + CHAR_SIZE * 8
        self.assertEqual(w[o3 + 0x1F4:o3 + 0x2A0], w[o8 + 0x1F4:o8 + 0x2A0])
        ids = [w[o8 + 0x1F4 + 13 * t + 2 + 2 * e] for t in range(5) for e in range(5)]
        self.assertTrue(ids and all(v == 0 or 175 < v <= 200 for v in ids), ids)
        back = canon.from_wii(w, T)["shared"]["characters"][8]
        for f in ("level", "exp", "ap", "affinity_coins", "skill_sp", "skill_learned", "skill_selected_tree", "arts"):
            self.assertEqual(back[f], c[8][f], f)

    def test_d2_members_away_with_stored_gear(self):
        """D2 (3D: refused). Phase 3E: the stored equipment is translated - DE -> Wii and DE -> 3DS carry it exactly
        (269/276/283); Fiora's later form away (288) is still refused with her name, nothing written."""
        for s in TRANSLATED:
            with self.subTest(story=s):
                d = fresh(f"d2_{s}")
                w = to_wii(de(s), d)
                self.assertEqual(canon.jsonable(shared(w.main_output)["stored_gear"]),
                                 canon.jsonable(shared(de(s))["stored_gear"]))
        d = fresh("d2_288")
        with self.assertRaises(xs.REFUSALS) as cm:
            to_wii(de(288), d)
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "w")))
        with self.assertRaises(xs.REFUSALS) as cm:
            s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=de(288), out=os.path.join(d, "x"),
                                          template=H.X3_USER, overflow="sidecar"))
        self.assertIn("Fiora is away from the party", str(cm.exception))

    def test_d2_rule_needs_real_gear_of_a_joined_member(self):
        """Not-yet-joined members (Dunban before 100: scripted prologue gear incl. the prologue Monado in his slot on
        the user's story-6/8/18 saves) and the post-reunion save are not affected."""
        import stored_gear as sg
        import wii_save
        for p in (H.W006, H.W018, H.X3_USER, H.W150):
            b = wii_of(p)
            ir = wii_save.decode_bytes(b)
            self.assertEqual(sg.departed(lambda k: sg.wii_stored(ir, k), fm.wii_get(b, 0x20), ir["party"], T), {}, p)
        b = rd(de(291))
        self.assertEqual(sg.departed(lambda k: sg.de_stored(b, k), 291, shared(de(291))["party"], T), {})

    def test_multi_hop_paths(self):
        """Wii -> DE -> 3DS -> Wii, DE -> Wii -> 3DS -> DE and 3DS -> DE -> Wii -> 3DS on the story-291 playthrough:
        the shared state survives every hop (no gameplay between hops here; game-written hops: GameWritten)."""
        d = fresh("hops")
        src = shared(de(291))
        # DE -> Wii -> 3DS -> DE
        w = to_wii(de(291), d)
        x = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=w.main_output, out=os.path.join(d, "x"),
                                          template=H.X3_USER))
        b = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=x.main_output, out=os.path.join(d, "b"),
                                          template=H.DE_TPL))
        self.assertEqual(core_diffs(src, shared(b.main_output)), set())
        self.assertTrue(equipment_same(src, shared(b.main_output)))
        # Wii -> DE -> 3DS -> Wii (starting from the Wii export)
        e = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "e"), template=H.DE_TPL))
        x2 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=e.main_output, out=os.path.join(d, "x2"),
                                           template=H.X3_USER, overflow="sidecar"))
        w2 = s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=x2.main_output, out=os.path.join(d, "w2")))
        self.assertEqual(core_diffs(shared(w.main_output), shared(w2.main_output)), set())
        self.assertTrue(equipment_same(shared(w.main_output), shared(w2.main_output)))
        # 3DS -> DE -> Wii -> 3DS
        e3 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=x.main_output, out=os.path.join(d, "e3"),
                                           template=H.DE_TPL))
        w3 = to_wii(e3.main_output, os.path.join(d, "w3"))
        x3 = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=w3.main_output, out=os.path.join(d, "x3"),
                                           template=H.X3_USER))
        self.assertEqual(core_diffs(shared(x.main_output), shared(x3.main_output)), set())
        self.assertTrue(equipment_same(shared(x.main_output), shared(x3.main_output)))


class TestAdversarial(unittest.TestCase):
    """Synthetic inputs (labelled): each must be refused with nothing written, never silently re-mapped."""

    @staticmethod
    def de_party(src, party):
        import de_save
        b = bytearray(rd(src))
        o = de_save.layout(bytes(b))["party"]
        for i in range(12):
            struct.pack_into("<H", b, o + 2 * i, party[i] if i < len(party) else 0)
        struct.pack_into("<I", b, o + 0x18, len(party))
        return bytes(b)

    @staticmethod
    def wii_party(img, party):
        import wii_save
        b = bytearray(img)
        for i in range(12):
            struct.pack_into(">H", b, wii_save.PARTY + 4 * i, party[i] if i < len(party) else 0)
        return xc3d.fix_wii_checksums(bytes(b))

    def refused(self, fn, out):
        with self.assertRaises(xs.REFUSALS):
            fn()
        self.assertFalse(os.path.exists(out) and os.listdir(out), "nothing may be written")

    def test_de_parties_outside_the_era_rule_are_refused(self):
        d = fresh("adv_de")
        cases = {"c8_before_rejoin": (269, [8, 1]), "c3_after_rejoin": (291, [3, 1]), "both": (291, [8, 3, 1]),
                 **{f"guest{g}": (291, [8, g]) for g in range(9, 14)}}
        for n, (s, party) in cases.items():
            with self.subTest(case=n):
                p = os.path.join(d, n + ".sav")
                open(p, "wb").write(self.de_party(de(s), party))
                self.assertEqual(canon.from_de(rd(p), T)["shared"]["party"], party)
                out = os.path.join(d, n)
                self.refused(lambda: to_wii(p, out), os.path.join(out, "w"))
                out3 = os.path.join(d, n + "_3ds")
                self.refused(lambda: s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=p, out=out3,
                                                                    template=H.X3_USER, overflow="sidecar")), out3)

    def test_wii_parties_outside_the_era_rule_are_refused(self):
        d = fresh("adv_wii")
        w291 = rd(to_wii(de(291), os.path.join(d, "src")).main_output)
        cases = {"c3_after_rejoin": (w291, [3, 1]), "c8_before_rejoin": (rd(H.W150), [8, 1]),
                 "guest_before": (rd(H.W150), [1, 9]), "guest_after": (w291, [8, 12])}
        for n, (img, party) in cases.items():
            with self.subTest(case=n):
                p = os.path.join(d, n)
                open(p, "wb").write(self.wii_party(img, party))
                out = os.path.join(d, n + "_de")
                self.refused(lambda: xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=out, template=H.DE_TPL)), out)
                # Wii -> 3DS is the same game (lossless transcode): the party is carried as it is, never re-mapped
                x = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=p, out=os.path.join(d, n + "_3ds"),
                                                  template=H.X3_USER))
                self.assertEqual(shared(x.main_output)["party"], party)

    def test_foreign_skill_ids_in_the_active_fiora_are_refused(self):
        """Record 8 after the rejoin holding Fiora-3 skill ids (51-75) is not guessed at: refused."""
        d = fresh("adv_ids")
        b = bytearray(rd(to_wii(de(291), os.path.join(d, "src")).main_output))
        for k in (3, 8):
            o = CHAR_BASE + CHAR_SIZE * k + 0x1F4 + 2
            b[o] = 51
        p = os.path.join(d, "w")
        open(p, "wb").write(xc3d.fix_wii_checksums(bytes(b)))
        out = os.path.join(d, "o")
        self.refused(lambda: xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=out, template=H.DE_TPL)), out)

    def test_character_8_before_the_era_is_refused(self):
        self.assertEqual(canon.unsupported_party({"story": 274, "party": [8]}), [8])

    def test_d1_shulk_arts_flag(self):
        """D1: a late DE save (game-written s232) exported onto the user's story-8 3DS save sets Shulk's Wii-only +0x118
        to 1 (the story-8 base has 0: with Shulk leading at Fallen Arm the 3DS game overflowed its stack and the Wii
        game hung - runs x_s269_rejoin / wd_s269_flag0, bisected); a story below 20 keeps the base's value."""
        d = fresh("d1")
        r = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "x"), template=H.X3_USER,
                                          overflow="sidecar"))
        self.assertEqual(wii_of(H.X3_USER)[CHAR_BASE + CHAR_SIZE + 0x118], 0)
        self.assertEqual(wii_of(r.main_output)[CHAR_BASE + CHAR_SIZE + 0x118], 1)
        import de_to_wii
        self.assertEqual(de_to_wii.SHULK_ARTS_FLAG_STORY, 20)


if __name__ == "__main__":
    unittest.main()
