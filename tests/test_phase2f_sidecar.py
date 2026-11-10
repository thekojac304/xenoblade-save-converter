"""Phase 2F workstream E: sidecar integrity, lineage, stale / mismatched sidecars, divergent histories, restoration.

Real inputs: monado01 / monado03 (user's Wii saves), user_v10_bfsgame00.sav (user's DE save, another playthrough),
the Wii -> DE conversion of monado01. All progress is SYNTHETIC (tests/p2f_util.py). Runs the real CLI
(xcconv.main) and writes only under work/test_phase2f/sidecar.
"""
import contextlib
import io
import json
import os
import shutil
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2f_util as U  # noqa: E402
import canon  # noqa: E402
import de_to_wii  # noqa: E402
import reimport  # noqa: E402
import sidecar as scmod  # noqa: E402
import xcconv  # noqa: E402

OUT = os.path.join(U.ROOT, "work", "test_phase2f", "sidecar")
T = None
TOL = ("/achievements", "/quest_counters", "/clock", "/characters/1/palette2")


def setUpModule():
    global T
    T = U.tables()
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)


def put(name, data):
    p = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return p


def cli(*args):
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        rc = xcconv.main(list(args))
    return rc, out.getvalue(), err.getvalue()


def de_progress(de, seed):
    """Realistic DE session: new landmark/collectopaedia-range flags, picked-up items, level-ups, money, time."""
    m = U.DE(de)
    for i in range(4):
        m.flag(0xA20 + 300 + seed * 7 + i, 1)
    for gid in U.valid_gids("collectable")[seed * 3:seed * 3 + 3]:
        m.pickup("collectable", gid, 1)
    m.pickup("weapon", U.valid_gids("weapon")[40 + seed], 1)
    m.level_up(2, 1)
    m.money(4321)
    m.play(1800)
    return m.done()


def wii_progress(w, seed):
    m = U.Wii(w)
    for i in range(3):
        m.flag(0xA20 + 900 + seed * 5 + i, 1)
    for gid in U.valid_gids("material")[seed * 2 + 40:seed * 2 + 42]:
        m.pickup("material", gid, 2)
    m.level_up(4, 1)
    m.money(777)
    m.play(2400)
    return m.done()


def add_de_only_item(de):
    m = U.DE(de)
    gid = U.de_only_gids("collectable")[0]
    sl = m.pickup("collectable", gid, 1)
    return m.done(), gid, sl


def count_gid(data, game, box, gid):
    c = (canon.from_wii(data, T) if game == "wii" else canon.from_de(data, T))["shared"]["inventory"][box]
    return sum(1 for r in c.values() if r["gid"] == gid)


class Chain:
    """Run a full chain through the CLI, keeping every artifact."""

    def __init__(self, tag):
        self.d = os.path.join(OUT, tag)
        self.n = 0

    def out(self):
        self.n += 1
        return os.path.join(self.d, f"step{self.n}")


