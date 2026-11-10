p = r"C:\Dev\XC_Wii_to_DE_Research\phase3f\scripts\erun3f.py"
s = open(p, encoding="utf-8").read()
old = """        dh.write_config._p3c = True
"""
new = """        dh.write_config._p3c = True
    if a.gfx:
        # Phase 3F: video backend of the run's own (isolated) Dolphin.ini only, e.g. Null while the desktop is locked
        # (a locked desktop stalls presentation; the game code runs unchanged with Null, nothing is drawn)
        base_wc = dh.write_config

        def wc(user, port, _b=base_wc):
            _b(user, port)
            ini = os.path.join(user, "Config", "Dolphin.ini")
            s = open(ini, encoding="utf-8").read().replace("[Core]\n", f"[Core]\nGFXBackend = {a.gfx}\n", 1)
            open(ini, "w", encoding="utf-8").write(s)
        dh.write_config = wc
"""
assert s.count(old) == 1
s = s.replace(old, new)
old2 = '    ap.add_argument("--diag", type=int, default=0, help="Dolphin: window capture every N s (harness diag)")\n'
assert s.count(old2) == 1
s = s.replace(old2, old2 + '    ap.add_argument("--gfx", help="Dolphin: GFXBackend for the isolated run (e.g. Null)")\n')
open(p, "w", encoding="utf-8").write(s)
print("ok")
