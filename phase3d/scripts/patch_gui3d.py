"""Make phase3d/gui (copy of phase3c/gui) the 3D-rc1 GUI: version strings and spec comments/paths. No interface
change. Also bumps the engine / service / Sync Hub version stamps to 3D-rc1 (engine changed in 3D: character 8)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
G = os.path.join(ROOT, "phase3d", "gui")


def sub(p, pairs):
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if b in s:
            continue
        assert a in s, (p, a)
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


sub(os.path.join(G, "xcgui", "__init__.py"), [('APP_VERSION = "3C-rc1"', 'APP_VERSION = "3D-rc1"')])
sub(os.path.join(G, "version_info.txt"), [
    ("filevers=(0, 9, 2, 0), prodvers=(0, 9, 2, 0)", "filevers=(0, 9, 3, 0), prodvers=(0, 9, 3, 0)"),
    ("Sync Hub 3C-rc1", "Sync Hub 3D-rc1"), ("'FileVersion', '3C-rc1'", "'FileVersion', '3D-rc1'"),
    ("'ProductVersion', '3C-rc1'", "'ProductVersion', '3D-rc1'")])
sub(os.path.join(G, "xcsaveconverter.spec"), [
    ("# PyInstaller spec (Phase 3C; layout unchanged from 3B)", "# PyInstaller spec (Phase 3D; layout unchanged from 3B)"),
    ("engine with the 3C item-correspondence fix", "engine with the 3C item correspondence and 3D character-8 support"),
    ("phase3c\\gui\\xcsaveconverter.spec", "phase3d\\gui\\xcsaveconverter.spec"),
    ("# folder of this spec file (phase3c/gui)", "# folder of this spec file (phase3d/gui)"),
    ("# engine (2H + Phase 3C item correspondence)", "# engine (2H + 3C item correspondence + 3D character 8)")])
sub(os.path.join(ROOT, "tools", "sidecar.py"), [
    ('CONVERTER_VERSION = "3C-rc1"   # engine changed in 3C (item correspondence); was "2G-rc1" 2G..3B',
     'CONVERTER_VERSION = "3D-rc1"   # 3D: character 8 / era rule, D1; 3C-rc1 = item correspondence; "2G-rc1" 2G..3B')])
sub(os.path.join(ROOT, "phase3a", "src", "xc3dservice.py"), [
    ('CONVERTER_VERSION = "3C-rc1"   # 3A-rc1 until 3B', 'CONVERTER_VERSION = "3D-rc1"   # 3C-rc1 in 3C, 3A-rc1 until 3B')])
sub(os.path.join(ROOT, "phase3b", "src", "xcsync", "__init__.py"), [('APP_VERSION = "3C-rc1"', 'APP_VERSION = "3D-rc1"')])
print("ok")
