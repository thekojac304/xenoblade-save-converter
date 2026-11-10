"""Phase 3E: stored equipment of party members who are away (tools/stored_gear) - decode, translation both ways,
game-written reunions, adversarial inputs, D3 (3DS link byte order). Fixtures: phase3e/fixtures (PROVENANCE.md)."""
import copy
import os
import shutil
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
P3E = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3E)
sys.path.insert(0, os.path.join(ROOT, "phase3c", "tests"))
import p3cfix as F  # noqa: E402,F401
from p3cfix import H, T, rd  # noqa: E402

import canon  # noqa: E402
import stored_gear as sg  # noqa: E402
import wii_save  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402
from de_to_wii import CHAR_BASE, CHAR_SIZE  # noqa: E402

FX = os.path.join(P3E, "fixtures")
F3C = os.path.join(ROOT, "phase3c", "fixtures")
F3D = os.path.join(ROOT, "phase3d", "fixtures")
WORK = os.path.join(P3E, "work", "tests")
SPLIT = [os.path.join(F3C, f) for f in ("de_s154_monado_autosave.sav", "de_s156_monado_autosave.sav",
                                         "de_s158_monado_autosave_c1.sav")] + \
        [os.path.join(F3D, f"de_s{s}_v10_monado.sav") for s in (269, 276, 283, 288)]


def fx(n):
    return os.path.join(FX, n)


def fresh(name):
    d = os.path.join(WORK, name)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def wii_of(b):
    return xc3d.transcode(xc3d.unpack(b), "wii") if b[:4] == b"!qzb" else b


def shared(p):
    b = wii_of(rd(p))
    return (canon.from_wii(b, T) if b[:4] == b"USRD" else canon.from_de(b, T))["shared"]


def stored(p):
    return canon.jsonable(shared(p).get("stored_gear"))


def gear(sh, k):
    """Equipped gear of k as (gid, socket count, sockets with gem contents)."""
    out = {}
    for sl, i in (sh["characters"][k].get("equipment") or {}).items():
        r = sh["inventory"][sl].get(i) if i is not None else None
        if r is None:
            out[sl] = None
            continue
        socks = []
        for s in r["sockets"]:
            if s and s[0] == "gem":
                g = sh["inventory"]["gem"][s[1]]
                socks.append(("gem", g["gid"], g["effect"], g["rank"], g["strength"], g["chance"]))
            else:
                socks.append(tuple(s) if s else None)
        out[sl] = (r["gid"], r["socket_count"], tuple(socks))
    return out


def stored_gear_view(sh, k):
    d = sh["stored_gear"][k]
    out = {}
    for sl, r in d["slots"].items():
        if r is None:
            out[sl] = None
            continue
        socks = []
        for s in r["sockets"]:
            if s and s[0] == "gem":
                g = d["gems"][s[1]]
                socks.append(("gem", g["gid"], g["effect"], g["rank"], g["strength"], g["chance"]))
            else:
                socks.append(tuple(s) if s else None)
        out[sl] = (r["gid"], r["socket_count"], tuple(socks))
    return out


