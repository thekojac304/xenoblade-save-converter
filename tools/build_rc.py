"""Assemble release_candidate/ (Phase 2E part G). Copies only; never touches game folders.

release_candidate/
  converter/        distributable code: tools (converter modules + CLI), specs, tests, docs, xcconv.cmd  (no game data)
  user_data/data/   bdat_wii.json / bdat_de.json made from YOUR game files - NOT FOR DISTRIBUTION
  user_saves/       your converted saves, sidecars and manifests - personal, NOT FOR DISTRIBUTION
  validation/       manifests, test logs, in-game run summaries
  SHA256SUMS.txt
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RC = os.path.join(ROOT, "release_candidate")
CODE = ["xcconv.py", "convert.py", "de_to_wii.py", "canon.py", "sidecar.py", "reimport.py", "wii_save.py", "de_save.py",
        "flagmap.py", "flag_transplant_eval.py", "phase2c.py", "quest_counters.py", "achievements.py", "minimap.py",
        "paths.py", "bdat.py", "dump_bdat.py"]
SPECS = ["wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json"]
DOCS = ["README_CONVERTER.md", "BIDIRECTIONAL_DESIGN.md", "KNOWN_LIMITATIONS.md"]
NOT_FOR_DIST = ("These files are derived from or are your own game data / saves. Keep them private; do not publish "
                "or share them.\n")


def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def main(user_saves):
    if os.path.exists(RC):
        raise SystemExit(f"{RC} exists; remove it first (it is generated)")
    conv = os.path.join(RC, "converter")
    for f in CODE:
        cp(os.path.join(HERE, f), os.path.join(conv, "tools", f))
    for f in SPECS:
        cp(os.path.join(ROOT, "specs", f), os.path.join(conv, "specs", f))
    for f in os.listdir(os.path.join(ROOT, "tests")):
        if f.endswith(".py"):
            cp(os.path.join(ROOT, "tests", f), os.path.join(conv, "tests", f))
    for f in DOCS:
        if os.path.exists(os.path.join(ROOT, f)):
            cp(os.path.join(ROOT, f), os.path.join(conv, f))
    open(os.path.join(conv, "xcconv.cmd"), "w").write('@echo off\r\npython "%~dp0tools\\xcconv.py" %*\r\n')
    open(os.path.join(conv, "tests", "README.txt"), "w").write(
        "The regression suite needs the research fixtures (your original saves under work/originals and the template "
        "under work/template). Run it from the research folder: python -m unittest discover -s tests -v\n")
    ud = os.path.join(RC, "user_data", "data")
    for f in ("bdat_wii.json", "bdat_de.json"):
        cp(os.path.join(ROOT, "data", f), os.path.join(ud, f))
    open(os.path.join(RC, "user_data", "NOT_FOR_DISTRIBUTION.txt"), "w").write(NOT_FOR_DIST)
    us = os.path.join(RC, "user_saves")
    for name, src in user_saves.items():
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(us, name))
        else:
            cp(src, os.path.join(us, name))
    open(os.path.join(us, "NOT_FOR_DISTRIBUTION.txt"), "w").write(NOT_FOR_DIST)
    val = os.path.join(RC, "validation")
    os.makedirs(val, exist_ok=True)
    for rel in ("work/phase2e/input_manifest_start.json", "work/phase2e/input_manifest_end.json",
                "work/phase2e/d2w_matrix.json", "work/phase2e/test_all.log", "work/phase2e/validation_summary.json"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            cp(p, os.path.join(val, os.path.basename(p)))
    for f in ("XC_WII_TO_DE_PHASE2E.md", "OVERNIGHT_SUMMARY.md"):
        if os.path.exists(os.path.join(ROOT, f)):
            cp(os.path.join(ROOT, f), os.path.join(RC, f))
    sums = []
    for r, _, fs in os.walk(RC):
        for f in sorted(fs):
            p = os.path.join(r, f)
            sums.append((hashlib.sha256(open(p, "rb").read()).hexdigest(), os.path.relpath(p, RC).replace("\\", "/")))
    open(os.path.join(RC, "SHA256SUMS.txt"), "w").write("".join(f"{h} *{p}\n" for h, p in sorted(sums, key=lambda x: x[1])))
    print(f"{len(sums)} files in {RC}")


if __name__ == "__main__":
    main(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {})
