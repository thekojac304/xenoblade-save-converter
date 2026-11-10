"""Generate phase3e/scripts/package_test_3e.py and build_rc_3e.py from the 3D versions (paths, version, checks)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))


def gen(src, dst, pairs):
    s = open(os.path.join(ROOT, "phase3d", "scripts", src), encoding="utf-8").read()
    for a, b in pairs:
        assert a in s, (src, a[:90])
        s = s.replace(a, b)
    open(os.path.join(HERE, dst), "w", encoding="utf-8").write(s)


gen("package_test_3d.py", "package_test_3e.py", [
    ('"""Phase 3D clean-directory checks', '"""Phase 3E clean-directory checks'),
    ("gives the 3D engine results", "gives the 3E engine results"),
    ("phase3d\\\\scripts\\\\package_test_3d.py", "phase3e\\\\scripts\\\\package_test_3e.py"),
    ("  * version stamp 3D-rc1 in xcconv.exe output and in its records;",
     "  * version stamp 3E-rc1 in xcconv.exe output and in its records;\n"
     "  * stored equipment (3E): DE 269 (five members away) -> 3DS -> DE unplayed = byte-identical; the 3DS game's save\n"
     "    after the audience reunion (Azahar x2) returns to DE with Shulk's gear and gems;"),
    ("  * D2: a DE save from the story split (288) is refused with the names, nothing written;",
     "  * Fiora's later form away (288) is still refused with her name, nothing written;"),
    ("  * the window starts and reports 3D-rc1.", "  * the window starts and reports 3E-rc1."),
    ('P3D = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3D)',
     'P3E = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3E)\nP3D = os.path.join(ROOT, "phase3d")'),
    ('check("version stamp 3D-rc1 (console and record)", "3D-rc1" in r1.stdout and',
     'check("version stamp 3E-rc1 (console and record)", "3E-rc1" in r1.stdout and'),
    ('["converter_version"] == "3D-rc1")', '["converter_version"] == "3E-rc1")'),
    ('check("window starts without Python (frozen); program version 3D-rc1",',
     'check("window starts without Python (frozen); program version 3E-rc1",'),
    ('si.get("visible") and pv == "3D-rc1", smoke=si, version=pv)', 'si.get("visible") and pv == "3E-rc1", smoke=si, version=pv)'),
    ('''    check("D2: story-split DE save (288) refused with the names, nothing written",
          r7.returncode == 2 and "Shulk, Reyn, Sharla left the party" in (r7.stdout + r7.stderr) and
          not os.path.exists(o7), out=(r7.stdout + r7.stderr)[-400:])''',
     '''    check("Fiora's later form away (288): refused with her name, nothing written",
          r7.returncode == 2 and "Fiora is away from the party" in (r7.stdout + r7.stderr) and
          not os.path.exists(o7), out=(r7.stdout + r7.stderr)[-400:])
    # Phase 3E: stored equipment
    import shutil as _sh
    s269 = os.path.join(inp, "de_s269.sav")
    _sh.copyfile(os.path.join(P3D, "fixtures", "de_s269_v10_monado.sav"), s269)
    o8, o9 = os.path.join(root, "o8"), os.path.join(root, "o9")
    r8 = run("de-to-3ds", "--de", s269, "--template", x3t, "--out", o8, "--overflow", "sidecar")
    r9 = run("3ds-to-de", "--3ds", os.path.join(o8, "3ds", "monado01"), "--record",
             os.path.join(o8, "de_to_3ds.record.json"), "--current-de", s269, "--out", o9)
    out9 = os.path.join(o9, "save_0", "bfsgame00.sav")
    check("stored equipment: DE 269 (five away) -> 3DS -> DE unplayed is byte-identical",
          r8.returncode == 0 and r9.returncode == 0 and os.path.exists(out9) and rd(out9) == rd(s269),
          err=(r8.stderr + r9.stderr)[-400:])
    s156 = os.path.join(inp, "de_s156.sav")
    _sh.copyfile(os.path.join(ROOT, "phase3c", "fixtures", "de_s156_monado_autosave.sav"), s156)
    o10, o11 = os.path.join(root, "o10"), os.path.join(root, "o11")
    r10 = run("de-to-3ds", "--de", s156, "--template", x3t, "--out", o10, "--overflow", "sidecar")
    x2 = os.path.join(ROOT, "phase3e", "fixtures", "x3_s158_azahar_x2_game_save")
    r11 = run("3ds-to-de", "--3ds", x2, "--template", os.path.join(ROOT, "work", "template", "bfsgame00.sav"),
              "--out", o11)
    ok11 = r10.returncode == 0 and r11.returncode == 0
    sh11 = canon.from_de(rd(os.path.join(o11, "save_0", "bfsgame00.sav")), T)["shared"] if ok11 else {}
    sh158 = canon.from_de(rd(os.path.join(ROOT, "phase3c", "fixtures", "de_s158_monado_autosave_c1.sav")), T)["shared"]
    check("3DS game's reunion save (Shulk back with his gear and gems) -> DE: stored gear of the others = native DE 158",
          ok11 and sh11.get("party") == [1] and
          canon.jsonable(sh11.get("stored_gear")) == canon.jsonable(sh158.get("stored_gear")),
          err=(r10.stderr + r11.stderr)[-400:])'''),
])

gen("build_rc_3d.py", "build_rc_3e.py", [
    ('"""Assemble release_candidate_3D/ (Phase 3D).', '"""Assemble release_candidate_3E/ (Phase 3E).'),
    ("release_candidate_3D/\n", "release_candidate_3E/\n"),
    ("tools/ (engine: 3C item correspondence + 3D character 8, D1, D2)",
     "tools/ (engine: 3C items + 3D character 8, D1 + 3E stored equipment, D3)"),
    ("phase3d/gui (3D-rc1), tests (2H, 3A, 3B, 3C, 3D, GUI)", "phase3e/gui (3E-rc1), tests (2H, 3A, 3B, 3C, 3D, 3E, GUI)"),
    ("  *.md               Phase 3D reports + the 3C/3B/3A guides", "  *.md               Phase 3E reports + the 3D/3C/3B/3A guides"),
    ("Usage: python phase3d/scripts/build_rc_3d.py", "Usage: python phase3e/scripts/build_rc_3e.py"),
    ('P3D = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3D)\n',
     'P3E = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3E)\nP3D = os.path.join(ROOT, "phase3d")\n'),
    ('RC = os.path.join(ROOT, "release_candidate_3D")', 'RC = os.path.join(ROOT, "release_candidate_3E")'),
    ('DOCS = ["PHASE3D_SUMMARY.md", "XC_PHASE3D_REPORT.md", "CHARACTER_STATE_MATRIX.md", "STORY_TRANSITION_RESULTS.md",',
     'DOCS = ["PHASE3E_SUMMARY.md", "XC_PHASE3E_REPORT.md", "STORED_EQUIPMENT_MAPPING.md", "REUNION_VALIDATION.md",\n'
     '        "PHASE3D_SUMMARY.md", "XC_PHASE3D_REPORT.md", "CHARACTER_STATE_MATRIX.md", "STORY_TRANSITION_RESULTS.md",'),
    ('            "PHASE3D_SUMMARY.md", "CHARACTER_STATE_MATRIX.md"]',
     '            "PHASE3E_SUMMARY.md", "STORED_EQUIPMENT_MAPPING.md", "CHARACTER_STATE_MATRIX.md"]'),
    ("XC Save Converter 3D-rc1 (with Xenoblade Sync Hub) - notices", "XC Save Converter 3E-rc1 (with Xenoblade Sync Hub) - notices"),
    ("XC Save Converter 3D-rc1 - Xenoblade Sync Hub + converter", "XC Save Converter 3E-rc1 - Xenoblade Sync Hub + converter"),
    ("What changed in 3D: PHASE3D_SUMMARY.md\n(Fiora's later form - character 8 - is supported; saves from the late-game story split are refused).",
     "What changed in 3E: PHASE3E_SUMMARY.md\n(saves made while party members are away in a story event now convert, their stored equipment included)."),
    ("is not a 3D PyInstaller build", "is not a 3E PyInstaller build"),
    ('    cptree(os.path.join(P3D, "gui"), os.path.join(src, "phase3d", "gui"))\n'
     '    for d in ("tests", "tests_gui", "tests_gui_3a"):\n'
     '        cptree(os.path.join(P3D, d), os.path.join(src, "phase3d", d), exts=(".py",))\n'
     '    for f in SCRIPTS3D:\n'
     '        cp(os.path.join(HERE, f), os.path.join(src, "phase3d", "scripts", f))\n',
     '    cptree(os.path.join(P3E, "gui"), os.path.join(src, "phase3e", "gui"))\n'
     '    for d in ("tests", "tests_gui", "tests_gui_3a"):\n'
     '        cptree(os.path.join(P3E, d), os.path.join(src, "phase3e", d), exts=(".py",))\n'
     '    cptree(os.path.join(P3D, "tests"), os.path.join(src, "phase3d", "tests"), exts=(".py",))\n'
     '    for f in SCRIPTS3D:\n'
     '        if os.path.exists(os.path.join(P3D, "scripts", f)):\n'
     '            cp(os.path.join(P3D, "scripts", f), os.path.join(src, "phase3d", "scripts", f))\n'
     '    for f in sorted(os.listdir(HERE)):\n'
     '        if f.endswith((".py", ".sh")):\n'
     '            cp(os.path.join(HERE, f), os.path.join(src, "phase3e", "scripts", f))\n'),
    ("GUI: python phase3d/gui/xcconv_gui.py", "GUI: python phase3e/gui/xcconv_gui.py"),
    ('    for f in sorted(os.listdir(os.path.join(P3D, "logs"))):\n        cp(os.path.join(P3D, "logs", f),',
     '    for f in sorted(os.listdir(os.path.join(P3E, "logs"))):\n        cp(os.path.join(P3E, "logs", f),'),
    ('    for f in ("stash_scan.tsv", "package_test_3d.json", "package_test_3b.json", "package_test_3a.json"):\n'
     '        if os.path.exists(os.path.join(P3D, "work", f)):\n'
     '            cp(os.path.join(P3D, "work", f), os.path.join(val, f))',
     '    for f in ("package_test_3e.json", "package_test_3b.json", "package_test_3a.json", "parity_3d.json"):\n'
     '        if os.path.exists(os.path.join(P3E, "work", f)):\n'
     '            cp(os.path.join(P3E, "work", f), os.path.join(val, f))'),
    ('        d = os.path.join(P3D, "runs", kind)', '        d = os.path.join(P3E, "runs", kind)'),
    ('    dsh = os.path.join(P3D, "runs", "dolphin")', '    dsh = os.path.join(P3E, "runs", "dolphin")'),
    ('    for f in sorted(os.listdir(os.path.join(P3D, "manifests"))):', '    for f in sorted(os.listdir(os.path.join(P3E, "manifests"))):'),
    ('            cp(os.path.join(P3D, "manifests", f), os.path.join(val, "manifests", f))',
     '            cp(os.path.join(P3E, "manifests", f), os.path.join(val, "manifests", f))'),
    ('    for f in os.listdir(os.path.join(P3D, "docs", "previous_3C")):\n'
     '        cp(os.path.join(P3D, "docs", "previous_3C", f), os.path.join(RC, "docs_3C", f))',
     '    for f in os.listdir(os.path.join(P3E, "docs", "previous_3D")):\n'
     '        cp(os.path.join(P3E, "docs", "previous_3D", f), os.path.join(RC, "docs_3D", f))'),
])
print("ok")
