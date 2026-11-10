"""Phase 3F: Fiora's later form (character 8) away at scenario 288 - decode, the code-backed guards, translation in
every direction, defect F1 (reunion room / skipped returns), game-written reunions (Monado native, Azahar from a
converted save), adversarial inputs and the Sync Hub. Fixtures: phase3f/fixtures (PROVENANCE.md)."""
import copy
import json
import os
import shutil
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
P3F = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3F)
sys.path.insert(0, os.path.join(ROOT, "phase3e", "tests"))
import test_phase3e_stored_gear as S  # noqa: E402
from test_phase3e_stored_gear import H, T, canon, rd, stored, wii_of, gear  # noqa: E402

import de_save  # noqa: E402
import de_to_wii as d2w  # noqa: E402
import flagmap as fm  # noqa: E402
import stored_gear as sg  # noqa: E402
import wii_save  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402
from xcsync import sync  # noqa: E402

FX = os.path.join(P3F, "fixtures")
F3D = os.path.join(ROOT, "phase3d", "fixtures")
WORK = os.path.join(P3F, "work", "tests")
DE283, DE288, DE291 = (os.path.join(F3D, f"de_s{s}_v10_monado.sav") for s in (283, 288, 291))
NATIVE291 = os.path.join(FX, "de_s291_monado_m1b_native_reunion.sav")
X3_EXPORT = os.path.join(FX, "x3_s288_export_3f")
X3_RECORD = X3_EXPORT + ".de_to_3ds.record.json"
X3_REUNION = os.path.join(FX, "x3_s291_azahar_x3_reunion_save")
X3_RELOAD = os.path.join(FX, "x3_s291_azahar_x4_reload_save")
X3_SKIPPED = os.path.join(FX, "x3_s291_azahar_x2_reunion_save")       # 3E-engine export, boxes full: F1
X3_EXPORT_3E = os.path.join(FX, "x3_s288_export_3e_engine")
M2 = os.path.join(FX, "de_s291_monado_m2_from_3ds_reunion.sav")
RETURNING = (1, 2, 5, 8)
GEAR = ("head", "body", "arm", "legs", "feet", "weapon")


def fresh(name):
    d = os.path.join(WORK, name)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def sh(p_or_b):
    b = rd(p_or_b) if isinstance(p_or_b, str) else p_or_b
    b = wii_of(b)
    return (canon.from_wii(b, T) if b[:4] == b"USRD" else canon.from_de(b, T))["shared"]


def stored_view(sh_, k):
    return S.stored_gear_view(sh_, k)


def contents(sh_):
    """Inventory content per box as a sorted list (no slot numbers or order)."""
    out = {}
    for box, recs in sh_["inventory"].items():
        rows = []
        for r in recs.values():
            r = dict(r)
            r.pop("order", None)
            if box in GEAR:
                r["sockets"] = [(["gem"] + sorted((k, v) for k, v in sh_["inventory"]["gem"][x[1]].items()
                                                  if k != "order")) if x and x[0] == "gem" else x
                                for x in r["sockets"]]
            rows.append(json.dumps(r, sort_keys=True, default=str))
        out[box] = sorted(rows)
    return out


def to_wii(p, d, base=None, **kw):
    return xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=os.path.join(d, "w"), base=base or H.W150,
                                                  overflow="sidecar", **kw))


def to_3ds(p, d, name="x"):
    return s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=p, out=os.path.join(d, name), template=H.X3_USER,
                                         overflow="sidecar"))


