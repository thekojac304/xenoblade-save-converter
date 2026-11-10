"""Assemble release_candidate_2F/ (Phase 2F). Copies only; never touches game folders or release_candidate/ (2E).

release_candidate_2F/
  converter/        distributable: tools (converter + CLI), specs, tests, docs, xcconv.cmd - no game data, no saves
  user_data/data/   bdat_wii.json / bdat_de.json made from YOUR game files - NOT FOR DISTRIBUTION
  user_saves/       your converted save (2F), sidecar, manifest - personal, NOT FOR DISTRIBUTION
  validation/       protected-file manifests, test logs, coverage matrix, game-run summaries, package test
  *.md              Phase 2F reports
  SHA256SUMS.txt
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RC = os.path.join(ROOT, "release_candidate_2F")
P2F = os.path.join(ROOT, "phase2f")
CODE = ["xcconv.py", "convert.py", "de_to_wii.py", "canon.py", "sidecar.py", "reimport.py", "safeio.py", "wii_save.py",
        "de_save.py", "flagmap.py", "flag_transplant_eval.py", "phase2c.py", "quest_counters.py", "achievements.py",
        "minimap.py", "paths.py", "bdat.py", "dump_bdat.py"]
SPECS = ["wii_to_de_rules.json", "wii_layout.json", "de_v10_layout.json", "wii_award_tiers.json"]
PKG_DOCS = ["README_CONVERTER.md", "BIDIRECTIONAL_DESIGN.md", "KNOWN_LIMITATIONS.md"]
REPORTS = ["XC_WII_TO_DE_PHASE2F.md", "TEST_COVERAGE_MATRIX.md", "EDGE_CASE_RESULTS.md", "KNOWN_LIMITATIONS.md",
           "README_CONVERTER.md", "RELEASE_READINESS.md", "WORKDAY_SUMMARY.md"]
NOT_FOR_DIST = ("These files are derived from or are your own game data / saves (or public research saves). Keep them "
                "private; do not publish or share them.\n")
NOTICE = """xcconv 2F-rc1 - notices

Licence: none chosen yet. The code was written for the owner of this research folder; all rights reserved until the
owner picks a licence. Nothing in this package is published.

Third-party information used (no third-party code is included):
  * DE save offsets: hashcade/xbde-save-editor documentation and hanyu1774 PartyMember.cs (cited in tools/de_save.py),
    re-verified against real saves and the DE executable.
  * CRC-16/ARC, zlib, base64, JSON: Python standard library.
The converter needs no packages beyond the Python standard library. The research disassembly helpers (not included)
use capstone.

Not included, by design: game executables, disc images, BDAT tables or other game data, and any save file. The
converter reads the tables from the user's own dumps (tools/dump_bdat.py; see README_CONVERTER.md, XCCONV_DATA).
"""
COMPAT = """# Compatibility (2F-rc1)

