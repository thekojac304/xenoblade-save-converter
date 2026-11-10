"""Phase 2G: the shared service layer (xcservice) used by the CLI and the GUI.

  * CLI output is unchanged by the refactor: byte-identical saves and companion files compared with the frozen
    2F-rc1 code (phase2g/baseline_2F), sidecars identical apart from the converter version string;
  * detect / preview read only verified fields; sidecar discovery never picks a stale or foreign sidecar;
  * real conversion stages are reported in order; output planning applies the commit's rules without writing.
Writes only under work/test_phase2g/service.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import unittest

import p2f_util as U

sys.path.insert(0, os.path.join(U.ROOT, "tools"))
import safeio  # noqa: E402
import sidecar as scmod  # noqa: E402
import xcconv  # noqa: E402
import xcservice as svc  # noqa: E402

W = os.path.join(U.ROOT, "work", "test_phase2g", "service")
BASE_2F = os.path.join(U.ROOT, "phase2g", "baseline_2F", "tools", "xcconv.py")
W01 = os.path.join(U.O, "monado01")
W02 = os.path.join(U.O, "monado02")
W03 = os.path.join(U.O, "monado03")
DE_USER = os.path.join(U.O, "user_v10_bfsgame00.sav")
DE_V7 = os.path.join(U.PUBLIC, "s206_207aed635e_bfsgame01.sav")


def setUpModule():
    shutil.rmtree(W, ignore_errors=True)
    os.makedirs(W)


def cli(*args):
    rc = xcconv.main(list(args))
    return rc


def files_of(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            out[os.path.relpath(p, d).replace("\\", "/")] = U.rd(p)
    return out


def strip_version(sc_bytes):
    d = json.loads(sc_bytes)
    d.pop("integrity")
    d.pop("converter_version")
    return d


class CliUnchangedBy2G(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(BASE_2F), "frozen 2F-rc1 baseline not present")
    def test_cli_output_identical_to_2f_rc1(self):
        """The CLI (now a front end of xcservice) writes what 2F-rc1 wrote, in both directions."""
        jobs = [("wii-to-de", "--wii", W01, "--template", U.TPL, "--slot", "01"),
                ("de-to-wii", "--de", DE_USER, "--base", W03)]
        for i, job in enumerate(jobs):
            new, old = os.path.join(W, f"cli2g_{i}"), os.path.join(W, f"cli2f_{i}")
            self.assertEqual(cli(*job, "--out", new), 0)
            r = subprocess.run([sys.executable, BASE_2F, *job, "--out", old], capture_output=True, text=True,
                               env={**os.environ, "XCCONV_DATA": os.path.join(U.ROOT, "data"),
                                    "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertEqual(r.returncode, 0, r.stderr)
            a, b = files_of(new), files_of(old)
            self.assertEqual(set(a), set(b))
            for rel in a:
                if rel.endswith(".sidecar.json"):
                    self.assertEqual(strip_version(a[rel]), strip_version(b[rel]), rel)
                elif rel == "manifest.json":
                    ma, mb = json.loads(a[rel]), json.loads(b[rel])
                    for m in (ma, mb):
                        m.pop("converter")
                        m["outputs"] = {k: v for k, v in m["outputs"].items() if not k.endswith(".sidecar.json")}
                    self.assertEqual(ma, mb)
                else:
                    self.assertEqual(a[rel], b[rel], rel)

    def test_cli_and_service_identical(self):
        """xcconv wii-to-de and svc.wii_to_de with the same inputs produce identical folders (all files)."""
        a, b = os.path.join(W, "par_cli"), os.path.join(W, "par_svc")
        self.assertEqual(cli("wii-to-de", "--wii", W01, "--template", U.TPL, "--out", a, "--slot", "02"), 0)
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=b, slot="02"))
        self.assertEqual(files_of(a), files_of(b))

    def test_version(self):
        # "2G-rc1" from 2G to 3B (engine unchanged); Phase 3C changed the engine (item correspondence) and its stamp
        self.assertEqual(scmod.CONVERTER_VERSION, "3E-rc1")


class Detection(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(svc.detect(W01)["kind"], "wii")
        self.assertEqual(svc.detect(DE_USER)["kind"], "de")
        self.assertEqual(svc.detect(DE_USER)["version"], 10)
        self.assertEqual(svc.detect(os.path.join(W, "nope"))["kind"], "missing")
        self.assertEqual(svc.detect(U.O)["kind"], "folder")
        self.assertIn(os.path.join(U.O, "monado01"), svc.detect(U.O)["saves"])
        p = os.path.join(W, "junk.bin")
        with open(p, "wb") as f:
            f.write(b"\0" * 1000)
        self.assertEqual(svc.detect(p)["kind"], "unknown")
        if os.path.exists(DE_V7):
            self.assertEqual(svc.detect(DE_V7)["version"], 7)

    def test_empty_wii_slot(self):
        k = svc.detect(W02)["kind"]
        self.assertIn(k, ("wii-empty", "wii"))
        if k == "wii-empty":
            with self.assertRaises(svc.Refused):
                svc.preview(W02)

    def test_sidecar_detected(self):
        out = os.path.join(W, "det_sc")
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=out))
        d = svc.detect(os.path.join(out, "wii_to_de.sidecar.json"))
        self.assertEqual((d["kind"], d["direction"]), ("sidecar", "wii_to_de"))


class Preview(unittest.TestCase):
    def test_user_wii_save(self):
        pv = svc.preview(W01)
        self.assertEqual((pv["game"], pv["story"], pv["map"], pv["map_name"], pv["play_time"]),
                         ("wii", 150, "ma1001", "Eryth Sea", "22:01:57"))
        self.assertEqual([m["name"] for m in pv["party"]], ["Shulk", "Dunban", "Riki", "Sharla", "Reyn", "Melia"])
        self.assertTrue(all(isinstance(m["level"], int) for m in pv["party"]))
        self.assertEqual(pv["unsupported_party"], [])

    def test_preview_matches_inspect(self):
        """The preview is the CLI's inspect summary (same decoder), only formatted."""
        s = svc.summary(U.rd(DE_USER))
        pv = svc.preview(DE_USER)
        self.assertEqual((pv["story"], pv["map"], pv["money"], pv["play_time"]),
                         (s["story"], s["map"], s["money"], s["play_time"]))
        self.assertEqual(pv["de_version"], 10)

    def test_unknown_map_is_not_guessed(self):
        names = svc.map_names()
        self.assertEqual(names.get("ma1001"), "Eryth Sea")
        self.assertIsNone(names.get("ma9999"))

    def test_v7_compatibility_explains_upgrade(self):
        if not os.path.exists(DE_V7):
            self.skipTest("public v7 save not present")
        rep = svc.compatibility(DE_V7)
        self.assertFalse(rep["compatible"])
        self.assertTrue(any("format v7" in p for p in rep["problems"]))


