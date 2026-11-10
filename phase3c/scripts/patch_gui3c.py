"""Make phase3c/gui (copy of phase3b/gui) the 3C-rc1 GUI: version strings, path to the 3B Sync Hub sources, spec paths.
No interface change."""
import os

G = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gui"))


def sub(rel, pairs):
    p = os.path.join(G, rel)
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if b in s:
            continue
        assert a in s, (rel, a)
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


sub(os.path.join("xcgui", "__init__.py"), [('APP_VERSION = "3B-rc1"', 'APP_VERSION = "3C-rc1"')])
sub(os.path.join("xcgui", "app.py"), [
    ('("..", "..", "src")):      # 2H engine + Phase 3A modules + Phase 3B Sync Hub (xcsync)',
     '("..", "..", "..", "phase3b", "src")):   # engine + Phase 3A modules + Sync Hub (xcsync, 3B code)')])
sub("version_info.txt", [("filevers=(0, 9, 1, 0), prodvers=(0, 9, 1, 0)", "filevers=(0, 9, 2, 0), prodvers=(0, 9, 2, 0)"),
                         ("Sync Hub 3B-rc1", "Sync Hub 3C-rc1"), ("'FileVersion', '3B-rc1'", "'FileVersion', '3C-rc1'"),
                         ("'ProductVersion', '3B-rc1'", "'ProductVersion', '3C-rc1'")])
sub("xcsaveconverter.spec", [
    ("# PyInstaller spec (Phase 3B)", "# PyInstaller spec (Phase 3C; layout unchanged from 3B)"),
    ("#   xcconv.exe           command-line converter (console), the unchanged 3A engine",
     "#   xcconv.exe           command-line converter (console), engine with the 3C item-correspondence fix"),
    ("phase3b\\gui\\xcsaveconverter.spec", "phase3c\\gui\\xcsaveconverter.spec"),
    ('GUI = SPECPATH          # folder of this spec file (phase3b/gui)\nP3B = os.path.normpath(os.path.join(GUI, ".."))\n'
     'ROOT = os.path.normpath(os.path.join(P3B, ".."))',
     'GUI = SPECPATH          # folder of this spec file (phase3c/gui)\nROOT = os.path.normpath(os.path.join(GUI, "..", ".."))\n'
     'P3B = os.path.join(ROOT, "phase3b")'),
    ('TOOLS = os.path.join(ROOT, "tools")                 # the unchanged 2H engine',
     'TOOLS = os.path.join(ROOT, "tools")                 # engine (2H + Phase 3C item correspondence)'),
    ('"paths", "bdat", "dump_bdat",', '"paths", "bdat", "dump_bdat", "itemcorr",'),
])
print("ok")
