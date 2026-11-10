"""Enumerate every bfsgame*.sav blob in a git save archive and extract DE metadata (read-only).

Usage: python -I scan_de_history.py <bare repo> <out.tsv>
Reads git objects only (no checkout); writes only <out.tsv>.

v7 offsets: hashcade/xbde-save-editor (docs/*.md, core/SaveDocument.cs) and
hanyu1774/XCDE-Save-File-Editor (XCDESave/XCDESaveData.cs, PartyMember.cs).
"""
import hashlib
import struct
import subprocess
import sys

V7_SIZE, V10_SIZE = 0x153860, 0x153F30
PARTY = {V7_SIZE: 0x152318, V10_SIZE: 0x1526D8}
CHARS = {V7_SIZE: 0x152368}  # 16 records x 0x138; level +0, EXP +4
MONEY = {V7_SIZE: 0x151B40}


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", repo, *args], input=data, capture_output=True, check=True).stdout


def de_meta(d):
    u = lambda fmt, off: struct.unpack_from("<" + fmt, d, off)[0]
    n = len(d)
    m = {
        "size": n, "version": u("I", 0), "play_s": u("I", 4), "ts_raw": d[8:16].hex(),
        "story": u("H", 0xDF0), "region_aff": [u("H", 0xDF4 + 2 * i) for i in range(5)],
        "pair_aff_1_6": [u("H", 0xE02 + 2 * i) for i in range(6)], "c6": d[0xCF8:0xCFF].hex(),
    }
    if n in PARTY:
        p = PARTY[n]
        m["party"] = [x for x in (u("H", p + 2 * i) for i in range(12)) if x]
    if n in CHARS:
        c = CHARS[n]
        m["levels_shulk_to_fioraM"] = [u("I", c + 0x138 * i) for i in range(8)]
        m["money"] = u("I", MONEY[n])
    return m


def main(repo, out):
    log = git(repo, "log", "--reverse", "--format=@%H %cI", "--raw", "--no-abbrev", "--", "*.sav").decode()
    rows, commit = [], None
    for line in log.splitlines():
        if line.startswith("@"):
            commit = line[1:].split()
        elif line.startswith(":"):
            meta, path = line.split("\t")
            blob = meta.split()[3]
            if not path.startswith("bfsgame") or set(blob) == {"0"}:
                continue
            d = git(repo, "cat-file", "blob", blob)
            m = de_meta(d)
            rows.append([commit[0], commit[1], path, blob, hashlib.sha256(d).hexdigest(), m])
    keys = ["size", "version", "play_s", "story", "party", "levels_shulk_to_fioraM", "money", "region_aff", "pair_aff_1_6", "c6", "ts_raw"]
    with open(out, "w", encoding="utf8") as f:
        f.write("\t".join(["commit", "date", "file", "blob", "sha256"] + keys) + "\n")
        for c, date, path, blob, sha, m in rows:
            f.write("\t".join([c, date, path, blob, sha] + [str(m.get(k, "")) for k in keys]) + "\n")
    print(f"{len(rows)} save blobs -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