class Stages(unittest.TestCase):
    def test_stage_order_and_dry_run(self):
        seen = []
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=os.path.join(W, "stages")), seen.append)
        self.assertEqual(seen, ["read", "check", "translate", "verify", "write", "final"])
        seen.clear()
        out = os.path.join(W, "stages_dry")
        svc.de_to_wii_convert(svc.DeToWiiRequest(de=DE_USER, base=W03, out=out, dry_run=True), seen.append)
        self.assertEqual(seen, ["read", "check", "translate", "verify"])
        self.assertFalse(os.path.exists(out))

    def test_refusal_writes_nothing(self):
        out = os.path.join(W, "refused")
        with self.assertRaises(svc.REFUSALS):
            svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=W03, out=out))
        self.assertFalse(os.path.exists(out))


class OutputPlanning(unittest.TestCase):
    def test_live_and_existing_refused(self):
        with self.assertRaises(safeio.Refused):
            svc.plan_output(r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save\x",
                            "wii_to_de", "01")
        d = os.path.join(W, "plan_nonempty")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "x"), "w") as f:
            f.write("x")
        with self.assertRaises(safeio.Refused):
            svc.plan_output(d, "de_to_wii", "monado01")
        with self.assertRaises(safeio.Refused):
            svc.plan_output(os.path.join(W, "plan_ok"), "wii_to_de", "1")
        self.assertIn("save_0/bfsgame05.sav", svc.plan_output(os.path.join(W, "plan_ok"), "wii_to_de", "05"))
        self.assertFalse(os.path.exists(os.path.join(W, "plan_ok")))


