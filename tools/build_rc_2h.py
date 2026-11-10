"""Assemble release_candidate_2H/ (Phase 2H). Copies only; never touches game folders or earlier releases.

release_candidate_2H/
  XCSaveConverter/   portable Windows x64 application (XCSaveConverter.exe + xcconv.exe), distributable:
                     no game data, no saves, no game executables
  source/            converter engine, service layer, GUI, specs, tests, build spec (distributable)
  user_data/data/    bdat_wii.json / bdat_de.json made from YOUR game files - NOT FOR DISTRIBUTION
                     (the application finds this folder automatically when it sits next to XCSaveConverter/)
  validation/        test logs, package test, screenshots, protected-file manifest
  *.md               Phase 2H report and guides
  SHA256SUMS.txt
Usage: python tools/build_rc_2h.py <PyInstaller dist folder XCSaveConverter>
"""
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RC = os.path.join(ROOT, "release_candidate_2H")
P2H = os.path.join(ROOT, "phase2h")
CODE = ["xcconv.py", "xcservice.py", "convert.py", "de_to_wii.py", "canon.py", "sidecar.py", "reimport.py", "safeio.py",
        "wii_save.py", "de_save.py", "flagmap.py", "flag_transplant_eval.py", "phase2c.py", "quest_counters.py",
        "achievements.py", "minimap.py", "paths.py", "bdat.py", "dump_bdat.py"]
SPECS = ["wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json"]
GUI = ["xcconv_gui.py", "xcconv_cli.py", "xcsaveconverter.spec", "version_info.txt",
       "xcgui/__init__.py", "xcgui/app.py", "xcgui/advanced.py", "xcgui/main_window.py", "xcgui/messages.py", "xcgui/widgets.py",
       "xcgui/worker.py", "tools/shots.py"]
DOCS_APP = ["GUI_USER_GUIDE.md", "KNOWN_LIMITATIONS.md"]
DOCS_SRC = ["README_CONVERTER.md", "BIDIRECTIONAL_DESIGN.md", "KNOWN_LIMITATIONS.md", "GUI_USER_GUIDE.md"]
REPORTS = ["XC_WII_TO_DE_PHASE2H.md", "GUI_TEST_RESULTS.md", "GUI_USER_GUIDE.md", "KNOWN_LIMITATIONS.md",
           "RELEASE_READINESS.md", "README_CONVERTER.md"]
NOT_FOR_DIST = ("These files are derived from your own game data. Keep them private; do not publish or share them.\n")
NOTICE = """XC Save Converter 2H-rc1 - notices

Licence: none chosen yet. The code was written for the owner of this research folder; all rights reserved until the
owner picks a licence. Nothing in this package is published.

Third-party software in this folder (runtime only, unmodified):
  * Python 3.14 runtime (PSF licence)
  * Qt 6 / PySide6 6.12 (LGPLv3; dynamically linked DLLs in _internal, replaceable)
  * PyInstaller bootloader (GPL with a bootloader exception)
Third-party information used (no third-party code): DE save offsets from hashcade/xbde-save-editor documentation and
hanyu1774 PartyMember.cs (cited in tools/de_save.py), re-verified against real saves and the DE executable.

Not included, by design: game executables, disc images, BDAT tables or other game data, and any save file. On first
start the application asks for the user's own tables (made from the user's own game files).
"""
README_FIRST = """XC Save Converter 2H-rc1 (Wii <-> Xenoblade Chronicles: Definitive Edition)

Start XCSaveConverter.exe. No installation and no Python needed. Keep this whole folder together.
Read GUI_USER_GUIDE.md first; KNOWN_LIMITATIONS.md lists what is not supported.

The program never writes into a game, emulator or save folder: it creates a new folder for each conversion
(by default Documents\\XC Save Converter\\Converted saves). You copy the result into the game yourself, after a backup.
xcconv.exe is the same converter for the command line (xcconv.exe --help).
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
        cp(os.path.join(HERE, f), os.path.join(src, "tools", f))
    for f in SPECS:
        cp(os.path.join(ROOT, "specs", f), os.path.join(src, "specs", f))
    for f in GUI:
        cp(os.path.join(ROOT, "gui", f), os.path.join(src, "gui", f))
    for d in ("tests", "tests_gui"):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith(".py"):
                cp(os.path.join(ROOT, d, f), os.path.join(src, d, f))
    for f in DOCS_SRC:
        cp(os.path.join(ROOT, f), os.path.join(src, f))
    with open(os.path.join(src, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE)
    ud = os.path.join(RC, "user_data", "data")
    for f in ("bdat_wii.json", "bdat_de.json"):
        cp(os.path.join(ROOT, "data", f), os.path.join(ud, f))
    with open(os.path.join(RC, "user_data", "NOT_FOR_DISTRIBUTION.txt"), "w") as f:
        f.write(NOT_FOR_DIST)
    val = os.path.join(RC, "validation")
    res = os.path.join(P2H, "results")
    for f in sorted(os.listdir(res)):
        cp(os.path.join(res, f), os.path.join(val, f))
    shots = os.path.join(P2H, "screenshots")
    if os.path.isdir(shots):
        shutil.copytree(shots, os.path.join(val, "screenshots"))
    for f in REPORTS:
        if os.path.exists(os.path.join(ROOT, f)):
            cp(os.path.join(ROOT, f), os.path.join(RC, f))
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
