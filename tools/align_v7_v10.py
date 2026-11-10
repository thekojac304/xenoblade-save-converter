"""Align a v7 DE save against a v10 DE save by unique byte windows (read-only).

Usage: python -I align_v7_v10.py <v7.sav> <v10.sav> <out.tsv>
For each 32-byte window of the v7 file that is distinctive (>= 8 nonzero bytes) and occurs exactly once in
the v7 file, finds its occurrences in the v10 file and records the offset delta. Writes only <out.tsv>.
"""
import sys

W = 32


def main(p7, p10, out):
    a, b = open(p7, "rb").read(), open(p10, "rb").read()
    rows = []
    for off in range(0, len(a) - W, 8):
        w = a[off:off + W]
        if sum(1 for x in w if x) < 8 or a.count(w) != 1:
            continue
        hits = []
        i = b.find(w)
        while i != -1 and len(hits) < 3:
            hits.append(i)
            i = b.find(w, i + 1)
        if len(hits) == 1:
            rows.append((off, hits[0] - off))
    with open(out, "w") as f:
        f.write("v7_off\tdelta\n")
        for off, dl in rows:
            f.write(f"0x{off:06X}\t{dl:+#x}\n")
    # summarise runs of equal delta
    runs = []
    for off, dl in rows:
        if runs and runs[-1][2] == dl:
            runs[-1][1] = off
            runs[-1][3] += 1
        else:
            runs.append([off, off, dl, 1])
    for s, e, dl, n in runs:
        if n >= 2:
            print(f"v7 0x{s:06X}-0x{e + W:06X}  delta {dl:+#x}  ({n} anchors)")


if __name__ == "__main__":
    main(*sys.argv[1:4])
