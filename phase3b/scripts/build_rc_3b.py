"""Assemble release_candidate_3B/ (Phase 3B). Copies only; never touches game folders or earlier releases.

release_candidate_3B/
  XCSaveConverter/   portable Windows x64 application: XCSaveConverter.exe (Sync Hub + converter), xcconv.exe,
                     xcsync.exe. Distributable: no game data, no saves, no game executables
  source/            tools/ (2H engine, unchanged), phase3a/src (3A, unchanged), phase3b/src (xcsync), phase3b/gui,
                     tests (2H, 3A, 3B, GUI), build spec and scripts - laid out like the research folder
  user_data/data/    bdat_wii.json / bdat_de.json made from YOUR game files - NOT FOR DISTRIBUTION
  validation/        test logs, package tests, screenshots, emulator runs, acceptance steps, protected manifests
  *.md               Phase 3B reports and guides (+ the 3A ones)
  SHA256SUMS.txt
Usage: python phase3b/scripts/build_rc_3b.py <PyInstaller dist folder XCSaveConverter>
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P3B = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3B)
P3 = os.path.join(ROOT, "phase3a")
RC = os.path.join(ROOT, "release_candidate_3B")
CODE = ["xcconv.py", "xcservice.py", "convert.py", "de_to_wii.py", "canon.py", "sidecar.py", "reimport.py", "safeio.py",
        "wii_save.py", "de_save.py", "flagmap.py", "flag_transplant_eval.py", "phase2c.py", "quest_counters.py",
        "achievements.py", "minimap.py", "paths.py", "bdat.py", "dump_bdat.py",
        "monado_harness.py", "dolphin_harness.py", "route.py", "droute.py"]
SRC3 = ["qlz.py", "xc3d.py", "xc3dstats.py", "xc3dservice.py", "xcservice3.py", "xcconv3.py",
        "azahar_harness.py", "seq.py", "arm.py", "ctr.py"]
SPECS = ["wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json"]
SCRIPTS = ["protect3b.py", "package_test_3b.py", "build_rc_3b.py", "patch_gui3b.py", "make_tests_gui_3a.py",
           "erun3b.py", "az3b.py", "acceptance.py", "smoke.py"]
DOCS = ["PHASE3B_SUMMARY.md", "XC_SYNC_HUB_PHASE3B.md", "SYNC_HUB_USER_GUIDE.md", "SYNC_TEST_RESULTS.md",
        "SYNC_HISTORY_DESIGN.md", "SYNC_KNOWN_LIMITATIONS.md", "RELEASE_READINESS.md",
        "XC_THREE_WAY_PHASE3A.md", "THREE_WAY_COMPATIBILITY.md", "SIDECAR_V3_DESIGN.md", "GUI_USER_GUIDE.md",
        "KNOWN_LIMITATIONS.md"]
DOCS_APP = ["SYNC_HUB_USER_GUIDE.md", "SYNC_KNOWN_LIMITATIONS.md", "GUI_USER_GUIDE.md", "KNOWN_LIMITATIONS.md"]
NOT_FOR_DIST = "These files are derived from your own game data. Keep them private; do not publish or share them.\n"
NOTICE = """XC Save Converter 3B-rc1 (with Xenoblade Sync Hub) - notices

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
README_FIRST = """XC Save Converter 3B-rc1 - Xenoblade Sync Hub + converter (Wii, Definitive Edition, Xenoblade 3D)

Start XCSaveConverter.exe. No installation and no Python needed. Keep this whole folder together.
Sync Hub tab: read SYNC_HUB_USER_GUIDE.md first (setup ~10 minutes; then Open -> Sync All -> Close).
Convert one save tab: the unchanged 3A converter (GUI_USER_GUIDE.md).
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
            raise SystemExit(f"{dist} is not a 3B PyInstaller build ({f} missing)")
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
    cptree(os.path.join(P3B, "gui"), os.path.join(src, "phase3b", "gui"))
    for d in ("tests", "tests_gui", "tests_gui_3a", "routes_dsl"):
        s = os.path.join(P3B, d) if d != "routes_dsl" else os.path.join(P3B, "runs", "routes_dsl")
        cptree(s, os.path.join(src, "phase3b", d), exts=(".py", ".txt", ".dsl"))
    for f in SCRIPTS:
        cp(os.path.join(HERE, f), os.path.join(src, "phase3b", "scripts", f))
    for d, dst in (("tests", "tests"), (os.path.join("phase3a", "tests"), os.path.join("phase3a", "tests")),
                   (os.path.join("phase3a", "tests_gui"), os.path.join("phase3a", "tests_gui"))):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith(".py"):
                cp(os.path.join(ROOT, d, f), os.path.join(src, dst, f))
    open(os.path.join(src, "NOTICE.txt"), "w", encoding="utf-8").write(NOTICE)
    open(os.path.join(src, "README_SOURCE.txt"), "w", encoding="utf-8").write(
        "Same layout as the research folder. GUI: python phase3b/gui/xcconv_gui.py; Sync Hub CLI: python "
        "phase3b/src/xcsync_cli.py --help; converter CLI: python phase3a/src/xcconv3.py --help. Tests need the "
        "owner's own saves and fixtures (not included).\n")
    ud = os.path.join(RC, "user_data", "data")
    for f in ("bdat_wii.json", "bdat_de.json"):
        cp(os.path.join(ROOT, "data", f), os.path.join(ud, f))
    open(os.path.join(RC, "user_data", "NOT_FOR_DISTRIBUTION.txt"), "w").write(NOT_FOR_DIST)
    val = os.path.join(RC, "validation")
    for f in sorted(os.listdir(os.path.join(P3B, "logs"))):
        cp(os.path.join(P3B, "logs", f), os.path.join(val, "logs", f))
    for f in sorted(os.listdir(os.path.join(P3B, "screenshots"))):
        if f.endswith(".png"):
            cp(os.path.join(P3B, "screenshots", f), os.path.join(val, "gui_screenshots", f))
    runs = {}
    for kind, fname in (("azahar", "result.json"), ("monado", "run_manifest.json"), ("dolphin", "run_manifest.json")):
        d = os.path.join(P3B, "runs", kind)
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
    dsh = os.path.join(P3B, "runs", "dolphin")
    if os.path.isdir(dsh):
        for name in os.listdir(dsh):
            for r, _, fs in os.walk(os.path.join(dsh, name, "user", "ScreenShots")):
                for f in fs:
                    cp(os.path.join(r, f), os.path.join(val, "emulator_shots", "dolphin", name, f))
    json.dump(runs, open(os.path.join(val, "emulator_runs.json"), "w", encoding="utf-8"), indent=1, default=str)
    steps = os.path.join(P3B, "runs", "acceptance", "steps")
    for name in sorted(os.listdir(steps)):
        for f in ("result.json", "window.png"):
            p = os.path.join(steps, name, f)
            if os.path.exists(p):
                cp(p, os.path.join(val, "acceptance_steps", name, f))
    hub = os.path.join(P3B, "runs", "acceptance", "Xenoblade Sync")
    for n in sorted(os.listdir(os.path.join(hub, "history"))):
        p = os.path.join(hub, "history", n, "generation.json")
        if os.path.exists(p):
            cp(p, os.path.join(val, "acceptance_history", n, "generation.json"))
    for f in sorted(os.listdir(os.path.join(P3B, "manifests"))):
        if f in ("protected_start.json",) or f.startswith("protected_after_final"):
            cp(os.path.join(P3B, "manifests", f), os.path.join(val, "manifests", f))
    for f in DOCS:
        cp(os.path.join(ROOT, f), os.path.join(RC, f))
    for f in os.listdir(os.path.join(P3B, "docs", "previous_3A")):
        cp(os.path.join(P3B, "docs", "previous_3A", f), os.path.join(RC, "docs_3A", f))
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