class SidecarDiscovery(unittest.TestCase):
    """Chain (all synthetic, written by the converter): g1 Wii->DE, g2 DE->Wii, g3 Wii->DE after Wii play."""

    @classmethod
    def setUpClass(cls):
        cls.root = os.path.join(W, "disc")
        os.makedirs(cls.root)
        g1 = os.path.join(cls.root, "g1")
        svc.wii_to_de(svc.WiiToDeRequest(wii=W01, template=U.TPL, out=g1))
        cls.de1 = os.path.join(g1, "save_0", "bfsgame00.sav")
        g2 = os.path.join(cls.root, "g2")
        svc.de_to_wii_convert(svc.DeToWiiRequest(de=cls.de1, sidecar=os.path.join(g1, "wii_to_de.sidecar.json"),
                                                 current_wii=W01, out=g2))
        m = U.Wii(U.rd(os.path.join(g2, "monado01")))
        m.play(3600)
        m.money(5000)
        m.level_up(1)
        cls.w2p = os.path.join(cls.root, "w2_played")
        with open(cls.w2p, "wb") as f:
            f.write(m.done())
        g3 = os.path.join(cls.root, "g3")
        svc.wii_to_de(svc.WiiToDeRequest(wii=cls.w2p, sidecar=os.path.join(g2, "de_to_wii.sidecar.json"),
                                         current_de=cls.de1, out=g3))
        cls.de3 = os.path.join(g3, "save_0", "bfsgame00.sav")
        cls.g1, cls.g2, cls.g3 = g1, g2, g3

    def test_newest_matching_sidecar_chosen(self):
        d = svc.find_sidecars(self.de3, "de_to_wii", [self.root])
        self.assertIsNotNone(d.chosen, d.reason)
        self.assertEqual(os.path.dirname(d.chosen.path), self.g3)
        self.assertEqual((d.chosen.status, d.chosen.generation), ("exact", 3))

    def test_stale_sidecar_never_chosen(self):
        """The older DE save matches g1's sidecar, but g3 (same history) is newer: the user must choose."""
        d = svc.find_sidecars(self.de1, "de_to_wii", [self.root])
        self.assertIsNone(d.chosen)
        g1 = [c for c in d.candidates if os.path.dirname(c.path) == self.g1][0]
        self.assertEqual(g1.status, "exact")
        self.assertFalse(g1.newest)

    def test_wii_side_and_directions(self):
        d = svc.find_sidecars(self.w2p, "wii_to_de", [self.root])
        st = {os.path.basename(os.path.dirname(c.path)): c.status for c in d.candidates}
        self.assertEqual(st["g2"], "continues")
        self.assertEqual(st["g1"], "wrong-direction")
        self.assertEqual(st["g3"], "wrong-direction")
        self.assertIsNone(d.chosen)      # g3 (a later conversion of this history) exists: choose deliberately

    def test_foreign_and_damaged(self):
        foreign = os.path.join(W, "disc_foreign")
        svc.de_to_wii_convert(svc.DeToWiiRequest(de=DE_USER, base=W03, out=foreign))
        bad = os.path.join(W, "disc_bad")
        os.makedirs(bad)
        with open(os.path.join(bad, "x.sidecar.json"), "w") as f:
            f.write("{not json")
        d = svc.find_sidecars(W01, "wii_to_de", [foreign, bad])
        st = sorted(c.status for c in d.candidates)
        self.assertEqual(st, ["invalid", "unrelated"])
        self.assertIsNone(d.chosen)

    def test_engine_still_refuses_stale_choice(self):
        """Choosing the stale sidecar deliberately: the engine's lineage checks still stop it."""
        with self.assertRaises(svc.REFUSALS):
            svc.de_to_wii_convert(svc.DeToWiiRequest(de=self.de1, sidecar=os.path.join(self.g1, "wii_to_de.sidecar.json"),
                                                     current_wii=self.w2p, out=os.path.join(W, "stale_out")))
        self.assertFalse(os.path.exists(os.path.join(W, "stale_out")))


class TablesSetup(unittest.TestCase):
    def test_data_dir_override_and_missing_inputs(self):
        import dump_bdat
        import paths
        self.assertTrue(paths.has_tables(os.path.join(U.ROOT, "data")))
        self.assertFalse(paths.has_tables(W))
        miss = dump_bdat.missing_inputs(W, W)
        self.assertEqual(len(miss), 3)
        self.assertTrue(os.path.isfile(paths.spec("wii_award_tiers.json")))


if __name__ == "__main__":
    unittest.main()
