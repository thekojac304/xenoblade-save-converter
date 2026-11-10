"""Character base stats exactly as the game computes them (Phase 3A).

The 3DS game keeps each character's live stat block in the save (record +0x17C..+0x1F4) and does NOT recompute it
on load (loader 0x350418 copies it as is), unlike the Wii.  A save whose block is stale (any DE -> Wii/3DS export:
the 2H engine keeps the structural base's block, harmless on the Wii) therefore shows wrong HP/Strength/... on the
3DS until the next level-up.  This module reproduces the game's level-up routine (3DS 0x2AB6B0, constants at
0x2AB870: 120.0, 25.0, 0.02; BTL_pclist columns hp/str/agi/eth and *_lv99 via the name table 0x4C6574):

  for each new level L' (2..99), for each stat s in (hp, str, agi, eth):
      diff = s_lv99 - s
      s   += trunc_u32( f32( s + f32( f32(f32(diff) * 120) / f32(120 - L') + 25 ) * 0.02 ) ) - s
starting from BTL_pclist's values at the character's join level (column lv).  Verified on every native record.
"""
import struct

_f32 = struct.Struct("<f")


def F(x):
    """Round to IEEE single precision (each +, -, *, / of two singles computed in double and rounded once is the
    correctly rounded single result, so this reproduces the ARM VFP arithmetic exactly)."""
    return _f32.unpack(_f32.pack(float(x)))[0]
COLS = ("hp", "str", "agi", "eth")


def _u32(x):
    x = float(x)
    return int(x) if x > 0 else 0


def base_stats(pc_row, level):
    """(hp, str, agi, eth) of a character at `level` (join level .. 99) per the game's routine."""
    cur = [pc_row[c] for c in COLS]
    lv0 = max(1, pc_row.get("lv", 1))
    for nl in range(lv0 + 1, min(level, 99) + 1):
        for i, c in enumerate(COLS):
            mx = pc_row[c + "_lv99"] & 0xFFFF
            cv = cur[i]
            diff = (mx - cv) & 0xFFFFFFFF if i == 0 else (mx - cv)
            if i == 0:
                diff = mx - cv           # u32 arithmetic in the game; HP never exceeds the lv99 value
            s1 = F(F(diff) * F(120.0))
            s3 = F(s1 / F(F(120.0) - F(nl)))
            new = F(F(cv) + F(F(s3 + F(25.0)) * F(0.02)))
            cur[i] = _u32(new)
    return tuple(cur)


def expected_block_values(pc_row, level):
    hp, s, a, e = base_stats(pc_row, level)
    return {"hp_max": hp, "str": s, "agi": a, "eth": e}


def check_record(rec, pc_row, endian=">"):
    """Is a character record's stat block consistent with its level? -> (ok, expected, stored)."""
    lv = struct.unpack_from(endian + "I", rec, 0x17C)[0]
    hp = struct.unpack_from(endian + "f", rec, 0x18C)[0]
    st = struct.unpack_from(endian + "3H", rec, 0x198)
    exp = base_stats(pc_row, lv)
    stored = (int(hp),) + st
    return stored == exp, exp, stored


# ---------------------------------------------------------------------------------------------- equipment caches
# playable characters 1-7 only (guests keep caches without item rows).
# record +0x28 + 0x20*slot (head, body, arm, legs, feet): u16[16], [9] eva_rate, [11] arm_phy, [12] arm_eth,
# [13] arm_type (ITM_equiplist row);  +0xC8 weapon cache (ITM_wpnlist row): f32 hit_range_near*0.01f,
# f32 hit_range_far*0.01f, f32 speed*0.1f, u16 dmg_low, dmg_hi, att_lev, 0, grd_rate, arm_phy, arm_eth, 0,
# u8 wpn_type, u8 elem, u16 flag.  flag & 4 (the Monados): dmg = int(f32(dmg * level) * 1.4 / 1.5), capped at 999
# (3DS 0x277300, run after every level-up).  Verified against every native record (see test_phase3a_stats).
def armour_cache(eq_row):
    c = [0] * 16
    if eq_row:
        c[9], c[11], c[12], c[13] = eq_row["eva_rate"], eq_row["arm_phy"], eq_row["arm_eth"], eq_row["arm_type"]
    return struct.pack(">16H", *c)


def weapon_cache(wp_row, level):
    if not wp_row:
        return bytes(0x20)
    lo, hi = wp_row["dmg_low"], wp_row["dmg_hi"]
    if wp_row["flag"] & 4:
        lo = int(F(F(lo * level) * F(1.4)))
        hi = int(F(F(hi * level) * F(1.5)))
        lo, hi = (999 if lo >= 1000 else lo), (999 if hi >= 1000 else hi)
    f = (F(wp_row["hit_range_near"]) * F(0.01), F(wp_row["hit_range_far"]) * F(0.01), F(wp_row["speed"]) * F(0.1))
    return (struct.pack(">3f", *[float(x) for x in f]) +
            struct.pack(">8H", lo, hi, wp_row["att_lev"], 0, wp_row["grd_rate"], wp_row["arm_phy"], wp_row["arm_eth"], 0) +
            struct.pack(">BBH", wp_row["wpn_type"], wp_row["elem"], wp_row["flag"]))


def rebuild(wii, bdat, chars=range(1, 8)):
    """Rebuild every character's derived block (base stats, armour and weapon caches) in a Wii-layout image.
    -> (new image, [changes]).  A record is only touched where it differs from what the game would compute."""
    import wii_save as W
    pc = {r["id"]: r for r in bdat["BTL_pclist"]["rows"]}
    eq = {r["id"]: r for r in bdat["ITM_equiplist"]["rows"]}
    wp = {r["id"]: r for r in bdat["ITM_wpnlist"]["rows"]}
    b = bytearray(wii)
    changes = []
    for k in chars:
        if k not in pc:
            continue
        o = W.CHAR_BASE + W.CHAR_SIZE * k
        lv = struct.unpack_from(">I", b, o + 0x17C)[0]
        if not 1 <= lv <= 99:
            continue
        hp, st, ag, et = base_stats(pc[k], lv)
        cur = (int(struct.unpack_from(">f", b, o + 0x18C)[0]),) + struct.unpack_from(">3H", b, o + 0x198)
        if cur != (hp, st, ag, et):
            struct.pack_into(">f", b, o + 0x18C, float(hp))
            struct.pack_into(">f", b, o + 0x180, float(hp))           # current HP = max (as after a rest)
            struct.pack_into(">3H", b, o + 0x198, st, ag, et)
            changes.append((k, "base stats", cur, (hp, st, ag, et)))
        rows = struct.unpack_from(">6H", b, o + 0xE)
        for s in range(5):
            want = armour_cache(eq.get(rows[s]) if rows[s] else None)
            if bytes(b[o + 0x28 + 0x20 * s:o + 0x48 + 0x20 * s]) != want:
                changes.append((k, f"armour cache {s}", b[o + 0x28 + 0x20 * s:o + 0x48 + 0x20 * s].hex(), want.hex()))
                b[o + 0x28 + 0x20 * s:o + 0x48 + 0x20 * s] = want
        want = weapon_cache(wp.get(rows[5]) if rows[5] else None, lv)
        if bytes(b[o + 0xC8:o + 0xE8]) != want:
            changes.append((k, "weapon cache", b[o + 0xC8:o + 0xE8].hex(), want.hex()))
            b[o + 0xC8:o + 0xE8] = want
    return bytes(b), changes
