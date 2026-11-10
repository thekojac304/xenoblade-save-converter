"""Generate phase3d/scripts/build_rc_3d.py from the 3C build script (paths, version, file lists; no user_data)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
s = open(os.path.join(ROOT, "phase3c", "scripts", "build_rc_3c.py"), encoding="utf-8").read()
rep = [
    ('"""Assemble release_candidate_3C/ (Phase 3C). Copies only; never touches game folders or earlier releases.\n\n'
     'release_candidate_3C/',
     '"""Assemble release_candidate_3D/ (Phase 3D). Copies only; never touches game folders or earlier releases.\n\n'
     'release_candidate_3D/'),
    ("tools/ (engine with the 3C item-correspondence fix)",
     "tools/ (engine: 3C item correspondence + 3D character 8, D1, D2)"),
    ("phase3c/gui (3C-rc1), tests (2H, 3A, 3B, 3C, GUI)", "phase3d/gui (3D-rc1), tests (2H, 3A, 3B, 3C, 3D, GUI)"),
    ("  user_data/data/    bdat_wii.json / bdat_de.json made from YOUR game files - NOT FOR DISTRIBUTION\n",
     "  (no user_data: unlike 3C, no game tables are copied; the application asks for your own tables)\n"),
    ("  *.md               Phase 3C reports + the 3B/3A guides", "  *.md               Phase 3D reports + the 3C/3B/3A guides"),
    ("Usage: python phase3c/scripts/build_rc_3c.py", "Usage: python phase3d/scripts/build_rc_3d.py"),
    ('P3C = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3C)\n',
     'P3D = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3D)\nP3C = os.path.join(ROOT, "phase3c")\n'),
    ('RC = os.path.join(ROOT, "release_candidate_3C")', 'RC = os.path.join(ROOT, "release_candidate_3D")'),
    ('"dump_bdat.py", "itemcorr.py",', '"dump_bdat.py", "itemcorr.py", "stored_gear.py",'),
    ('DOCS = ["PHASE3C_SUMMARY.md",',
     'DOCS = ["PHASE3D_SUMMARY.md", "XC_PHASE3D_REPORT.md", "CHARACTER_STATE_MATRIX.md", "STORY_TRANSITION_RESULTS.md",\n'
     '        "THREE_PLATFORM_REGRESSION.md", "PHASE3C_SUMMARY.md",'),
    ('            "PHASE3C_SUMMARY.md"]', '            "PHASE3D_SUMMARY.md", "CHARACTER_STATE_MATRIX.md"]'),
    ('XC Save Converter 3C-rc1 (with Xenoblade Sync Hub) - notices', 'XC Save Converter 3D-rc1 (with Xenoblade Sync Hub) - notices'),
    ('XC Save Converter 3C-rc1 - Xenoblade Sync Hub + converter', 'XC Save Converter 3D-rc1 - Xenoblade Sync Hub + converter'),
    ("What changed in 3C: PHASE3C_SUMMARY.md.",
     "What changed in 3D: PHASE3D_SUMMARY.md\n(Fiora's later form - character 8 - is supported; saves from the late-game story split are refused)."),
    ("is not a 3C PyInstaller build", "is not a 3D PyInstaller build"),
    ('    cptree(os.path.join(P3C, "gui"), os.path.join(src, "phase3c", "gui"))\n',
     '    cptree(os.path.join(P3D, "gui"), os.path.join(src, "phase3d", "gui"))\n'
     '    for d in ("tests", "tests_gui", "tests_gui_3a"):\n'
     '        cptree(os.path.join(P3D, d), os.path.join(src, "phase3d", d), exts=(".py",))\n'
     '    for f in SCRIPTS3D:\n'
     '        cp(os.path.join(HERE, f), os.path.join(src, "phase3d", "scripts", f))\n'),
    ('        if os.path.exists(os.path.join(HERE, f)):\n            cp(os.path.join(HERE, f), os.path.join(src, "phase3c", "scripts", f))',
     '        if os.path.exists(os.path.join(P3C, "scripts", f)):\n            cp(os.path.join(P3C, "scripts", f), os.path.join(src, "phase3c", "scripts", f))'),
    ("GUI: python phase3c/gui/xcconv_gui.py", "GUI: python phase3d/gui/xcconv_gui.py"),
    ('    ud = os.path.join(RC, "user_data", "data")\n'
     '    for f in ("bdat_wii.json", "bdat_de.json"):\n'
     '        cp(os.path.join(ROOT, "data", f), os.path.join(ud, f))\n'
     '    open(os.path.join(RC, "user_data", "NOT_FOR_DISTRIBUTION.txt"), "w").write(NOT_FOR_DIST)\n', ''),
    ('    for f in sorted(os.listdir(os.path.join(P3C, "logs"))):\n        cp(os.path.join(P3C, "logs", f),',
     '    for f in sorted(os.listdir(os.path.join(P3D, "logs"))):\n        cp(os.path.join(P3D, "logs", f),'),
    ('    for f in ("e_parity_3b.json",):\n        if os.path.exists(os.path.join(P3C, "work", f)):\n'
     '            cp(os.path.join(P3C, "work", f), os.path.join(val, f))',
     '    for f in ("stash_scan.tsv", "package_test_3d.json", "package_test_3b.json", "package_test_3a.json"):\n'
     '        if os.path.exists(os.path.join(P3D, "work", f)):\n'
     '            cp(os.path.join(P3D, "work", f), os.path.join(val, f))'),
    ('        d = os.path.join(P3C, "runs", kind)', '        d = os.path.join(P3D, "runs", kind)'),
    ('    dsh = os.path.join(P3C, "runs", "dolphin")', '    dsh = os.path.join(P3D, "runs", "dolphin")'),
    ('    for f in sorted(os.listdir(os.path.join(P3C, "manifests"))):', '    for f in sorted(os.listdir(os.path.join(P3D, "manifests"))):'),
    ('            cp(os.path.join(P3C, "manifests", f), os.path.join(val, "manifests", f))',
     '            cp(os.path.join(P3D, "manifests", f), os.path.join(val, "manifests", f))'),
    ('    for f in os.listdir(os.path.join(P3C, "docs", "previous_3B")):\n'
     '        cp(os.path.join(P3C, "docs", "previous_3B", f), os.path.join(RC, "docs_3B", f))',
     '    for f in os.listdir(os.path.join(P3D, "docs", "previous_3C")):\n'
     '        cp(os.path.join(P3D, "docs", "previous_3C", f), os.path.join(RC, "docs_3C", f))'),
    ('SCRIPTS3C = [',
     'SCRIPTS3D = ["protect3d.py", "build_rc_3d.py", "make_build_rc_3d.py", "erun3d.py", "az3d.py", "package_test_3d.py",\n'
     '             "make_tests_gui_3d.py", "patch_gui3d.py", "stash.py", "stash_scan.py", "wdiff.py", "ccmp.py",\n'
     '             "itemset.py", "wii_callers.py", "bisect3ds.py", "fp_check.py", "a_char38.py", "mkstory.py",\n'
     '             "mkdroute.py", "runs_summary.py"]\nSCRIPTS3C = ['),
]
for a, b in rep:
    assert a in s, a[:90]
    s = s.replace(a, b, 1)
open(os.path.join(HERE, "build_rc_3d.py"), "w", encoding="utf-8").write(s)
print("ok")