# =================================================================================================== A: state
class TestScenario288State(unittest.TestCase):
    def test_genuine_288_state(self):
        """288: party [4,6,7]; stored Shulk, Reyn, Sharla, Fiora-8 (her 667-671 armour with fixed gems, Mechonis
        Swords 65 with two socketed gems); 283 and 291 have nothing stored for 8; record 3 never stored."""
        s288 = sh(DE288)
        self.assertEqual(s288["party"], [4, 6, 7])
        self.assertEqual(sorted(s288["stored_gear"]), [1, 2, 5, 8])
        f = s288["stored_gear"][8]
        self.assertEqual([f["slots"][sl]["gid"] for sl in GEAR], [667, 668, 669, 670, 671, 65])
        self.assertEqual([(g["effect"], g["rank"], g["strength"]) for g in f["gems"]], [(1, 4, 35), (65, 4, 20)])
        self.assertEqual(f["slots"]["weapon"]["sockets"], [["gem", 0], ["gem", 1]])
        self.assertEqual([f["slots"][sl]["sockets"] for sl in ("head", "body", "arm", "legs", "feet")],
                         [[["fixed", 3221]], [["fixed", 3147]], [["fixed", 3113]], [["fixed", 3113]], []])
        self.assertNotIn(8, sh(DE283).get("stored_gear", {}))
        self.assertNotIn("stored_gear", sh(DE291))
        for p in (DE283, DE288, DE291):
            self.assertNotIn(3, sh(p).get("stored_gear", {}))

    def test_join_mask_records_fioras_first_join(self):
        """0x80082D28 gates the character-8 first-join initialisation of 0x8007FB98 by bit 8 of the join mask: set in
        every genuine save from 276, carried to the Wii flag 0x108 by the converter."""
        for s in (276, 283, 288, 291):
            self.assertTrue(sh(os.path.join(F3D, f"de_s{s}_v10_monado.sav"))["flag_bitmask_0"] >> 8 & 1, s)
        self.assertFalse(sh(os.path.join(F3D, "de_s269_v10_monado.sav"))["flag_bitmask_0"] >> 8 & 1)
        d = fresh("mask")
        w = rd(to_wii(DE288, d).main_output)
        self.assertEqual(fm.wii_get(w, 0x108), sh(DE288)["flag_bitmask_0"])
        x = wii_of(rd(to_3ds(DE288, d).main_output))
        self.assertEqual(fm.wii_get(x, 0x108), sh(DE288)["flag_bitmask_0"])

    def test_fiora_arts_skills_links_unchanged_by_the_native_reunion(self):
        """The DE's own reunion changes character 8 only by the event's AP/SP (same for all seven) and her gear."""
        a, b = sh(DE288)["characters"][8], sh(NATIVE291)["characters"][8]
        for k in set(a) | set(b):
            if k in ("ap", "skill_sp", "equipment"):
                continue
            self.assertEqual(a.get(k), b.get(k), k)
        self.assertEqual(b["ap"] - a["ap"], 108)
        self.assertEqual([y - x for x, y in zip(a["skill_sp"], b["skill_sp"])], [0, 38, 0, 0, 0])


