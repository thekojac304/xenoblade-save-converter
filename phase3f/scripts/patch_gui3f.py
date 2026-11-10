"""Make phase3f/gui (copy of phase3e/gui) the 3F-rc1 GUI: version stamps, spec paths, and one plain-language rule for
the new F1 refusal (a return the Wii/3DS game skipped). No layout change. Idempotent."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
G = os.path.join(ROOT, "phase3f", "gui")


def sub(p, pairs):
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if b in s:
            continue
        assert a in s, (p, a)
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


sub(os.path.join(G, "xcgui", "__init__.py"), [('APP_VERSION = "3E-rc1"', 'APP_VERSION = "3F-rc1"')])
sub(os.path.join(G, "version_info.txt"), [
    ("filevers=(0, 9, 4, 0), prodvers=(0, 9, 4, 0)", "filevers=(0, 9, 5, 0), prodvers=(0, 9, 5, 0)"),
    ("Sync Hub 3E-rc1", "Sync Hub 3F-rc1"), ("'FileVersion', '3E-rc1'", "'FileVersion', '3F-rc1'"),
    ("'ProductVersion', '3E-rc1'", "'ProductVersion', '3F-rc1'")])
sub(os.path.join(G, "xcsaveconverter.spec"), [
    ("# PyInstaller spec (Phase 3E; layout unchanged from 3B)", "# PyInstaller spec (Phase 3F; layout unchanged from 3B)"),
    ("3D character 8, 3E stored equipment", "3D character 8, 3E stored equipment, 3F Fiora-8 stored gear"),
    ("phase3e\\gui\\xcsaveconverter.spec", "phase3f\\gui\\xcsaveconverter.spec"),
    ("# folder of this spec file (phase3e/gui)", "# folder of this spec file (phase3f/gui)"),
    ("# engine (2H + 3C items + 3D character 8 + 3E stored gear)",
     "# engine (2H + 3C items + 3D character 8 + 3E stored gear + 3F Fiora-8 / F1)")])
sub(os.path.join(G, "xcgui", "messages.py"), [
    ('''    (r"party \\[[^\\]]*\\] cannot exist on the Wii",''',
     '''    (r"back in the party, but the game has not given back",
     "Equipment not given back by the game",
     "In this save a character is back in the party, but the game has not given back the equipment it kept while "
     "the character was away (the Wii/3DS game skips that when an equipment pocket is full at the reunion). "
     "Converting it would lose that equipment, so the converter stopped. Nothing was written."),
    (r"party \\[[^\\]]*\\] cannot exist on the Wii",'''),
])
print("ok")
