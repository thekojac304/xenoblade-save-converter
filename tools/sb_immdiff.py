"""Compare inline 16-bit immediates (opcode 0x07, CONST_I_W) of paired Wii/DE SB scripts (read-only).

Usage: python sb_immdiff.py <wii script.pkb> <de script dir> <sb_pairs.tsv> <out.tsv> [de_endian <|>]

For each paired script, collects the multiset of u16 operands following byte 0x07 in the code
section (a superset: some hits are operand bytes of other opcodes). For every Wii value in the
1-bit flag-id range it records which deltas (0, +300, +500, ...) make it present in the DE script.
"""
import csv
import os
import re
import struct
import sys
from collections import Counter, defaultdict


def code_imms(d, e):
    code_hdr = struct.unpack_from(e + "I", d, 8)[0]
    off, _, size = struct.unpack_from(e + "3I", d, code_hdr)
    c = d[code_hdr + off:code_hdr + off + size]
    out = Counter()
    for i in range(len(c) - 2):
        if c[i] == 0x07:
            out[struct.unpack_from(e + "H", c, i + 1)[0]] += 1
    return out


def main(pkb, de_dir, pairs_tsv, out, de_e="<"):
    w = open(pkb, "rb").read()
    starts = [m.start() for m in re.finditer(rb"SB  \x02", w)]
    ends = dict(zip(starts, starts[1:] + [len(w)]))
    pairs = [r for r in csv.DictReader(open(pairs_tsv), delimiter="\t") if float(r["score"]) >= 0.6]
    deltas = (0, 300, 500, 200, 80, -300)
    stats = defaultdict(Counter)  # wii value -> Counter(delta explaining it)
    seen = Counter()
    for r in pairs:
        s = int(r["wii_pkb_offset"], 16)
        wi = code_imms(w[s:ends[s]], ">")
        di = code_imms(open(os.path.join(de_dir, r["de_file"]), "rb").read(), de_e)
        for v in wi:
            if 0xA20 <= v < 0x3720:
                seen[v] += 1
                for dl in deltas:
                    if di.get(v + dl):
                        stats[v][dl] += 1
    with open(out, "w") as f:
        f.write("wii_gid\twii_n\tscripts\t" + "\t".join(f"d{dl:+d}" for dl in deltas) + "\n")
        for v in sorted(seen):
            f.write(f"{v}\t{v - 0xA20}\t{seen[v]}\t" + "\t".join(str(stats[v][dl]) for dl in deltas) + "\n")
    # summary by n-range
    bins = defaultdict(Counter)
    for v in seen:
        n = v - 0xA20
        b = n // 256 * 256
        best = max(deltas, key=lambda dl: stats[v][dl]) if stats[v] else None
        bins[b][best] += 1
    for b in sorted(bins):
        print(f"n {b:5}-{b + 255:5}: " + ", ".join(f"{k}:{c}" for k, c in bins[b].most_common()))


if __name__ == "__main__":
    main(*sys.argv[1:5], *(sys.argv[5:6] or ["<"]))