class TestDecode(unittest.TestCase):
    def test_genuine_split_saves_read(self):
        want = {154: [1, 2, 4, 5, 6], 156: [1, 2, 4, 5, 6], 158: [2, 4, 5, 6, 7], 269: [2, 4, 5, 6, 7],
                276: [2, 4, 5, 6, 7], 283: [4, 6, 7], 288: [1, 2, 5, 8]}
        for p in SPLIT:
            sh = shared(p)
            with self.subTest(story=sh["story"]):
                self.assertEqual(sorted(sh["stored_gear"]), want[sh["story"]])
                self.assertFalse([k for k, v in sh["stored_gear"].items() if "unreadable" in v])

    def test_saves_outside_splits_have_no_stored_gear_key(self):
        for p in (H.W150, H.W018, H.W006, H.DE_S232, os.path.join(F3D, "de_s291_v10_monado.sav"),
                  os.path.join(F3C, "de_s233_monado_autosave_l1.sav")):
            self.assertNotIn("stored_gear", shared(p), p)

    def test_wii_encoder_matches_game_written_staging(self):
        """Dunban's scripted prologue gear on the user's story-18 Wii save, re-encoded from its canonical form: equal to
        the game's bytes except the item age (+5); the gem-box reference fields of script records are 0, ours 0xFFFF
        (the game's own copies from the inventory carry 0xFFFF, Wii 150)."""
        import de_to_wii as d2w
        b = rd(H.W018)
        ir = wii_save.decode_bytes(b)
        c = sg.wii_read(b, ir, 4)
        img = d2w.WiiImage(b)
        sg.write_wii(img, 4, c, T)
        for sl in sg.SLOTS:
            typ, off, size, _ = d2w.WII_BOX[sl]
            o = wii_save.ITEM + off + size * 154
            diff = {i for i in range(size) if b[o + i] != img.b[o + i]}
            self.assertLessEqual(diff, {5} | set(range(0x28, 0x30)), sl)

    def test_users_story8_3ds_save_has_reyn_stored(self):
        """The user's own 3DS save (story 8, Shulk alone): the 3DS game keeps Reyn's starting gear for him."""
        st = shared(H.X3_USER)["stored_gear"]
        self.assertEqual(list(st), [2])
        self.assertEqual([r["gid"] for r in st[2]["slots"].values()], [647, 648, 649, 650, 651, 10])

    def test_defaults_departure_is_stored_too(self):
        """Melia leaves at 158 wearing her table defaults; the DE stores them - translated like any gear."""
        sh = shared(SPLIT[2])
        self.assertEqual([r["gid"] for r in sh["stored_gear"][7]["slots"].values()], [662, 663, 664, 665, 666, 56])


class TestTranslation(unittest.TestCase):
    def test_all_directions_on_genuine_split_saves(self):
        for p in SPLIT[:-1]:            # 288 (Fiora away): refused, see test_fiora_away_is_refused
            src = stored(p)
            with self.subTest(save=os.path.basename(p)):
                d = fresh("tr_" + os.path.basename(p)[:12])
                w = xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=os.path.join(d, "w"), base=H.W150,
                                                           overflow="sidecar"))
                self.assertEqual(stored(w.main_output), src)
                b = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "b"),
                                                   sidecar=w.sidecar_path, current_de=p))
                self.assertEqual(rd(b.main_output), rd(p))                         # unchanged return
                f = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "f"), template=H.DE_TPL))
                self.assertEqual(stored(f.main_output), src)                         # first-time
                x = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=p, out=os.path.join(d, "x"), template=H.X3_USER,
                                                  overflow="sidecar"))
                self.assertEqual(stored(x.main_output), src)
                x2 = s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=x.main_output, out=os.path.join(d, "x2")))
                self.assertEqual(stored(x2.main_output), src)

    def test_fiora_away_is_refused(self):
        d = fresh("fiora288")
        with self.assertRaises(xs.REFUSALS) as cm:
            xs.de_to_wii_convert(xs.DeToWiiRequest(de=SPLIT[-1], out=os.path.join(d, "w"), base=H.W150,
                                                   overflow="sidecar"))
        self.assertIn("Fiora is away from the party", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "w")))

    def test_repeated_three_platform_conversions_are_stable(self):
        p = SPLIT[1]
        src = stored(p)
        d = fresh("rep")
        cur = p
        for i in range(3):
            w = xs.de_to_wii_convert(xs.DeToWiiRequest(de=cur, out=os.path.join(d, f"w{i}"), base=H.W150,
                                                       overflow="sidecar"))
            x = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=w.main_output, out=os.path.join(d, f"x{i}"),
                                              template=H.X3_USER))
            e = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=x.main_output, out=os.path.join(d, f"e{i}"),
                                              template=H.DE_TPL))
            self.assertEqual(stored(e.main_output), src, i)
            cur = e.main_output

    def test_d3_link_table_is_bytes_on_the_3ds(self):
        """D3: the staged-gem links are two bytes (slot+1, socket) on both machines; the 3DS file keeps the Wii byte
        order (3A swapped them as u16 and the 3DS game skipped the gems - run x1c)."""
        d = fresh("d3")
        x = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=SPLIT[1], out=os.path.join(d, "x"), template=H.X3_USER,
                                          overflow="sidecar"))
        w = wii_of(rd(x.main_output))
        self.assertEqual(w[wii_save.ITEM + 0x12038:wii_save.ITEM + 0x12038 + 12].hex(), "010003000400050006000601")
        raw = xc3d.unpack(rd(x.main_output))
        self.assertIn(bytes.fromhex("010003000400050006000601"), raw)        # same byte order as the Wii
        self.assertNotIn(bytes.fromhex("000100030004000500060106"), raw)     # 3A's swapped form


