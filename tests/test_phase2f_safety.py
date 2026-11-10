"""Phase 2F workstreams F + H: corrupt input, transactional output with failure injection, path safety, CLI behaviour.

Disposable trees only (work/test_phase2f/safety); "live-looking" folders are fakes created there. Real saves are
read, never written. Every refusal must say that nothing was written, exit with code 2 (1 for validate), leave no
output folder and no staging folder, and never print a Python traceback.
"""
import contextlib
import io
import json
import os
import random
import shutil
import struct
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2f_util as U  # noqa: E402
import safeio  # noqa: E402
import wii_save  # noqa: E402
import xcconv  # noqa: E402

OUT = os.path.join(U.ROOT, "work", "test_phase2f", "safety")
XCCONV = os.path.join(U.ROOT, "tools", "xcconv.py")


def setUpModule():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    U.tables()


def cli(*args):
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        rc = xcconv.main(list(args))
    return rc, out.getvalue(), err.getvalue()


def put(name, data):
    p = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return p


def fix_crc(b):
    img = U.de_to_wii.WiiImage(bytes(b))
    U.de_to_wii.fix_crcs(img)
    return bytes(img.b)


def staging_left(folder):
    return [n for n in os.listdir(folder) if n.startswith(safeio.STAGING_PREFIX)] if os.path.isdir(folder) else []