# =================================================================================================== C: translation
class TestTranslation(unittest.TestCase):
    def test_de288_to_wii_and_back_unchanged_is_byte_identical(self):
        d = fresh("w_rt")
        w = to_wii(DE288, d)
        self.assertEqual(stored(w.main_output), stored(DE288))
        b = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "b"), sidecar=w.sidecar_path,
                                           current_de=DE288))
        self.assertEqual(rd(b.main_output), rd(DE288))

    def test_de288_to_3ds_and_back_unchanged_is_byte_identical(self):
        d = fresh("x_rt")
        x = to_3ds(DE288, d)
        self.assertEqual(stored(x.main_output), stored(DE288))
        b = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=x.main_output, out=os.path.join(d, "b"),
                                          record=x.record_path if hasattr(x, "record_path") else x.sidecar_path,
                                          current=DE288))
        self.assertEqual(rd(b.main_output), rd(DE288))

    def test_wii288_to_3ds_to_wii(self):
        d = fresh("w3w")
        w = to_wii(DE288, d)
        x = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=w.main_output, out=os.path.join(d, "x"),
                                          template=H.X3_USER))
        self.assertEqual(stored(x.main_output), stored(DE288))
        w2 = s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=x.main_output, out=os.path.join(d, "w2")))
        self.assertEqual(stored(w2.main_output), stored(DE288))
        a, b = sh(w.main_output), sh(w2.main_output)
        self.assertEqual(canon.jsonable(a), canon.jsonable(b))

    def test_wii288_to_de_to_3ds_to_wii(self):
        """First-time Wii -> DE (template), DE -> 3DS, 3DS -> Wii: stored gear, party and Fiora-8 identical."""
        d = fresh("wd3w")
        w = to_wii(DE288, d)
        e = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "e"), template=H.DE_TPL))
        self.assertEqual(stored(e.main_output), stored(DE288))
        x = to_3ds(e.main_output, d, "x")
        w2 = s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=x.main_output, out=os.path.join(d, "w2")))
        for p in (e.main_output, x.main_output, w2.main_output):
            s = sh(p)
            self.assertEqual(canon.jsonable(s["stored_gear"]), stored(DE288), p)
            self.assertEqual(s["party"], [4, 6, 7])
            c8, o8 = s["characters"][8], sh(DE288)["characters"][8]
            for k in ("level", "exp", "ap", "affinity_coins", "skill_sp", "arts", "palette"):
                self.assertEqual(c8.get(k), o8.get(k), (p, k))

    def test_fiora_link_slot_round_trips(self):
        """Other characters' Fiora-8 link slot (DE slot 8) and unlock levels survive DE -> Wii -> DE (first time)."""
        d = fresh("links")
        w = to_wii(DE288, d)
        e = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "e"), template=H.DE_TPL))
        a, b = sh(DE288)["characters"], sh(e.main_output)["characters"]
        for k in (1, 2, 4, 5, 6, 7):
            self.assertEqual(a[k].get("links"), b[k].get("links"), k)
            self.assertEqual(a[k].get("link_unlock"), b[k].get("link_unlock"), k)

    def test_repeated_generations_are_stable(self):
        d = fresh("gens")
        cur = DE288
        for i in range(3):
            w = to_wii(cur, os.path.join(d, f"g{i}"))
            x = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=w.main_output, out=os.path.join(d, f"x{i}"),
                                              template=H.X3_USER))
            e = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=x.main_output, out=os.path.join(d, f"e{i}"),
                                              template=H.DE_TPL))
            self.assertEqual(stored(e.main_output), stored(DE288), i)
            cur = e.main_output


# =================================================================================================== F1
class TestReunionRoom(unittest.TestCase):
    """F1: a full pocket makes the Wii/3DS skip a returning character's gear (0x8007F368 returns at the failed add)."""

    def test_room_left_for_the_returning_gear(self):
        need = sg.reunion_room(sh(DE288)["stored_gear"])
        self.assertEqual(need, {"head": 4, "body": 4, "arm": 4, "legs": 4, "feet": 4, "weapon": 4, "gem": 13})
        d = fresh("room")
        for p in (to_wii(DE288, d).main_output, to_3ds(DE288, d).main_output):
            b = wii_of(rd(p))
            ir = wii_save.decode_bytes(b)
            caps = d2w.wii_capacity(b)
            for box, n in need.items():
                used = len([r for r in ir["items"][box] if r["index"] < 150 and r["header"]["gid"]])
                self.assertLessEqual(used, caps[box] - n, (p, box))

    def test_exports_of_3e_engine_were_full(self):
        """Reproduction: the 3E engine filled the 3DS boxes to the capacity (60) of the story-8 template."""
        b = wii_of(rd(X3_EXPORT_3E))
        ir = wii_save.decode_bytes(b)
        self.assertEqual(d2w.wii_capacity(b)["head"], 60)
        self.assertEqual(len([r for r in ir["items"]["head"] if r["index"] < 150 and r["header"]["gid"]]), 60)

    def test_skipped_return_is_refused_never_lost(self):
        """The 3DS game's save after the reunion on the full 3E export: Shulk and Reyn back in the party with staged
        references -> refused with their names, nothing written."""
        b = wii_of(rd(X3_SKIPPED))
        ir = wii_save.decode_bytes(b)
        self.assertEqual(sorted(sg.unfinished_returns(ir, 291)), [1, 2])
        d = fresh("skipped")
        with self.assertRaises(s3.REFUSALS) as cm:
            s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=X3_SKIPPED, out=os.path.join(d, "o"), record=X3_RECORD,
                                          current=DE288))
        self.assertIn("Shulk, Reyn: back in the party", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "o")))

    def test_no_room_rule_without_stored_characters(self):
        for p in (DE291, H.DE_S232, NATIVE291):
            self.assertEqual(sg.reunion_room(sh(p).get("stored_gear", {})), {})

    def test_refuse_mode_names_the_reunion(self):
        d = fresh("refuse")
        with self.assertRaises(xs.REFUSALS) as cm:
            xs.de_to_wii_convert(xs.DeToWiiRequest(de=DE288, out=os.path.join(d, "w"), base=H.W150))
        self.assertIn("reunion", str(cm.exception))

    def test_genuine_saves_have_no_unfinished_returns(self):
        for p in (H.W150, H.W018, H.W006, H.X3_USER, X3_REUNION, X3_RELOAD,
                  os.path.join(ROOT, "phase3e", "fixtures", "wii_s160_dolphin_a6_reload_save"),
                  os.path.join(ROOT, "phase3e", "fixtures", "x3_s160_azahar_x7_reload_save"),
                  os.path.join(F3D, "wii_s291_dolphin_wd_game_save")):
            b = wii_of(rd(p))
            self.assertEqual(sg.unfinished_returns(wii_save.decode_bytes(b), fm.wii_get(b, 0x20)), {}, p)