class NormalUse(unittest.TestCase):
    def test_six_step_cycle_through_cli(self):
        """E1 + B3: export, play, re-import, export, play, re-import; a DE-only item stays parked in the sidecar
        through two Wii sessions per cycle and is never duplicated; lineage generation increases; nothing is lost."""
        c = Chain("e1")
        w0 = os.path.join(U.O, "monado01")
        o = c.out()
        rc, so, se = cli("wii-to-de", "--wii", w0, "--template", U.TPL, "--out", o)
        self.assertEqual(rc, 0, se)
        de = U.rd(os.path.join(o, "save_0", "bfsgame00.sav"))
        sc_w2d = os.path.join(o, "wii_to_de.sidecar.json")
        de, gid, _ = add_de_only_item(de_progress(de, 1))       # DE play + a DE-only item
        cur_wii = w0
        for cycle in range(2):
            de_p = put(f"e1/de_played_{cycle}.sav", de)
            o = c.out()
            rc, so, se = cli("de-to-wii", "--de", de_p, "--sidecar", sc_w2d, "--current-wii", cur_wii, "--out", o)
            self.assertEqual(rc, 0, se)
            w = U.rd(os.path.join(o, "monado01"))
            sc_d2w = os.path.join(o, "de_to_wii.sidecar.json")
            info = scmod.load(U.rd(sc_d2w).decode("utf-8"))
            self.assertEqual(info["lineage"]["generation"], 2 + 2 * cycle)
            self.assertIn(gid, [r["gid"] for r in info["deferred"]["de_only_items"]["collectable"].values()])
            self.assertEqual(count_gid(w, "wii", "collectable", gid), 0)
            w = wii_progress(w, 10 + cycle)                     # two Wii sessions (save, reload, play, save)
            w = wii_progress(w, 20 + cycle)
            cur_wii = put(f"e1/wii_played_{cycle}", w)
            o = c.out()
            rc, so, se = cli("wii-to-de", "--wii", cur_wii, "--sidecar", sc_d2w, "--current-de", de_p, "--out", o)
            self.assertEqual(rc, 0, se)
            de = U.rd(os.path.join(o, "save_0", "bfsgame00.sav"))
            sc_w2d = os.path.join(o, "wii_to_de.sidecar.json")
            self.assertEqual(count_gid(de, "de", "collectable", gid), 1)      # restored once, never duplicated
            cw, cd = canon.from_wii(w, T)["shared"], canon.from_de(de, T)["shared"]
            self.assertEqual((cd["money"], cd["story"], cd["play_time_s"]), (cw["money"], cw["story"], cw["play_time_s"]))
            for k in cw["characters"]:
                self.assertEqual(cd["characters"][k]["level"], cw["characters"][k]["level"])
            de = de_progress(de, 3 + cycle)
        sc = scmod.load(U.rd(sc_w2d).decode("utf-8"))
        self.assertEqual(sc["lineage"]["generation"], 5)


