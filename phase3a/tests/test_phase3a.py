"""Phase 3A regression tests: Xenoblade Chronicles 3D container, Wii <-> 3DS transcoder, derived-stat rebuild,
the four new conversion directions, conversion records (lineage, divergence, integrity) and path safety.

  python -m unittest discover -s phase3a/tests -v        (from the research root; needs the user's own fixtures)
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3)
for p in (os.path.join(P3, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import canon  # noqa: E402
import qlz  # noqa: E402
import safeio  # noqa: E402
import wii_save as W  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xc3dstats  # noqa: E402
import xcconv3  # noqa: E402
import xcservice as xs  # noqa: E402

FIX = os.path.join(P3, "fixtures")
X3_USER = os.path.join(P3, "originals", "azahar_live", "00000001", "monado01")       # game-written, story 8
X3_EMPTY = os.path.join(P3, "originals", "azahar_live", "00000001", "monado02")      # DMMY slot
X3_GAME_S150 = os.path.join(P3, "runs", "azahar", "a2_s150_gameplay", "save_after", "00000001", "monado02")
X3_GAME_A1 = os.path.join(P3, "runs", "azahar", "a1_wii_s150_to_3ds", "save_after", "00000001", "monado03")
W150 = os.path.join(FIX, "wii_user_s150.bin")
W018 = os.path.join(FIX, "wii_user_s018.bin")
W006 = os.path.join(FIX, "wii_d7_s006.bin")
W150_LATER = os.path.join(ROOT, "work", "phase2e", "dolphin", "d6_travel", "user", "Wii", "title", "00010000",
                          "53583445", "data", "monado01")                             # the s150 playthrough, played on
DE_TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
DE_S232 = os.path.join(ROOT, "phase2f", "fixtures", "real", "s232_v10_monado.sav")
WORK = os.path.join(P3, "work", "tests")


def rd(p):
    with open(p, "rb") as f:
        return f.read()


def out(name):
    p = os.path.join(WORK, name)
    if os.path.exists(p):
        shutil.rmtree(p)
    return p


def req(direction, source, o, **kw):
    return s3.ThreeDSRequest(direction=direction, source=source, out=o, **kw)


def setUpModule():
    os.makedirs(WORK, exist_ok=True)


# ------------------------------------------------------------------------------------------------- codec
class QuickLZ(unittest.TestCase):
    def test_game_files_recompress_byte_identical(self):
        for p in (X3_USER, X3_EMPTY, X3_GAME_S150):
            f = rd(p)
            blk = f[12:]
            self.assertEqual(qlz.compress(qlz.decompress(blk)), blk, p)

    def test_synthetic_roundtrip(self):
        import random
        rnd = random.Random(7)
        for n in (216, 1000, 0x28000):
            data = bytes(rnd.choice(b"\0\0\0\1\2abc\xe3") for _ in range(n))
            self.assertEqual(qlz.decompress(qlz.compress(data)), data)
        data = os.urandom(5000)                                  # incompressible -> stored block
        blk = qlz.compress(data)
        self.assertEqual(blk[0] & 1, 0)
        self.assertEqual(qlz.decompress(blk), data)

    def test_damaged_blocks_refused(self):
        blk = rd(X3_USER)[12:]
        for bad in (blk[:100], b"\x4d" + blk[1:], blk[:9] + b"\0\0\0\0" + blk[13:]):
            with self.assertRaises(qlz.QLZError):
                qlz.decompress(bad)


class Container(unittest.TestCase):
    def test_user_save(self):
        raw = xc3d.unpack(rd(X3_USER))
        self.assertEqual(xc3d.kind(raw), "save")
        self.assertEqual(xc3d.check_container(raw), [])
        self.assertEqual(xc3d.pack(raw), rd(X3_USER))

    def test_empty_slot(self):
        self.assertEqual(xc3d.kind(xc3d.unpack(rd(X3_EMPTY))), "empty")
        with self.assertRaises(safeio.Refused):
            s3.load_3ds(X3_EMPTY, "x")

    def test_invalid_and_truncated(self):
        f = rd(X3_USER)
        cases = {"wrong magic": b"!qzc" + f[4:], "truncated": f[:-10], "padded": f + b"\0",
                 "bad size": f[:4] + struct.pack("<I", 0x27000) + f[8:]}
        for name, b in cases.items():
            with self.assertRaises(xc3d.FormatError, msg=name):
                xc3d.unpack(b)

    def test_checksum_damage_refused(self):
        raw = bytearray(xc3d.unpack(rd(X3_USER)))
        raw[0xB300] ^= 1                                   # inside GAME, CRC not updated
        self.assertIn("section GAME checksum", xc3d.check_container(bytes(raw)))
        p = os.path.join(WORK, "damaged_monado01")
        with open(p, "wb") as f:
            f.write(xc3d.pack(bytes(raw)))
        with self.assertRaises(safeio.Refused):
            s3.load_3ds(p, "x")
        self.assertEqual(s3.kind_of(rd(p)), "3ds")       # detected as a 3DS save, refused when loaded


# ------------------------------------------------------------------------------------------------- schema
class Schema(unittest.TestCase):
    def test_full_coverage(self):
        pos = 0
        for s, e, k in xc3d.SCHEMA:
            self.assertEqual(s, pos)
            pos = e
        self.assertEqual(pos, xc3d.RAW_SIZE)

    def test_3ds_wii_3ds_byte_exact(self):
        raw = xc3d.unpack(rd(X3_USER))
        self.assertEqual(xc3d.transcode(xc3d.transcode(raw, "wii"), "3ds", template=raw), raw)

    def test_wii_3ds_wii_byte_exact(self):
        tpl = xc3d.unpack(rd(X3_USER))
        for p in (W150, W006):
            w = rd(p)
            self.assertEqual(xc3d.transcode(xc3d.transcode(w, "3ds", template=tpl), "wii"), w, p)

    def test_known_bitfields(self):
        raw = xc3d.unpack(rd(X3_USER))
        wii = xc3d.transcode(raw, "wii")
        # material record: global id 2170, type 11, row 19 (same item in a native Wii save)
        h = W.item_header(wii[W.ITEM + 0x10B18:W.ITEM + 0x10B18 + 8])
        self.assertEqual((h["gid"], h["type"], h["row"]), (2170, 11, 19))
        # gem descriptor of Dunban's weapon (record 154) in the user's 3DS save == the Wii's own
        w = rd(W006)
        o = W.ITEM + 0xA58C + 0x34 * 154 + 8
        self.assertEqual(W.gem_desc(wii[o:o + 8]), W.gem_desc(w[o:o + 8]))
        self.assertEqual(W.gem_desc(wii[o:o + 8])["strength"], 100)

    def test_playtime_and_thumbnail_fields(self):
        wii = xc3d.transcode(xc3d.unpack(rd(X3_USER)), "wii")
        pt = struct.unpack_from(">I", wii, 0x11EB0)[0]
        self.assertEqual((pt >> 12, pt >> 6 & 63, pt & 63), (0, 12, 9))        # the load menu showed 00:12
        self.assertEqual(struct.unpack_from(">H", wii, 0x20)[0], 8)            # THUM scenario

    def test_treasure_chest_layout_from_game_resave(self):
        # the 3DS game re-wrote chests 0-2 and 5-10 of the converted s150 save in its own layout
        gw = xc3d.transcode(xc3d.unpack(rd(X3_GAME_A1)), "wii")
        w = rd(W150)
        for n in (0, 1, 2, 5, 6, 7, 8, 9, 10):
            o = 0x244A4 + 28 * n
            self.assertEqual(gw[o:o + 28], w[o:o + 28], n)

    def test_wrong_source_refused(self):
        with self.assertRaises(xc3d.FormatError):
            xc3d.transcode(rd(W150), "wii")
        with self.assertRaises(xc3d.FormatError):
            xc3d.transcode(xc3d.unpack(rd(X3_USER)), "3ds")


# ------------------------------------------------------------------------------------------------- stats
class Stats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.B = s3.wii_bdat()

    def test_rebuild_is_noop_on_game_written_saves(self):
        for w in (rd(W150), rd(W018), xc3d.transcode(xc3d.unpack(rd(X3_USER)), "wii")):
            nb, ch = xc3dstats.rebuild(w, self.B)
            self.assertEqual(ch, [])
            self.assertEqual(nb, w)

    def test_weapon_flag_is_u16(self):
        # regression: an early 3A build copied +0xE6 as two bytes; the 3DS game then saw flag 0x0500 (no Monado
        # scaling).  That save (played and re-saved by the 3DS game) is repaired by the rebuild.
        w = xc3d.transcode(xc3d.unpack(rd(X3_GAME_S150)), "wii")
        nb, ch = xc3dstats.rebuild(w, self.B)
        self.assertEqual([(c[0], c[1]) for c in ch], [(1, "weapon cache")])
        self.assertEqual(nb[W.CHAR_BASE + W.CHAR_SIZE + 0xE4:W.CHAR_BASE + W.CHAR_SIZE + 0xE8], bytes([0, 2, 0, 5]))

    def test_level_up_formula(self):
        pc = {r["id"]: r for r in self.B["BTL_pclist"]["rows"]}
        self.assertEqual(xc3dstats.base_stats(pc[1], 2), (331, 26, 17, 34))
        self.assertEqual(xc3dstats.base_stats(pc[1], 52), (3933, 311, 90, 321))
        self.assertEqual(xc3dstats.base_stats(pc[6], 51), (7274, 317, 94, 304))

    def test_monado_scaling(self):
        wp = {r["id"]: r for r in self.B["ITM_wpnlist"]["rows"]}
        c = xc3dstats.weapon_cache(wp[1], 52)
        self.assertEqual(struct.unpack_from(">2H", c, 0xC), (582, 780))
        self.assertEqual(c[0x1C:], bytes([0, 2, 0, 5]))

    def test_stale_blocks_rebuilt(self):
        # a Wii save whose blocks are stale (2F DE -> Wii export, re-saved by the Wii game, which keeps them)
        stale = rd(os.path.join(ROOT, "phase2f", "fixtures", "real", "game_chain_s232", "w_saved_by_wii_game"))
        nb, ch = xc3dstats.rebuild(stale, self.B)
        self.assertTrue(any(c[1] == "base stats" for c in ch))
        self.assertEqual(xc3dstats.rebuild(nb, self.B)[1], [])


# ------------------------------------------------------------------------------------------------- service
class Directions(unittest.TestCase):
    def test_wii_to_3ds_and_back_byte_identical(self):
        a = s3.convert3(req("wii_to_3ds", W150, out("w2x"), template=X3_USER))
        self.assertTrue(a.report["checkpoint_backup"])
        b = s3.convert3(req("3ds_to_wii", a.main_output, out("w2x2w"), record=a.sidecar_path, current=W150))
        self.assertEqual(rd(b.main_output), rd(W150))
        self.assertEqual(xs.validate_bytes(rd(b.main_output))["problems"], [])

    def test_3ds_to_wii_and_back_byte_identical(self):
        a = s3.convert3(req("3ds_to_wii", X3_USER, out("x2w")))
        b = s3.convert3(req("wii_to_3ds", a.main_output, out("x2w2x"), template=X3_USER, record=a.sidecar_path,
                            current=X3_USER))
        self.assertEqual(rd(b.main_output), rd(X3_USER))

    def test_de_to_3ds_and_back_byte_identical(self):
        a = s3.convert3(req("de_to_3ds", DE_TPL, out("d2x"), template=X3_USER))
        b = s3.convert3(req("3ds_to_de", a.main_output, out("d2x2d"), record=a.sidecar_path, no_current=True))
        self.assertEqual(rd(b.main_output), rd(DE_TPL))

    def test_3ds_to_de_and_back_byte_identical(self):
        a = s3.convert3(req("3ds_to_de", X3_USER, out("x2d"), template=DE_TPL))
        b = s3.convert3(req("de_to_3ds", a.main_output, out("x2d2x"), template=X3_USER, record=a.sidecar_path,
                            current=X3_USER))
        self.assertEqual(rd(b.main_output), rd(X3_USER))

    def test_three_platform_chain_keeps_shared_state(self):
        # Wii -> DE (2H) -> 3DS -> Wii -> DE : the DE-only state and the shared state survive
        T = xs.tables()
        r1 = xs.wii_to_de(xs.WiiToDeRequest(wii=W150, out=out("c1"), template=DE_TPL))
        r2 = s3.convert3(req("de_to_3ds", r1.main_output, out("c2"), template=X3_USER, record=r1.sidecar_path,
                             no_current=True))
        r3 = s3.convert3(req("3ds_to_wii", r2.main_output, out("c3"), record=r2.sidecar_path, current=W150))
        r4 = s3.convert3(req("3ds_to_de", r2.main_output, out("c4"), record=r2.sidecar_path,
                             current=r1.main_output))
        self.assertEqual(rd(r4.main_output), rd(r1.main_output))   # unchanged -> the DE save byte for byte
        c0 = canon.from_wii(rd(W150), T)["shared"]
        c3 = canon.from_wii(rd(r3.main_output), T)["shared"]
        self.assertEqual(xs.readback_diffs(c0, c3), [])
        rec = s3.load_record(r3.sidecar_path)[1]
        self.assertEqual(rec["lineage"]["generation"], 3)
        self.assertTrue(rec["de_sidecar"])                         # DE-only state carried forward

    def test_deterministic_output(self):
        a = s3.convert3(req("wii_to_3ds", W150, out("det1"), template=X3_USER))
        b = s3.convert3(req("wii_to_3ds", W150, out("det2"), template=X3_USER))
        self.assertEqual({k: v for k, v in a.written.items() if k != "manifest.json"},
                         {k: v for k, v in b.written.items() if k != "manifest.json"})

    def test_de_to_3ds_overflow(self):
        with self.assertRaises(s3.REFUSALS):
            s3.convert3(req("de_to_3ds", DE_S232, out("ovf1"), template=X3_USER))
        self.assertFalse(os.path.exists(os.path.join(WORK, "ovf1")))
        r = s3.convert3(req("de_to_3ds", DE_S232, out("ovf2"), template=X3_USER, overflow="sidecar"))
        self.assertTrue(any("rebuilt" in n for n in r.report["notes"]))
        nb, ch = xc3dstats.rebuild(xc3d.transcode(xc3d.unpack(rd(r.main_output)), "wii"), s3.wii_bdat())
        self.assertEqual(ch, [])                                     # the 3DS file holds correct stats

    def test_template_required(self):
        with self.assertRaises(safeio.Refused):
            s3.convert3(req("wii_to_3ds", W150, out("nt1")))
        with self.assertRaises(safeio.Refused):
            s3.convert3(req("3ds_to_de", X3_USER, out("nt2")))


class Lineage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = s3.convert3(req("wii_to_3ds", W150, out("lin_first"), template=X3_USER))

    def test_current_required_with_record(self):
        with self.assertRaises(safeio.Refused):
            s3.convert3(req("3ds_to_wii", X3_GAME_S150, out("lin_a"), record=self.first.sidecar_path))

    def test_different_playthrough_refused(self):
        with self.assertRaises(safeio.Refused):
            s3.convert3(req("3ds_to_wii", X3_USER, out("lin_b"), record=self.first.sidecar_path, no_current=True))

    def test_divergence_needs_explicit_choice(self):
        # 3DS played after the export (game-written s150 save) AND the Wii played too (d6_travel)
        with self.assertRaises(safeio.Refused) as cm:
            s3.convert3(req("3ds_to_wii", X3_GAME_S150, out("lin_c"), record=self.first.sidecar_path,
                            current=W150_LATER))
        self.assertIn("both games were played", str(cm.exception))
        r = s3.convert3(req("3ds_to_wii", X3_GAME_S150, out("lin_d"), record=self.first.sidecar_path,
                            current=W150_LATER, branch="keep_source"))
        self.assertTrue(any("branch" in n for n in r.report["notes"]))

    def test_normal_return_after_3ds_play(self):
        r = s3.convert3(req("3ds_to_wii", X3_GAME_S150, out("lin_e"), record=self.first.sidecar_path, current=W150))
        rec = s3.load_record(r.sidecar_path)[1]
        self.assertEqual(rec["lineage"]["parent_session"], s3.load_record(self.first.sidecar_path)[1]["session_id"])

    def test_tampered_record_refused(self):
        rec = json.loads(rd(self.first.sidecar_path))
        rec["source"]["story"] = 999
        p = os.path.join(WORK, "tampered.record.json")
        with open(p, "w") as f:
            json.dump(rec, f)
        with self.assertRaises(safeio.Refused):
            s3.load_record(p)


class Safety(unittest.TestCase):
    def test_3ds_live_paths_refused(self):
        bad = [os.path.join(WORK, "fake", "Nintendo 3DS", "0" * 32, "0" * 32, "title", "00040000", "0f700100", "data"),
               os.path.join(os.environ.get("APPDATA", "C:\\x"), "Azahar", "sdmc", "x"),
               os.path.join(WORK, "SD", "3ds", "Checkpoint", "saves", "x")]
        for p in bad:
            with self.assertRaises(safeio.Refused, msg=p):
                s3.convert3(req("wii_to_3ds", W150, p, template=X3_USER))

    def test_junction_into_live_folder_refused(self):
        target = os.path.join(WORK, "jt", "Nintendo 3DS")
        os.makedirs(target, exist_ok=True)
        link = os.path.join(WORK, "junction_out")
        if os.path.lexists(link):
            os.rmdir(link)
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True)
        if r.returncode != 0:
            self.skipTest("cannot create a junction here")
        try:
            with self.assertRaises(safeio.Refused):
                s3.convert3(req("wii_to_3ds", W150, os.path.join(link, "new"), template=X3_USER))
        finally:
            os.rmdir(link)

    def test_existing_output_folder_refused(self):
        p = out("exists")
        os.makedirs(p)
        with open(os.path.join(p, "x"), "w") as f:
            f.write("x")
        with self.assertRaises(safeio.Refused):
            s3.convert3(req("wii_to_3ds", W150, p, template=X3_USER))

    def test_atomic_failure_leaves_nothing(self):
        p = out("atomic")

        def fault(stage, detail=""):
            if stage == "rename":
                raise OSError("injected")
        old = safeio._FAULT
        safeio._FAULT = fault
        try:
            with self.assertRaises(Exception):
                s3.convert3(req("wii_to_3ds", W150, p, template=X3_USER))
        finally:
            safeio._FAULT = old
        self.assertFalse(os.path.exists(p))
        self.assertEqual(safeio.leftovers(WORK), [])

    def test_inputs_unchanged(self):
        before = {p: hashlib.sha256(rd(p)).hexdigest() for p in (X3_USER, W150, DE_TPL)}
        s3.convert3(req("wii_to_3ds", W150, out("unch"), template=X3_USER))
        self.assertEqual(before, {p: hashlib.sha256(rd(p)).hexdigest() for p in before})


class CLI(unittest.TestCase):
    def test_refusal_exit_code_and_nothing_written(self):
        p = out("cli_ref")
        self.assertEqual(xcconv3.main(["3ds-to-wii", "--3ds", X3_EMPTY, "--out", p]), 2)
        self.assertFalse(os.path.exists(p))

    def test_cli_and_service_parity(self):
        p1, p2 = out("cli_par1"), out("cli_par2")
        self.assertEqual(xcconv3.main(["wii-to-3ds", "--wii", W150, "--template", X3_USER, "--out", p1]), 0)
        s3.convert3(req("wii_to_3ds", W150, p2, template=X3_USER))
        for rel in ("3ds/monado01", "wii_to_3ds.record.json"):
            self.assertEqual(rd(os.path.join(p1, rel)), rd(os.path.join(p2, rel)))

    def test_2h_commands_pass_through(self):
        self.assertEqual(xcconv3.main(["wii-to-de", "--wii", W150, "--template", DE_TPL, "--out", out("cli_2h"),
                                       "--dry-run"]), 0)

    def test_inspect_validate_3ds(self):
        self.assertEqual(xcconv3.main(["validate", X3_USER]), 0)
        self.assertEqual(xcconv3.main(["inspect", X3_USER]), 0)


if __name__ == "__main__":
    unittest.main()
