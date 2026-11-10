# PyInstaller spec (Phase 3A): portable folder "XCSaveConverter" with two programs sharing one runtime.
#   XCSaveConverter.exe  desktop application (windowed)
#   xcconv.exe           command-line converter (console), the same engine
# Bundled data: the converter's own spec files only. Game tables (bdat_*.json), game files and saves are NEVER
# bundled; the application asks for the user's own tables on first run.
# Build:  python -m PyInstaller --noconfirm --workpath <build> --distpath <dist> gui\xcsaveconverter.spec
import os

GUI = SPECPATH          # folder of this spec file (phase3a/gui)
P3 = os.path.normpath(os.path.join(GUI, ".."))
ROOT = os.path.normpath(os.path.join(P3, ".."))
TOOLS = os.path.join(ROOT, "tools")      # the unchanged 2H engine
SRC3 = os.path.join(P3, "src")           # Phase 3A: 3DS format, transcoder, stats, service, CLI
SPECS = [(os.path.join(ROOT, "specs", f), "specs") for f in
         ("wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json")]
ENGINE = ["xcconv", "xcservice", "convert", "de_to_wii", "canon", "sidecar", "reimport", "safeio", "wii_save",
          "de_save", "flagmap", "flag_transplant_eval", "phase2c", "quest_counters", "achievements", "minimap",
          "paths", "bdat", "dump_bdat",
          "qlz", "xc3d", "xc3dstats", "xc3dservice", "xcservice3", "xcconv3"]
EXCLUDES = ["tkinter", "capstone", "matplotlib", "numpy", "PIL", "pytest", "pytestqt",
            "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtSvg",
            "PySide6.QtOpenGL", "PySide6.QtDBus"]

gui_a = Analysis([os.path.join(GUI, "xcconv_gui.py")], pathex=[SRC3, TOOLS, GUI], datas=SPECS,
                 hiddenimports=ENGINE + ["xcgui.app", "xcgui.main_window"], excludes=EXCLUDES, noarchive=False)
cli_a = Analysis([os.path.join(GUI, "xcconv_cli.py")], pathex=[SRC3, TOOLS], datas=SPECS,
                 hiddenimports=ENGINE, excludes=EXCLUDES + ["PySide6", "shiboken6"], noarchive=False)

gui_a.binaries = [b for b in gui_a.binaries if not b[0].lower().endswith("opengl32sw.dll")]   # unused by Widgets

gui_pyz = PYZ(gui_a.pure)
cli_pyz = PYZ(cli_a.pure)
gui_exe = EXE(gui_pyz, gui_a.scripts, [], exclude_binaries=True, name="XCSaveConverter", console=False,
              debug=False, strip=False, upx=False, version=os.path.join(GUI, "version_info.txt"))
cli_exe = EXE(cli_pyz, cli_a.scripts, [], exclude_binaries=True, name="xcconv", console=True,
              debug=False, strip=False, upx=False, version=os.path.join(GUI, "version_info.txt"))
coll = COLLECT(gui_exe, gui_a.binaries, gui_a.datas, cli_exe, cli_a.binaries, cli_a.datas,
               strip=False, upx=False, name="XCSaveConverter")
