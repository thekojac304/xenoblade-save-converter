"""Generate phase3f/scripts/package_test_3f.py and build_rc_3f.py from the 3E versions (paths, version, checks)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))


def gen(src, dst, pairs):
    s = open(os.path.join(ROOT, "phase3e", "scripts", src), encoding="utf-8").read()
    for a, b in pairs:
        assert a in s, (src, a[:90])
        s = s.replace(a, b)
    open(os.path.join(HERE, dst), "w", encoding="utf-8").write(s)


gen("package_test_3e.py", "package_test_3f.py", [
    ('"""Phase 3E clean-directory checks', '"""Phase 3F clean-directory checks'),
    ("gives the 3E engine results", "gives the 3F engine results"),
    ("phase3e\\\\scripts\\\\package_test_3e.py", "phase3f\\\\scripts\\\\package_test_3f.py"),
    ("  * version stamp 3E-rc1 in xcconv.exe output and in its records;",
     "  * version stamp 3F-rc1 in xcconv.exe output and in its records;\n"
     "  * Fiora's later form away (3F): DE 288 -> 3DS -> DE unplayed = byte-identical, room kept for the reunion (F1);\n"
     "    the 3DS game's save after the 288 reunion (Azahar x4) returns to DE = the native DE reunion's items; a save\n"
     "    where the game skipped a return (Azahar x2, 3E export) is refused with the names, nothing written;"),
    ("  * Fiora's later form away (288) is still refused with her name, nothing written;\n", ""),
    ("  * the window starts and reports 3E-rc1.", "  * the window starts and reports 3F-rc1."),
    ('check("version stamp 3E-rc1 (console and record)", "3E-rc1" in r1.stdout and',
     'check("version stamp 3F-rc1 (console and record)", "3F-rc1" in r1.stdout and'),
    ('["converter_version"] == "3E-rc1")', '["converter_version"] == "3F-rc1")'),
    ('check("window starts without Python (frozen); program version 3E-rc1",',
     'check("window starts without Python (frozen); program version 3F-rc1",'),
    ('si.get("visible") and pv == "3E-rc1", smoke=si, version=pv)', 'si.get("visible") and pv == "3F-rc1", smoke=si, version=pv)'),
    ('''    check("Fiora's later form away (288): refused with her name, nothing written",
          r7.returncode == 2 and "Fiora is away from the party" in (r7.stdout + r7.stderr) and
          not os.path.exists(o7), out=(r7.stdout + r7.stderr)[-400:])''',
     '''    s288 = os.path.join(inp, "de_s288_v10_monado.sav")
    o7b = os.path.join(root, "o7b")
    r7b = run("3ds-to-de", "--3ds", os.path.join(o7, "3ds", "monado01"), "--record",
              os.path.join(o7, "de_to_3ds.record.json"), "--current-de", s288, "--out", o7b)
    out7b = os.path.join(o7b, "save_0", "bfsgame00.sav")
    check("Fiora's later form away (288): DE -> 3DS -> DE unplayed is byte-identical (3E refused it)",
          r7.returncode == 0 and r7b.returncode == 0 and os.path.exists(out7b) and rd(out7b) == rd(s288),
          err=(r7.stderr + r7b.stderr)[-400:])
    import de_to_wii as _d2w
    import stored_gear as _sg
    import wii_save as _ws
    import xc3d as _x
    ok7 = r7.returncode == 0
    w7 = _x.transcode(_x.unpack(rd(os.path.join(o7, "3ds", "monado01"))), "wii") if ok7 else b""
    room_ok = False
    if ok7:
        ir7, caps7 = _ws.decode_bytes(w7), _d2w.wii_capacity(w7)
        need = _sg.reunion_room(canon.from_wii(w7, T)["shared"]["stored_gear"])
        room_ok = all(len([r for r in ir7["items"][bx] if r["index"] < 150 and r["header"]["gid"]]) <= caps7[bx] - n
                      for bx, n in need.items())
    check("F1: the 288 export leaves room in every pocket for the gear the game gives back", room_ok)
    o7c = os.path.join(root, "o7c")
    r7c = run("3ds-to-de", "--3ds", os.path.join(inp, "x3_s291_azahar_x4_reload_save"), "--record",
              os.path.join(inp, "x3_s288_export_3f.de_to_3ds.record.json"), "--current-de", s288, "--out", o7c)
    out7c = os.path.join(o7c, "save_0", "bfsgame00.sav")
    ok7c = r7c.returncode == 0 and os.path.exists(out7c)
    a7, n7 = (canon.from_de(rd(p), T)["shared"] for p in (out7c, os.path.join(inp, "de_s291_native.sav"))) \\
        if ok7c else ({}, {})
    check("3DS game's save after the 288 reunion -> DE: party and every item = the native DE reunion",
          ok7c and a7["party"] == n7["party"] == [4, 6, 7, 1, 2, 5, 8] and "stored_gear" not in a7 and
          {x: sorted(map(str, map(canon.strip_order, v.values()))) for x, v in a7["inventory"].items()} ==
          {x: sorted(map(str, map(canon.strip_order, v.values()))) for x, v in n7["inventory"].items()},
          err=r7c.stderr[-400:])
    o7d = os.path.join(root, "o7d")
    r7d = run("3ds-to-de", "--3ds", os.path.join(inp, "x3_s291_azahar_x2_reunion_save"), "--record",
              os.path.join(inp, "x3_s288_export_3e_engine.de_to_3ds.record.json"), "--current-de", s288, "--out", o7d)
    check("F1: a save where the game skipped Shulk's and Reyn's return is refused with the names, nothing written",
          r7d.returncode == 2 and "Shulk, Reyn: back in the party" in (r7d.stdout + r7d.stderr) and
          not os.path.exists(o7d), out=(r7d.stdout + r7d.stderr)[-400:])'''),
    ('''    shutil.copyfile(os.path.join(P3D, "fixtures", "de_s269_v10_monado.sav"), os.path.join(inp, "de_s269.sav"))''',
     '''    shutil.copyfile(os.path.join(P3D, "fixtures", "de_s269_v10_monado.sav"), os.path.join(inp, "de_s269.sav"))
    F3F = os.path.join(ROOT, "phase3f", "fixtures")
    for n in ("x3_s291_azahar_x4_reload_save", "x3_s288_export_3f.de_to_3ds.record.json",
              "x3_s291_azahar_x2_reunion_save", "x3_s288_export_3e_engine.de_to_3ds.record.json"):
        shutil.copyfile(os.path.join(F3F, n), os.path.join(inp, n))
    shutil.copyfile(os.path.join(F3F, "de_s291_monado_m1b_native_reunion.sav"), os.path.join(inp, "de_s291_native.sav"))'''),
])

gen("build_rc_3e.py", "build_rc_3f.py", [
    ('"""Assemble release_candidate_3E/ (Phase 3E).', '"""Assemble release_candidate_3F/ (Phase 3F).'),
    ("release_candidate_3E/\n", "release_candidate_3F/\n"),
    ("tools/ (engine: 3C items + 3D character 8, D1 + 3E stored equipment, D3)",
     "tools/ (engine: 3C items + 3D character 8, D1 + 3E stored equipment, D3 + 3F Fiora-8 stored gear, F1)"),
    ("phase3e/gui (3E-rc1), tests (2H, 3A, 3B, 3C, 3D, 3E, GUI)", "phase3f/gui (3F-rc1), tests (2H, 3A, 3B, 3C, 3D, 3E, 3F, GUI)"),
    ("  *.md               Phase 3E reports + the 3D/3C/3B/3A guides", "  *.md               Phase 3F reports + the 3E/3D/3C/3B/3A guides"),
    ("Usage: python phase3e/scripts/build_rc_3e.py", "Usage: python phase3f/scripts/build_rc_3f.py"),
    ('P3E = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3E)\n',
     'P3F = os.path.normpath(os.path.join(HERE, ".."))\nROOT = os.path.dirname(P3F)\nP3E = os.path.join(ROOT, "phase3e")\n'),
    ('RC = os.path.join(ROOT, "release_candidate_3E")', 'RC = os.path.join(ROOT, "release_candidate_3F")'),
    ('DOCS = ["PHASE3E_SUMMARY.md", "XC_PHASE3E_REPORT.md", "STORED_EQUIPMENT_MAPPING.md", "REUNION_VALIDATION.md",',
     'DOCS = ["PHASE3F_SUMMARY.md", "XC_PHASE3F_REPORT.md", "FIORA_REUNION_ANALYSIS.md", "FIORA_REUNION_GAMEPLAY_TESTS.md",\n'
     '        "SYNC_HUB_REGRESSION.md",\n'
     '        "PHASE3E_SUMMARY.md", "XC_PHASE3E_REPORT.md", "STORED_EQUIPMENT_MAPPING.md", "REUNION_VALIDATION.md",'),
    ('            "PHASE3E_SUMMARY.md", "STORED_EQUIPMENT_MAPPING.md", "CHARACTER_STATE_MATRIX.md"]',
     '            "PHASE3F_SUMMARY.md", "STORED_EQUIPMENT_MAPPING.md", "CHARACTER_STATE_MATRIX.md"]'),
    ("XC Save Converter 3E-rc1 (with Xenoblade Sync Hub) - notices", "XC Save Converter 3F-rc1 (with Xenoblade Sync Hub) - notices"),
    ("XC Save Converter 3E-rc1 - Xenoblade Sync Hub + converter", "XC Save Converter 3F-rc1 - Xenoblade Sync Hub + converter"),
    ("What changed in 3E: PHASE3E_SUMMARY.md\n(saves made while party members are away in a story event now convert, their stored equipment included).",
     "What changed in 3F: PHASE3F_SUMMARY.md\n(saves made while Fiora's later form is away - story 288 - now convert; conversions made during a story\n"
     "separation keep room in your pockets so the game can give the stored equipment back)."),
    ("is not a 3E PyInstaller build", "is not a 3F PyInstaller build"),
    ('    cptree(os.path.join(P3E, "gui"), os.path.join(src, "phase3e", "gui"))\n'
     '    for d in ("tests", "tests_gui", "tests_gui_3a"):\n'
     '        cptree(os.path.join(P3E, d), os.path.join(src, "phase3e", d), exts=(".py",))\n',
     '    cptree(os.path.join(P3F, "gui"), os.path.join(src, "phase3f", "gui"))\n'
     '    for d in ("tests", "tests_gui", "tests_gui_3a"):\n'
     '        cptree(os.path.join(P3F, d), os.path.join(src, "phase3f", d), exts=(".py",))\n'
     '    cptree(os.path.join(P3E, "tests"), os.path.join(src, "phase3e", "tests"), exts=(".py",))\n'),
    ('    for f in sorted(os.listdir(HERE)):\n'
     '        if f.endswith((".py", ".sh")):\n'
     '            cp(os.path.join(HERE, f), os.path.join(src, "phase3e", "scripts", f))\n',
     '    for f in sorted(os.listdir(HERE)):\n'
     '        if f.endswith((".py", ".sh")):\n'
     '            cp(os.path.join(HERE, f), os.path.join(src, "phase3f", "scripts", f))\n'
     '    for f in sorted(os.listdir(os.path.join(P3E, "scripts"))):\n'
     '        if f.endswith((".py", ".sh")):\n'
     '            cp(os.path.join(P3E, "scripts", f), os.path.join(src, "phase3e", "scripts", f))\n'),
    ("GUI: python phase3e/gui/xcconv_gui.py", "GUI: python phase3f/gui/xcconv_gui.py"),
    ('    for f in sorted(os.listdir(os.path.join(P3E, "logs"))):\n        cp(os.path.join(P3E, "logs", f),',
     '    for f in sorted(os.listdir(os.path.join(P3F, "logs"))):\n        cp(os.path.join(P3F, "logs", f),'),
    ('    for f in ("package_test_3e.json", "package_test_3b.json", "package_test_3a.json", "parity_3d.json"):\n'
     '        if os.path.exists(os.path.join(P3E, "work", f)):\n'
     '            cp(os.path.join(P3E, "work", f), os.path.join(val, f))',
     '    for f in ("package_test_3f.json", "package_test_3b.json", "package_test_3a.json", "parity_3e.json"):\n'
     '        if os.path.exists(os.path.join(P3F, "work", f)):\n'
     '            cp(os.path.join(P3F, "work", f), os.path.join(val, f))'),
    ('        d = os.path.join(P3E, "runs", kind)', '        d = os.path.join(P3F, "runs", kind)'),
    ('    dsh = os.path.join(P3E, "runs", "dolphin")', '    dsh = os.path.join(P3F, "runs", "dolphin")'),
    ('    for f in sorted(os.listdir(os.path.join(P3E, "manifests"))):', '    for f in sorted(os.listdir(os.path.join(P3F, "manifests"))):'),
    ('            cp(os.path.join(P3E, "manifests", f), os.path.join(val, "manifests", f))',
     '            cp(os.path.join(P3F, "manifests", f), os.path.join(val, "manifests", f))'),
    ('    for f in os.listdir(os.path.join(P3E, "docs", "previous_3D")):\n'
     '        cp(os.path.join(P3E, "docs", "previous_3D", f), os.path.join(RC, "docs_3D", f))',
     '    for f in os.listdir(os.path.join(P3F, "docs", "previous_3E")):\n'
     '        cp(os.path.join(P3F, "docs", "previous_3E", f), os.path.join(RC, "docs_3E", f))'),
])
print("ok")
