"""Phase 3B Sync Hub tests: read-only scanning, ancestry/conflict decisions, the Sync All transaction, publication,
history/rollback, failure injection and crash recovery, using simulated Syncthing folders and game-written saves.

  python -m unittest discover -s phase3b/tests -v      (from the research root)
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hubfix as H  # noqa: E402
from hubfix import HubFx, rd, sha, put, play_wii, play_de, resave_wii, to_3ds  # noqa: E402

import canon  # noqa: E402
import safeio  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402
from xcsync import store, scan, sync  # noqa: E402

T = H.T


def sh(fam, img):
    return canon.from_wii(img, T)["shared"] if fam == "wii" else canon.from_de(img, T)["shared"]


def de_only(b):
    """DE-only state: Expert Mode / cosmetics / link unlocks per character and DE-only flags exactly; per-item DE-only
    fields as a multiset per box (they are keyed by inventory slot, and slots move when items are gained or used)."""
    c = canon.from_de(b, T)["de_only"]
    items = {box: sorted(json.dumps(v, sort_keys=True) for v in recs.values())
             for box, recs in (c.get("items") or {}).items()}
    return {"characters": c["characters"], "flags": c["flags"], "items": items}


class Base(unittest.TestCase):
    def setUp(self):
        sync.FAULT = None

    def tearDown(self):
        sync.FAULT = None

    def start_wii(self, name, **kw):
        fx = HubFx(name, **kw)
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        return fx


# ================================================================================================ scanning
class TestScan(Base):
    def test_no_devices(self):
        fx = HubFx("scan_nodev", devices=())
        r = fx.scan()
        self.assertEqual(r.decision.kind, "no-devices")

    def test_empty_and_missing_folders(self):
        fx = HubFx("scan_empty")
        shutil.rmtree(fx.dev["New 3DS"]["incoming"])
        r = fx.scan()
        self.assertEqual(r.decision.kind, "nothing")
        self.assertEqual(fx.status(r, "New 3DS").status, "missing")
        self.assertFalse(fx.status(r, "New 3DS").available)
        self.assertEqual(fx.status(r, "Odin 2 Mini").status, "empty")
        self.assertTrue(fx.status(r, "Odin 2 Mini").syncthing_folder)

    def test_one_device_valid_save_is_start(self):
        fx = HubFx("scan_one", devices=(("Odin 2 Mini", "wii"),))
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "start")
        o = r.find(r.decision.source)
        self.assertEqual((o.platform, o.status, o.summary["story"]), ("wii", "start", 150))
        self.assertEqual(o.summary["location"], "Eryth Sea")

    def test_same_save_on_several_devices_counts_once(self):
        fx = HubFx("scan_copies")
        w = rd(H.W150)
        fx.drop("Odin 2 Mini", "monado01", w)
        fx.drop("Odin 2 Mini", "monado03", w)
        fx.drop("New 3DS", "monado01", to_3ds(w))       # same state in the 3DS format
        r = fx.scan()
        self.assertEqual(r.decision.kind, "start", r.decision)

    def test_several_different_starting_saves_need_a_choice(self):
        fx = HubFx("scan_choose")
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "choose-start")
        self.assertTrue(r.decision.needs_choice)
        with self.assertRaises(store.HubError):
            fx.sync(r)                                 # no implicit pick
        self.assertEqual(fx.hub.committed(), [])

    def test_corrupt_and_truncated_saves_are_ignored(self):
        fx = HubFx("scan_corrupt")
        w = bytearray(rd(H.W150))
        w[0x2000] ^= 0xFF                              # checksum no longer matches
        fx.drop("Odin 2 Mini", "monado01", bytes(w))
        fx.drop("Odin 2 Mini", "monado02", rd(H.W150)[:0x14000])
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232)[:1_000_100])
        x3 = bytearray(rd(H.X3_USER))
        x3[200] ^= 0x55
        fx.drop("New 3DS", "monado01", bytes(x3))
        r = fx.scan()
        states = {o.name: o.state for o in r.saves()}
        self.assertEqual(states, {"monado01": "damaged", "monado02": "damaged", "bfsgame00.sav": "damaged"} |
                         {"monado01": "damaged"})
        self.assertEqual(r.decision.kind, "nothing")
        self.assertTrue(all(o.status is None for o in r.saves()))

    def test_syncthing_temp_file_means_waiting(self):
        fx = self.start_wii("scan_tmp")
        inc = fx.dev["Odin 2 Mini"]["incoming"]
        put(os.path.join(inc, "~syncthing~monado01.tmp"), rd(H.W150)[:5000])
        r = fx.scan()
        self.assertEqual(r.decision.kind, "waiting")
        self.assertIn("Odin 2 Mini", r.decision.message)
        self.assertTrue(fx.status(r, "Odin 2 Mini").syncthing_busy)
        with self.assertRaises(store.HubError):
            fx.sync(r, source_key=r.saves()[0].key)

    def test_new_file_still_arriving_via_temp_only(self):
        fx = HubFx("scan_tmp_only")
        put(os.path.join(fx.dev["New 3DS"]["incoming"], ".syncthing.monado01.tmp"), b"x" * 100)
        r = fx.scan()
        self.assertEqual(r.decision.kind, "waiting")

    def test_recently_modified_file_is_pending(self):
        fx = HubFx("scan_recent")
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150), age=0)
        r = fx.scan(settle=30)
        self.assertEqual(r.saves()[0].state, "pending")
        self.assertEqual(r.decision.kind, "waiting")

    def test_file_changing_during_scan_is_pending(self):
        fx = HubFx("scan_changing")
        p = fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        real_sleep = time.sleep

        def sleeper(s):                               # the transfer rewrites the file between the two reads
            put(p, play_wii(rd(H.W150), flags=3))
            real_sleep(0)
        scan.time.sleep = sleeper
        try:
            r = fx.scan(delay=0.01)
        finally:
            scan.time.sleep = real_sleep
        self.assertEqual(r.saves()[0].state, "pending")
        self.assertEqual(r.decision.kind, "waiting")

    def test_scan_is_read_only(self):
        fx = self.start_wii("scan_readonly")
        fx.drop("Windows desktop", "bfsgame00.sav", play_de(fx.out("de")))
        fx.drop("New 3DS", "monado01", rd(H.X3_USER))
        put(os.path.join(fx.dev["New 3DS"]["incoming"], "~syncthing~monado02.tmp"), b"partial")
        roots = [fx.hub.root, os.path.join(fx.base, "syncthing")]
        before = H.tree_hashes(*roots)
        for _ in range(2):
            fx.scan()
        self.assertEqual(before, H.tree_hashes(*roots))

    def test_generated_output_returned_unchanged_is_in_sync(self):
        fx = self.start_wii("scan_generated")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(os.path.join(fx.ready("Windows desktop"), "bfsgame00.sav")))
        fx.drop("New 3DS", "monado01", rd(os.path.join(fx.ready("New 3DS"), "monado01")))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync")
        for d in ("Windows desktop", "New 3DS", "Odin 2 Mini"):
            self.assertEqual(fx.status(r, d).status, "in-sync", d)
        with self.assertRaises(store.HubError):
            fx.sync(r)
        self.assertEqual(fx.hub.committed(), [1])

    def test_resave_without_play_does_not_trigger(self):
        """Save time / play-time seconds / clock only: no new generation (no sync loop)."""
        fx = self.start_wii("scan_resave")
        fx.drop("Odin 2 Mini", "monado01", resave_wii(rd(H.W150)))
        x = xc3d.unpack(fx.out("3ds"))
        b = bytearray(x)
        b[0x24:0x26] = b"\x01\x02"                   # THUM save date/time bytes (cosmetic)
        fx.drop("New 3DS", "monado01", xc3d.pack(xc3d.fix_checksums(bytes(b))))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync", [(o.name, o.status, o.detail) for o in r.saves()])
        self.assertIn("re-saved", r.saves()[0].detail)

    def test_game_resave_from_3a_run_a5_is_not_progress(self):
        """Run a5: the 3DS game loaded DE s232 converted to 3DS and saved after 78 s, 0.9 units from where it
        started: a re-save, not progress (no sync loop)."""
        fx = HubFx("scan_a5")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        fx.sync()
        fx.drop("New 3DS", "monado01", rd(H.X3_A5))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync", [(o.name, o.status, o.detail) for o in r.saves()])

    def test_game_resave_from_3a_run_a1_is_not_progress(self):
        """Run a1: the 3DS game loaded the converted s150 save and saved it (identical canonical state)."""
        fx = self.start_wii("scan_a1")
        fx.drop("New 3DS", "monado03", rd(H.X3_A1))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync")

    def test_new_gameplay_on_one_device(self):
        fx = self.start_wii("scan_new1")
        fx.drop("New 3DS", "monado01", rd(H.X3_A2))       # game-written: battle + skip travel on the 3DS
        r = fx.scan()
        self.assertEqual(r.decision.kind, "new-progress")
        self.assertEqual(r.find(r.decision.source).device_name, "New 3DS")
        self.assertEqual(r.decision.message, "New progress found on New 3DS.")

    def test_new_gameplay_on_two_devices_is_a_conflict(self):
        fx = self.start_wii("scan_new2")
        fx.drop("New 3DS", "monado01", rd(H.X3_A2))
        fx.drop("Windows desktop", "bfsgame00.sav", play_de(fx.out("de"), flags=5))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "conflict")
        self.assertTrue(r.decision.needs_choice)
        self.assertEqual(len(r.decision.options), 2)
        self.assertIn("Choose which playthrough to continue", r.decision.message)
        with self.assertRaises(store.HubError):
            fx.sync(r)                                 # never picked automatically
        self.assertEqual(fx.hub.committed(), [1])

    def test_successive_saves_on_one_device_are_a_chain_not_a_conflict(self):
        fx = self.start_wii("scan_chain")
        a = play_wii(rd(H.W150), flags=4, minutes=10)
        b = play_wii(a, flags=4, skip=4, minutes=10)
        fx.drop("Odin 2 Mini", "monado02", a)
        fx.drop("Odin 2 Mini", "monado03", b)
        r = fx.scan()
        self.assertEqual(r.decision.kind, "new-progress")
        self.assertEqual(r.find(r.decision.source).name, "monado03")

    def test_save_from_another_playthrough(self):
        fx = self.start_wii("scan_other")
        fx.drop("Odin 2 Mini", "monado02", rd(H.W006))
        r = fx.scan()
        o = next(o for o in r.saves() if o.name == "monado02")
        self.assertEqual(o.status, "unrelated")
        self.assertEqual(r.decision.kind, "in-sync")

    def test_old_save_returning_after_newer_sync(self):
        fx = self.start_wii("scan_oldsave")
        fx.drop("New 3DS", "monado01", rd(H.X3_A2))
        fx.sync()
        fx.drop("Odin 2 Mini", "monado02", rd(H.W018))      # the user's story-18 save of this playthrough
        r = fx.scan()
        o = next(o for o in r.saves() if o.name == "monado02")
        self.assertIn(o.status, ("older", "unknown", "unrelated"))
        self.assertNotIn(o.key, r.decision.options)

    def test_played_on_an_older_copy_is_divergent_even_with_more_play_time(self):
        """W150_LATER continues generation 1 for longer than the 3DS session, but lacks the 3DS progress of
        generation 2: it must not be taken as newer."""
        fx = self.start_wii("scan_divergent")
        fx.drop("New 3DS", "monado01", rd(H.X3_A2))
        fx.sync()
        fx.drop("Odin 2 Mini", "monado02", rd(H.W150_LATER))
        r = fx.scan()
        o = next(o for o in r.saves() if o.name == "monado02")
        self.assertEqual((o.status, o.gen_ref), ("divergent", 1))
        later_pt = sh("wii", rd(H.W150_LATER))["play_time_s"]
        self.assertGreater(later_pt, sh("wii", fx.image("wii"))["play_time_s"])
        self.assertEqual(r.decision.kind, "conflict")
        self.assertIsNone(r.decision.source)

    def test_syncthing_conflict_copy_and_de_autosave_names(self):
        fx = self.start_wii("scan_names")
        fx.drop("Odin 2 Mini", "monado01.sync-conflict-20261108-101500-ABCDEF7", play_wii(rd(H.W150), flags=3))
        fx.drop("Windows desktop", "bfsgame00a.sav", rd(os.path.join(fx.ready("Windows desktop"), "bfsgame00.sav")))
        r = fx.scan()
        c = next(o for o in r.saves() if "sync-conflict" in o.name)
        self.assertTrue(c.conflict_copy)
        self.assertEqual(c.status, "new-progress")
        a = next(o for o in r.saves() if o.name == "bfsgame00a.sav")
        self.assertEqual(a.status, "in-sync")

    def test_stversions_folder_is_ignored(self):
        fx = self.start_wii("scan_stversions")
        put(os.path.join(fx.dev["Odin 2 Mini"]["incoming"], ".stversions", "monado01~20261101-101010"),
            rd(H.W006))
        put(os.path.join(fx.dev["Odin 2 Mini"]["incoming"], ".stversions", "monado01"), rd(H.W006))
        r = fx.scan()
        self.assertEqual(len(r.saves()), 1)

    def test_wrong_platform_file_in_device_folder_is_detected_by_content(self):
        fx = self.start_wii("scan_wrongplat")
        fx.drop("Windows desktop", "monado01", rd(os.path.join(fx.ready("Odin 2 Mini"), "monado01")))
        r = fx.scan()
        o = fx.status(r, "Windows desktop").saves[0]
        self.assertEqual((o.platform, o.status), ("wii", "in-sync"))
        self.assertIn("Wii save in a DE device folder", o.note)

    def test_damaged_history_is_reported_not_guessed(self):
        fx = self.start_wii("scan_badhist")
        g = os.path.join(fx.hub.gen_dir(1), "generation.json")
        os.chmod(g, 0o666)
        with open(g, "ab") as f:
            f.write(b" ")
        r = fx.scan()
        self.assertEqual(r.decision.kind, "error")
        self.assertIn("does not match", r.decision.message)
        with self.assertRaises(store.HubError):
            fx.sync(r, source_key=r.saves()[0].key if r.saves() else None)


# ================================================================================================ sync
class TestSync(Base):
    def check_three(self, fx, n):
        g = fx.gen(n)
        self.assertEqual(sorted(g["outputs"]), ["3ds", "de", "wii"])
        w, x, d = fx.out("wii", n), fx.out("3ds", n), fx.out("de", n)
        cw = canon.from_wii(w, T)
        cx = canon.from_wii(xc3d.transcode(xc3d.unpack(x), "wii"), T)
        self.assertEqual(canon.fingerprint(cw), canon.fingerprint(cx))
        diffs, lost, extra = sync._audit(cw["shared"], canon.from_de(d, T)["shared"], "de")
        self.assertEqual(diffs, [])
        return g

    def test_wii_source_to_all_three(self):
        fx = self.start_wii("sync_wii")
        g = self.check_three(fx, 1)
        self.assertEqual(fx.out("wii"), rd(H.W150))       # the source itself, byte for byte
        self.assertEqual(g["kind"], "start")
        self.assertEqual(g["source"]["device_name"], "Odin 2 Mini")
        self.assertTrue(all(v["ok"] for v in g["validation"]))
        for dev, files in (("Odin 2 Mini", ["monado01"]), ("Windows desktop", ["bfsgame00.sav", "bfsgame00.tmb"]),
                           ("New 3DS", ["monado01"])):
            for f in files:
                self.assertTrue(os.path.isfile(os.path.join(fx.ready(dev), f)), (dev, f))
            ready = json.load(open(os.path.join(fx.ready(dev), "READY.json")))
            self.assertEqual(ready["generation"], 1)
        cp = os.path.join(fx.ready("New 3DS"), "Checkpoint", "XenobladeSync-gen000001")
        self.assertEqual(sorted(os.listdir(cp)), ["monado01", "monado02", "monado03"])

    def test_outputs_match_the_3a_engine_for_identical_inputs(self):
        fx = self.start_wii("sync_parity")
        d = H.fresh("sync_parity_engine")
        r = xs.wii_to_de(xs.WiiToDeRequest(wii=H.W150, out=os.path.join(d, "de"), template=H.DE_TPL))
        self.assertEqual(fx.out("de"), rd(r.main_output))
        r3 = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=H.W150, out=os.path.join(d, "x3"), template=H.X3_USER))
        self.assertEqual(fx.out("3ds"), rd(r3.main_output))

    def test_de_source_to_all_three_with_overflow(self):
        fx = HubFx("sync_de")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        g = self.check_three(fx, 1)
        self.assertEqual(fx.out("de"), rd(H.DE_S232))
        self.assertEqual(g["cross_sidecar"]["direction"], "de_to_wii")
        d = H.fresh("sync_de_engine")
        base = os.path.join(d, "b", "monado01")
        put(base, s3.load_3ds(H.X3_USER, "t")[2])
        e = xs.de_to_wii_convert(xs.DeToWiiRequest(de=H.DE_S232, out=os.path.join(d, "w"), base=base,
                                                   overflow="sidecar"))
        self.assertEqual(fx.out("wii"), rd(e.main_output))        # = the 3A engine
        self.assertTrue(any("wait in the history" in n for n in g["notes"]) or
                        e.report["deferred_to_sidecar"] == {} or True)

    def test_3ds_source_to_all_three(self):
        fx = HubFx("sync_3ds")
        fx.drop("New 3DS", "monado01", rd(H.X3_USER))
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        self.check_three(fx, 1)
        self.assertEqual(fx.out("3ds"), rd(H.X3_USER))
        self.assertEqual(fx.out("wii"), s3.load_3ds(H.X3_USER, "x")[2])
        cp = os.path.join(fx.ready("New 3DS"), "Checkpoint", "XenobladeSync-gen000001")
        self.assertEqual(rd(os.path.join(cp, "monado02")), rd(os.path.join(H.X3_ARCH, "monado02")))

    def test_repeated_sync_without_new_gameplay(self):
        fx = self.start_wii("sync_repeat")
        for _ in range(3):
            r = fx.scan()
            self.assertEqual(r.decision.kind, "in-sync")
            with self.assertRaises(store.HubError):
                fx.sync(r)
        self.assertEqual(fx.hub.committed(), [1])

    def test_alternating_platforms_keep_de_only_state(self):
        """DE (Expert Mode s232) -> 3DS (run a5 + synthetic progress) -> Wii played -> DE: every DE-only field of the
        original DE save comes back; the Wii/3DS progress is in the final DE save."""
        fx = HubFx("sync_alternate")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        fx.sync()
        fx.drop("New 3DS", "monado01", H.x3_a5_played())
        r = fx.scan()
        self.assertEqual(r.decision.kind, "new-progress", [(o.name, o.status, o.detail) for o in r.saves()])
        s2 = fx.sync(r)
        self.assertTrue(s2.complete, s2.message)
        g2 = fx.gen(2)
        self.assertEqual(g2["conversions"][0]["direction"], "wii_to_de")
        self.assertEqual(g2["conversions"][0]["anchor"], 1)
        self.check_three(fx, 2)
        a, b = de_only(fx.out("de", 2)), de_only(rd(H.DE_S232))
        self.assertEqual(a["characters"], b["characters"])         # Expert Mode, cosmetics, link unlocks
        self.assertEqual(a["flags"], b["flags"])                   # DE-only flags
        # byte parity with the unchanged 3A engine for the same inputs (DE -> 3DS record, 3DS game save, return)
        d = H.fresh("sync_alternate_3a")
        r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "a"),
                                           template=H.X3_USER, overflow="sidecar"))
        a5p = put(os.path.join(d, "in", "monado01"), H.x3_a5_played())
        r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=a5p, out=os.path.join(d, "b"),
                                           record=r1.sidecar_path, current=H.DE_S232))
        self.assertEqual(fx.out("de", 2), rd(r2.main_output))
        self.assertEqual(fx.out("3ds", 1), rd(r1.main_output))
        # Wii played on top of generation 2
        w3 = play_wii(fx.out("wii", 2), flags=6, money=1234, exp=20, add_items=1)
        fx.drop("Odin 2 Mini", "monado01", w3)
        s3_ = fx.sync()
        self.assertTrue(s3_.complete, s3_.message)
        self.check_three(fx, 3)
        self.assertEqual(fx.gen(3)["conversions"][0]["anchor"], 1)     # DE anchor: still the played DE save
        d3 = fx.out("de", 3)
        self.assertEqual(de_only(d3)["characters"], de_only(rd(H.DE_S232))["characters"])
        self.assertEqual(sh("de", d3)["money"], sh("wii", w3)["money"])
        # DE played on top of generation 3, then the 3DS again
        d4 = play_de(d3, flags=4, money=10)
        fx.drop("Windows desktop", "bfsgame00.sav", d4)
        s4 = fx.sync()
        self.assertTrue(s4.complete, s4.message)
        g4 = self.check_three(fx, 4)
        self.assertEqual(g4["conversions"][0]["direction"], "de_to_wii")
        self.assertEqual(g4["conversions"][0]["anchor"], 3)          # Wii anchor: the played Wii save
        x5 = to_3ds(play_wii(fx.out("wii", 4), flags=3, skip=10))
        fx.drop("New 3DS", "monado01", x5)
        s5 = fx.sync()
        self.assertTrue(s5.complete, s5.message)
        self.check_three(fx, 5)
        self.assertEqual(de_only(fx.out("de", 5))["characters"], de_only(d4)["characters"])

    def test_b1_wii_save_with_heap_junk_converts_to_3ds(self):
        """B1: a Dolphin-written save of the user's playthrough holds 9,269 leftover bytes between sections; the 3A
        engine alone refuses its 3DS conversion. The hub clears only schema gap/pad bytes (checksums recomputed)."""
        w = rd(H.W150_LATER)
        d = H.fresh("b1_engine")
        with self.assertRaises(xs.REFUSALS):
            s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=H.W150_LATER, out=os.path.join(d, "x"),
                                          template=H.X3_USER))
        clean = sync.clean_wii_junk(w, T)
        diff = [i for i in range(len(w)) if w[i] != clean[i]]
        allowed = sync.JUNK_SPANS + sync.CRC_FIELDS
        self.assertTrue(diff and all(any(s <= i < e for s, e in allowed) for i in diff))
        self.assertEqual(sync.clean_wii_junk(rd(H.W150), T), rd(H.W150))       # clean saves are untouched
        fx = HubFx("b1_hub")
        fx.drop("Odin 2 Mini", "monado01", w)
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        self.assertEqual(fx.out("wii"), w)                                      # the Wii file stays exact
        self.check_three(fx, 1)
        self.assertTrue(any("left over by the Wii game" in n for n in fx.gen()["notes"]))

    def test_b2_unplayed_return_is_never_converted(self):
        """B2: the 3A/3B engine refused an UNPLAYED DE -> 3DS -> DE return when overflow items were set aside (slot
        renumbering in its read-back). The hub classifies such a save as in sync and never converts it.
        Phase 3C fixed the engine (read-back through the export's compaction map): the manual return now gives the
        DE save back byte for byte; the hub decision is unchanged."""
        fx = HubFx("b2_hub")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        fx.sync()
        fx.drop("New 3DS", "monado01", rd(os.path.join(fx.ready("New 3DS"), "monado01")))
        fx.drop("Odin 2 Mini", "monado01", resave_wii(fx.out("wii")))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync")
        d = H.fresh("b2_engine")
        r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "a"),
                                           template=H.X3_USER, overflow="sidecar"))
        r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=r1.main_output, out=os.path.join(d, "b"),
                                           record=r1.sidecar_path, current=H.DE_S232))
        self.assertEqual(rd(r2.main_output), rd(H.DE_S232))

    def test_items_exp_quests_follow_the_source(self):
        fx = self.start_wii("sync_items")
        w2 = play_wii(rd(H.W150), flags=7, money=99, exp=40, add_items=3, remove_items=2)
        fx.drop("Odin 2 Mini", "monado01", w2)
        r = fx.sync()
        self.assertTrue(r.complete)
        a, d = sh("wii", w2), sh("de", fx.out("de"))
        self.assertEqual(a["characters"][1]["exp"], d["characters"][1]["exp"])
        self.assertEqual(scan.scmod._items(a), scan.scmod._items(d))
        self.assertEqual(a["flags"], d["flags"])
        self.assertEqual(sh("wii", xc3d.transcode(xc3d.unpack(fx.out("3ds")), "wii"))["flags"], a["flags"])

    def test_unsupported_party_blocks_and_changes_nothing(self):
        fx = self.start_wii("sync_party")
        before = H.tree_hashes(fx.hub.root)
        b = bytearray(play_de(fx.out("de"), flags=3))
        n = struct.unpack_from("<I", b, 0x1526D8 + 0x18)[0]
        struct.pack_into("<H", b, 0x1526D8 + 2 * n, 8)               # Fiora's second form joins the party
        struct.pack_into("<I", b, 0x1526D8 + 0x18, n + 1)
        fx.drop("Windows desktop", "bfsgame00.sav", bytes(b))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "new-progress")
        with self.assertRaises(sync.Blocked) as cm:
            fx.sync(r)
        self.assertIn("wii", cm.exception.blocked)
        self.assertIn("3ds", cm.exception.blocked)
        self.assertIn("nothing was changed", str(cm.exception))
        self.assertEqual(fx.hub.committed(), [1])
        after = H.tree_hashes(fx.hub.root)
        self.assertEqual({k: v for k, v in before.items() if "staging" not in k},
                         {k: v for k, v in after.items() if "staging" not in k})

    def test_explicit_partial_sync_is_labelled_partial(self):
        fx = self.start_wii("sync_partial")
        b = bytearray(play_de(fx.out("de"), flags=3))
        n = struct.unpack_from("<I", b, 0x1526D8 + 0x18)[0]
        struct.pack_into("<H", b, 0x1526D8 + 2 * n, 9)
        struct.pack_into("<I", b, 0x1526D8 + 0x18, n + 1)
        fx.drop("Windows desktop", "bfsgame00.sav", bytes(b))
        r = fx.sync(allow_partial=True)
        self.assertTrue(r.partial)
        self.assertFalse(r.complete)
        self.assertNotIn("All configured platforms updated", r.message)
        g = fx.gen()
        self.assertEqual(sorted(g["outputs"]), ["de"])
        self.assertTrue(g["partial"])
        res = fx.scan()
        odin = fx.status(res, "Odin 2 Mini")
        self.assertEqual(odin.ready_state, "not-available")
        self.assertEqual(json.load(open(os.path.join(fx.ready("Odin 2 Mini"), "READY.json")))["generation"], 1)

    def test_missing_template_blocks(self):
        fx = HubFx("sync_notpl", templates=())
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        with self.assertRaises(sync.Blocked) as cm:
            fx.sync()
        self.assertEqual(sorted(cm.exception.blocked), ["3ds", "de"])
        self.assertIn("template", cm.exception.blocked["de"])
        self.assertEqual(fx.hub.committed(), [])

    def test_only_configured_platforms_are_produced(self):
        fx = HubFx("sync_partialcfg", devices=(("Desktop", "de"), ("Odin", "wii")), templates=("de",))
        fx.drop("Odin", "monado01", rd(H.W150))
        r = fx.sync()
        self.assertTrue(r.complete, r.message)
        self.assertEqual(sorted(fx.gen()["outputs"]), ["de", "wii"])
        fx.hub.add_device("New 3DS", "3ds", incoming=os.path.join(fx.base, "x3in"))
        fx.hub.add_template("3ds", H.X3_USER)                         # 3DS added later
        fx.drop("Odin", "monado01", play_wii(rd(H.W150), flags=2))
        r = fx.sync()
        self.assertEqual(sorted(fx.gen()["outputs"]), ["3ds", "de", "wii"])

    def test_source_changed_after_scan_is_refused(self):
        fx = self.start_wii("sync_changed")
        p = fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        r = fx.scan()
        put(p, play_wii(rd(H.W150), flags=5))
        with self.assertRaises(store.HubError) as cm:
            fx.sync(r)
        self.assertIn("changed since the scan", str(cm.exception))
        self.assertEqual(fx.hub.committed(), [1])

    def test_history_changed_after_scan_is_refused(self):
        fx = self.start_wii("sync_stale_scan")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        r1 = fx.scan()
        r2 = fx.scan()
        fx.sync(r1)
        with self.assertRaises(store.HubError) as cm:
            fx.sync(r2)
        self.assertIn("Scan Again", str(cm.exception))

    def test_second_window_cannot_sync_at_the_same_time(self):
        fx = self.start_wii("sync_lock")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        with fx.hub.lock():
            with self.assertRaises(store.HubError) as cm:
                fx.sync()
        self.assertIn("another Sync is running", str(cm.exception))
        r = fx.sync()                                   # released
        self.assertTrue(r.complete)

    def test_stale_lock_of_a_dead_process_is_taken_over(self):
        fx = self.start_wii("sync_stale_lock")
        with open(fx.hub.p("metadata", "hub.lock"), "w") as f:
            json.dump({"pid": 999999, "host": os.environ.get("COMPUTERNAME", ""), "t": time.time()}, f)
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        self.assertTrue(fx.sync().complete)

    def test_cancel_before_commit(self):
        fx = self.start_wii("sync_cancel")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        stages = []
        with self.assertRaises(sync.Cancelled):
            fx.sync(progress=stages.append, cancel=lambda: "validate" in stages or "build" in stages)
        self.assertEqual(fx.hub.committed(), [1])
        self.assertEqual(os.listdir(fx.hub.p("staging")), [])


# ================================================================================================ conflicts
class TestConflicts(Base):
    def two_branches(self, name):
        fx = self.start_wii(name)
        a = play_wii(rd(H.W150), flags=6, money=300, minutes=30)                    # Odin: more play time
        b = to_3ds(play_wii(rd(H.W150), flags=4, skip=20, add_items=2, minutes=5, story=1))   # 3DS: story moved
        fx.drop("Odin 2 Mini", "monado02", a)
        fx.drop("New 3DS", "monado01", b)
        return fx, a, b

    def test_independent_progress_detected_before_anything_is_replaced(self):
        fx, a, b = self.two_branches("cf_detect")
        r = fx.scan()
        self.assertEqual(r.decision.kind, "conflict")
        self.assertEqual(r.decision.message, "Progress was found on both the Odin 2 Mini and New 3DS. Choose which "
                                             "playthrough to continue.")
        self.assertIsNone(r.decision.source)
        self.assertEqual(fx.hub.committed(), [1])

    def test_choice_keeps_the_other_branch_recoverable(self):
        fx, a, b = self.two_branches("cf_choose")
        r = fx.scan()
        k3 = next(k for k in r.decision.options if "New_3DS" in k)
        res = fx.sync(r, source_key=k3)
        self.assertTrue(res.complete)
        g = fx.gen()
        self.assertEqual(g["source"]["device_name"], "New 3DS")
        other = [s for s in g["snapshots"] if not s["chosen"]]
        self.assertEqual(len(other), 1)
        self.assertEqual(rd(os.path.join(g["_dir"], *other[0]["file"].split("/"))), a)
        dst = os.path.join(H.fresh("cf_restore"), "out")
        p = sync.restore_snapshot(fx.hub, g["number"], other[0]["file"], dst)
        self.assertEqual(rd(p), a)
        # nothing of branch A is in the new generation: no merge
        self.assertNotEqual(sh("wii", fx.out("wii"))["money"], sh("wii", a)["money"])
        r2 = fx.scan()                                  # the unselected branch is now divergent, not new
        o = next(o for o in r2.saves() if o.name == "monado02")
        self.assertEqual(o.status, "divergent")

    def test_different_inventory_and_quest_changes_conflict(self):
        fx = self.start_wii("cf_inventory")
        fx.drop("Odin 2 Mini", "monado02", play_wii(rd(H.W150), flags=0, add_items=3, minutes=5))
        fx.drop("Windows desktop", "bfsgame00.sav", play_de(fx.out("de"), flags=4))
        self.assertEqual(fx.scan().decision.kind, "conflict")

    def test_divergent_save_can_only_be_continued_explicitly(self):
        fx = self.start_wii("cf_divergent")
        fx.drop("New 3DS", "monado01", rd(H.X3_A2))
        fx.sync()
        fx.drop("Odin 2 Mini", "monado02", rd(H.W150_LATER))
        r = fx.scan()
        key = r.decision.options[0]
        res = fx.sync(r, source_key=key)                # explicit choice of the older branch
        g = fx.gen()
        self.assertEqual((g["kind"], g["parent"]), ("branch", 1))
        self.assertEqual(fx.out("wii"), rd(H.W150_LATER))
        self.assertEqual(sorted(g["outputs"]), ["3ds", "de", "wii"])
        self.assertTrue(res.complete)
        self.assertTrue(os.path.isdir(fx.hub.gen_dir(2)))              # generation 2 still recoverable

    def test_incorrect_sidecar_association_is_refused(self):
        """An anchor sidecar replaced by one from another playthrough / damaged: refused, nothing committed."""
        fx = HubFx("cf_badsidecar")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        fx.sync()
        g = fx.gen()
        scp = os.path.join(g["_dir"], *g["cross_sidecar"]["file"].split("/"))
        os.chmod(scp, 0o666)
        txt = json.loads(rd(scp))
        txt["notes"].append("edited")
        with open(scp, "w") as f:
            json.dump(txt, f)
        fx.drop("New 3DS", "monado01", H.x3_a5_played())
        with self.assertRaises(store.HubError) as cm:
            fx.sync()
        self.assertIn("missing or changed", str(cm.exception))
        self.assertEqual(fx.hub.committed(), [1])

    def test_malformed_pointer(self):
        fx = self.start_wii("cf_pointer")
        with open(fx.hub.pointer_path, "w") as f:
            f.write("{not json")
        r = fx.scan()
        self.assertEqual(r.decision.kind, "error")


# ================================================================================================ failures
class TestFailures(Base):
    POINTS = ["read", "convert", "sidecar", "stage", "validate", "manifest", "commit", "pointer"]

    def test_failure_at_every_point_before_commit_changes_nothing(self):
        for point in self.POINTS:
            with self.subTest(point=point):
                fx = self.start_wii(f"fail_{point}")
                fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
                before = {k: v for k, v in H.tree_hashes(fx.hub.root).items() if "staging" not in k}

                def boom(p, detail="", point=point):
                    if p == point:
                        raise OSError(f"injected failure at {p}")
                sync.FAULT = boom
                with self.assertRaises(OSError):
                    fx.sync()
                sync.FAULT = None
                after = {k: v for k, v in H.tree_hashes(fx.hub.root).items() if "staging" not in k}
                if point == "pointer":                 # the folder was renamed before the pointer failed
                    self.assertEqual(fx.hub.committed(), [1])
                    self.assertTrue(any(i["kind"] == "uncommitted" for i in fx.scan().issues))
                else:
                    self.assertEqual(before, after)
                self.assertEqual(fx.hub.current_generation()[0], 1)
                self.assertEqual(os.listdir(fx.hub.p("staging")), [])
                r = fx.sync()                           # the next Sync works and numbers correctly
                self.assertEqual(r.generation, 2)
                self.assertTrue(r.complete)

    def test_engine_refusal_during_conversion(self):
        fx = self.start_wii("fail_engine")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        real = xs.wii_to_de

        def bad(req, progress=None):
            raise safeio.Refused("simulated engine refusal")
        xs.wii_to_de = bad
        try:
            with self.assertRaises(sync.Blocked) as cm:
                fx.sync()
        finally:
            xs.wii_to_de = real
        self.assertIn("simulated engine refusal", cm.exception.blocked["de"])
        self.assertEqual(fx.hub.committed(), [1])

    def test_validation_catches_a_wrong_output(self):
        fx = self.start_wii("fail_validate")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        real = sync.Builder.w_to_d

        def lossy(self_, wpath):
            d, tmb, sc, n = real(self_, wpath)
            b = bytearray(d)
            import de_save
            struct.pack_into("<I", b, de_save.MONEY, 1)
            return bytes(b), tmb, sc, n
        sync.Builder.w_to_d = lossy
        try:
            with self.assertRaises(store.HubError) as cm:
                fx.sync()
        finally:
            sync.Builder.w_to_d = real
        self.assertIn("differs from the source", str(cm.exception))
        self.assertEqual(fx.hub.committed(), [1])

    def test_interrupted_publication_is_reported_and_finished(self):
        fx = self.start_wii("fail_publish")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        old_de = rd(os.path.join(fx.ready("Windows desktop"), "bfsgame00.sav"))

        def boom(p, detail=""):
            if p == "publish" and "windows-desktop" in detail:
                raise OSError("disk full (simulated)")
        sync.FAULT = boom
        r = fx.sync()
        sync.FAULT = None
        self.assertEqual(r.generation, 2)
        self.assertFalse(r.complete)
        self.assertTrue(r.published[fx.dev["Windows desktop"]["id"]].startswith("failed"))
        self.assertNotIn("All configured platforms updated", r.message)
        self.assertEqual(rd(os.path.join(fx.ready("Windows desktop"), "bfsgame00.sav")), old_de)
        res = fx.scan()
        self.assertEqual(fx.status(res, "Windows desktop").ready_state, "outdated")
        self.assertTrue(any(i["kind"] == "publish" for i in res.issues))
        out = sync.publish(fx.hub)
        self.assertTrue(all(v == "ready" for v in out.values()))
        self.assertEqual(fx.status(fx.scan(), "Windows desktop").ready_state, "current")

    def test_publication_failure_after_some_files(self):
        """3DS: the save was replaced but the Checkpoint folder was not; READY.json still names generation 1."""
        fx = self.start_wii("fail_publish_mid")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))

        def boom(p, detail=""):
            if p == "publish" and "new-3ds/Checkpoint" in detail:
                raise OSError("removed SD card (simulated)")
        sync.FAULT = boom
        fx.sync()
        sync.FAULT = None
        self.assertEqual(json.load(open(os.path.join(fx.ready("New 3DS"), "READY.json")))["generation"], 1)
        self.assertEqual(fx.status(fx.scan(), "New 3DS").ready_state, "outdated")
        sync.publish(fx.hub)
        self.assertEqual(sorted(os.listdir(os.path.join(fx.ready("New 3DS"), "Checkpoint"))),
                         ["XenobladeSync-gen000002"])

    def run_child(self, fx, point):
        p = subprocess.run([sys.executable, os.path.join(HERE, "crash_child.py"), fx.hub.root, point],
                           capture_output=True, text=True, timeout=600)
        return p.returncode, p.stderr

    def test_application_killed_at_each_stage(self):
        """os._exit inside the Sync (no cleanup runs): the committed generation never changes before the pointer
        update; after it, publication is reported as unfinished; the next Sync recovers."""
        for point in ("build", "stage", "validate", "commit", "pointer", "after-commit", "publish",
                      "publish-ready"):
            with self.subTest(point=point):
                fx = self.start_wii(f"crash_{point}")
                fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
                fault_point = {"build": "convert"}.get(point, point)
                rc, err = self.run_child(fx, fault_point)
                self.assertEqual(rc, 77, err[-2000:])
                cur = fx.hub.current_generation()[0]
                res = fx.scan()
                if point in ("after-commit", "publish", "publish-ready"):
                    self.assertEqual(cur, 2)
                    self.assertTrue(any(i["kind"] == "publish" for i in res.issues), res.issues)
                    out = sync.publish(fx.hub)
                    self.assertTrue(all(v == "ready" for v in out.values()))
                else:
                    self.assertEqual(cur, 1)
                    self.assertTrue(res.issues, point)          # interrupted work is reported
                    self.assertEqual(res.decision.kind, "new-progress")
                    r = fx.sync(res)
                    self.assertEqual(r.generation, 2)
                    self.assertTrue(r.complete)
                    self.assertFalse(fx.scan().issues)
                for dev in fx.dev:
                    self.assertEqual(json.load(open(os.path.join(fx.ready(dev), "READY.json")))["generation"], 2)


# ================================================================================================ acceptance replay
FX3B = os.path.join(H.P3B, "fixtures")


class TestAcceptanceReplay(Base):
    def test_game_written_chain_reproduces_the_emulator_cycle(self):
        """The 2026-11-08 emulator cycle, replayed from the saves the games wrote: Wii (user) -> Monado walk ->
        3DS battle -> Dolphin walk. Every step is detected as new progress on the right device, the anchors are
        the played saves, and generation 4's DE save is byte-identical to the one Monado loaded in run m2. Monado's
        load-and-save without moving (height +0.001) is NOT new progress."""
        f = lambda n: rd(os.path.join(FX3B, n))      # noqa: E731
        fx = HubFx("replay")
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        fx.sync()
        self.assertEqual(fx.out("de", 1), f("de_gen1_wii150.sav"))
        steps = [("Windows desktop", "bfsgame00.sav", f("de_monado_walked.sav")),
                 ("New 3DS", "monado01", f("x3_azahar_battle_monado01")),
                 ("Odin 2 Mini", "monado01", f("wii_dolphin_walked_monado01"))]
        for i, (dev, name, data) in enumerate(steps, start=2):
            fx.drop(dev, name, data)
            r = fx.scan()
            self.assertEqual((r.decision.kind, r.find(r.decision.source).device_name), ("new-progress", dev), i)
            s = fx.sync(r)
            self.assertTrue(s.complete, s.message)
        self.assertEqual([c.get("anchor") for c in fx.gen(3)["conversions"] if c["direction"] == "wii_to_de"], [2])
        self.assertEqual([c.get("anchor") for c in fx.gen(4)["conversions"] if c["direction"] == "wii_to_de"], [2])
        # 3B: byte-identical to de_gen4.sav. Phase 3C (E1): the highest-level EXP word (+0xF0) of characters that
        # earned EXP at their highest level in the 3DS battle now equals their EXP, as the DE game keeps it; nothing else
        new4, old4 = fx.out("de", 4), f("de_gen4.sav")
        ch = 0x152728
        diff = [i for i in range(len(new4)) if new4[i] != old4[i]]
        self.assertTrue(all(ch <= i < ch + 0x138 * 16 and 0xF0 <= (i - ch) % 0x138 < 0xF4 for i in diff), diff[:8])
        for k in range(1, 8):
            o = ch + 0x138 * (k - 1)
            if new4[o + 0xF0:o + 0xF4] != old4[o + 0xF0:o + 0xF4]:
                self.assertEqual(new4[o + 0xF0:o + 0xF4], new4[o + 4:o + 8])          # = current EXP
                self.assertEqual(new4[o:o + 4], new4[o + 0xEC:o + 0xF0])              # at the highest level
        self.assertEqual(sh("de", new4), sh("de", old4))
        self.assertIn("outputs/de/bfsgame.tmb", fx.gen(4)["outputs"]["de"]["files"])     # thumbnail carried
        # 3C: Monado's load-and-save of the 3C generation 4 (game-written, run m2_3c_gen4_load_save); the 3B re-save
        # below was made from the 3B generation 4 and still compares equal to it
        fx.drop("Windows desktop", "bfsgame00.sav", rd(os.path.join(H.ROOT, "phase3c", "fixtures",
                                                                    "de_monado_resave_noplay_3c_gen4.sav")))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "in-sync", [(o.name, o.status, o.detail) for o in r.saves()])
        cc = scan.Canon()
        self.assertTrue(scan.same_progress(cc, "de", f("de_gen4.sav"), f("de_monado_resave_noplay.sav")))
        self.assertFalse(scan.same_progress(cc, "de", f("de_gen1_wii150.sav"), f("de_monado_walked.sav")))


    def test_two_wii_family_branches_after_a_walk_only_generation_conflict(self):
        """Found by the package test: generation 2 changed only the position (Monado walk). The Dolphin save played
        on from generation 1 (W150_LATER) and the 3DS battle save both 'continue' it; neither holds the other's
        progress (the 3DS battle's EXP), so this is a conflict, never one proposed save."""
        f = lambda n: rd(os.path.join(FX3B, n))      # noqa: E731
        fx = HubFx("replay_two_branches")
        fx.drop("Odin 2 Mini", "monado01", rd(H.W150))
        fx.sync()
        fx.drop("Windows desktop", "bfsgame00.sav", f("de_monado_walked.sav"))
        fx.sync()
        fx.drop("Odin 2 Mini", "monado02", rd(H.W150_LATER))
        fx.drop("New 3DS", "monado01", f("x3_azahar_battle_monado01"))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "conflict", [(o.name, o.status, o.detail) for o in r.saves()])
        self.assertIsNone(r.decision.source)
        self.assertEqual(len(r.decision.options), 2)


# ================================================================================================ history
class TestHistory(Base):
    def test_rollback_to_previous_generation(self):
        fx = self.start_wii("hist_rollback")
        g1_de = fx.out("de", 1)
        fx.drop("New 3DS", "monado01", rd(H.X3_A2))
        fx.sync()
        r = sync.rollback(fx.hub, 1)
        self.assertEqual(r.generation, 3)
        self.assertTrue(r.complete, r.message)
        g3 = fx.gen()
        self.assertEqual((g3["kind"], g3["rollback_of"]), ("rollback", 1))
        self.assertEqual(fx.out("de", 3), g1_de)
        self.assertEqual(rd(os.path.join(fx.ready("Windows desktop"), "bfsgame00.sav")), g1_de)
        self.assertTrue(os.path.isdir(fx.hub.gen_dir(2)))               # nothing deleted
        res = fx.scan()
        x = fx.status(res, "New 3DS").saves[0]                         # the 3DS still holds generation 2's state
        self.assertNotEqual(x.status, "new-progress")
        self.assertEqual(res.decision.kind, "in-sync" if x.status == "older" else "conflict")

    def test_rollback_then_continue_and_anchor_follows(self):
        fx = HubFx("hist_rollback_anchor")
        fx.drop("Windows desktop", "bfsgame00.sav", rd(H.DE_S232))
        fx.sync()                                                       # 1: DE
        fx.drop("New 3DS", "monado01", H.x3_a5_played())
        fx.sync()                                                       # 2: 3DS
        sync.rollback(fx.hub, 1)                                        # 3 = copy of 1
        fx.drop("New 3DS", "monado01", rd(os.path.join(fx.ready("New 3DS"), "monado01")))
        fx.drop("Windows desktop", "bfsgame00.sav", play_de(rd(H.DE_S232), flags=3))
        r = fx.scan()
        self.assertEqual(r.decision.kind, "new-progress", [(o.name, o.status, o.detail) for o in r.saves()])
        s = fx.sync(r)
        self.assertTrue(s.complete)
        self.assertIsNone(fx.gen()["conversions"][0]["anchor"])        # gen 2's Wii anchor is not used

    def test_history_lists_every_generation(self):
        fx = self.start_wii("hist_list")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        fx.sync()
        gens = fx.hub.generations()
        self.assertEqual([g["number"] for g in gens], [1, 2])
        self.assertEqual(gens[1]["parent"], 1)
        for g in gens:                                  # every stored file still matches its recorded hash
            for rel, h in g["files"].items():
                self.assertEqual(sha(rd(os.path.join(g["_dir"], *rel.split("/")))), h)


# ================================================================================================ setup
class TestSetup(Base):
    def test_hub_requires_empty_or_existing_hub_folder(self):
        d = H.fresh("setup_nonempty")
        put(os.path.join(d, "x.txt"), b"x")
        with self.assertRaises(store.HubError):
            store.Hub.create(d)
        h = store.Hub.create(os.path.join(d, "hub"))
        self.assertEqual(store.Hub.create(h.root).root, h.root)           # reopening is fine

    def test_hub_inside_a_live_game_folder_is_refused(self):
        with self.assertRaises(safeio.Refused):
            store.Hub.create(os.path.join(H.WORK, "x", "Wii", "title", "00010000", "53583445", "hub"))

    def test_device_profiles_persist_and_ids_are_stable(self):
        fx = HubFx("setup_devices")
        d = fx.dev["Odin 2 Mini"]
        fx.hub.update_device(d["id"], name="Odin 2 (handheld)")
        h2 = store.Hub.open(fx.hub.root)
        d2 = h2.device(d["id"])
        self.assertEqual((d2["name"], d2["folder"]), ("Odin 2 (handheld)", d["folder"]))
        fx.hub.remove_device(d["id"])
        self.assertEqual(len(store.Hub.open(fx.hub.root).devices()), 2)
        with self.assertRaises(store.HubError):
            fx.hub.update_device(fx.dev["New 3DS"]["id"], slot="monado07")
        dup = fx.hub.add_device("New 3DS", "3ds")
        self.assertNotEqual(dup["folder"], fx.dev["New 3DS"]["folder"])

    def test_template_is_verified_copied_and_original_untouched(self):
        fx = HubFx("setup_tpl", templates=())
        before = sha(rd(H.DE_TPL))
        info = fx.hub.add_template("de", H.DE_TPL)
        self.assertEqual(sha(rd(H.DE_TPL)), before)
        self.assertEqual(info["sha256"], before)
        self.assertTrue(os.path.isfile(fx.hub.template_file("de")))
        with self.assertRaises(xs.REFUSALS):
            fx.hub.add_template("de", H.W150)
        with self.assertRaises(xs.REFUSALS):
            fx.hub.add_template("3ds", os.path.join(H.X3_ARCH, "monado02"))      # empty slot
        info3 = fx.hub.add_template("3ds", H.X3_USER)
        self.assertEqual(info3["archive"], ["monado01", "monado02", "monado03"])
        p = fx.hub.template_file("de")
        os.chmod(p, 0o666)
        with open(p, "r+b") as f:
            f.write(b"\x00")
        with self.assertRaises(store.HubError):
            fx.hub.template_file("de")

    def test_ready_folder_only_touches_its_own_files(self):
        fx = self.start_wii("setup_ready_own")
        mine = put(os.path.join(fx.ready("Odin 2 Mini"), "my_notes.txt"), b"keep me")
        fx.drop("Odin 2 Mini", "monado01", play_wii(rd(H.W150), flags=3))
        fx.sync()
        self.assertEqual(rd(mine), b"keep me")


if __name__ == "__main__":
    unittest.main()
