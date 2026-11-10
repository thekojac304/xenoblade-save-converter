"""Evaluate the candidate Wii -> DE game-flag mapping rules against real saves (read-only).

Usage: python -I flag_mapping_eval.py <out.tsv> <wii_save>... -- <de_save>...
Prints agreement statistics per bank; writes per-flag evidence rows to <out.tsv>.

Candidate rules (XC_WII_TO_DE_PHASE2A.md section 6):
  1-bit : Wii BE u32 words @0xACB0, DE LE u32 words @0x50, bit n = word n>>5, bit n&31.
          DE index = n for n < B1, n + 300 for n >= B1, with B1 in (9459, 9897].
  8-bit : Wii byte @0xA4AE + q  <->  DE byte @0x5F0 + q   for q < 1000 (quest-state bytes, by quest id).
  16-bit: Wii BE u16 @0xA0B2 + 2j <-> DE LE u16 @0xDF0 + 2j (only j = 0 and 2..6 are claimed).
"""
import random
import struct
import sys

B1 = 9897
WII_B1, DE_B1 = 0xACB0, 0x50
WII_B8, DE_B8 = 0xA4AE, 0x5F0


def bitset(d, base, fmt):
    out = set()
    for w in range(360):
        v = struct.unpack_from(fmt, d, base + 4 * w)[0]
        for j in range(32):
            if v >> j & 1:
                out.add(32 * w + j)
    return out


def map1(n):
    return n + 300 if n >= B1 else n


def main(argv):
    out = argv[0]
    sep = argv.index("--")
    wii = {p.replace("\\", "/").split("/")[-1]: open(p, "rb").read() for p in argv[1:sep]}
    de = {p.replace("\\", "/").split("/")[-1]: open(p, "rb").read() for p in argv[sep + 1:]}
    wbits = {k: bitset(d, WII_B1, ">I") for k, d in wii.items()}
    dbits = {k: bitset(d, DE_B1, "<I") for k, d in de.items()}
    rows = []
    rng = random.Random(1)
    print("1-bit bank: fraction of Wii set flags that are set in DE (rule / identity / random-shift baseline)")
    for wk, ws in wbits.items():
        for dk, ds in dbits.items():
            rule = sum(1 for n in ws if map1(n) in ds)
            ident = sum(1 for n in ws if n in ds)
            base = []
            for _ in range(200):
                s = rng.randrange(500, 11000)
                base.append(sum(1 for n in ws if (n + s) % 11520 in ds))
            print(f"  {wk:<10} -> {dk:<40} rule {rule:4}/{len(ws)} = {rule / len(ws):.1%}   identity {ident / len(ws):.1%}"
                  f"   random-shift mean {sum(base) / len(base) / len(ws):.1%} max {max(base) / len(ws):.1%}")
    print("  Wii bits beyond DE capacity under rule (n+300 >= 11520):",
          {k: sorted(n for n in s if map1(n) >= 11520) for k, s in wbits.items()})
    print("8-bit bank: Wii quest-state bytes at valid quest ids (validity of base 0xA4AE vs 0xA4B0)")
    for wk, d in wii.items():
        for base in (0xA4AE, 0xA4B0):
            nz = [q for q in range(1, 1000) if d[base + q]]
            print(f"  {wk:<10} base 0x{base:X}: {len(nz)} nonzero in 1..999; q=0 byte {d[base]}")
    for wk, d in wii.items():
        for q in range(0, 1000):
            if d[WII_B8 + q]:
                rows.append(("b8", wk, q, d[WII_B8 + q], ";".join(f"{dk}={dd[DE_B8 + q]}" for dk, dd in de.items())))
        for n in sorted(wbits[wk]):
            rows.append(("b1", wk, n, 1, ";".join(f"{dk}={int(map1(n) in ds)}" for dk, ds in dbits.items())))
        for j in (0, 2, 3, 4, 5, 6):
            v = struct.unpack_from(">H", d, 0xA0B2 + 2 * j)[0]
            rows.append(("b16", wk, j, v, ";".join(f"{dk}={struct.unpack_from('<H', dd, 0xDF0 + 2 * j)[0]}"
                                                 for dk, dd in de.items())))
    with open(out, "w", encoding="utf8") as f:
        f.write("bank\twii_save\tindex\twii_value\tde_values_under_rule\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    print(f"{len(rows)} evidence rows -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
