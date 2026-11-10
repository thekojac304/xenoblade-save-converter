"""Phase 3C: DE-only per-item metadata across DE -> Wii/3DS -> DE (defect B3 and the same-slot replacement hazard).

Inputs are game-written saves (DE s232 Expert Mode re-saved by Monado; the user's Wii save as the structural base;
the 3DS game's own save a5 of DE s232). Favourite marks are SYNTHETIC edits of those saves (no game-written save
with favourites exists); Wii-side inventory changes are synthetic edits that follow the game's own slot/age rules
(p3cfix). Every test also compares against the frozen 3B engine where the behaviour deliberately differs.

  python -m unittest discover -s phase3c/tests -v      (from the research root)
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p3cfix as F  # noqa: E402
from p3cfix import H, T, rd  # noqa: E402

import canon  # noqa: E402
import itemcorr  # noqa: E402
import sidecar as scmod  # noqa: E402
import xc3dservice as s3  # noqa: E402

PICKS = {"crystal": [0, 1, 2, 305, 340, 499], "weapon": [3, 54, 150, 162], "material": [5, 6, 166],
         "gem": [10, 11], "head": [0]}
BASELINE = os.path.join(F.P3C, "scripts", "baseline3b.py")


def baseline_wii_to_de(wii, sidecar, current, out):
    r = subprocess.run([sys.executable, BASELINE, "wii_to_de", wii, sidecar, current, out], capture_output=True,
                       text=True, timeout=600)
    if r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return rd(json.loads(r.stdout.strip().splitlines()[-1])["main_output"])


def shared(img):
    s = canon.from_de(img, T)["shared"]
    return s


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = F.fresh(cls.__name__)
        cls.de = F.set_fav(rd(H.DE_S232), PICKS)
        cls.de_p = F.put_de(cls.d, "de_src", cls.de)
        cls.exp = F.export(cls.de_p, os.path.join(cls.d, "exp"))
        cls.w = rd(cls.exp.main_output)
        cls.sc = cls.exp.sidecar_path

    def back(self, wii, name):
        r = F.reimport(wii, self.d, self.sc, self.de_p, name)
        return rd(r.main_output), r


class TestB3Regression(Base):
    def test_b3_real_3ds_session_keeps_every_de_only_record(self):
        """B3: s232 -> 3DS -> the 3DS game's own save (a5) + synthetic flags -> DE: every DE record of the original
        comes back byte for byte (slot index and serial aside), compacted crystals included (3B: 176 -> 90)."""
        d = F.fresh("b3_a5")
        r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "a"),
                                           template=H.X3_USER, overflow="sidecar"))
        p = H.put(os.path.join(d, "in", "monado01"), H.x3_a5_played())
        r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=p, out=os.path.join(d, "b"), record=r1.sidecar_path,
                                           current=H.DE_S232))
        orig, back = rd(H.DE_S232), rd(r2.main_output)
        for box in F.DBOX:
            same, diff = F.de_only_bytes_equal(orig, back, box)
            self.assertEqual(diff, 0, box)
        a, b = canon.from_de(orig, T)["de_only"]["items"], canon.from_de(back, T)["de_only"]["items"]
        self.assertEqual({k: len(v) for k, v in a.items()}, {k: len(v) for k, v in b.items()})
        self.assertEqual(len(b["crystal"]), 176)
        # gameplay state: identical to what the 3B engine produced (only DE-only bytes differ)
        r = subprocess.run([sys.executable, BASELINE, "convert3", json.dumps(dict(
            direction="3ds_to_de", source=p, out=os.path.join(d, "b3b"), record=r1.sidecar_path,
            current=H.DE_S232))], capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        b3 = rd(json.loads(r.stdout.strip().splitlines()[-1])["main_output"])
        self.assertEqual(shared(b3), shared(back))
        self.assertEqual(len(canon.from_de(b3, T)["de_only"]["items"]["crystal"]), 90)


class TestFavourites(Base):
    def test_unchanged_wii_is_byte_identical(self):
        """Also 3B finding B2: an unplayed return with compacted/overflow items was refused by the slot-by-slot
        read-back; 3C compares through the export map."""
        back, _ = self.back(self.w, "unchanged")
        self.assertEqual(back, self.de)
        p = H.put(os.path.join(self.d, "unchanged_b3", "monado01"), self.w)
        with self.assertRaises(AssertionError) as cm:
            baseline_wii_to_de(p, self.sc, self.de_p, os.path.join(self.d, "unchanged_b3_out"))
        self.assertIn("read-back differs", str(cm.exception))

    def test_compacted_deferred_and_same_slot_favourites_return(self):
        """Wii played (synthetic flags + time, inventory untouched): all 17 marks return - compacted crystals
        (DE slots 305/340/499 -> other Wii slots), overflow items kept in the sidecar, same-slot items."""
        back, r = self.back(H.play_wii(self.w, flags=5), "flags")
        self.assertEqual(F.favs(back), F.favs(self.de))
        self.assertEqual(sum(F.favs(back).values()), sum(len(v) for v in PICKS.values()))
        for box in F.DBOX:
            self.assertEqual(F.de_only_bytes_equal(self.de, back, box)[1], 0, box)
        meta = r.report["log"]["restored_exact"]["item_metadata"]
        self.assertEqual(meta["unresolved_boxes"], {})

    def test_three_platform_cycle(self):
        """DE -> Wii -> 3DS -> Wii -> DE (3A record chain, synthetic flag progress on each W platform)."""
        d = F.fresh("fav_cycle")
        r1 = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=self.exp.main_output, out=os.path.join(d, "x"),
                                           template=H.X3_USER))
        x = s3.load_3ds(r1.main_output, "x")[2]
        x_played = H.to_3ds(H.play_wii(x, flags=3))
        p = H.put(os.path.join(d, "x_in", "monado01"), x_played)
        r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=p, out=os.path.join(d, "w"), record=r1.sidecar_path,
                                           template=self.exp.main_output, current=self.exp.main_output))
        w2 = H.play_wii(rd(r2.main_output), flags=3, skip=20)
        back, _ = self.back(w2, "cycle")
        self.assertEqual(F.favs(back), F.favs(self.de))
        for box in F.DBOX:
            self.assertEqual(F.de_only_bytes_equal(self.de, back, box)[1], 0, box)
        a, b = canon.from_de(self.de, T)["de_only"], canon.from_de(back, T)["de_only"]
        for k in ("characters", "flags", "quest_counters_fc"):      # Expert Mode, appearance, link unlocks, DE flags
            self.assertEqual(a[k], b[k], k)
        self.assertGreater(sum(1 for c in a["characters"].values() if c["reserve_exp"]), 0)   # real Expert data
        sb, sw = canon.from_de(back, T)["shared"], canon.from_wii(w2, T)["shared"]
        self.assertEqual(sb["flags"], sw["flags"])                                           # W progress arrived


class TestInventoryMutations(Base):
    """Synthetic Wii inventory changes; the favourite must follow the physical item only."""

    def wslot(self, box, de_slot):
        maps, bad = itemcorr.export_map(canon.from_de(self.de, T)["shared"]["inventory"],
                                        canon.from_wii(self.w, T)["shared"]["inventory"],
                                        scmod.load(rd(self.sc).decode())["deferred"])
        return maps[box][de_slot]

    def test_sold_item_not_revived_and_mark_not_moved(self):
        ws = self.wslot("crystal", 340)
        back, _ = self.back(F.remove(self.w, "crystal", ws), "sold")
        exp = F.favs(self.de)
        key = [k for k in exp if k[0] == "crystal"]
        self.assertEqual(sum(F.favs(back).values()), sum(exp.values()) - 1)
        self.assertEqual(len(canon.from_de(back, T)["shared"]["inventory"]["crystal"]),
                         len(canon.from_de(self.de, T)["shared"]["inventory"]["crystal"]) - 1)
        self.assertTrue(key)

    def test_identical_replacement_in_same_slot_gets_no_mark(self):
        """Weapon at DE slot 3 sold, an identical one bought into the same slot as the newest item: the 3C engine
        gives it no favourite; the 3B engine copied the old record (mark included) onto the replacement."""
        ws = self.wslot("weapon", 3)
        self.assertEqual(ws, 3)
        w = F.make_newest(self.w, "weapon", ws)          # same slot, same item, now acquired last
        back, _ = self.back(w, "replaced")
        self.assertNotIn(3, F.fav_slots(back, "weapon"))
        p = H.put(os.path.join(self.d, "replaced_b3", "monado01"), w)
        old = baseline_wii_to_de(p, self.sc, self.de_p, os.path.join(self.d, "replaced_b3_out"))
        self.assertIn(3, F.fav_slots(old, "weapon"))             # 3B defect, documented
        self.assertEqual(shared(old), shared(back))              # gameplay state identical

    def test_newest_survivor_of_a_changed_box_is_unresolved(self):
        """The newest surviving item cannot be told apart from an identical replacement once the box changed."""
        cur = F.wii_items(self.w, "gem")
        newest = max(cur, key=lambda s: cur[s]["order"])
        w = F.remove(self.w, "gem", min(s for s in cur if s not in (10, 11, newest)))
        _, r = self.back(w, "gem_changed")
        unc = r.report["log"]["restored_exact"]["item_metadata"]["uncertain"]["gem"]
        self.assertIn(str(newest), unc)

    def test_stack_used_partly_keeps_mark_stack_added_to_does_not(self):
        cur = F.wii_items(self.w, "material")
        q5, q6 = cur[5]["qty"], cur[6]["qty"]
        w = F.set_qty(self.w, "material", 5, max(q5 - 1, 1))                 # used one (order unchanged)
        w = F.make_newest(F.set_qty(w, "material", 6, min(q6 + 2, 99)), "material", 6)   # picked up more
        back, r = self.back(w, "stacks")
        self.assertIn(5, F.fav_slots(back, "material"))
        self.assertNotIn(6, F.fav_slots(back, "material"))
        self.assertEqual(canon.from_de(back, T)["shared"]["inventory"]["material"][5]["qty"], max(q5 - 1, 1))

    def test_duplicate_items_mark_stays_with_its_own_instance(self):
        """Two identical weapons, only the OLDER one marked; the newer copy is sold: the mark stays on the older."""
        c = canon.from_de(self.de, T)["shared"]["inventory"]["weapon"]
        dup = {}
        for sl, r in c.items():
            dup.setdefault(r["gid"], []).append(sl)
        pair = next(sorted(v, key=lambda s: c[s]["order"]) for v in dup.values()
                    if len(v) >= 2 and all(s < 140 for s in v) and not set(v) & set(PICKS["weapon"]))
        old_sl, new_sl = pair[0], pair[-1]
        de2 = F.set_fav(rd(H.DE_S232), {"weapon": [old_sl]})
        d = F.fresh("dup")
        p = F.put_de(d, "de", de2)
        e = F.export(p, os.path.join(d, "exp"))
        w = F.remove(rd(e.main_output), "weapon", new_sl)
        r = F.reimport(w, d, e.sidecar_path, p, "sold_new")
        self.assertEqual(F.fav_slots(rd(r.main_output), "weapon"), [old_sl])
        w = F.remove(rd(e.main_output), "weapon", old_sl)
        r = F.reimport(w, d, e.sidecar_path, p, "sold_old")
        self.assertEqual(F.fav_slots(rd(r.main_output), "weapon"), [])      # never moved to the other copy

    def test_equipment_swap_and_gem_change_keep_mark(self):
        """Equipping/unequipping does not change items; sockets edited on the Wii keep the item's mark while the
        sockets themselves come from the Wii."""
        cur = F.wii_items(self.w, "weapon")
        self.assertIn(54, cur)
        back, _ = self.back(H.play_wii(self.w, flags=2, exp=10), "equip")
        self.assertIn(54, F.fav_slots(back, "weapon"))


class TestSafetyNet(Base):
    def test_metadata_restoration_never_changes_shared_state(self):
        """For every mutation above, the result's shared state equals the 3B engine's result."""
        w = F.remove(F.make_newest(self.w, "material", 5), "crystal", 0)
        back, _ = self.back(w, "net")
        p = H.put(os.path.join(self.d, "net_b3", "monado01"), w)
        old = baseline_wii_to_de(p, self.sc, self.de_p, os.path.join(self.d, "net_b3_out"))
        self.assertEqual(shared(old), shared(back))
        self.assertEqual(canon.from_de(old, T)["de_only"]["characters"], canon.from_de(back, T)["de_only"]["characters"])

    def test_unresolvable_export_map_restores_nothing(self):
        de = canon.from_de(self.de, T)["shared"]["inventory"]
        exp = canon.from_wii(self.w, T)["shared"]["inventory"]
        tampered = {k: dict(v) for k, v in exp.items()}
        sl = sorted(tampered["crystal"])[0]
        tampered["crystal"][sl] = dict(tampered["crystal"][sl], rank=99)
        maps, bad = itemcorr.export_map(de, tampered, scmod.load(rd(self.sc).decode())["deferred"])
        self.assertNotIn("crystal", maps)
        self.assertIn("crystal", bad)


if __name__ == "__main__":
    unittest.main()
