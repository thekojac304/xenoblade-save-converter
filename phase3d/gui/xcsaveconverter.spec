# PyInstaller spec (Phase 3D; layout unchanged from 3B): portable folder "XCSaveConverter" with three programs sharing one runtime.
#   XCSaveConverter.exe  desktop application (windowed): Sync Hub tab + the 3A three-step converter tab
#   xcconv.exe           command-line converter (console), engine with the 3C item correspondence and 3D character-8 support
#   xcsync.exe           Sync Hub command line (console): init, devices, templates, scan, sync, publish, history
# Bundled data: the converter's own spec files only. Game tables (bdat_*.json), game files and saves are NEVER
# bundled; the application asks for the user's own tables on first run.
# Build:  python -m PyInstaller --noconfirm --workpath <build> --distpath <dist> phase3d\gui\xcsaveconverter.spec
import os

GUI = SPECPATH          # folder of this spec file (phase3d/gui)
ROOT = os.path.normpath(os.path.join(GUI, "..", ".."))
P3B = os.path.join(ROOT, "phase3b")
TOOLS = os.path.join(ROOT, "tools")                 # engine (2H + 3C item correspondence + 3D character 8)
SRC3 = os.path.join(ROOT, "phase3a", "src")         # Phase 3A: 3DS format, transcoder, stats, service, CLI (unchanged)
SRC3B = os.path.join(P3B, "src")                    # Phase 3B: xcsync (Sync Hub)
SPECS = [(os.path.join(ROOT, "specs", f), "specs") for f in
         ("wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json")]
ENGINE = ["xcconv", "xcservice", "convert", "de_to_wii", "canon", "sidecar", "reimport", "safeio", "wii_save",
          "de_save", "flagmap", "flag_transplant_eval", "phase2c", "quest_counters", "achievements", "minimap",
          "paths", "bdat", "dump_bdat", "itemcorr", "stored_gear",
          "qlz", "xc3d", "xc3dstats", "xc3dservice", "xcservice3", "xcconv3"]
SYNC = ["xcsync", "xcsync.paths3b", "xcsync.store", "xcsync.scan", "xcsync.sync", "xcsync.cli"]
EXCLUDES = ["tkinter", "capstone", "matplotlib", "numpy", "PIL", "pytest", "pytestqt",
            "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtSvg",
            "PySide6.QtOpenGL", "PySide6.QtDBus"]

gui_a = Analysis([os.path.join(GUI, "xcconv_gui.py")], pathex=[SRC3B, SRC3, TOOLS, GUI], datas=SPECS,
                 hiddenimports=ENGINE + SYNC + ["xcgui.app", "xcgui.main_window", "xcgui.shell",
                                                "xcgui.synchub_view"],
                 excludes=EXCLUDES, noarchive=False)
cli_a = Analysis([os.path.join(GUI, "xcconv_cli.py")], pathex=[SRC3, TOOLS], datas=SPECS,
                 hiddenimports=ENGINE, excludes=EXCLUDES + ["PySide6", "shiboken6"], noarchive=False)
sync_a = Analysis([os.path.join(SRC3B, "xcsync_cli.py")], pathex=[SRC3B, SRC3, TOOLS], datas=SPECS,
                  hiddenimports=ENGINE + SYNC, excludes=EXCLUDES + ["PySide6", "shiboken6"], noarchive=False)

gui_a.binaries = [b for b in gui_a.binaries if not b[0].lower().endswith("opengl32sw.dll")]   # unused by Widgets

gui_pyz = PYZ(gui_a.pure)
cli_pyz = PYZ(cli_a.pure)
sync_pyz = PYZ(sync_a.pure)
gui_exe = EXE(gui_pyz, gui_a.scripts, [], exclude_binaries=True, name="XCSaveConverter", console=False,
              debug=False, strip=False, upx=False, version=os.path.join(GUI, "version_info.txt"))
cli_exe = EXE(cli_pyz, cli_a.scripts, [], exclude_binaries=True, name="xcconv", console=True,
              debug=False, strip=False, upx=False, version=os.path.join(GUI, "version_info.txt"))
sync_exe = EXE(sync_pyz, sync_a.scripts, [], exclude_binaries=True, name="xcsync", console=True,
               debug=False, strip=False, upx=False, version=os.path.join(GUI, "version_info.txt"))
coll = COLLECT(gui_exe, gui_a.binaries, gui_a.datas, cli_exe, cli_a.binaries, cli_a.datas,
               sync_exe, sync_a.binaries, sync_a.datas, strip=False, upx=False, name="XCSaveConverter")
