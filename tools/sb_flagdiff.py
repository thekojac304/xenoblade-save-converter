"""Pair Wii and DE SB event scripts and collect integer-constant substitutions (read-only).

Usage: python sb_flagdiff.py <wii script.pkb> <de romfs/script dir> <out_pairs.tsv> <out_subst.tsv>

The SB header (both versions) holds 14 u32 section offsets at +8; the int pool section is
{u32 off=8, u32 count} followed by count u32 constants (Wii big-endian, DE little-endian).
Scripts are paired by int-pool multiset similarity, the pools aligned with difflib, and every
replaced constant pair (wii, de) recorded. Flag ids appear as plain constants passed to the
flag plugins, so systematic substitutions inside a flag-id range expose renumbering.
"""
import difflib
import os
import re
import struct
import sys
from collections import Counter, defaultdict


def int_pool(d, e):
    o = struct.unpack_from(e + "I", d, 8 + 4 * 2)[0]
    off, cnt = struct.unpack_from(e + "2I", d, o)
    return list(struct.unpack_from(e + "%dI" % cnt, d, o + off))


def de_name(d):
    m = re.search(rb"scene\\([0-9a-z_]+)\.sp", d)
    return m.group(1).decode() if m else None


def main(pkb, de_dir, out_pairs, out_sub):
    w = open(pkb, "rb").read()
    starts = [m.start() for m in re.finditer(rb"SB  \x02", w)]
    wii = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(w)
        try:
            wii.append((s, int_pool(w[s:e], ">")))
        except struct.error:
            pass
    de = []
    for fn in sorted(os.listdir(de_dir)):
        if fn.endswith(".sb"):
            d = open(os.path.join(de_dir, fn), "rb").read()
            de.append((fn, int_pool(d, "<")))
    de_sets = [(fn, Counter(p)) for fn, p in de]
    pairs = []
    for off, p in wii:
        cp = Counter(p)
        best = max(de_sets, key=lambda x: sum((cp & x[1]).values()) / max(1, max(len(p), sum(x[1].values()))))
        score = sum((cp & best[1]).values()) / max(1, max(len(p), sum(best[1].values())))
        pairs.append((off, best[0], score, len(p), sum(best[1].values())))
    depool = dict(de)
    subst = Counter()
    where = defaultdict(set)
    for (off, p), (_, fn, score, _, _) in zip(wii, pairs):
        if score < 0.6:
            continue
        q = depool[fn]
        sm = difflib.SequenceMatcher(None, p, q, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and i2 - i1 == j2 - j1:
                for a, b in zip(p[i1:i2], q[j1:j2]):
                    subst[(a, b)] += 1
                    where[(a, b)].add(fn)
    with open(out_pairs, "w") as f:
        f.write("wii_pkb_offset\tde_file\tscore\twii_pool\tde_pool\n")
        for off, fn, sc, a, b in pairs:
            f.write(f"0x{off:X}\t{fn}\t{sc:.3f}\t{a}\t{b}\n")
    with open(out_sub, "w") as f:
        f.write("wii_const\tde_const\tdelta\tcount\tfiles\n")
        for (a, b), c in sorted(subst.items()):
            f.write(f"{a}\t{b}\t{b - a}\t{c}\t{','.join(sorted(where[(a, b)])[:6])}\n")
    good = sum(1 for x in pairs if x[2] >= 0.6)
    print(f"wii blobs {len(wii)}, de scripts {len(de)}, paired (score>=0.6) {good}, substitutions {len(subst)}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
