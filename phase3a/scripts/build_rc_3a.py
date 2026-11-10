"""Assemble release_candidate_3A/ (Phase 3A). Copies only; never touches game folders or earlier releases.

release_candidate_3A/
  XCSaveConverter/   portable Windows x64 application (XCSaveConverter.exe + xcconv.exe), distributable:
                     no game data, no saves, no game executables
  source/            tools/ (2H engine, unchanged), phase3a/src (3DS modules + CLI), phase3a/gui (3A GUI),
                     specs, tests (2H), phase3a/tests, phase3a/tests_gui, build spec - laid out like the research
                     folder so it runs from here (python source/phase3a/gui/xcconv_gui.py)
  user_data/data/    bdat_wii.json / bdat_de.json made from YOUR game files - NOT FOR DISTRIBUTION
  validation/        test logs, package test, GUI screenshots, emulator run summaries, protected-file manifest
  *.md               Phase 3A reports and guides
  SHA256SUMS.txt
Usage: python phase3a/scripts/build_rc_3a.py <PyInstaller dist folder XCSaveConverter>
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3)
RC = os.path.join(ROOT, "release_candidate_3A")
CODE = ["xcconv.py", "xcservice.py", "convert.py", "de_to_wii.py", "canon.py", "sidecar.py", "reimport.py", "safeio.py",
        "wii_save.py", "de_save.py", "flagmap.py", "flag_transplant_eval.py", "phase2c.py", "quest_counters.py",
        "achievements.py", "minimap.py", "paths.py", "bdat.py", "dump_bdat.py"]
SRC3 = ["qlz.py", "xc3d.py", "xc3dstats.py", "xc3dservice.py", "xcservice3.py", "xcconv3.py",
        "azahar_harness.py", "seq.py", "arm.py", "ctr.py"]
SPECS = ["wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json"]
GUI = ["xcconv_gui.py", "xcconv_cli.py", "xcsaveconverter.spec", "version_info.txt",
       "xcgui/__init__.py", "xcgui/app.py", "xcgui/advanced.py", "xcgui/main_window.py", "xcgui/messages.py",
       "xcgui/widgets.py", "xcgui/worker.py", "tools/shots3a.py"]
SCRIPTS = ["protect3a.py", "package_test_3a.py", "make_package_test_3a.py", "patch_gui3a.py", "build_rc_3a.py",
           "cmp_canon.py", "inv_multiset.py"]
DOCS = ["PHASE3A_SUMMARY.md", "XC_THREE_WAY_PHASE3A.md", "THREE_WAY_COMPATIBILITY.md", "THREE_WAY_TEST_RESULTS.md",
        "SIDECAR_V3_DESIGN.md", "GUI_USER_GUIDE.md", "KNOWN_LIMITATIONS.md", "RELEASE_READINESS.md"]
DOCS_APP = ["GUI_USER_GUIDE.md", "KNOWN_LIMITATIONS.md"]
NOT_FOR_DIST = "These files are derived from your own game data. Keep them private; do not publish or share them.\n"
NOTICE = """XC Save Converter 3A-rc1 - notices

Licence: none chosen yet. The code was written for the owner of this research folder; all rights reserved until the
owner picks a licence. Nothing in this package is published.

Third-party software in this folder (runtime only, unmodified):
  * Python 3.14 runtime (PSF licence)
  * Qt 6 / PySide6 6.12 (LGPLv3; dynamically linked DLLs in _internal, replaceable)
  * PyInstaller bootloader (GPL with a bootloader exception)
Formats implemented from public descriptions, no third-party code: QuickLZ 1.5 level-3 block format (qlz.py, an
independent implementation); DE save offsets from hashcade/xbde-save-editor documentation and hanyu1774
PartyMember.cs (cited in tools/de_save.py), re-verified. The GBAtemp "Xenoblade Chronicles 3D Save Utility"
(WulfyStylez, 2016) was consulted for its description only; none of its code is used.

Not included, by design: game executables, ROMs, disc images, keys, BDAT tables or other game data, and any save
file. On first start the application asks for the user's own tables (made from the user's own game files).
"""
README_FIRST = """XC Save Converter 3A-rc1 (Wii <-> Xenoblade Chronicles: Definitive Edition <-> Xenoblade Chronicles 3D)

Start XCSaveConverter.exe. No installation and no Python needed. Keep this whole folder together.
Read GUI_USER_GUIDE.md first; KNOWN_LIMITATIONS.md lists what is not supported. Real New 3DS support is untested.

The program never writes into a game, emulator, SD-card or save folder: it creates a new folder for each conversion
(by default Documents\\XC Save Converter\\Converted saves). You copy the result into the game yourself, after a backup.
xcconv.exe is the same converter for the command line (xcconv.exe --help).
"""
README_3A = """

---

# 3A additions: New 3DS (Xenoblade Chronicles 3D)

`xcconv.exe` (or `python source/phase3a/src/xcconv3.py`) keeps every command above unchanged and adds:

