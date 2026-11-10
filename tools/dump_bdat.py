"""Dump the Wii and DE game-data tables used by Phase 2C into data/bdat_wii.json and data/bdat_de.json (read-only).

  python dump_bdat.py <wii files dir (…/DATA/files)> <DE romfs dir> [<output dir>]

Wii: lang/en/static.arc (data tables) + common/en/common.pkb (menu text, prefixed 'menu:').
DE:  bdat/*.bdat (data) + bdat/gb/*.bdat (English text, prefixed 'gb:').
The game files are only read. Phase 2G: an output folder can be given (the GUI's first-run setup uses one), and the
two files are written under temporary names and renamed only once both are complete.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bdat  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "data")


def missing_inputs(wii_files, romfs):
    """Plain-language list of what is missing from the two game folders (empty when both look right)."""
    miss = []
    for rel in (("lang", "en", "static.arc"), ("common", "en", "common.pkb")):
        if not os.path.isfile(os.path.join(wii_files or "", *rel)):
            miss.append(f"Wii game files: {'/'.join(rel)} not found in {wii_files}")
    if not glob.glob(os.path.join(romfs or "", "bdat", "*.bdat")):
        miss.append(f"DE game files: no bdat/*.bdat in {romfs}")
    return miss


def main(wii_files, romfs, out=OUT, log=print):
    w = bdat.tables_in(os.path.join(wii_files, "lang", "en", "static.arc"))
    w.update({"menu:" + k: v for k, v in bdat.tables_in(os.path.join(wii_files, "common", "en", "common.pkb")).items()})
    d = {}
    for p in sorted(glob.glob(os.path.join(romfs, "bdat", "*.bdat"))):
        d.update(bdat.tables_in(p))
    for p in sorted(glob.glob(os.path.join(romfs, "bdat", "gb", "*.bdat"))):
        d.update({"gb:" + k: v for k, v in bdat.tables_in(p).items()})
    os.makedirs(out, exist_ok=True)
    done, counts = [], {}
    try:
        for name, tabs in (("wii", w), ("de", d)):
            errs = [k for k, v in tabs.items() if "error" in v]
            log(f"{name} {len(tabs)} tables; {len(errs)} unparsed: {errs[:8]}")
            counts[name] = len(tabs)
            tmp = os.path.join(out, f"bdat_{name}.json.partial")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(tabs, f, ensure_ascii=False)
            done.append((tmp, os.path.join(out, f"bdat_{name}.json")))
        for tmp, final in done:
            os.replace(tmp, final)
    finally:
        for tmp, _ in done:
            if os.path.exists(tmp):
                os.remove(tmp)
    return counts


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(*sys.argv[1:])
