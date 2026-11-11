# Third-party notices

The converter's own code and documentation are MIT-licensed ([LICENSE](LICENSE)). The MIT License does not cover the
components below, and it grants no rights in *Xenoblade Chronicles* or its data.

## In the Windows package (`XCSaveConverter-*-win-x64.zip`)

| Component | Version in 3F-rc1.1 | License | Text in the package |
|---|---|---|---|
| Python runtime and standard library (incl. bzip2, libffi, Zstandard, xz) | 3.14.5 | PSF License Agreement, plus the bundled libraries' licenses | `LICENSES/Python-3.14.5-LICENSE.txt` |
| OpenSSL (`libcrypto-3.dll`, `libssl-3.dll`) | 3.0.20 | Apache-2.0 | `LICENSES/OpenSSL-Apache-2.0.txt` |
| Qt for Python: PySide6 and Shiboken6 | 6.12.0 | LGPL-3.0-only (chosen from LGPL-3.0 / GPL-2.0 / GPL-3.0) | `LICENSES/LGPL-3.0.txt`, `LICENSES/GPL-3.0.txt` |
| Qt 6 (Core, Gui, Widgets, Network, Svg and plugins) | 6.12.0 | LGPL-3.0-only; Qt's bundled third-party code under its own licenses | `LICENSES/LGPL-3.0.txt`, `LICENSES/GPL-3.0.txt`, `LICENSES/Qt-third-party.txt` |
| Microsoft Visual C++ and Universal C runtime DLLs | — | Microsoft distributable code (redistribution permitted by Microsoft's terms) | — |
| PyInstaller bootloader | 6.x | GPL-2.0 with the bootloader exception, which allows distributing the bundled program under any license | — |

**Qt and PySide6 (LGPL):**
- The Qt and PySide6 libraries are unmodified and dynamically linked. They are separate DLLs and `.pyd` files in
  `_internal\`, so you can replace them with your own builds.
- The converter's complete source is in this repository, so the application can also be rebuilt against a modified Qt.
- Sources of the exact versions:
  - Qt 6.12.0: https://download.qt.io/official_releases/qt/6.12/6.12.0/
  - Qt for Python 6.12.0: https://download.qt.io/official_releases/QtForPython/
- A copy of these sources can also be requested through this repository's issues.

## Knowledge used, no third-party code

- The QuickLZ 1.5 level-3 block format is implemented independently in `qlz.py`.
- Definitive Edition save offsets come from the documentation of hashcade/xbde-save-editor and from hanyu1774's
  `PartyMember.cs`. They are cited in `tools/de_save.py` and were re-verified.
- Syncthing is not bundled or controlled.

## Not included

No game executables, ROMs, disc images, keys, BDAT tables, other game data or save files. The app builds its tables
from the user's own extracted game files.
