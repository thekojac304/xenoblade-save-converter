"""Phase 3A protected-input manifest (extends the Phase 2F one): Wii/DE/3DS originals and live save folders,
emulator executables, game images and every earlier release candidate. Read-only.

  python protect3a.py start | check [name]      (manifests in phase3a/manifests)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase2f", "scripts"))
import protect_manifest as pm  # noqa: E402

APPDATA = os.environ.get("APPDATA", r"C:\Users\lawma\AppData\Roaming")
SD3 = r"Nintendo 3DS\00000000000000000000000000000000\00000000000000000000000000000000\title\00040000\0f700100"
pm.DIRS.update({
    "azahar_live_xc3d": os.path.join(APPDATA, "Azahar", "sdmc", SD3),
    "azahar_sysdata": os.path.join(APPDATA, "Azahar", "sysdata"),
    "azahar_config": os.path.join(APPDATA, "Azahar", "config"),
    "citra_live_xc3d": os.path.join(r"E:\Launchbox\Emulators\Citra\user\sdmc", SD3),
    "release_candidate_2F": os.path.join(ROOT, "release_candidate_2F"),
    "release_candidate_2G": os.path.join(ROOT, "release_candidate_2G"),
    "release_candidate_2H": os.path.join(ROOT, "release_candidate_2H"),
})
pm.FILES.update({
    "azahar_exe": r"E:\Launchbox\Emulators\Azahar\azahar.exe",
    "citra_exe": r"E:\Launchbox\Emulators\Citra\citra-qt.exe",
    "xc3d_rom": r"E:\Launchbox\Games\ROMs\3DS\Xenoblade Chronicles (USA).3ds",
})
pm.MAN = os.path.join(ROOT, "phase3a", "manifests")

if __name__ == "__main__":
    sys.exit(pm.main(sys.argv))
