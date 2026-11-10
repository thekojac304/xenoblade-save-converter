"""Phase 2H: conversion-history decisions and slot suggestions in xcservice (used by the simplified GUI).

resolve_history() decides first vs return conversion from one "destination save"; it must never pick a stale or
ambiguous history and never fall back to a first conversion when the saves have a matching history or look like one
playthrough without one. Writes only under work/test_phase2h/service.
"""
import os
import shutil
import sys
import unittest

import p2f_util as U

sys.path.insert(0, os.path.join(U.ROOT, "tools"))
import xcservice as svc  # noqa: E402

W = os.path.join(U.ROOT, "work", "test_phase2h", "service")
W01 = os.path.join(U.O, "monado01")
W03 = os.path.join(U.O, "monado03")
DE_USER = os.path.join(U.O, "user_v10_bfsgame00.sav")
DE_USER_A = os.path.join(U.O, "user_v10_bfsgame00a.sav")


def setUpModule():
    shutil.rmtree(W, ignore_errors=True)
    os.makedirs(W)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


class History(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = os.path.join(W, "hist")
        g1 = os.path.join(cls.root, "g1")
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=g1))
        cls.g1, cls.de1 = g1, os.path.join(g1, "save_0", "bfsgame00.sav")

    def test_first_conversion(self):
        p = svc.resolve_history(W01, "wii_to_de", U.TPL, [os.path.join(W, "nothing")])
        self.assertEqual((p.mode, p.issue), ("first", ""))
        self.assertLess(p.similarity, svc.SAME_PLAYTHROUGH)

    def test_return_found_and_destination_checked(self):
        p = svc.resolve_history(self.de1, "de_to_wii", W01, [self.root])
        self.assertEqual((p.mode, p.dest_relation), ("return", "exact"))
        self.assertEqual(os.path.dirname(p.sidecar), self.g1)
        m = U.Wii(U.rd(W01))
        m.play(600)
        later = write(os.path.join(W, "w_later", "monado01"), m.done())
        self.assertEqual(svc.resolve_history(self.de1, "de_to_wii", later, [self.root]).dest_relation, "continues")
        p = svc.resolve_history(self.de1, "de_to_wii", W03, [self.root])          # another playthrough
        self.assertEqual((p.mode, p.issue), ("blocked", "dest-unrelated"))
        p = svc.resolve_history(self.de1, "de_to_wii", None, [self.root])         # no destination save yet
        self.assertEqual((p.mode, p.dest_relation), ("return", ""))

    def test_same_playthrough_without_history_is_not_a_silent_first_conversion(self):
        iso = write(os.path.join(W, "iso", "bfsgame05.sav"), U.rd(self.de1))
        p = svc.resolve_history(W01, "wii_to_de", iso, [os.path.join(W, "nothing")])
        self.assertEqual((p.mode, p.issue), ("blocked", "same-playthrough"))
        self.assertGreaterEqual(p.similarity, svc.SAME_PLAYTHROUGH)
        p = svc.resolve_history(W01, "wii_to_de", iso, [os.path.join(W, "nothing")], start_fresh=True)
        self.assertEqual(p.mode, "first")

    def test_ambiguous(self):
        root = os.path.join(W, "amb")
        a, b = os.path.join(root, "a"), os.path.join(root, "b")
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=DE_USER, out=a))
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=DE_USER_A, out=b))
        p = svc.resolve_history(os.path.join(a, "save_0", "bfsgame00.sav"), "de_to_wii", W01, [root])
        self.assertEqual((p.mode, p.issue), ("blocked", "choose"))
        self.assertEqual(len(p.choices), 2)
        p = svc.resolve_history(os.path.join(a, "save_0", "bfsgame00.sav"), "de_to_wii", W01, [root],
                                chosen=os.path.join(b, "wii_to_de.sidecar.json"))
        self.assertEqual(p.mode, "return")

    def test_chosen_record_of_other_save(self):
        other = os.path.join(W, "other")
        svc.de_to_wii_convert(svc.DeToWiiRequest(de=DE_USER, base=W03, out=other))
        p = svc.resolve_history(W01, "wii_to_de", self.de1, [], chosen=os.path.join(other, "de_to_wii.sidecar.json"))
        self.assertEqual((p.mode, p.issue), ("blocked", "chosen-invalid"))

    def test_older_history(self):
        g2 = os.path.join(self.root, "g2")
        svc.de_to_wii_convert(svc.DeToWiiRequest(de=self.de1, sidecar=os.path.join(self.g1, "wii_to_de.sidecar.json"),
                                                 current_wii=W01, out=g2))
        m = U.Wii(U.rd(os.path.join(g2, "monado01")))
        m.play(1800)
        m.level_up(1)
        w2p = write(os.path.join(W, "w2p", "monado01"), m.done())
        g3 = os.path.join(self.root, "g3")
        svc.wii_to_de(svc.WiiToDeRequest(wii=w2p, sidecar=os.path.join(g2, "de_to_wii.sidecar.json"),
                                         current_de=self.de1, out=g3))
        p = svc.resolve_history(self.de1, "de_to_wii", w2p, [self.root])
        self.assertEqual((p.mode, p.issue), ("blocked", "older"))
        p = svc.resolve_history(os.path.join(g3, "save_0", "bfsgame00.sav"), "de_to_wii", w2p, [self.root])
        self.assertEqual((p.mode, os.path.dirname(p.sidecar)), ("return", g3))
        shutil.rmtree(g2)
        shutil.rmtree(g3)


class Slots(unittest.TestCase):
    def test_de_slot_not_used_next_to_destination(self):
        d = os.path.join(W, "slots_de")
        for n in ("bfsgame00.sav", "bfsgame01.sav", "bfsgame03.sav"):
            write(os.path.join(d, n), b"x")
        s = svc.suggest_slot("wii_to_de", os.path.join(d, "bfsgame00.sav"))
        self.assertEqual((s.slot, s.free, s.used), ("02", True, ["00", "01", "03"]))
        self.assertEqual(svc.suggest_slot("wii_to_de", None).slot, "01")

    def test_wii_slot(self):
        d = os.path.join(W, "slots_wii")
        write(os.path.join(d, "monado01"), U.rd(W01))
        write(os.path.join(d, "monado02"), U.rd(os.path.join(U.O, "monado02")))     # empty (DMMY) slot
        s = svc.suggest_slot("de_to_wii", os.path.join(d, "monado01"))
        self.assertEqual((s.slot, s.free), ("monado02" if svc.detect(os.path.join(d, "monado02"))["kind"] != "wii"
                                            else "monado03", True))
        write(os.path.join(d, "monado02"), U.rd(W03))
        write(os.path.join(d, "monado03"), U.rd(W03))
        s = svc.suggest_slot("de_to_wii", os.path.join(d, "monado01"))
        self.assertEqual((s.slot, s.free), ("monado01", False))


if __name__ == "__main__":
    unittest.main()