```
xcconv inspect <3DS monado0N>            validate <3DS monado0N>
xcconv wii-to-3ds --wii W --template X3 --out NEW [--slot 1|2|3] [--record R (--current-3ds X | --no-current-3ds)]
xcconv 3ds-to-wii --3ds X --out NEW [--slot monado0N] [--record R (--current-wii W | --no-current-wii)]
xcconv de-to-3ds  --de D --template X3 --out NEW [--slot 1|2|3] [--overflow sidecar] [--record R (--current-3ds X | --no-current-3ds)]
xcconv 3ds-to-de  --3ds X --out NEW (--template DE | --record R (--current-de D | --no-current-de)) [--slot NN]
   --keep-this-progress   on a divergence keep this save's progress (never merges)
xcconv record-info <file.record.json>    unpack-3ds <3DS save> <out.bin>
```

Outputs: `NEW\\3ds\\monado0N` (+ `NEW\\checkpoint\\xcconv_<id>\\` = the complete save archive when the template sits in
a complete archive folder), `NEW\\monado0N`, or `NEW\\save_0\\bfsgameNN.sav`; always `<direction>.record.json` and
`manifest.json`. See SIDECAR_V3_DESIGN.md and THREE_WAY_COMPATIBILITY.md.
"""


def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def main(dist):
    if os.path.exists(RC):
        raise SystemExit(f"{RC} exists; it is generated - move it away first")
    for f in ("XCSaveConverter.exe", "xcconv.exe"):
        if not os.path.isfile(os.path.join(dist, f)):
            raise SystemExit(f"{dist} is not a PyInstaller build of XCSaveConverter ({f} missing)")
    app = os.path.join(RC, "XCSaveConverter")
    shutil.copytree(dist, app)
    for f in DOCS_APP:
        cp(os.path.join(ROOT, f), os.path.join(app, f))
    with open(os.path.join(app, "README_FIRST.txt"), "w", encoding="utf-8") as f:
        f.write(README_FIRST)
    with open(os.path.join(app, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE)
    src = os.path.join(RC, "source")
    for f in CODE:
        cp(os.path.join(ROOT, "tools", f), os.path.join(src, "tools", f))
    for f in SRC3:
        cp(os.path.join(P3, "src", f), os.path.join(src, "phase3a", "src", f))
    for f in SPECS:
        cp(os.path.join(ROOT, "specs", f), os.path.join(src, "specs", f))
    cp(os.path.join(P3, "specs", "xc3d_layout.json"), os.path.join(src, "phase3a", "specs", "xc3d_layout.json"))
    for f in GUI:
        cp(os.path.join(P3, "gui", f), os.path.join(src, "phase3a", "gui", f))
    for f in SCRIPTS:
        cp(os.path.join(P3, "scripts", f), os.path.join(src, "phase3a", "scripts", f))
    for d, dst in (("tests", os.path.join(src, "tests")), (os.path.join("phase3a", "tests"), os.path.join(src, "phase3a", "tests")),
                   (os.path.join("phase3a", "tests_gui"), os.path.join(src, "phase3a", "tests_gui"))):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith(".py"):
                cp(os.path.join(ROOT, d, f), os.path.join(dst, f))
    with open(os.path.join(src, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE)
    with open(os.path.join(src, "README_SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write("Same layout as the research folder. GUI: python phase3a/gui/xcconv_gui.py; CLI: python "
                "phase3a/src/xcconv3.py --help. Tests need the owner's own saves (not included).\n")
    ud = os.path.join(RC, "user_data", "data")
    for f in ("bdat_wii.json", "bdat_de.json"):
        cp(os.path.join(ROOT, "data", f), os.path.join(ud, f))
    with open(os.path.join(RC, "user_data", "NOT_FOR_DISTRIBUTION.txt"), "w") as f:
        f.write(NOT_FOR_DIST)
    val = os.path.join(RC, "validation")
    for f in ("final_unittest_3a.txt", "final_unittest_2H.txt", "final_gui_3a.txt", "package_test_3a.json",
              "baseline_unittest_2H_full.txt"):
        p = os.path.join(P3, "logs", f)
        if os.path.exists(p):
            cp(p, os.path.join(val, "logs", f))
    for f in sorted(os.listdir(os.path.join(P3, "screenshots"))):
        if f.endswith(".png"):
            cp(os.path.join(P3, "screenshots", f), os.path.join(val, "gui_screenshots", f))
    runs = {}
    for name in sorted(os.listdir(os.path.join(P3, "runs", "azahar"))):
        p = os.path.join(P3, "runs", "azahar", name, "result.json")
        if os.path.exists(p):
            runs[f"azahar/{name}"] = json.load(open(p))
    for kind in ("dolphin", "monado"):
        d = os.path.join(ROOT, "phase2f", "runs", kind)
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name, "run_manifest.json")
            if name.startswith("p3a_") and os.path.exists(p):
                runs[f"{kind}/{name}"] = json.load(open(p))
    with open(os.path.join(val, "emulator_runs.json"), "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=1, default=str)
    for f in ("protected_start.json", "protected_final.json"):
        p = os.path.join(P3, "manifests", f)
        if os.path.exists(p):
            cp(p, os.path.join(val, "manifests", f))
    for f in DOCS:
        cp(os.path.join(ROOT, f), os.path.join(RC, f))
    readme = open(os.path.join(ROOT, "phase3a", "docs", "previous_2H", "README_CONVERTER.md"), encoding="utf-8").read()
    with open(os.path.join(RC, "README_CONVERTER.md"), "w", encoding="utf-8") as f:
        f.write(readme + README_3A)
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