class TestGameWrittenReunions(unittest.TestCase):
    """The target games played the reunions on converted saves (debug positioning only; see REUNION_VALIDATION.md)."""

    def test_wii_156_to_158_shulk(self):
        w, de158 = shared(fx("wii_s158_dolphin_a1_game_save")), shared(os.path.join(F3C, "de_s158_monado_autosave_c1.sav"))
        self.assertEqual((w["story"], w["party"]), (158, [1]))
        self.assertEqual(gear(w, 1), gear(de158, 1))
        self.assertEqual(gear(w, 1), stored_gear_view(shared(SPLIT[1]), 1))
        self.assertEqual(canon.jsonable(w["stored_gear"]), canon.jsonable(de158["stored_gear"]))   # incl. Melia

    def test_wii_158_to_160_four_friends(self):
        w, de160 = shared(fx("wii_s160_dolphin_a5c_game_save")), shared(os.path.join(F3C, "de_s160_monado_autosave_c9.sav"))
        self.assertEqual((w["story"], w["party"]), (160, [1, 2, 4, 5, 6]))
        for k in (1, 2, 4, 5, 6):
            self.assertEqual(gear(w, k), gear(de160, k), k)

    def test_wii_cold_reload_and_return_to_de(self):
        a, b = shared(fx("wii_s160_dolphin_a5c_game_save")), shared(fx("wii_s160_dolphin_a6_reload_save"))
        self.assertEqual({x[0] for x in canon.compare(a, b)}, {"/clock/hour", "/clock/minute", "/play_time_s"})
        d = fresh("ret160")
        r = xs.wii_to_de(xs.WiiToDeRequest(wii=fx("wii_s160_dolphin_a6_reload_save"), out=os.path.join(d, "o"),
                                           sidecar=fx("wii_s156_export_3e.de_to_wii.sidecar.json"),
                                           current_de=SPLIT[1]))
        x = shared(r.main_output)
        n = shared(os.path.join(F3C, "de_s160_monado_autosave_c9.sav"))
        for k in (1, 2, 4, 5, 6):
            self.assertEqual(gear(x, k), gear(n, k), k)
        self.assertEqual(canon.jsonable(x["stored_gear"]), canon.jsonable(n["stored_gear"]))

    def test_3ds_156_to_158_shulk_with_gems(self):
        x = shared(fx("x3_s158_azahar_x2_game_save"))
        self.assertEqual((x["story"], x["party"]), (158, [1]))
        self.assertEqual(gear(x, 1), gear(shared(os.path.join(F3C, "de_s158_monado_autosave_c1.sav")), 1))

    def test_3ds_158_to_160_four_friends_reload_and_return(self):
        x, n = shared(fx("x3_s160_azahar_x6c_game_save")), shared(os.path.join(F3C, "de_s160_monado_autosave_c9.sav"))
        self.assertEqual((x["story"], x["party"]), (160, [1, 2, 4, 5, 6]))
        for k in (1, 2, 4, 5, 6):
            self.assertEqual(gear(x, k), gear(n, k), k)
        r = shared(fx("x3_s160_azahar_x7_reload_save"))
        self.assertEqual({d[0] for d in canon.compare(x, r)}, {"/clock/hour", "/clock/minute", "/play_time_s"})
        d = fresh("ret3ds160")
        b = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=fx("x3_s160_azahar_x7_reload_save"), out=os.path.join(d, "o"),
                                          record=fx("x3_s156_export_3e.de_to_3ds.record.json"), current=SPLIT[1]))
        y = shared(b.main_output)
        for k in (1, 2, 4, 5, 6):
            self.assertEqual(gear(y, k), gear(n, k), k)
        self.assertEqual(canon.jsonable(y["stored_gear"]), canon.jsonable(n["stored_gear"]))

    def test_de_reunion_from_a_wii_converted_stash(self):
        """Wii 158 (Wii game save) -> DE first-time (no sidecar) -> Monado played 158 -> 160: same gear as native."""
        m = shared(fx("de_s160_monado_m1_from_wii_stash.sav"))
        n = shared(os.path.join(F3C, "de_s160_monado_autosave_c9.sav"))
        self.assertEqual((m["story"], m["party"]), (160, [1, 2, 4, 5, 6]))
        for k in (1, 2, 4, 5, 6):
            self.assertEqual(gear(m, k), gear(n, k), k)