class CorruptInput(unittest.TestCase):
    def refuse(self, args, out, expect_rc=2):
        rc, so, se = cli(*args)
        self.assertEqual(rc, expect_rc, (args, se))
        self.assertNotIn("Traceback", se + so)
        self.assertFalse(os.path.exists(out), out)
        self.assertEqual(staging_left(os.path.dirname(out)), [])
        return se

    def test_wii_corruptions(self):
        w = U.wii01()
        cases = {"truncated_1000": w[:1000], "truncated_half": w[:len(w) // 2], "one_byte_long": w + b"\0",
                 "empty": b"", "wrong_header": b"XXXX" + w[4:], "empty_slot": U.rd(os.path.join(U.O, "monado02")),
                 "crc_flip_game": w[:0xB300] + bytes([w[0xB300] ^ 1]) + w[0xB301:],
                 "crc_flip_item": w[:0x12000] + bytes([w[0x12000] ^ 0x80]) + w[0x12001:],
                 "section_tag_damaged": w[:0xA020] + b"ZZZZ" + w[0xA024:]}
        for name, b in cases.items():
            p = put(f"wii_{name}", b)
            o = os.path.join(OUT, f"o_{name}")
            se = self.refuse(["wii-to-de", "--wii", p, "--template", U.TPL, "--out", o], o)
            self.assertIn("nothing was written", se, name)
            self.refuse(["validate", p], o, expect_rc=1)

    def test_wii_out_of_range_values_with_valid_crc(self):
        """Values the game never writes, with checksums recomputed (a hand-edited save): refused, not repaired."""
        def edit(off, fmt, v):
            b = bytearray(U.wii01())
            struct.pack_into(">" + fmt, b, off, v)
            return fix_crc(b)
        c1 = wii_save.CHAR_BASE + wii_save.CHAR_SIZE * 1
        ir = wii_save.decode_bytes(U.wii01())
        mat = ir["items"]["material"][0]["index"]
        cases = {"level_0": edit(c1 + 0x17C, "I", 0), "level_150": edit(c1 + 0x17C, "I", 150),
                 "exp_over_next": edit(c1 + 0x2A4, "I", 10 ** 8), "coins_5000": edit(c1 + 0x284, "I", 5000),
                 "party_guest": edit(wii_save.PARTY, "H", 9),
                 "item_bad_id": edit(wii_save.ITEM + 0x10B18 + 8 * mat, "I",
                                     4095 << 20 | 11 << 16 | (ir["items"]["material"][0]["header"]["row"] << 5)),
                 "item_qty_0": edit(wii_save.ITEM + 0x10B18 + 8 * mat + 6, "B", 0),
                 "equip_dangling": edit(c1 + 0x1C + 2 * 5, "H", 149)}
        for name, b in cases.items():
            p = put(f"wii_oor_{name}", b)
            o = os.path.join(OUT, f"oor_{name}")
            self.refuse(["wii-to-de", "--wii", p, "--template", U.TPL, "--out", o], o)

    def test_de_corruptions_and_invalid_states(self):
        de = U.de0()

        def edit(off, fmt, *v):
            b = bytearray(de)
            struct.pack_into("<" + fmt, b, off, *v)
            return bytes(b)
        lay = {"truncated": de[:5000], "long": de + b"\0", "version_mismatch": edit(0, "I", 7),
               "v7": U.rd(os.path.join(U.PUBLIC, "s232_207aed635e_bfsgame00.sav")),
               "level_0": edit(U.DE_CHAR, "I", 0), "level_100": edit(U.DE_CHAR, "I", 100),
               "exp_over": edit(U.DE_CHAR + 4, "I", 10 ** 8), "party_99": edit(0x1526D8, "H", 99),
               "equip_dangling": edit(U.DE_CHAR + 0x14 + 4 * 5, "HH", 499, 2),
               "gem_dangling": edit(0x3B10 + 0x30 * 0 + 0x18, "HH", 498, 3),
               "story_0": edit(0xDF0, "H", 0), "story_9999": edit(0xDF0, "H", 9999),
               "fc_map": edit(0x149C00, "I", 0x00010051),
               "quest_bad_byte": edit(0x1270 + 8 * 449, "B", 0x80)}
        for name, b in lay.items():
            p = put(f"de_{name}.sav", b)
            o = os.path.join(OUT, f"d_{name}")
            se = self.refuse(["de-to-wii", "--de", p, "--base", os.path.join(U.O, "monado01"), "--out", o], o)
            self.assertIn("nothing was written", se, name)

    def test_random_bit_flips(self):
        """F1 fuzz (seeded): 60 random flips of 1..8 bits in each format. Every outcome is a clean success (with a
        verified output) or a clean refusal - never a crash (exit 3), a traceback or a partial output."""
        rng = random.Random(2026)
        stats = {"ok": 0, "refused": 0}
        for i in range(60):
            game = "wii" if i % 2 == 0 else "de"
            b = bytearray(U.wii01() if game == "wii" else U.de0())
            for _ in range(rng.randint(1, 8)):
                pos = rng.randrange(len(b))
                b[pos] ^= 1 << rng.randrange(8)
            p = put(f"fuzz/{i}_{game}", bytes(b))
            o = os.path.join(OUT, "fuzz", f"o{i}")
            args = ["wii-to-de", "--wii", p, "--template", U.TPL, "--out", o] if game == "wii" else \
                ["de-to-wii", "--de", p, "--base", os.path.join(U.O, "monado01"), "--out", o]
            rc, so, se = cli(*args)
            self.assertIn(rc, (0, 2), (i, se))
            self.assertNotIn("Traceback", se)
            if rc == 0:
                stats["ok"] += 1
                m = json.loads(U.rd(os.path.join(o, "manifest.json")))
                for rel, e in m["outputs"].items():
                    self.assertEqual(safeio.sha(U.rd(os.path.join(o, rel))), e["sha256"])
            else:
                stats["refused"] += 1
                self.assertFalse(os.path.exists(o))
        U.save_fixture("F1_bitflip_fuzz_summary", {"seed": 2026, "cases": 60, **stats})


class Transactional(unittest.TestCase):
    def args(self, o):
        return ["wii-to-de", "--wii", os.path.join(U.O, "monado01"), "--template", U.TPL, "--out", o]

    def test_failure_injection_every_stage(self):
        """F2: a failure while staging, writing, flushing, verifying or renaming leaves no output and no staging."""
        stages = [("write", "save_0/bfsgame00.sav"), ("write", "wii_to_de.sidecar.json"), ("write", "manifest.json"),
                  ("flush", "save_0/bfssystem.sav"), ("verify", "manifest.json"), ("rename", None)]
        for st, rel in stages:
            o = os.path.join(OUT, "tx", f"{st}_{(rel or 'x').replace('/', '_')}")

            def fault(stage, detail, st=st, rel=rel):
                if stage == st and (rel is None or detail == rel):
                    raise OSError(f"injected failure at {stage} {detail}")
            safeio._FAULT = fault
            try:
                rc, so, se = cli(*self.args(o))
            finally:
                safeio._FAULT = None
            self.assertEqual(rc, 3, (st, rel, se))
            self.assertIn("nothing was written", se)
            self.assertFalse(os.path.exists(o), (st, rel))
            self.assertEqual(staging_left(os.path.dirname(o)), [], (st, rel))

    def test_manifest_matches_written_bytes_and_no_overwrite(self):
        o = os.path.join(OUT, "tx", "good")
        rc, so, se = cli(*self.args(o))
        self.assertEqual(rc, 0, se)
        m = json.loads(U.rd(os.path.join(o, "manifest.json")))
        self.assertEqual(set(m["outputs"]) | {"manifest.json"}, {os.path.relpath(os.path.join(dp, f), o).replace("\\", "/")
                                                                  for dp, _, fs in os.walk(o) for f in fs})
        for rel, e in m["outputs"].items():
            self.assertEqual(safeio.sha(U.rd(os.path.join(o, rel))), e["sha256"])
        self.assertEqual(m["inputs"]["wii"]["sha256"], safeio.sha(U.wii01()))
        before = {f: safeio.sha(U.rd(os.path.join(o, "save_0", f))) for f in os.listdir(os.path.join(o, "save_0"))}
        rc, so, se = cli(*self.args(o))                       # same folder again: refused, nothing touched
        self.assertEqual(rc, 2)
        self.assertEqual(before, {f: safeio.sha(U.rd(os.path.join(o, "save_0", f)))
                                  for f in os.listdir(os.path.join(o, "save_0"))})
        empty = os.path.join(OUT, "tx", "empty_ok")
        os.makedirs(empty)
        self.assertEqual(cli(*self.args(empty))[0], 0)         # an existing EMPTY folder is accepted

    def test_interrupted_run_recovery(self):
        """A crash can only leave a staging folder; the next run is unaffected and cleanup-staging removes it."""
        d = os.path.join(OUT, "tx", "crash")
        os.makedirs(os.path.join(d, safeio.STAGING_PREFIX + "abc", "save_0"))
        put("tx/crash/" + safeio.STAGING_PREFIX + "abc/save_0/bfsgame00.sav", b"partial")
        rc, so, se = cli(*self.args(os.path.join(d, "out")))
        self.assertEqual(rc, 0, se)
        rc, so, se = cli("cleanup-staging", d)
        self.assertEqual(rc, 0)
        self.assertEqual(staging_left(d), [])
        self.assertTrue(os.path.isfile(os.path.join(d, "out", "save_0", "bfsgame00.sav")))

    def test_dry_run_and_report(self):
        o = os.path.join(OUT, "tx", "dry")
        rep = os.path.join(OUT, "tx", "dry_report.json")
        rc, so, se = cli(*self.args(o), "--dry-run", "--report", rep)
        self.assertEqual(rc, 0, se)
        self.assertFalse(os.path.exists(o))
        self.assertFalse(os.path.exists(rep))
        rc, so, se = cli(*self.args(o), "--report", rep)
        self.assertEqual(rc, 0, se)
        self.assertTrue(json.loads(U.rd(rep))["written"])


class PathSafety(unittest.TestCase):
    def fake_tree(self, name, marker):
        root = os.path.join(OUT, "paths", name)
        os.makedirs(root, exist_ok=True)
        if marker:
            put(os.path.relpath(os.path.join(root, marker), OUT), b"x")
        return root

    def refused(self, o):
        rc, so, se = cli("wii-to-de", "--wii", os.path.join(U.O, "monado01"), "--template", U.TPL, "--out", o)
        self.assertEqual(rc, 2, se)
        self.assertFalse(os.path.exists(o))
        return se

    def test_live_markers_traversal_and_case(self):
        base = os.path.join(OUT, "paths")
        self.refused(os.path.join(base, "Dolphin", "User", "Wii", "x"))
        self.refused(os.path.join(base, "dOLPHIN", "uSER", "wII", "x"))                       # case alias
        self.refused(os.path.join(base, "a", "..", "Dolphin", "User", "Wii", "y"))              # traversal
        self.refused(os.path.join(base, "nand", "title", "00010000", "53583445", "data"))
        for marker in ("xcde.exe", os.path.join("build", "xcde.exe"), "Dolphin.exe", "portable.txt", "xcde.ini"):
            root = self.fake_tree(marker.replace(os.sep, "_"), marker)
            se = self.refused(os.path.join(root, "save", "save_0", "out"))
            self.assertIn("installation", se)

    def test_junction_and_symlink_into_live_tree(self):
        live = os.path.join(OUT, "paths", "fake", "Dolphin", "User", "Wii")
        os.makedirs(live, exist_ok=True)
        j = os.path.join(OUT, "paths", "innocent_junction")
        r = subprocess.run(["cmd", "/c", "mklink", "/J", j, live], capture_output=True)
        if r.returncode == 0:
            self.refused(os.path.join(j, "o"))
            self.assertEqual(os.listdir(live), [])
        inst = self.fake_tree("inst", "xcde.exe")
        s = os.path.join(OUT, "paths", "innocent_link")
        try:
            os.symlink(inst, s, target_is_directory=True)
        except OSError:
            self.skipTest("symbolic links need Developer Mode / admin on this Windows; junction case covered")
        self.refused(os.path.join(s, "o"))

    def test_output_folder_itself_a_junction(self):
        target = os.path.join(OUT, "paths", "jt_target")
        os.makedirs(target, exist_ok=True)
        j = os.path.join(OUT, "paths", "jt")
        if subprocess.run(["cmd", "/c", "mklink", "/J", j, target], capture_output=True).returncode:
            self.skipTest("mklink /J unavailable")
        rc, so, se = cli("wii-to-de", "--wii", os.path.join(U.O, "monado01"), "--template", U.TPL, "--out", j)
        self.assertEqual(rc, 2, se)
        self.assertEqual(os.listdir(target), [])

    def test_unexpected_working_directory(self):
        """The packaged CLI finds its modules and tables from any cwd; relative paths are relative to the cwd."""
        cwd = os.path.join(OUT, "paths", "elsewhere")
        os.makedirs(cwd, exist_ok=True)
        shutil.copyfile(os.path.join(U.O, "monado01"), os.path.join(cwd, "w"))
        r = subprocess.run([sys.executable, XCCONV, "wii-to-de", "--wii", "w", "--template", U.TPL, "--out", "rel_out"],
                           cwd=cwd, capture_output=True, text=True, env=dict(os.environ, XCCONV_DATA=os.path.join(U.ROOT, "data")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(cwd, "rel_out", "save_0", "bfsgame00.sav")))

    def test_slot_names(self):
        for slot in ("00/../../x", "..", "0", "000", "aa", "/abs"):
            o = os.path.join(OUT, "paths", "slot_" + str(abs(hash(slot)) % 1000))
            rc, so, se = cli("wii-to-de", "--wii", os.path.join(U.O, "monado01"), "--template", U.TPL, "--out", o,
                             "--slot", slot)
            self.assertEqual(rc, 2, slot)
        for slot in ("monado04", "../monado01", os.path.join(OUT, "x"), "monado01/x"):
            o = os.path.join(OUT, "paths", "wslot_" + str(abs(hash(slot)) % 1000))
            rc, so, se = cli("de-to-wii", "--de", put("paths/de.sav", U.de0()), "--base", os.path.join(U.O, "monado01"),
                             "--out", o, "--slot", slot)
            self.assertEqual(rc, 2, slot)
            self.assertFalse(os.path.exists(o))


class CommandLine(unittest.TestCase):
    def test_help_lists_every_command(self):
        r = subprocess.run([sys.executable, XCCONV, "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for c in ("inspect", "validate", "wii-to-de", "de-to-wii", "roundtrip-check", "compatibility-check",
                  "sidecar-info", "cleanup-staging", "--current-de", "--no-current-wii", "Exit codes"):
            self.assertIn(c, r.stdout)
        for c in ("wii-to-de", "de-to-wii", "cleanup-staging"):
            r = subprocess.run([sys.executable, XCCONV, c, "--help"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)

    def test_clear_messages(self):
        o = os.path.join(OUT, "cmd", "x")
        rc, so, se = cli("wii-to-de", "--wii", os.path.join(U.O, "monado01"), "--out", o)
        self.assertIn("--template", se)
        rc, so, se = cli("wii-to-de", "--wii", os.path.join(OUT, "missing"), "--template", U.TPL, "--out", o)
        self.assertIn("file not found", se)
        rc, so, se = cli("de-to-wii", "--de", put("cmd/de.sav", U.de0()), "--base", os.path.join(U.O, "monado01"),
                         "--out", o)
        self.assertEqual(rc, 0, se)
        self.assertIn("keep this sidecar", so)
        rc, so, se = cli("inspect", os.path.join(U.O, "monado01"))
        self.assertEqual((rc, json.loads(so)["story"]), (0, 150))
        rc, so, se = cli("validate", os.path.join(U.O, "monado01"))
        self.assertEqual(rc, 0)
        rc, so, se = cli("roundtrip-check", "--wii", os.path.join(U.O, "monado01"), "--template", U.TPL)
        self.assertEqual((rc, json.loads(so)["byte_identical"]), (0, True))


if __name__ == "__main__":
    unittest.main()