# =================================================================================================== B: game-written
class TestGameWrittenReunion(unittest.TestCase):
    def test_native_de_reunion_returns_exactly_the_stored_gear(self):
        st, n = sh(DE288), sh(NATIVE291)
        self.assertEqual((n["story"], n["party"]), (291, [4, 6, 7, 1, 2, 5, 8]))
        self.assertNotIn("stored_gear", n)
        for k in RETURNING:
            self.assertEqual(gear(n, k), stored_view(st, k), k)

    def test_3ds_reunion_on_converted_save_equals_native(self):
        x, n, st = sh(X3_REUNION), sh(NATIVE291), sh(DE288)
        self.assertEqual((x["story"], x["party"]), (291, n["party"]))
        self.assertNotIn("stored_gear", x)
        for k in (1, 2, 4, 5, 6, 7, 8):
            self.assertEqual(gear(x, k), gear(n, k), k)
        for k in RETURNING:
            self.assertEqual(gear(x, k), stored_view(st, k), k)
        # Fiora-8 progression: only the event's AP/SP moved (same as the native event), EXP as the event gives it
        a, b = sh(X3_EXPORT)["characters"][8], x["characters"][8]
        for k in set(a) | set(b):
            if k not in ("ap", "skill_sp", "equipment", "exp"):
                self.assertEqual(a.get(k), b.get(k), k)
        self.assertEqual((b["ap"] - a["ap"], b["exp"] - a["exp"]), (108, 915))

    def test_3ds_reunion_inventory_change_equals_native(self):
        def delta(a, b):
            out, A, B = {}, contents(a), contents(b)
            for box in A:
                ca, cb = A[box], B[box]
                add = list(cb)
                for r in ca:
                    if r in add:
                        add.remove(r)
                out[box] = sorted(add)
            return out
        self.assertEqual(delta(sh(X3_EXPORT), sh(X3_REUNION)), delta(sh(DE288), sh(NATIVE291)))

    def test_3ds_cold_reload_changes_clock_and_time_only(self):
        a, b = canon.jsonable(sh(X3_REUNION)), canon.jsonable(sh(X3_RELOAD))
        diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
        self.assertEqual(diff, {"clock", "play_time_s"})

    def test_3ds_reunion_back_to_de_equals_native_content(self):
        d = fresh("x4back")
        e = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=X3_RELOAD, out=os.path.join(d, "e"), record=X3_RECORD,
                                          current=DE288))
        a, n = sh(e.main_output), sh(NATIVE291)
        self.assertEqual(contents(a), contents(n))
        for k in (1, 2, 4, 5, 6, 7, 8):
            self.assertEqual(gear(a, k), gear(n, k), k)
        self.assertNotIn("stored_gear", a)
        # the DE stash of the returning characters is cleared (as the DE game does)
        b = rd(e.main_output)
        for k in RETURNING:
            self.assertEqual(sg.de_stored(b, k), {sl: 0 for sl in GEAR}, k)

    def test_monado_cold_load_of_the_returned_save(self):
        a, b = canon.jsonable(sh(os.path.join(P3F, "inputs", "m2_x4back", "bfsgame00.sav"))), canon.jsonable(sh(M2))
        diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
        self.assertLessEqual(diff, {"clock", "play_time_s", "characters"})
        ca, cb = a["characters"], b["characters"]
        self.assertEqual({k for k in ca if ca[k] != cb[k]}, {"1"})       # Shulk's palette slot 0 (DE normalises it)
        self.assertEqual({k for k in ca["1"] if ca["1"][k] != cb["1"][k]}, {"palette"})