| Item | Supported | Notes |
|---|---|---|
| Wii game | Xenoblade Chronicles NTSC-U (SX4E01) saves `monado01..03` | other regions not tested |
| DE game | save format v10 (DE 2.0 / Monado recompilation) | v7 is refused for export; load + save once in DE 2.0 |
| Party | Shulk, Reyn, Fiora (first form), Dunban, Sharla, Riki, Melia | Fiora's second form (8) and guests refused |
| Maps | the 28 Wii maps (FLD_maplist) | DE-only and Future Connected maps refused |
| Wii -> DE | **VALIDATED** for the user's playthrough (scenario 150, story verified to 156 in 2E; 2F file reloaded) | |
| DE -> Wii | **PARTIALLY VALIDATED** (load, party, combat, travel, save; late-game DE save round trip in 2F) | Wii story progression after export not played |
| Python | 3.11+ (tested with 3.14) | Windows paths tested; standard library only |
"""


def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def main():
    if os.path.exists(RC):
        raise SystemExit(f"{RC} exists; it is generated - move it away first")
    conv = os.path.join(RC, "converter")
    for f in CODE:
        cp(os.path.join(HERE, f), os.path.join(conv, "tools", f))
    for f in SPECS:
        cp(os.path.join(ROOT, "specs", f), os.path.join(conv, "specs", f))
    for f in sorted(os.listdir(os.path.join(ROOT, "tests"))):
        if f.endswith(".py"):
            cp(os.path.join(ROOT, "tests", f), os.path.join(conv, "tests", f))
    for f in PKG_DOCS:
        cp(os.path.join(ROOT, f), os.path.join(conv, f))
    with open(os.path.join(conv, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE)
    with open(os.path.join(conv, "COMPATIBILITY.md"), "w", encoding="utf-8") as f:
        f.write(COMPAT)
    with open(os.path.join(conv, "xcconv.cmd"), "w", encoding="utf-8") as f:
        f.write('@echo off\r\npython "%~dp0tools\\xcconv.py" %*\r\n')
    with open(os.path.join(conv, "tests", "README.txt"), "w", encoding="utf-8") as f:
        f.write("The regression suite needs the research fixtures (your saves under work/originals, the template under "
                "work/template, phase2f/fixtures). Run it from the research folder:\n"
                "  python -m unittest discover -s tests -v\n"
                "From a clean copy of this package, use the CLI checks instead (roundtrip-check, validate); see "
                "validation/package_test.json for the clean-directory run.\n")
    ud = os.path.join(RC, "user_data", "data")
    for f in ("bdat_wii.json", "bdat_de.json"):
        cp(os.path.join(ROOT, "data", f), os.path.join(ud, f))
    with open(os.path.join(RC, "user_data", "NOT_FOR_DISTRIBUTION.txt"), "w") as f:
        f.write(NOT_FOR_DIST)
    us = os.path.join(RC, "user_saves")
    shutil.copytree(os.path.join(P2F, "rc_user", "wii_to_de_monado01"), os.path.join(us, "wii_to_de_monado01"))
    cp(os.path.join(P2F, "rc_user", "wii_to_de_monado01_report.json"), os.path.join(us, "wii_to_de_monado01_report.json"))
    with open(os.path.join(us, "NOT_FOR_DISTRIBUTION.txt"), "w") as f:
        f.write(NOT_FOR_DIST)
    val = os.path.join(RC, "validation")
    for rel in ("manifests/protected_start.json", "manifests/protected_end.json", "manifests/snapshot_2E_sha256.json",
                "results/baseline_2E_tests.log", "results/full_suite_final.log", "results/coverage_matrix.json",
                "results/d1_checkpoint_matrix.json", "results/d4_flag_blocks.md", "results/package_test.json",
                "fixtures/F1_bitflip_fuzz_summary.json", "fixtures/real/PROVENANCE.md", "CHECKPOINT.md"):
        p = os.path.join(P2F, rel)
        if os.path.exists(p):
            cp(p, os.path.join(val, os.path.basename(p)))
    runs = []
    for kind in ("monado", "dolphin"):
        d = os.path.join(P2F, "runs", kind)
        for n in sorted(os.listdir(d)):
            m = os.path.join(d, n, "run_manifest.json")
            if os.path.exists(m):
                with open(m) as f:
                    j = json.load(f)
                runs.append({"emulator": kind, "run": n, **{k: j.get(k) for k in (
                    "status", "seconds", "mounted", "live_unchanged", "protected_unchanged", "protected_all_unchanged",
                    "watchdog_violation", "save_changed", "nand_root")}})
    with open(os.path.join(val, "game_runs_2F.json"), "w") as f:
        json.dump(runs, f, indent=1)
    for f in REPORTS:
        if os.path.exists(os.path.join(ROOT, f)):
            cp(os.path.join(ROOT, f), os.path.join(RC, f))
    sums = []
    for r, _, fs in os.walk(RC):
        for f in sorted(fs):
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                sums.append((hashlib.sha256(fh.read()).hexdigest(), os.path.relpath(p, RC).replace("\\", "/")))
    with open(os.path.join(RC, "SHA256SUMS.txt"), "w", newline="\n") as f:
        f.write("".join(f"{h} *{p}\n" for h, p in sorted(sums, key=lambda x: x[1])))
    print(f"{len(sums)} files in {RC}")


if __name__ == "__main__":
    sys.exit(main())
