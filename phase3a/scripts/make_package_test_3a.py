"""Generate phase3a/scripts/package_test_3a.py from the Phase 2H package test (every 2H check kept unchanged) plus
the Phase 3A New 3DS checks."""
import os

P3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P3)
s = open(os.path.join(ROOT, "phase2h", "scripts", "package_test.py"), encoding="utf-8").read()


def rep(a, b):
    global s
    assert a in s, a[:120]
    s = s.replace(a, b, 1)


rep('"""Phase 2H clean-directory test of the packaged application.', '"""Phase 3A clean-directory test of the packaged application (all Phase 2H checks + New 3DS checks).')
rep('''USER_SHA = "1028f718c0c567e75e03184492287b20b5f78b8280b7e0d70ba1eecc943673b2"''',
    '''USER_SHA = "1028f718c0c567e75e03184492287b20b5f78b8280b7e0d70ba1eecc943673b2"
P3 = os.path.join(ROOT, "phase3a")
X3_DIR = os.path.join(P3, "originals", "azahar_live", "00000001")      # copy of the user's own 3DS save archive''')
rep('''    for n in ("monado01", "monado03", "user_v10_bfsgame00.sav"):
        shutil.copyfile(os.path.join(O, n), os.path.join(inp, n))''', '''    for n in ("monado01", "monado03", "user_v10_bfsgame00.sav"):
        shutil.copyfile(os.path.join(O, n), os.path.join(inp, n))
    os.makedirs(os.path.join(inp, "3ds"))
    for n in ("monado01", "monado02", "monado03"):
        shutil.copyfile(os.path.join(X3_DIR, n), os.path.join(inp, "3ds", n))''')
rep('''    def research_cli(*args):''', '''    def research_cli3(*args):
        r = subprocess.run([sys.executable, os.path.join(P3, "src", "xcconv3.py"), *args], capture_output=True,
                           text=True, env=dict(os.environ, XCCONV_DATA=os.path.join(ROOT, "data")))
        return r.returncode

    def research_cli(*args):''')
rep('''    # 9. inputs and the app folder unchanged''', '''    # 3A. New 3DS
    x3 = os.path.join(inp, "3ds", "monado01")
    r = run([cli, "--help"])
    check("xcconv.exe --help lists the 3DS commands", r.returncode == 0 and "wii-to-3ds" in r.stdout and
          "3ds-to-de" in r.stdout)
    r = run([cli, "validate", x3], extra_env={"XCCONV_DATA": data})
    check("xcconv.exe validate (3DS save)", r.returncode == 0 and '"ok": true' in r.stdout, rc=r.returncode,
          err=r.stderr[-300:])
    r = run([cli, "wii-to-3ds", "--wii", w01, "--template", x3, "--out",
             os.path.join(os.environ.get("APPDATA", ""), "Azahar", "sdmc", "xcconv_test")], extra_env={"XCCONV_DATA": data})
    check("xcconv.exe refuses a live 3DS save folder", r.returncode == 2 and "nothing was written" in r.stderr,
          rc=r.returncode)
    o3 = os.path.join(root, "gui_out_3ds")                  # the 3DS jobs: first conversions in their own folder
    g = automate("w2x", source=w01, dest=x3, output_parent=o3)
    ref = os.path.join(root, "cli_ref", "w2x")
    rc = research_cli3("wii-to-3ds", "--wii", w01, "--template", x3, "--out", ref, "--slot", g.get("file_name", "?")[-1:])
    check("GUI Wii -> 3DS succeeds", g.get("ok") and g.get("direction") == "wii_to_3ds" and
          g["file_name"] == "monado02", result=g)
    check("GUI Wii -> 3DS identical to research CLI (all files)", g.get("ok") and rc == 0 and tree(g["out_dir"]) == tree(ref))
    check("Wii -> 3DS output includes a complete Checkpoint-style archive", g.get("ok") and
          any(k.startswith("checkpoint/") for k in tree(g["out_dir"])))
    if g.get("ok"):
        h = automate("x2w_return", source=g["main_output"], dest=w01, output_parent=o3)
        check("GUI 3DS -> Wii found the conversion record automatically",
              (h.get("plan") or {}).get("record") == g["sidecar"], plan=h.get("plan"))
        check("GUI 3DS -> Wii return gives the Wii save back byte for byte", h.get("ok") and
              sha(h["main_output"]) == sha(w01))
    k = automate("x2w_nodest", source=x3, target="wii", output_parent=os.path.join(root, "gui_out_3ds_b"))
    ref = os.path.join(root, "cli_ref", "x2w")
    r = run([cli, "3ds-to-wii", "--3ds", x3, "--out", ref, "--slot", k.get("file_name", "?")], extra_env={"XCCONV_DATA": data})
    check("GUI 3DS -> Wii without a destination save identical to packaged CLI", k.get("ok") and r.returncode == 0 and
          tree(k["out_dir"]) == tree(ref), rc=r.returncode, err=r.stderr[-300:])
    m = automate("d2x", source=tpl, dest=x3, output_parent=os.path.join(root, "gui_out_3ds_c"))
    if m.get("ok"):
        n = automate("x2d_return", source=m["main_output"], dest=tpl, output_parent=os.path.join(root, "gui_out_3ds_c"))
        check("GUI DE -> 3DS -> DE returns the DE save byte for byte", n.get("ok") and
              (n.get("plan") or {}).get("mode") == "return" and sha(n["main_output"]) == sha(tpl))
    else:
        check("GUI DE -> 3DS succeeds", False, result=m)
    q = automate("x2d_first", source=x3, dest=tpl, output_parent=os.path.join(root, "gui_out_3ds_d"))
    ref = os.path.join(root, "cli_ref", "x2d")
    rc = research_cli3("3ds-to-de", "--3ds", x3, "--template", tpl, "--out", ref, "--slot", q.get("file_name", "?")[7:9])
    check("GUI 3DS -> DE identical to research CLI", q.get("ok") and rc == 0 and tree(q["out_dir"]) == tree(ref))
    e3 = automate("x_empty", source=os.path.join(inp, "3ds", "monado02"), target="wii")
    check("GUI refuses an empty 3DS slot", not e3.get("ok") and e3.get("missing"), missing=e3.get("missing"))

    # 9. inputs and the app folder unchanged''')
rep('''    check("inputs unchanged", all(sha(os.path.join(inp, n)) == sha(os.path.join(O, n))
                                  for n in ("monado01", "monado03", "user_v10_bfsgame00.sav")))''',
    '''    check("inputs unchanged", all(sha(os.path.join(inp, n)) == sha(os.path.join(O, n))
                                  for n in ("monado01", "monado03", "user_v10_bfsgame00.sav")) and
          all(sha(os.path.join(inp, "3ds", n)) == sha(os.path.join(X3_DIR, n)) for n in ("monado01", "monado02", "monado03")))''')
open(os.path.join(P3, "scripts", "package_test_3a.py"), "w", encoding="utf-8", newline="\n").write(s)
print("ok")