class BadSidecars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = os.path.join(OUT, "e2")
        rc, so, se = cli("de-to-wii", "--de", put("e2/de.sav", U.de0()), "--base", os.path.join(U.O, "monado01"),
                         "--same-playthrough", "--out", os.path.join(cls.d, "x"))
        assert rc == 0, se
        cls.sc_path = os.path.join(cls.d, "x", "de_to_wii.sidecar.json")
        cls.sc_text = U.rd(cls.sc_path).decode("utf-8")
        cls.w = put("e2/w_played", wii_progress(U.rd(os.path.join(cls.d, "x", "monado01")), 1))
        cls.de = os.path.join(OUT, "e2", "de.sav")

    def reimport(self, sc_path, *extra):
        o = os.path.join(self.d, f"o{len(os.listdir(self.d))}")
        rc, so, se = cli("wii-to-de", "--wii", self.w, "--sidecar", sc_path, "--current-de", self.de, "--out", o, *extra)
        return rc, se, o

    def bad(self, name, text):
        return put(f"e2/{name}.json", text.encode("utf-8"))

    def test_good_sidecar_works(self):
        rc, se, o = self.reimport(self.sc_path)
        self.assertEqual(rc, 0, se)

    def test_missing_corrupted_and_unsupported(self):
        cases = {"missing": os.path.join(self.d, "nope.json"),
                 "truncated": self.bad("truncated", self.sc_text[:len(self.sc_text) // 2]),
                 "not_json": self.bad("not_json", "hello"),
                 "schema": self.bad("schema", self.sc_text.replace('"xc1-sidecar/1"', '"xc1-sidecar/9"')),
                 "bitflip": self.bad("bitflip", self.sc_text.replace('"generation": 1', '"generation": 2'))}
        for name, p in cases.items():
            rc, se, o = self.reimport(p)
            self.assertEqual(rc, 2, name)
            self.assertIn("nothing was written", se, name)
            self.assertFalse(os.path.exists(o), name)

    def test_internally_inconsistent_sidecars(self):
        """Edits whose integrity hash was recomputed (the hash is not a signature) are caught by consistency checks."""
        def forged(mut):
            sc = json.loads(self.sc_text)
            mut(sc)
            sc["integrity"] = {"sha256": scmod._body_hash(sc)}
            return self.bad("forged", json.dumps(sc))
        muts = {
            "source_hash": lambda s: s["source"].__setitem__("sha256", "0" * 64),
            "session_id": lambda s: s.__setitem__("session_id", "f" * 32),
            "self_parent": lambda s: (s["lineage"].__setitem__("parent_session", s["session_id"]),
                                      s["lineage"].__setitem__("generation", 2)),
            "games": lambda s: s["source"].__setitem__("game", "wii"),
            "snapshot": lambda s: s["snapshots"]["output"].__setitem__("data", "AAAA"),
        }
        for name, m in muts.items():
            with self.assertRaises(scmod.SidecarError, msg=name):
                scmod.load(U.rd(forged(m)).decode("utf-8"))

    def test_wrong_direction_and_missing_current(self):
        o = os.path.join(self.d, "wd")
        rc, so, se = cli("wii-to-de", "--wii", os.path.join(U.O, "monado01"), "--template", U.TPL, "--out", o)
        self.assertEqual(rc, 0, se)
        rc, se, o2 = self.reimport(os.path.join(o, "wii_to_de.sidecar.json"))
        self.assertEqual(rc, 2)
        self.assertIn("this command needs the sidecar of a DE -> Wii export", se)
        o3 = os.path.join(self.d, "nocur")
        rc, so, se = cli("wii-to-de", "--wii", self.w, "--sidecar", self.sc_path, "--out", o3)
        self.assertEqual(rc, 2)
        self.assertIn("--current-de", se)
        self.assertFalse(os.path.exists(o3))

    def test_other_slot_and_other_playthrough(self):
        """A sidecar is matched by content, never by file name: other playthroughs / slots are refused."""
        o = os.path.join(self.d, "foreign")
        rc, so, se = cli("de-to-wii", "--de", put("e2/user_v10.sav", U.rd(os.path.join(U.O, "user_v10_bfsgame00.sav"))),
                         "--base", os.path.join(U.O, "monado03"), "--out", o)
        self.assertEqual(rc, 0, se)
        rc, se, o2 = self.reimport(os.path.join(o, "de_to_wii.sidecar.json"))
        self.assertEqual(rc, 2)
        self.assertIn("does not continue the exported one", se)
        w3 = put("e2/monado03_copy", U.wii03())          # another slot of the user's (scenario 18)
        o4 = os.path.join(self.d, "slot3")
        rc, so, se = cli("wii-to-de", "--wii", w3, "--sidecar", self.sc_path, "--current-de", self.de, "--out", o4)
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(o4))

    def test_altered_wii_save(self):
        """A Wii save edited without fixing checksums is refused; with fixed checksums it is indistinguishable from
        play (documented limitation) and imports as progress."""
        b = bytearray(U.rd(self.w))
        b[0x11F60 + 0x120E8 + 3] ^= 1
        rc, so, se = cli("wii-to-de", "--wii", put("e2/w_bad_crc", bytes(b)), "--sidecar", self.sc_path,
                         "--current-de", self.de, "--out", os.path.join(self.d, "crc"))
        self.assertEqual(rc, 2)
        self.assertIn("checksum", se)


class StaleSidecar(unittest.TestCase):
    def test_old_sidecar_is_refused_even_with_branch(self):
        """E2 'reuse of an old sidecar' (the 2E defect: an item sold in DE came back). Generation 1 sidecar S1, a
        newer export S3 exists; re-importing the newer Wii save with S1 must be refused, with or without --branch."""
        de0, gid, _ = add_de_only_item(U.de0())
        w1, log, dfr = de_to_wii.build(de0, U.wii01(), T, lineage=True)
        s1 = scmod.load(scmod.dumps(scmod.make("de_to_wii", de0, w1, canon.from_de(de0, T), canon.from_wii(w1, T),
                                               deferred=dfr)))
        w1p = wii_progress(w1, 1)
        de2, _ = reimport.wii_to_de_reimport(w1p, s1, T, current_de=de0)
        s2 = scmod.make("wii_to_de", w1p, de2, canon.from_wii(w1p, T), canon.from_de(de2, T), parent=s1)
        m = U.DE(de_progress(de2, 2))                       # DE session: real progress, and the DE-only item is sold
        c = canon.from_de(m.done(), T)["shared"]["inventory"]["collectable"]
        m.remove("collectable", next(sl for sl, r in c.items() if r["gid"] == gid))
        de2s = m.done()
        w3, log3, dfr3 = de_to_wii.build(de2s, scmod.source_image(s2), T, lineage=True)
        s3 = scmod.load(scmod.dumps(scmod.make("de_to_wii", de2s, w3, canon.from_de(de2s, T), canon.from_wii(w3, T),
                                               deferred=dfr3, parent=s2)))
        w3p = wii_progress(w3, 3)
        for branch in (None, "wii"):
            with self.assertRaises(reimport.DivergenceError) as cm:
                reimport.wii_to_de_reimport(w3p, s1, T, current_de=de2s, branch=branch)
            self.assertIn("older than your latest", str(cm.exception))
        good, _ = reimport.wii_to_de_reimport(w3p, s3, T, current_de=de2s)
        self.assertEqual(count_gid(good, "de", "collectable", gid), 0)      # the sold item stays sold
        # the 2E behaviour (no current DE given, user states none is newer) is now an explicit, documented choice
        stale, _ = reimport.wii_to_de_reimport(w3p, s1, T, no_newer_de=True)
        self.assertEqual(count_gid(stale, "de", "collectable", gid), 1)


class Divergence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.de0 = U.de0()
        cls.w0, log, dfr = de_to_wii.build(cls.de0, U.wii01(), T, lineage=True)
        cls.sc = scmod.load(scmod.dumps(scmod.make("de_to_wii", cls.de0, cls.w0, canon.from_de(cls.de0, T),
                                                   canon.from_wii(cls.w0, T), deferred=dfr)))
        # branch W: Wii earns money, materials, a level, flags; branch D: DE earns other things and deletes an item
        cls.wb = wii_progress(cls.w0, 5)
        m = U.DE(de_progress(cls.de0, 6))
        c = canon.from_de(m.done(), T)["shared"]
        cls.deleted = next(sl for sl in sorted(c["inventory"]["collectable"])
                           if ("collectable", sl) not in U.referenced(c))
        m.remove("collectable", cls.deleted)
        cls.db = m.done()

    def test_refused_without_branch(self):
        with self.assertRaises(reimport.DivergenceError):
            reimport.wii_to_de_reimport(self.wb, self.sc, T, current_de=self.db)

    def test_branch_wii_keeps_wii_state_without_contamination(self):
        out, log = reimport.wii_to_de_reimport(self.wb, self.sc, T, current_de=self.db, branch="wii")
        co, cw, cdb = (canon.from_de(out, T)["shared"], canon.from_wii(self.wb, T)["shared"],
                       canon.from_de(self.db, T)["shared"])
        self.assertEqual([d for d in canon.compare(cw, co) if not d[0].startswith(TOL)], [])
        only_de = set(cdb["flags"]) - set(canon.from_de(self.de0, T)["shared"]["flags"])
        self.assertTrue(only_de)
        self.assertFalse(only_de & set(co["flags"]))                      # no DE-branch flag leaked in
        self.assertNotEqual(co["money"], cdb["money"])
        self.assertIn(self.deleted, co["inventory"]["collectable"])       # the DE-branch deletion is not applied

    def test_branch_de_keeps_de_state_without_contamination(self):
        """Mirror case through the CLI: Wii -> DE export, both sides play, de-to-wii needs --branch de."""
        d = os.path.join(OUT, "e3")
        w = os.path.join(U.O, "monado01")
        rc, so, se = cli("wii-to-de", "--wii", w, "--template", U.TPL, "--out", os.path.join(d, "a"))
        self.assertEqual(rc, 0, se)
        de = U.rd(os.path.join(d, "a", "save_0", "bfsgame00.sav"))
        de_b = put("e3/de_b.sav", de_progress(de, 7))
        w_b = put("e3/w_b", wii_progress(U.wii01(), 8))
        sc = os.path.join(d, "a", "wii_to_de.sidecar.json")
        rc, so, se = cli("de-to-wii", "--de", de_b, "--sidecar", sc, "--current-wii", w_b, "--out", os.path.join(d, "b"))
        self.assertEqual(rc, 2)
        self.assertIn("--branch de", se)
        rc, so, se = cli("de-to-wii", "--de", de_b, "--sidecar", sc, "--current-wii", w_b, "--branch", "de",
                         "--out", os.path.join(d, "c"))
        self.assertEqual(rc, 0, se)
        out = U.rd(os.path.join(d, "c", "monado01"))
        co, cd, cwb = (canon.from_wii(out, T)["shared"], canon.from_de(U.rd(de_b), T)["shared"],
                       canon.from_wii(U.rd(w_b), T)["shared"])
        self.assertEqual([x for x in canon.compare(cd, co) if not x[0].startswith(TOL)], [])
        only_w = set(cwb["flags"]) - set(canon.from_wii(U.wii01(), T)["shared"]["flags"])
        self.assertFalse(only_w & set(co["flags"]))

    def test_only_de_exclusive_change_is_kept(self):
        """The current DE save differs from the export only in DE-exclusive fields (a cosmetic): not a divergence,
        and the newer DE-exclusive state is the one re-imported (2E would have reverted it)."""
        b = bytearray(self.de0)
        struct.pack_into("<I", b, U.DE_CHAR + 0x30, 0x2222)
        out, log = reimport.wii_to_de_reimport(self.wb, self.sc, T, current_de=bytes(b))
        self.assertEqual(struct.unpack_from("<I", out, U.DE_CHAR + 0x30)[0], 0x2222)
        self.assertIn("template", log)


class Restoration(unittest.TestCase):
    def test_de_exclusive_state_survives_and_wii_progress_wins(self):
        """E4: Expert Mode (switch, highest level, reserve), cosmetics, DE-only item, DE-only flag, Future Connected
        byte, Noponstones survive; Wii progress on shared items/levels is not overwritten by the sidecar."""
        b = bytearray(U.de0())
        b[0x1490D5] |= 1
        o = U.DE_CHAR + 0x138 * 3                                         # Dunban
        lv = struct.unpack_from("<I", b, o)[0]
        struct.pack_into("<III", b, o + 0xEC, lv + 2, 1234, 55555)       # highest level above active, reserve
        struct.pack_into("<I", b, o + 0x30, 0x77)                         # cosmetic
        struct.pack_into("<I", b, 0x10, 42)                               # Noponstones
        n = 0x3550 - 0xA20
        b[0x50 + 4 * (n >> 5) + (n & 31) // 8] |= 1 << ((n & 31) % 8)    # DE-only flag
        b[0x1270 + 8 * 1100] = 3                                          # Future Connected quest counter byte
        de, gid, _ = add_de_only_item(bytes(b))
        w, log, dfr = de_to_wii.build(de, U.wii01(), T, lineage=True)
        sc = scmod.load(scmod.dumps(scmod.make("de_to_wii", de, w, canon.from_de(de, T), canon.from_wii(w, T),
                                               deferred=dfr)))
        m = U.Wii(w)
        m.level_up(4, 3)                                                  # Dunban passes his highest level on the Wii
        c = canon.from_wii(m.b, T)["shared"]["inventory"]["material"]
        sl = sorted(c)[0]
        mo = U.wii_save.ITEM + U.WBOX["material"][1] + 8 * sl
        m.img.put(mo + 6, "B", min(c[sl]["qty"] + 5, 99))                 # more of an item that existed at export
        w2 = m.done()
        out, log = reimport.wii_to_de_reimport(w2, sc, T, current_de=de)
        self.assertEqual(out[0x1490D5] & 1, 1)
        self.assertEqual(struct.unpack_from("<I", out, 0x10)[0], 42)
        self.assertEqual(struct.unpack_from("<I", out, o + 0x30)[0], 0x77)
        self.assertEqual(struct.unpack_from("<I", out, o)[0], lv + 3)                     # Wii level-up applied
        self.assertEqual(struct.unpack_from("<I", out, o + 0xEC)[0], lv + 3)              # highest follows above
        self.assertEqual(struct.unpack_from("<I", out, o + 0xF4)[0], 55555)               # reserve untouched
        self.assertEqual(out[0x1270 + 8 * 1100], 3)
        self.assertEqual(count_gid(out, "de", "collectable", gid), 1)
        self.assertEqual(canon.from_de(out, T)["shared"]["inventory"]["material"][sl]["qty"], min(c[sl]["qty"] + 5, 99))


if __name__ == "__main__":
    unittest.main()
