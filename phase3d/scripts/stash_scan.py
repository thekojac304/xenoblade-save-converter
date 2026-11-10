"""Scan the public DE archive (public/xcde-saves.git blobs listed in tables/de_history.tsv) for "departed" main
characters: absent from the party, not Fiora's retired record 3, with non-default gear in the DE stash (0x3BB50).
Read-only (git cat-file).  python stash_scan.py > out.tsv"""
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import canon  # noqa: E402
import stash  # noqa: E402

GIT = os.path.join(ROOT, "public", "xcde-saves.git")
d = json.load(open(os.path.join(ROOT, "data", "bdat_de.json"), encoding="utf-8"))["BTL_pclist"]
rows = d["rows"] if isinstance(d, dict) and "rows" in d else d
rows = rows if isinstance(rows, list) else list(rows.values())
DEF = {r["id"]: {r[c] for c in ("def_wpn", "def_head", "def_body", "def_arm", "def_waist", "def_legg",
                                "melia_def_wpn", "melia_def_head", "melia_def_body", "melia_def_arm",
                                "melia_def_waist", "melia_def_legg")} for r in rows}


def departed(blob, story, party):
    e = stash.entries(blob, range(1, 9))
    out = {}
    for k in canon.main_chars(story):
        if k in party or k == 3:
            continue
        real = {s: v["gid"] for (kk, s), v in e.items() if kk == k and v["gid"] and v["gid"] not in DEF[k]}
        if real:
            out[k] = real
    return out


if __name__ == "__main__":
    w = sys.stdout
    w.write("story\tparty\tdeparted_with_gear\tfile\tdate\n")
    for r in csv.DictReader(open(os.path.join(ROOT, "tables", "de_history.tsv")), delimiter="\t"):
        try:
            blob = subprocess.run(["git", "--git-dir", GIT, "cat-file", "blob", r["blob"]], capture_output=True,
                                  check=True).stdout
        except subprocess.CalledProcessError:
            continue
        if len(blob) < 0x46900:
            continue
        story, party = int(r["story"]), json.loads(r["party"])
        dep = departed(blob, story, party)
        w.write(f"{story}\t{party}\t{json.dumps({k: sorted(v.values()) for k, v in dep.items()}) if dep else ''}\t"
                f"{r['file']}\t{r['date'][:10]}\n")
