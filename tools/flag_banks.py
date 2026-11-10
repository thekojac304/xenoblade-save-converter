"""Wii / DE game-flag bank extraction and correspondence tests (read-only).

Usage:
  python -I flag_banks.py dump <save> [<save> ...]          per-bank summary
  python -I flag_banks.py compare <wii_save> <de_save> [...] score candidate mappings
  python -I flag_banks.py byte8 <wii_save> <de_save> <idx>... show 8-bit flags side by side

Bank layouts (structural hypothesis, see XC_WII_TO_DE_PHASE2A.md section 4/5):
  Wii FLAG payload 0xA030-0xB250 (big-endian): 32-bit x32 @0xA030, 16-bit x512 @0xA0B0,
      8-bit x2048 @0xA4B0, 1-bit x11520 @0xACB0 (0x5A0 bytes)
  DE (v7 and v10 prefix, little-endian): 1-bit x11520 @0x50, 8-bit x2048 @0x5F0,
      16-bit x512 @0xDF0, 32-bit x32 @0x11F0
DE global flag ids (from hashcade descriptor constants): 32-bit 0x000-0x01F, 16-bit 0x020-0x21F,
8-bit 0x220-0xA1F, 1-bit 0xA20-0x371F.
"""
import struct
import sys

WII = {"b32": 0xA030, "b16": 0xA0B0, "b8": 0xA4B0, "b1": 0xACB0, "end": 0xB250}
DE = {"b1": 0x50, "b8": 0x5F0, "b16": 0xDF0, "b32": 0x11F0, "end": 0x1270}
N = {"b32": 32, "b16": 512, "b8": 2048, "b1": 11520}


def load(path):
    d = open(path, "rb").read()
    if d[:4] == b"USRD":
        return "wii", d
    return "de", d


def banks(kind, d):
    if kind == "wii":
        o, e = WII, ">"
    else:
        o, e = DE, "<"
    out = {
        "b32": list(struct.unpack_from(e + "32I", d, o["b32"])),
        "b16": list(struct.unpack_from(e + "512H", d, o["b16"])),
        "b8": list(d[o["b8"]:o["b8"] + 2048]),
        "b1raw": d[o["b1"]:o["b1"] + 0x5A0],
    }
    return out


def bits(raw, order):
    """Expand the 1-bit bank to a list of flag values under a candidate bit numbering."""
    res = []
    if order == "byte_lsb":  # flag n = byte n>>3, bit n&7 (LSB first)
        for b in raw:
            res.extend((b >> i) & 1 for i in range(8))
    elif order == "byte_msb":  # flag n = byte n>>3, bit 7-(n&7)
        for b in raw:
            res.extend((b >> (7 - i)) & 1 for i in range(8))
    elif order in ("word_le", "word_be"):  # 32-bit words, flag n = word n>>5, bit n&31
        fmt = "<I" if order == "word_le" else ">I"
        for i in range(0, len(raw), 4):
            w = struct.unpack_from(fmt, raw, i)[0]
            res.extend((w >> j) & 1 for j in range(32))
    elif order == "word_be_msb":  # big-endian words, flag n = bit 31-(n&31)
        for i in range(0, len(raw), 4):
            w = struct.unpack_from(">I", raw, i)[0]
            res.extend((w >> (31 - j)) & 1 for j in range(32))
    return res


ORDERS = ["byte_lsb", "byte_msb", "word_le", "word_be", "word_be_msb"]


def dump(paths):
    for p in paths:
        kind, d = load(p)
        b = banks(kind, d)
        nz8 = [i for i, v in enumerate(b["b8"]) if v]
        nz16 = [(i, v) for i, v in enumerate(b["b16"]) if v]
        print(f"== {kind} {p}")
        print(f"  b32 nonzero: {[(i, v) for i, v in enumerate(b['b32']) if v]}")
        print(f"  b16 nonzero ({len(nz16)}): {nz16[:40]}")
        print(f"  b8 nonzero count {len(nz8)}; first: {[(i, b['b8'][i]) for i in nz8[:30]]}")
        print(f"  b1 set bits (byte_lsb) {sum(bits(b['b1raw'], 'byte_lsb'))}")


def overlap(a, b, shift=0):
    """For index sets a (Wii) and b (DE): |a+shift & b| / |a|, |a+shift & b| / |b|."""
    sa = {i + shift for i in a}
    inter = len(sa & b)
    return inter, len(a), len(b)


def compare(wii_path, de_paths):
    _, wd = load(wii_path)
    wb = banks("wii", wd)
    for dp in de_paths:
        _, dd = load(dp)
        db = banks("de", dd)
        print(f"== Wii {wii_path.split('/')[-1]}  vs  DE {dp.split('/')[-1]}")
        # 8-bit bank: index sets of nonzero bytes, test shifts
        w8 = {i for i, v in enumerate(wb["b8"]) if v}
        d8 = {i for i, v in enumerate(db["b8"]) if v}
        best = sorted(((overlap(w8, d8, s)[0], s) for s in range(-8, 9)), reverse=True)[:3]
        print(f"  b8 nonzero: wii {len(w8)} de {len(d8)}; best shifts (overlap, shift): {best}")
        eq = sum(1 for i in w8 & d8 if wb["b8"][i] == db["b8"][i])
        print(f"     shift 0: overlap {len(w8 & d8)}, identical values {eq}")
        # 1-bit bank: all bit orders on each side
        dset = {i for i, v in enumerate(bits(db["b1raw"], "byte_lsb")) if v}
        for wo in ORDERS:
            wset = {i for i, v in enumerate(bits(wb["b1raw"], wo)) if v}
            res = sorted(((overlap(wset, dset, s)[0], s) for s in (-8, -1, 0, 1, 8)), reverse=True)[0]
            inter, na, nb = overlap(wset, dset, 0)
            exp = na * nb / N["b1"]
            print(f"  b1 wii:{wo:<12} vs de:byte_lsb  wii={na:5} de={nb:5} overlap@0={inter:5} "
                  f"(chance ~{exp:7.1f})  best shift {res[1]:+d}->{res[0]}")


def byte8(wii_path, de_path, idxs):
    _, wd = load(wii_path)
    _, dd = load(de_path)
    wb, db = banks("wii", wd), banks("de", dd)
    for i in idxs:
        print(f"  b8[{i:#05x}] wii={wb['b8'][i]:3} de={db['b8'][i]:3}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dump":
        dump(sys.argv[2:])
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3:])
    elif cmd == "byte8":
        byte8(sys.argv[2], sys.argv[3], [int(x, 0) for x in sys.argv[4:]])
