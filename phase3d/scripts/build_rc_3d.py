"""Assemble release_candidate_3D/ (Phase 3D). Copies only; never touches game folders or earlier releases.

release_candidate_3D/
  XCSaveConverter/   portable Windows x64 application: XCSaveConverter.exe (Sync Hub + converter), xcconv.exe,
                     xcsync.exe. Distributable: no game data, no saves, no game executables
  source/            tools/ (engine: 3C item correspondence + 3D character 8, D1, D2), phase3a/src, phase3b/src (xcsync),
                     phase3d/gui (3D-rc1), tests (2H, 3A, 3B, 3C, 3D, GUI), build spec and scripts - laid out like the research folder
  (no user_data: unlike 3C, no game tables are copied; the application asks for your own tables)
  validation/        test logs, package tests, screenshots, emulator runs, acceptance steps, protected manifests
  *.md               Phase 3D reports + the 3C/3B/3A guides
  SHA256SUMS.txt
Usage: python phase3d/scripts/build_rc_3d.py <PyInstaller dist folder XCSaveConverter>
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P3D = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3D)
P3C = os.path.join(ROOT, "phase3c")
P3B = os.path.join(ROOT, "phase3b")
P3 = os.path.join(ROOT, "phase3a")
RC = os.path.join(ROOT, "release_candidate_3D")
CODE = ["xcconv.py", "xcservice.py", "convert.py", "de_to_wii.py", "canon.py", "sidecar.py", "reimport.py", "safeio.py",
        "wii_save.py", "de_save.py", "flagmap.py", "flag_transplant_eval.py", "phase2c.py", "quest_counters.py",
        "achievements.py", "minimap.py", "paths.py", "bdat.py", "dump_bdat.py", "itemcorr.py", "stored_gear.py",
        "monado_harness.py", "dolphin_harness.py", "route.py", "droute.py"]
SRC3 = ["qlz.py", "xc3d.py", "xc3dstats.py", "xc3dservice.py", "xcservice3.py", "xcconv3.py",
        "azahar_harness.py", "seq.py", "arm.py", "ctr.py"]
SPECS = ["wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json"]
SCRIPTS = ["protect3b.py", "package_test_3b.py", "build_rc_3b.py", "patch_gui3b.py", "make_tests_gui_3a.py",
           "erun3b.py", "az3b.py", "acceptance.py", "smoke.py"]
SCRIPTS3D = ["protect3d.py", "build_rc_3d.py", "make_build_rc_3d.py", "erun3d.py", "az3d.py", "package_test_3d.py",
             "make_tests_gui_3d.py", "patch_gui3d.py", "stash.py", "stash_scan.py", "wdiff.py", "ccmp.py",
             "itemset.py", "wii_callers.py", "bisect3ds.py", "fp_check.py", "a_char38.py", "mkstory.py",
             "mkdroute.py", "runs_summary.py"]
SCRIPTS3C = ["protect3c.py", "build_rc_3c.py", "erun3c.py", "az3c.py", "baseline3b.py", "e_parity_3b.py",
             "mkstory.py", "b_checkpoint.py", "d_flagsites.py", "a1_item_bytes.py", "a1_roundtrip_loss.py",
             "a1_exe_scan.py", "a1_fav_scan.py", "a1_slot_motion.py", "a1_age_behaviour.py", "a1_named.py",
             "package_test_3c.py"]
DOCS = ["PHASE3D_SUMMARY.md", "XC_PHASE3D_REPORT.md", "CHARACTER_STATE_MATRIX.md", "STORY_TRANSITION_RESULTS.md",
        "THREE_PLATFORM_REGRESSION.md", "PHASE3C_SUMMARY.md", "XC_PHASE3C_REPORT.md", "DE_METADATA_FIDELITY.md", "STORY_PROGRESSION_TESTS.md",
        "GAMEPLAY_COMPATIBILITY_MATRIX.md", "REGRESSION_RESULTS.md", "PHASE3B_SUMMARY.md", "XC_SYNC_HUB_PHASE3B.md", "SYNC_HUB_USER_GUIDE.md", "SYNC_TEST_RESULTS.md",
        "SYNC_HISTORY_DESIGN.md", "SYNC_KNOWN_LIMITATIONS.md", "RELEASE_READINESS.md",
        "XC_THREE_WAY_PHASE3A.md", "THREE_WAY_COMPATIBILITY.md", "SIDECAR_V3_DESIGN.md", "GUI_USER_GUIDE.md",
        "KNOWN_LIMITATIONS.md"]
DOCS_APP = ["SYNC_HUB_USER_GUIDE.md", "SYNC_KNOWN_LIMITATIONS.md", "GUI_USER_GUIDE.md", "KNOWN_LIMITATIONS.md",
            "PHASE3D_SUMMARY.md", "CHARACTER_STATE_MATRIX.md"]
NOT_FOR_DIST = "These files are derived from your own game data. Keep them private; do not publish or share them.\n"
NOTICE = """XC Save Converter 3D-rc1 (with Xenoblade Sync Hub) - notices

