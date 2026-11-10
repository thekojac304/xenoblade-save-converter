"""Read-only reader for XC1 DE saves, format v7 (0x153860) and v10 (0x153F30, game 2.0.0 / Monado), Phase 2C.

Offsets: v7 from hashcade/xbde-save-editor (native-code citations in their docs) and hanyu1774 PartyMember.cs;
v10 = v7 for everything below 0x151B44 and v7 + 0x3C0 for the party/character/art block (Phase 2A anchors),
re-verified here against the user's v10 file. Nothing is written.

  python de_save.py <bfsgameNN.sav>
"""
import json
import struct
import sys

V7, V10 = 0x153860, 0x153F30
BOXES = [  # name, type, offset, record size, slots
    ("weapon", 2, 0x3B10, 0x30, 500), ("head", 4, 0x98D0, 0x30, 500), ("body", 5, 0xF690, 0x30, 500),
    ("arm", 6, 0x15450, 0x30, 500), ("legs", 7, 0x1B210, 0x30, 500), ("feet", 8, 0x20FD0, 0x30, 500),
    ("crystal", 9, 0x26D90, 0x2C, 500), ("gem", 3, 0x2C380, 0x2C, 500), ("collectable", 10, 0x31970, 0x14, 500),
    ("material", 11, 0x34080, 0x14, 500), ("keyitem", 12, 0x36790, 0x14, 500), ("artmanual", 13, 0x38EA0, 0x14, 500)]
SERIALS = 0x46900          # u32 per item type
MONEY = 0x151B40
EQUIP_SLOTS = ["head", "body", "arm", "legs", "feet", "weapon"]   # character +0x14 .. +0x28


def le(fmt, d, o):
    return struct.unpack_from("<" + fmt, d, o)[0]


def layout(d):
    if len(d) == V10:
        return {"version": 10, "party": 0x1526D8, "chars": 0x152728, "arts": 0x153AA8}
    if len(d) == V7:
        return {"version": 7, "party": 0x152318, "chars": 0x152368, "arts": 0x1536E8}
    raise ValueError(f"unknown DE save size 0x{len(d):X}")


def decode_char(d, o):
    return {
        "level": le("I", d, o), "exp": le("I", d, o + 4), "ap": le("I", d, o + 8), "affinity_coins": le("I", d, o + 0xC),
        "equipment": {s: {"index": le("H", d, o + 0x14 + 4 * i), "type": le("H", d, o + 0x16 + 4 * i)}
                      for i, s in enumerate(EQUIP_SLOTS)},
        "cosmetic": list(struct.unpack_from("<6I", d, o + 0x30)),
        "palette": list(struct.unpack_from("<9H", d, o + 0x48)), "palette2": list(struct.unpack_from("<9H", d, o + 0x5A)),
        "skill_selected_tree": le("I", d, o + 0x78), "skill_sp": list(struct.unpack_from("<5I", d, o + 0x7C)),
        "skill_learned": list(struct.unpack_from("<5I", d, o + 0x90)),
        "link_unlock_index": list(struct.unpack_from("<8I", d, o + 0xA4)),
        "links": [list(d[o + 0xC4 + 5 * s:o + 0xC9 + 5 * s]) for s in range(8)],
        "highest_level": le("I", d, o + 0xEC), "highest_level_exp": le("I", d, o + 0xF0), "reserve_exp": le("I", d, o + 0xF4),
        "raw": {"u10": d[o + 0x10:o + 0x14].hex(), "u2c": d[o + 0x2C:o + 0x30].hex(), "u6c": d[o + 0x6C:o + 0x78].hex(),
                "uec": d[o + 0xEC + 12:o + 0x138].hex()},
    }


def decode_box(d, name, typ, off, size, n):
    out = []
    for i in range(n):
        o = off + size * i
        if d[o + 0x10] == 0:
            continue
        r = {"slot": i, "index": le("H", d, o), "type": le("H", d, o + 2), "gid": le("H", d, o + 4),
             "gid_type": le("H", d, o + 6), "qty": le("H", d, o + 8), "u0a": le("H", d, o + 0xA),
             "serial": le("I", d, o + 0xC), "present": d[o + 0x10], "favorite": d[o + 0x11]}
        if size == 0x30:
            r.update(armour_class=d[o + 0x14], socket_count=d[o + 0x15],
                     sockets=[{"normal": le("I", d, o + 0x18 + 8 * s), "fixed": le("I", d, o + 0x1C + 8 * s)}
                              for s in range(3)])
        elif typ == 3:
            r.update(rank=d[o + 0x16], attribute=d[o + 0x17], effect=le("H", d, o + 0x1C),
                     strength=d[o + 0x1E], chance=d[o + 0x1F], cylinder=d[o + 0x19])
        out.append(r)
    return out


def decode(path):
    with open(path, "rb") as f:
        return decode_bytes(f.read(), path)


def decode_bytes(d, path="<bytes>"):
    L = layout(d)
    party_n = le("I", d, L["party"] + 0x18) if L["version"] == 10 else d[L["party"] + 0x18]
    return {
        "source": path, "version": le("I", d, 0), "layout": L, "play_time_s": le("I", d, 4),
        "story": le("H", d, 0xDF0), "money": le("I", d, MONEY),
        "party": [le("H", d, L["party"] + 2 * i) for i in range(12)][:party_n],
        "characters": {cid: decode_char(d, L["chars"] + 0x138 * (cid - 1)) for cid in range(1, 17)},
        "arts": [[d[L["arts"] + 2 * i], d[L["arts"] + 2 * i + 1]] for i in range(188)],
        "boxes": {n: decode_box(d, n, t, o, s, c) for n, t, o, s, c in BOXES},
        "serial_counters": [le("I", d, SERIALS + 4 * t) for t in range(14)],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ir = decode(sys.argv[1])
    print(json.dumps({k: (v if k != "boxes" else {b: len(x) for b, x in v.items()}) for k, v in ir.items()
                      if k not in ("characters", "arts")}, indent=1))