# =================================================================================================== D: adversarial
class TestAdversarial(unittest.TestCase):
    def _de_with(self, mutate, name):
        b = bytearray(rd(DE288))
        mutate(b)
        d = fresh(name)
        p = os.path.join(d, "bfsgame00.sav")
        open(p, "wb").write(bytes(b))
        return p, d

    def test_first_join_bit_clear_is_refused(self):
        """Fiora-8 stored while bit 8 of the join mask is clear: the Wii/3DS would re-initialise her at the return."""
        self.assertEqual(sg.first_join_problems({8: {}}, 0b111011111110)[0][:5], "Fiora")
        self.assertEqual(sg.first_join_problems({8: {}}, 0b111111111110), [])
        self.assertEqual(sg.first_join_problems({1: {}}, 0), [])
        # Wii side: the export with bit 8 cleared in flag 0x108
        d = fresh("fj")
        w = bytearray(rd(to_wii(DE288, d).main_output))
        g = 0x108
        off = fm.WII_P + 0x80 + 4 * ((g - 0x20) >> 1) + (0 if (g - 0x20) & 1 else 2)
        v = struct.unpack_from(">H", w, off)[0]
        self.assertEqual(v, fm.wii_get(bytes(w), 0x108))
        struct.pack_into(">H", w, off, v & ~(1 << 8))
        w = xc3d.fix_wii_checksums(bytes(w))
        p = os.path.join(d, "monado01_bit8_clear")
        open(p, "wb").write(w)
        with self.assertRaises(xs.REFUSALS) as cm:
            xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=os.path.join(d, "o"), template=H.DE_TPL))
        self.assertIn("first joining", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "o")))

    def _stash(self, k, j):
        return sg.STASH + sg.ENTRY * (sg.PER_CHAR * (k - 1) + j)

    def test_empty_slot_in_fioras_stored_gear(self):
        """Her stored head entry empty (as after an unequipped head): translated as empty, room shrinks by one."""
        def m(b):
            o = self._stash(8, 0)
            b[o:o + sg.ENTRY] = bytes(sg.ENTRY)
        p, d = self._de_with(m, "empty_head")
        src = stored(p)
        self.assertIsNone(src["8"]["slots"]["head"])
        w = to_wii(p, d)
        self.assertEqual(stored(w.main_output), src)
        e = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "e"), template=H.DE_TPL))
        self.assertEqual(stored(e.main_output), src)
        self.assertEqual(sg.reunion_room(sh(p)["stored_gear"])["head"], 3)

    def test_stored_gem_without_socket_is_refused(self):
        """Fiora's weapon socket 1 cleared while its gem copy stays: inconsistent, refused (nothing written)."""
        def m(b):
            o = self._stash(8, 5)
            struct.pack_into("<II", b, o + 0x18 + 8, 0, 0)
        p, d = self._de_with(m, "orphan_gem")
        with self.assertRaises(xs.REFUSALS):
            to_wii(p, d)
        self.assertFalse(os.path.exists(os.path.join(d, "w")))

    def test_more_than_8_gems_for_fiora_on_the_wii_is_refused(self):
        sg8 = copy.deepcopy(sh(DE288)["stored_gear"][8])
        sg8["gems"] = sg8["gems"] * 5
        img = d2w.WiiImage(rd(H.W150))
        with self.assertRaises(d2w.IncompatibleError):
            sg.write_wii(img, 8, sg8, T)

    def test_duplicate_items_go_to_the_right_owner(self):
        """Shulk and Reyn both stored legs 1227 (+ the same fixed gem): each got his own back on the 3DS."""
        st = sh(DE288)["stored_gear"]
        self.assertEqual(st[1]["slots"]["legs"]["gid"], st[2]["slots"]["legs"]["gid"])
        x = sh(X3_REUNION)
        self.assertEqual(gear(x, 1)["legs"], stored_view(sh(DE288), 1)["legs"])
        self.assertEqual(gear(x, 2)["legs"], stored_view(sh(DE288), 2)["legs"])

    def test_exp_earned_on_the_wii_while_fiora_is_away(self):
        """Wii session at 288 (Fiora away, record 8 gains EXP, money): back to DE with the sidecar - EXP moves, stored
        gear and DE metadata kept."""
        d = fresh("exp")
        w = to_wii(DE288, d)
        p = os.path.join(d, "played")
        open(p, "wb").write(H.play_wii(rd(w.main_output), flags=3, exp=250, char=8, money=77))
        e = xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=os.path.join(d, "e"), sidecar=w.sidecar_path, current_de=DE288))
        a, b = sh(DE288), sh(e.main_output)
        self.assertEqual(b["characters"][8]["exp"], a["characters"][8]["exp"] + 250)
        self.assertEqual(canon.jsonable(b["stored_gear"]), canon.jsonable(a["stored_gear"]))
        self.assertEqual(rd(e.main_output)[sg.STASH:sg.STASH_END], rd(DE288)[sg.STASH:sg.STASH_END])

    def test_de_only_item_metadata_survives_the_split_round_trip(self):
        d = fresh("meta")
        w = to_wii(DE288, d)
        e = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "e"), sidecar=w.sidecar_path,
                                           current_de=DE288))
        self.assertEqual(canon.from_de(rd(e.main_output), T)["de_only"], canon.from_de(rd(DE288), T)["de_only"])

    def test_return_of_the_3e_full_export_unplayed_is_still_byte_identical(self):
        """Files exported by the 3E engine (no room kept) still return byte-identically to their DE save."""
        d = fresh("old_export")
        b = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=X3_EXPORT_3E, out=os.path.join(d, "b"),
                                          record=X3_EXPORT_3E + ".de_to_3ds.record.json", current=DE288))
        self.assertEqual(rd(b.main_output), rd(DE288))


