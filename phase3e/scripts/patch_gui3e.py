"""Make phase3e/gui (copy of phase3d/gui) the 3E-rc1 GUI and bump the engine / service / Sync Hub stamps to 3E-rc1
(engine changed in 3E: stored equipment, D3). No interface change."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
G = os.path.join(ROOT, "phase3e", "gui")


def sub(p, pairs):
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        if b in s:
            continue
        assert a in s, (p, a)
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


sub(os.path.join(G, "xcgui", "__init__.py"), [('APP_VERSION = "3D-rc1"', 'APP_VERSION = "3E-rc1"')])
sub(os.path.join(G, "version_info.txt"), [
    ("filevers=(0, 9, 3, 0), prodvers=(0, 9, 3, 0)", "filevers=(0, 9, 4, 0), prodvers=(0, 9, 4, 0)"),
    ("Sync Hub 3D-rc1", "Sync Hub 3E-rc1"), ("'FileVersion', '3D-rc1'", "'FileVersion', '3E-rc1'"),
    ("'ProductVersion', '3D-rc1'", "'ProductVersion', '3E-rc1'")])
sub(os.path.join(G, "xcsaveconverter.spec"), [
    ("# PyInstaller spec (Phase 3D; layout unchanged from 3B)", "# PyInstaller spec (Phase 3E; layout unchanged from 3B)"),
    ("3C item correspondence and 3D character-8 support", "3C item correspondence, 3D character 8, 3E stored equipment"),
    ("phase3d\\gui\\xcsaveconverter.spec", "phase3e\\gui\\xcsaveconverter.spec"),
    ("# folder of this spec file (phase3d/gui)", "# folder of this spec file (phase3e/gui)"),
    ("# engine (2H + 3C item correspondence + 3D character 8)", "# engine (2H + 3C items + 3D character 8 + 3E stored gear)")])
sub(os.path.join(ROOT, "tools", "sidecar.py"), [
    ('CONVERTER_VERSION = "3D-rc1"   # 3D: character 8 / era rule, D1; 3C-rc1 = item correspondence; "2G-rc1" 2G..3B',
     'CONVERTER_VERSION = "3E-rc1"   # 3E: stored equipment, D3; 3D-rc1: character 8, D1; 3C-rc1: items; "2G-rc1" 2G..3B')])
sub(os.path.join(ROOT, "phase3a", "src", "xc3dservice.py"), [
    ('CONVERTER_VERSION = "3D-rc1"   # 3C-rc1 in 3C, 3A-rc1 until 3B', 'CONVERTER_VERSION = "3E-rc1"   # 3D-rc1, 3C-rc1, 3A-rc1 until 3B')])
sub(os.path.join(ROOT, "phase3b", "src", "xcsync", "__init__.py"), [('APP_VERSION = "3D-rc1"', 'APP_VERSION = "3E-rc1"')])
sub(os.path.join(ROOT, "tests", "test_phase2g_service.py"), [
    ('self.assertEqual(scmod.CONVERTER_VERSION, "3D-rc1")', 'self.assertEqual(scmod.CONVERTER_VERSION, "3E-rc1")')])
print("ok")