Licence: none chosen yet. The code was written for the owner of this research folder; all rights reserved until the
owner picks a licence. Nothing in this package is published.

Third-party software in this folder (runtime only, unmodified):
  * Python 3.14 runtime (PSF licence)
  * Qt 6 / PySide6 (LGPLv3; dynamically linked DLLs in _internal, replaceable)
  * PyInstaller bootloader (GPL with a bootloader exception)
Formats implemented from public descriptions, no third-party code: QuickLZ 1.5 level-3 block format (qlz.py, an
independent implementation); DE save offsets from hashcade/xbde-save-editor documentation and hanyu1774
PartyMember.cs (cited in tools/de_save.py), re-verified. Syncthing is not bundled or controlled; the Sync Hub only
reads ordinary folders.

Not included, by design: game executables, ROMs, disc images, keys, BDAT tables or other game data, and any save
file. On first start the application asks for the user's own tables (made from the user's own game files).
"""
README_FIRST = """XC Save Converter 3D-rc1 - Xenoblade Sync Hub + converter (Wii, Definitive Edition, Xenoblade 3D)

Start XCSaveConverter.exe. No installation and no Python needed. Keep this whole folder together.
Sync Hub tab: read SYNC_HUB_USER_GUIDE.md first (setup ~10 minutes; then Open -> Sync All -> Close).
Convert one save tab: the converter (GUI_USER_GUIDE.md). What changed in 3D: PHASE3D_SUMMARY.md
(Fiora's later form - character 8 - is supported; saves from the late-game story split are refused).
SYNC_KNOWN_LIMITATIONS.md and KNOWN_LIMITATIONS.md list what is not supported. Real New 3DS and Android devices are
untested.

The program never writes into a game, emulator, SD-card or save folder and never installs saves: the Sync Hub puts
new saves into per-device ready folders inside the Sync Hub folder you choose; you copy them into the game.
xcsync.exe is the Sync Hub for the command line, xcconv.exe the converter (both: --help).
"""


def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def cptree(src, dst, exts=(".py", ".txt", ".spec", ".md", ".dsl", ".json")):
    for r, ds, fs in os.walk(src):
        ds[:] = [d for d in ds if d != "__pycache__"]
        for f in fs:
            if f.endswith(exts):
                cp(os.path.join(r, f), os.path.join(dst, os.path.relpath(os.path.join(r, f), src)))


def main(dist):
    if os.path.exists(RC):
        raise SystemExit(f"{RC} exists; it is generated - move it away first")
    for f in ("XCSaveConverter.exe", "xcconv.exe", "xcsync.exe"):
        if not os.path.isfile(os.path.join(dist, f)):
            raise SystemExit(f"{dist} is not a 3D PyInstaller build ({f} missing)")
    app = os.path.join(RC, "XCSaveConverter")
    shutil.copytree(dist, app)
    for f in DOCS_APP:
        cp(os.path.join(ROOT, f), os.path.join(app, f))
    open(os.path.join(app, "README_FIRST.txt"), "w", encoding="utf-8").write(README_FIRST)
    open(os.path.join(app, "NOTICE.txt"), "w", encoding="utf-8").write(NOTICE)
    src = os.path.join(RC, "source")
    for f in CODE:
        cp(os.path.join(ROOT, "tools", f), os.path.join(src, "tools", f))
    for f in SRC3:
        cp(os.path.join(P3, "src", f), os.path.join(src, "phase3a", "src", f))
    for f in SPECS:
        cp(os.path.join(ROOT, "specs", f), os.path.join(src, "specs", f))
    cp(os.path.join(P3, "specs", "xc3d_layout.json"), os.path.join(src, "phase3a", "specs", "xc3d_layout.json"))
    cptree(os.path.join(P3B, "src"), os.path.join(src, "phase3b", "src"))
    cptree(os.path.join(P3D, "gui"), os.path.join(src, "phase3d", "gui"))
    for d in ("tests", "tests_gui", "tests_gui_3a"):
        cptree(os.path.join(P3D, d), os.path.join(src, "phase3d", d), exts=(".py",))
    for f in SCRIPTS3D:
        cp(os.path.join(HERE, f), os.path.join(src, "phase3d", "scripts", f))
    cptree(os.path.join(P3C, "tests"), os.path.join(src, "phase3c", "tests"), exts=(".py",))
    for f in SCRIPTS3C:
        if os.path.exists(os.path.join(P3C, "scripts", f)):
            cp(os.path.join(P3C, "scripts", f), os.path.join(src, "phase3c", "scripts", f))
    for d in ("tests", "tests_gui", "tests_gui_3a", "routes_dsl"):
        s = os.path.join(P3B, d) if d != "routes_dsl" else os.path.join(P3B, "runs", "routes_dsl")
        cptree(s, os.path.join(src, "phase3b", d), exts=(".py", ".txt", ".dsl"))
    for f in SCRIPTS:
        cp(os.path.join(P3B, "scripts", f), os.path.join(src, "phase3b", "scripts", f))
    for d, dst in (("tests", "tests"), (os.path.join("phase3a", "tests"), os.path.join("phase3a", "tests")),
                   (os.path.join("phase3a", "tests_gui"), os.path.join("phase3a", "tests_gui"))):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith(".py"):
                cp(os.path.join(ROOT, d, f), os.path.join(src, dst, f))
    open(os.path.join(src, "NOTICE.txt"), "w", encoding="utf-8").write(NOTICE)
    open(os.path.join(src, "README_SOURCE.txt"), "w", encoding="utf-8").write(
        "Same layout as the research folder. GUI: python phase3d/gui/xcconv_gui.py; Sync Hub CLI: python "
        "phase3b/src/xcsync_cli.py --help; converter CLI: python phase3a/src/xcconv3.py --help. Tests need the "
        "owner's own saves and fixtures (not included).\n")
    val = os.path.join(RC, "validation")
    for f in sorted(os.listdir(os.path.join(P3D, "logs"))):
        cp(os.path.join(P3D, "logs", f), os.path.join(val, "logs", f))
    for f in ("stash_scan.tsv", "package_test_3d.json", "package_test_3b.json", "package_test_3a.json"):
        if os.path.exists(os.path.join(P3D, "work", f)):
            cp(os.path.join(P3D, "work", f), os.path.join(val, f))
    runs = {}
    for kind, fname in (("azahar", "result.json"), ("monado", "run_manifest.json"), ("dolphin", "run_manifest.json")):
        d = os.path.join(P3D, "runs", kind)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name, fname)
            if os.path.exists(p):
                runs[f"{kind}/{name}"] = json.load(open(p))
            shots = os.path.join(d, name, "shots")
            if os.path.isdir(shots):
                for f in sorted(os.listdir(shots)):
                    cp(os.path.join(shots, f), os.path.join(val, "emulator_shots", kind, name, f))
    dsh = os.path.join(P3D, "runs", "dolphin")
    if os.path.isdir(dsh):
        for name in os.listdir(dsh):
            for r, _, fs in os.walk(os.path.join(dsh, name, "user", "ScreenShots")):
                for f in fs:
                    cp(os.path.join(r, f), os.path.join(val, "emulator_shots", "dolphin", name, f))
    json.dump(runs, open(os.path.join(val, "emulator_runs.json"), "w", encoding="utf-8"), indent=1, default=str)
    for f in sorted(os.listdir(os.path.join(P3D, "manifests"))):
        if f in ("protected_start.json",) or f.startswith("protected_after_") or f.startswith("protected_final"):
            cp(os.path.join(P3D, "manifests", f), os.path.join(val, "manifests", f))
    for f in DOCS:
        cp(os.path.join(ROOT, f), os.path.join(RC, f))
    for f in os.listdir(os.path.join(P3D, "docs", "previous_3C")):
        cp(os.path.join(P3D, "docs", "previous_3C", f), os.path.join(RC, "docs_3C", f))
    sums = []
    for r, _, fs in os.walk(RC):
        for f in sorted(fs):
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                sums.append((hashlib.sha256(fh.read()).hexdigest(), os.path.relpath(p, RC).replace("\\", "/")))
    with open(os.path.join(RC, "SHA256SUMS.txt"), "w", newline="\n") as f:
        f.write("".join(f"{h} *{p}\n" for h, p in sorted(sums, key=lambda x: x[1])))
    print(f"{len(sums)} files in {RC}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