# =================================================================================================== F: Sync Hub
def _hub_sh(img):
    return sh(img)


class TestSyncHub(unittest.TestCase):
    def test_283_288_291_sequence_is_one_playthrough(self):
        """Genuine DE 283 -> 288 (split) -> native 291 (reunion played by Monado): new progress each time, the Wii and
        3DS outputs carry exactly the stored gear (Fiora's included), nothing stored after the reunion; rollback to
        the split restores it exactly."""
        fx = H.HubFx("p3f_hub_seq")
        split_gen = None
        for n, p in enumerate((DE283, DE288, NATIVE291), 1):
            fx.drop("Windows desktop", "bfsgame00.sav", rd(p), age=900 - 100 * n)
            res = fx.scan()
            self.assertIn(res.decision.kind, ("start", "new-progress"), (p, res.decision.message))
            r = fx.sync(res)
            self.assertTrue(r.complete, r.message)
            want = canon.jsonable(sh(p).get("stored_gear"))
            self.assertEqual(canon.jsonable(_hub_sh(fx.out("wii")).get("stored_gear")), want, p)
            self.assertEqual(canon.jsonable(_hub_sh(fx.out("3ds")).get("stored_gear")), want, p)
            if p == DE288:
                split_gen = fx.hub.current_generation()[0]
        self.assertEqual(_hub_sh(fx.out("3ds"))["party"], [4, 6, 7, 1, 2, 5, 8])
        sync.rollback(fx.hub, split_gen)
        self.assertEqual(fx.out("de"), rd(DE288))

    def test_wii_session_during_the_split_keeps_the_stored_gear(self):
        fx = H.HubFx("p3f_hub_wii")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(DE288))
        self.assertTrue(fx.sync().complete)
        w = H.play_wii(fx.out("wii"), flags=3, skip=30, money=10)
        fx.drop("Odin 2 Mini", "monado01", w)
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        self.assertEqual(canon.jsonable(sh(fx.out("de"))["stored_gear"]), stored(DE288))
        de = fx.out("de")
        self.assertEqual(de[sg.STASH:sg.STASH_END], rd(DE288)[sg.STASH:sg.STASH_END])   # no outdated/duplicate gear

    def test_3ds_game_reunion_comes_back_through_the_hub(self):
        """The hub's 3DS output of the 288 generation is byte-identical to the file the 3DS game played (Azahar x3/x4
        differ before play only by the debug position); the game's post-reunion save is new progress from the New 3DS,
        and the DE output holds the native reunion's items - nothing duplicated, nothing still stored."""
        fx = H.HubFx("p3f_hub_x3")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(DE288), age=600)
        self.assertTrue(fx.sync().complete)
        self.assertEqual(fx.out("3ds"), rd(X3_EXPORT))
        fx.drop("New 3DS", "monado01", rd(X3_RELOAD), age=100)
        res = fx.scan()
        self.assertEqual(res.decision.kind, "new-progress", res.decision.message)
        r = fx.sync(res)
        self.assertTrue(r.complete, r.message)
        de, n = sh(fx.out("de")), sh(NATIVE291)
        self.assertEqual(de["party"], n["party"])
        self.assertNotIn("stored_gear", de)
        self.assertEqual(contents(de), contents(n))
        for k in RETURNING:
            self.assertEqual(sg.de_stored(fx.out("de"), k), {sl: 0 for sl in GEAR}, k)
        self.assertNotIn("stored_gear", sh(fx.out("wii")))

    def test_interrupted_sync_of_the_split_commits_nothing(self):
        fx = H.HubFx("p3f_hub_fault")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(DE283), age=700)
        self.assertTrue(fx.sync().complete)
        gen_before = fx.hub.current_generation()[0]
        fx.drop("Windows desktop", "bfsgame00.sav", rd(DE288), age=600)

        def boom(p, detail=""):
            if p == "convert" and detail == "de_to_wii":
                raise OSError("power loss (simulated)")
        sync.FAULT = boom
        try:
            with self.assertRaises(Exception):
                fx.sync()
        finally:
            sync.FAULT = None
        self.assertEqual(fx.hub.current_generation()[0], gen_before)
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        self.assertEqual(canon.jsonable(sh(fx.out("wii"))["stored_gear"]), stored(DE288))

    def test_divergent_reunions_are_not_merged(self):
        """DE plays the reunion (native 291) and the Wii plays on from the same 288 generation: a conflict, never a
        silent merge."""
        fx = H.HubFx("p3f_hub_div")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(DE288), age=600)
        self.assertTrue(fx.sync().complete)
        w = H.play_wii(fx.out("wii"), flags=4, skip=10)
        fx.drop("Odin 2 Mini", "monado01", w, age=100)
        fx.drop("Windows desktop", "bfsgame00.sav", rd(NATIVE291), age=100)
        res = fx.scan()
        self.assertEqual(res.decision.kind, "conflict", res.decision.message)
        before = fx.hub.current_generation()[0]
        with self.assertRaises((sync.Blocked, sync.HubError)):     # a choice is required - nothing committed
            fx.sync(res)
        self.assertEqual(fx.hub.current_generation()[0], before)


if __name__ == "__main__":
    unittest.main()
