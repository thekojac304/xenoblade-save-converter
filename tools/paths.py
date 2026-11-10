"""Where the converter finds its game tables (BDAT dumps made from the user's own game files; never distributed).

Search order: set_data_dir() (the folder chosen in the GUI), $XCCONV_DATA, <root>/data, <root>/../user_data/data. Each
must contain bdat_wii.json and bdat_de.json (created by tools/dump_bdat.py from your own Wii disc and DE romfs).
Spec files (the converter's own layout data, not game data) are found next to the code, or inside the PyInstaller
bundle when frozen (Phase 2G)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
TABLES = ("bdat_wii.json", "bdat_de.json")
FALLBACKS = [os.path.join(ROOT, "data"), os.path.join(ROOT, "..", "user_data", "data")]   # research / 2F layouts
_OVERRIDE = None


def has_tables(d):
    return bool(d) and all(os.path.isfile(os.path.join(d, t)) for t in TABLES)


def set_data_dir(d):
    """Search this folder first (None clears it). Callers that cache loaded tables must reload them."""
    global _OVERRIDE
    _OVERRIDE = os.path.normpath(d) if d else None


def data_dir():
    cands = [_OVERRIDE, os.environ.get("XCCONV_DATA"), *FALLBACKS]
    for c in cands:
        if has_tables(c):
            return os.path.normpath(c)
    raise FileNotFoundError("game tables not found: set XCCONV_DATA to a folder with bdat_wii.json and bdat_de.json "
                            "(run tools/dump_bdat.py on your own Wii disc extraction and DE romfs)")


def data(name):
    return os.path.join(data_dir(), name)


def spec(name):
    base = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    return os.path.join(base or ROOT, "specs", name)
