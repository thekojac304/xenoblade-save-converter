"""In-memory dry run of the Wii -> DE game-flag transplant (read-only; writes only a TSV report).

Usage: python flag_transplant_eval.py <wii save> <de template save> <out.tsv> [<de reference save> ...]

Builds the DE flag state (global id -> value) that the code-derived rules produce from the Wii save on
top of the DE template, without serialising it to any save file. Reports per-bank counts, rule
exceptions, and agreement with optional real DE reference saves.

Rules (XC_WII_TO_DE_PHASE2B.md section 6):
  32-bit : DE[0x000] = Wii 16-bit[0x108] (bitmask widened in DE); other 32-bit ids kept from template.
  16-bit : identity for 0x020-0x21F, except 0x108 (moved) and HOLD16 (unverified -> template).
  8-bit  : id < 0x608 identity; 0x608 <= id <= 0x8F3 -> id + 300; DE 0x608-0x733 (Future Connected
           quest slots 1000-1299) kept from template.
  1-bit  : id < 0x30C8 identity (DE-only 0x1E70 kept); 0x30C8 <= id < 0x3424 -> +300;
           id >= 0x3424 -> +500.  DE-only 0x30C8-0x31F3 kept; DE-only 0x3550-0x3617 ("B" mirror)
           kept from template (option: rebuild as subset of transplanted 0x346C block).
"""
import sys

import flagmap as fm

HOLD16 = {0xB7, 0xBE, 0xBF, 0xC3, 0xF9}
DE_ONLY_1BIT = [(0x1E70, 0x1E71), (0x30C8, 0x31F4), (0x3550, 0x3618)]
DE_ONLY_8BIT = [(0x608, 0x734)]


def map_wii_to_de(gid):
    k = fm.kind(gid)
    if k == 32:
        return None
    if k == 16:
        if gid == 0x108:
            return 0x000
        return None if gid in HOLD16 else gid
    if k == 8:
        if gid < 0x608:
            return gid
        return gid + 300 if gid <= 0x8F3 else "overflow"
    if gid < 0x30C8:
        return gid
    if gid < 0x3424:
        return gid + 300
    return gid + 500 if gid + 500 < 0x3720 else "overflow"


def in_ranges(g, ranges):
    return any(a <= g < b for a, b in ranges)


def build(wii, de_tpl):
    state, notes = {}, []
    for width in (32, 16, 8, 1):
        lo, hi = fm.DE_RANGE[width]
        for g in range(lo, hi):
            state[g] = fm.de_get(de_tpl, g)  # template baseline
    written = set()
    for width in (32, 16, 8, 1):
        lo, hi = fm.WII_RANGE[width]
        for g in range(lo, hi):
            v = fm.wii_get(wii, g)
            t = map_wii_to_de(g)
            if t is None:
                if v:
                    notes.append(("held_from_template", hex(g), v))
                continue
            if t == "overflow":
                if v:
                    # Phase 2E: Wii 1-bit 0x352C-0x36CF is set by normal Wii play (block 0x3440+i: NPC registration /
                    # update notifications, e.g. 0x36C5/0x36C7 after visiting Colony 9 and Frontier Village) and has no
                    # DE slot: Wii-only state, kept on the Wii side (lineage base), not an error.
                    wii_only = fm.kind(g) == 1 and 0x352C <= g <= 0x36CF
                    notes.append(("wii_only_high_1bit" if wii_only else "OVERFLOW_nonzero", hex(g), v))
                continue
            if fm.kind(t) == 1 and (t == 0x1E70 or in_ranges(t, DE_ONLY_1BIT)):
                notes.append(("target_is_de_only", hex(g), v))
                continue
            state[t] = v
            written.add(t)
    for width, ranges in ((1, DE_ONLY_1BIT), (8, DE_ONLY_8BIT)):
        for a, b in ranges:
            for g in range(a, b):
                if g in written:
                    notes.append(("CONFLICT_de_only_written", hex(g), state[g]))
    return state, written, notes


def main(argv):
    wii = fm.load(argv[0])[1]
    tpl = fm.load(argv[1])[1]
    refs = [fm.load(p)[1] for p in argv[3:]]
    state, written, notes = build(wii, tpl)
    for width in (32, 16, 8, 1):
        lo, hi = fm.DE_RANGE[width]
        nz = sum(1 for g in range(lo, hi) if state[g])
        tz = sum(1 for g in range(lo, hi) if fm.de_get(tpl, g))
        wr = sum(1 for g in written if lo <= g < hi)
        print(f"{width:>2}-bit: ids written from Wii {wr:5}; nonzero after transplant {nz:5} (template had {tz})")
    print("story counter ->", state[0x20], "| 32-bit[0] ->", hex(state[0]))
    from collections import Counter
    print("notes:", Counter(n[0] for n in notes))
    for r in refs:
        b1 = [g for g in range(0xA20, 0x3720) if state[g]]
        ok = sum(1 for g in b1 if fm.de_get(r, g))
        q = [g for g in range(0x221, 0x608) if state[g]]
        okq = sum(1 for g in q if fm.de_get(r, g))
        print(f"vs reference (story {fm.de_get(r, 0x20)}): 1-bit set flags also set {ok}/{len(b1)}; "
              f"nonzero quest bytes also nonzero {okq}/{len(q)}")
    with open(argv[2], "w") as f:
        f.write("note\twii_gid\tvalue\n")
        for n in notes:
            f.write("\t".join(map(str, n)) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