class TestAdversarial(unittest.TestCase):
    """Synthetic damage to genuine stored gear: refused, nothing written - never guessed."""

    def _de(self, edit):
        b = bytearray(rd(SPLIT[1]))
        edit(b)
        p = os.path.join(fresh("adv_" + edit.__name__), "in.sav")
        open(p, "wb").write(bytes(b))
        return p

    def refused_de(self, p):
        out = os.path.join(os.path.dirname(p), "o")
        with self.assertRaises(xs.REFUSALS):
            xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=out, base=H.W150, overflow="sidecar"))
        self.assertFalse(os.path.exists(out))

    def test_socket_names_a_gem_that_is_not_stored(self):
        def missing_gem(b):        # Shulk's head socket points at a gem slot no stored record has
            o = sg.STASH + 0x18
            struct.pack_into("<I", b, o, (3 << 16) | 499)
        self.refused_de(self._de(missing_gem))

    def test_orphan_stored_gem(self):
        def orphan(b):             # Shulk's head: socket cleared, its gem copy left behind
            struct.pack_into("<I", b, sg.STASH + 0x18, 0)
        self.refused_de(self._de(orphan))

    def test_duplicate_gem_numbers(self):
        def dup(b):                # Shulk's weapon: both gem copies claim the same slot number
            o = sg.STASH + sg.ENTRY * 5
            first = struct.unpack_from("<H", b, o + 0x30)[0]
            struct.pack_into("<H", b, o + 0x30 + 0x2C, first)
        self.refused_de(self._de(dup))

    def test_more_than_eight_gems_is_refused_for_the_wii(self):
        p = SPLIT[1]
        c = canon.from_de(rd(p), T)["shared"]["stored_gear"][1]
        big = copy.deepcopy(c)
        big["gems"] = big["gems"] * 2
        import de_to_wii as d2w
        img = d2w.WiiImage(rd(H.W150))
        with self.assertRaises(d2w.IncompatibleError):
            sg.write_wii(img, 1, big, T)

    def test_wii_staging_record_with_another_item_is_refused(self):
        b = bytearray(rd(fx("wii_s158_dolphin_a1_game_save")))
        o = CHAR_BASE + CHAR_SIZE * 2 + 0x02 + 2 * 5           # Reyn's weapon reference -> a different gear id
        struct.pack_into(">H", b, o, struct.unpack_from(">H", b, o)[0] + 1)
        d = fresh("adv_wii")
        p = os.path.join(d, "w")
        open(p, "wb").write(xc3d.fix_wii_checksums(bytes(b)))
        with self.assertRaises(xs.REFUSALS):
            xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=os.path.join(d, "o"), template=H.DE_TPL))
        self.assertFalse(os.path.exists(os.path.join(d, "o")))

    def test_absent_character_still_equipped_from_inventory_is_refused(self):
        b = bytearray(rd(fx("wii_s158_dolphin_a1_game_save")))
        o = CHAR_BASE + CHAR_SIZE * 2 + 0x1C + 2 * 1           # Reyn's body reference -> inventory slot 0
        struct.pack_into(">H", b, o, 0)
        d = fresh("adv_wii2")
        p = os.path.join(d, "w")
        open(p, "wb").write(xc3d.fix_wii_checksums(bytes(b)))
        with self.assertRaises(xs.REFUSALS):
            xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=os.path.join(d, "o"), template=H.DE_TPL))

    def test_equipment_changed_before_reunion_follows_the_save(self):
        """A stored item modified on the DE side before the conversion (here: a gem's strength) is what arrives."""
        def stronger(b):
            o = sg.STASH + 0x30          # Shulk's head gem copy
            b[o + 0x1E] = min(b[o + 0x1E] + 5, 255)
        p = self._de(stronger)
        d = os.path.dirname(p)
        w = xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=os.path.join(d, "w"), base=H.W150, overflow="sidecar"))
        self.assertEqual(stored(w.main_output), stored(p))
        self.assertNotEqual(stored(w.main_output), stored(SPLIT[1]))


if __name__ == "__main__":
    unittest.main()
