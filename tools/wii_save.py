"""Read-only decoder for the XC1 Wii (SX4E) save: container, character records and the ITEM section (Phase 2C).

Every layout constant below is backed by a routine in main.dol (SX4E01); see specs/wii_layout.json for the
citations. The decoder never writes a file. decode() returns a plain-dict intermediate representation (IR) in
which every byte of the character records and of the ITEM section is either a named field or listed under
"raw" (unknown/derived spans, hex), so nothing is silently dropped. encode_*() re-serialise the IR for the
round-trip tests.

  python wii_save.py <monadoNN> [out.json]
"""
import json
import struct
import sys

# ---- container (THUM … OPTD), CRC-16/ARC per section, header at tag+0, CRC at tag+0xE ----
SECTIONS = [("THUM", 0x10, 0x20, 0x9CA0), ("FLAG", 0xA020, 0xA030, 0xB244), ("GAME", 0xB250, 0xB260, 0x11E88),
            ("TIME", 0x11EA0, 0x11EB0, 0x11EBC), ("PCPM", 0x11ED0, 0x11EE0, 0x11F14), ("CAMD", 0x11F20, 0x11F30, 0x11F40),
            ("ITEM", 0x11F50, 0x11F60, 0x24080), ("WTHR", 0x24080, 0x24090, 0x240A0), ("SNDS", 0x240B0, 0x240C0, 0x240D0),
            ("MINE", 0x240E0, 0x240F0, 0x24474), ("TBOX", 0x24490, 0x244A0, 0x246D4), ("OPTD", 0x248A0, 0x248B0, 0x248F0)]

# ---- GAME (serializer 0x8023E414 / loader 0x8023F5B8) ----
GAME = 0xB260                    # memcpy 0x41F0 bytes of the game-state object, then 14 character records
CHAR_BASE, CHAR_SIZE, N_CHARS = GAME + 0x41F0, 0x304, 14   # record k = character ID k (0 unused)
PARTY = 0xD1FE                   # u16 per member, stride 4 (game object +0x1F9E)
CHAR_NAMES = {1: "Shulk", 2: "Reyn", 3: "Fiora", 4: "Dunban", 5: "Sharla", 6: "Riki", 7: "Melia", 8: "Fiora (Mechon)",
              9: "Dickson", 10: "Mumkhar", 11: "Alvis", 12: "Dunban (prologue)", 13: "Dunban (alt)"}
EQUIP_SLOTS = ["head", "body", "arm", "legs", "feet", "weapon"]

# ---- ITEM (memcpy of the 0x12120-byte item object at r13-0x56C8; box getter 0x80158490) ----
ITEM = 0x11F60
BOXES = [  # name, item type, object offset, record size, slots (inventory), capacity source
    ("head", 4, 0x0000, 0x34, 163), ("body", 5, 0x211C, 0x34, 163), ("arm", 6, 0x4238, 0x34, 163),
    ("legs", 7, 0x6354, 0x34, 163), ("feet", 8, 0x8470, 0x34, 163), ("weapon", 2, 0xA58C, 0x34, 163),
    ("crystal", 9, 0xC6A8, 0x1C, 300), ("gem", 3, 0xE778, 0x10, 300), ("artmanual", 13, 0xFA38, 0x08, 240),
    ("collectable", 10, 0x101B8, 0x08, 300), ("material", 11, 0x10B18, 0x08, 300), ("keyitem", 12, 0x11478, 0x08, 200)]
EQUIP_INVENTORY_SLOTS = 150      # 0x80158308: slot 150+charId (1..11) is the per-character staging record
ITEM_TAIL = 0x11AB8              # 88 x 16-byte records (0x80158308 type 3), u16[88] @0x12038, money @0x120E8 …


def be(fmt, d, o):
    return struct.unpack_from(">" + fmt, d, o)[0]


def crc16_arc(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def load(path):
    with open(path, "rb") as f:
        d = f.read()
    if d[:4] != b"USRD":
        raise ValueError("not a Wii XC1 save")
    return d


def check_crcs(d):
    return {tag: be("H", d, hdr + 0xE) == crc16_arc(d[s:e]) for tag, hdr, s, e in SECTIONS}


# fixed container headers (identical in every real save: magic/size/header-size words; section tag, section size =
# distance to the next header, header size 0x10, zero halfword; the CRC follows at +0xE)
FILE_HEADER = struct.pack(">4sIII", b"USRD", 0x248F0, 0x10, 0x70002)
SECTION_SIZES = {"THUM": 0xA010, "FLAG": 0x1230, "GAME": 0x6C50, "TIME": 0x30, "PCPM": 0x50, "CAMD": 0x30,
                 "ITEM": 0x12130, "WTHR": 0x30, "SNDS": 0x30, "MINE": 0x3B0, "TBOX": 0x410, "OPTD": 0x50}


def check_container(d):
    """Container problems (Phase 2F): file size, file header, every section header (tag/size), every CRC."""
    if len(d) != 0x28000:
        return [f"file size {len(d)} (expected {0x28000})"]
    bad = [] if d[:16] == FILE_HEADER else ["file header"]
    for tag, hdr, s, e in SECTIONS:
        if d[hdr:hdr + 0xE] != struct.pack(">4sIIH", tag.encode(), SECTION_SIZES[tag], 0x10, 0):
            bad.append(f"section header {tag}")
    bad += [f"section {t} checksum" for t, ok in check_crcs(d).items() if not ok]
    return bad


# ---- shared item-record pieces ----
def item_header(b):
    """8-byte header written by 0x80158BE4: word0 = gid<<20 | type<<16 | row<<5 | low5; u16 serial; u8 qty; u8 flags."""
    w0 = be("I", b, 0)
    return {"gid": w0 >> 20, "type": w0 >> 16 & 15, "row": w0 >> 5 & 0x7FF, "low5": w0 & 31,
            "serial": be("H", b, 4), "qty": b[6], "flags": b[7]}


def enc_header(h):
    w0 = h["gid"] << 20 | h["type"] << 16 | h["row"] << 5 | h["low5"]
    return struct.pack(">IHBB", w0, h["serial"], h["qty"], h["flags"])


def gem_desc(b):
    """8-byte gem descriptor (packer 0x80156380): [gid-2048:11][strength:11][rank:3][chance:7] [effect:12][cat:3][f:1] u16."""
    w0, hw, tail = struct.unpack_from(">IHH", b)
    return {"gid": (w0 >> 21) + 2048 if w0 >> 21 else 0, "strength": w0 >> 10 & 0x7FF, "rank": w0 >> 7 & 7,
            "chance": w0 & 0x7F, "effect": hw >> 4, "category": hw >> 1 & 7, "flag": hw & 1, "tail": tail}


def enc_gem_desc(g):
    w0 = ((g["gid"] - 2048) & 0x7FF if g["gid"] else 0) << 21 | g["strength"] << 10 | g["rank"] << 7 | g["chance"]
    return struct.pack(">IHH", w0, g["effect"] << 4 | g["category"] << 1 | g["flag"], g["tail"])


CRYSTAL_KINDS = {1: "list", 2: "drop", 3: "cylinder"}  # header flags & 3


def crystal_fields(b):
    """Crystal record (0x1C). Type-9 handler vtables 0x8052FA48 / 0x8052F8D8 (flags&3 == 3) give:
    rank = (word0 >> 2) & 7 (setter 0x8015678C); effect slot i = u16 at +8+2i, effect = >>4 (0x8015C6A0);
    value i = u8 at +0x12+i (0x8015C610); +0x16 u8 (getter 0x801573F8); source = u16 +0x18 & 0x7FFF, bit 15 =
    cylinder (0x8015C5DC / 0x8015C5B0); +0x10 u16 (0x8015C5A8, = source % 100). Header flags = atr_type<<2 | kind.
    Header gid: list = global crystal item; drop = ITM_dropcrystallist row; cylinder = BTL_skilllist effect."""
    w0 = be("I", b, 0)
    src = be("H", b, 0x18)
    slots = [be("H", b, 8 + 2 * i) for i in range(4)]
    return {"kind": CRYSTAL_KINDS.get(b[7] & 3, "unknown"), "atr_type": b[7] >> 2, "rank": w0 >> 2 & 7,
            "effects": [s >> 4 for s in slots], "effect_low4": [s & 15 for s in slots], "values": list(b[0x12:0x16]),
            "source": src & 0x7FFF, "cylinder": src >> 15, "u10": be("H", b, 0x10), "u16": b[0x16], "u17": b[0x17],
            "u1a": be("H", b, 0x1A)}


def decode_equipment(b):
    sockets = []
    for s in range(4):
        x = b[8 + 8 * s:16 + 8 * s]
        ref = be("H", b, 0x28 + 2 * s)
        sockets.append({"desc": gem_desc(x) if any(x) else None, "gem_box_ref": None if ref == 0xFFFF else ref,
                        "raw": x.hex()})
    return {"header": item_header(b), "sockets": sockets, "slot_count": b[0x30], "kind": b[0x31],
            "tail": be("H", b, 0x32)}


def encode_equipment(e):
    out = bytearray(enc_header(e["header"]))
    for s in e["sockets"]:
        out += bytes.fromhex(s["raw"])
    for s in e["sockets"]:
        out += struct.pack(">H", 0xFFFF if s["gem_box_ref"] is None else s["gem_box_ref"])
    out += struct.pack(">BBH", e["slot_count"], e["kind"], e["tail"])
    return bytes(out)


def decode_record(kind, b):
    if not any(b):
        return None
    if kind in ("head", "body", "arm", "legs", "feet", "weapon"):
        return decode_equipment(b)
    if kind == "gem":
        return {"header": item_header(b), "desc": gem_desc(b[8:16]), "raw8": b[8:16].hex()}
    if kind == "crystal":
        return {"header": item_header(b), "crystal": crystal_fields(b), "payload_raw": b[8:].hex()}
    return {"header": item_header(b)}


def encode_record(kind, r, size):
    if r is None:
        return bytes(size)
    if kind in ("head", "body", "arm", "legs", "feet", "weapon"):
        return encode_equipment(r)
    if kind == "gem":
        return enc_header(r["header"]) + bytes.fromhex(r["raw8"])
    if kind == "crystal":
        return enc_header(r["header"]) + bytes.fromhex(r["payload_raw"])
    return enc_header(r["header"])


# ---- character record (0x304) ----
CHAR_FIELDS = [  # (offset, size, name, kind) – kind: field | derived | unknown
    (0x000, 2, "id", "field"), (0x002, 12, "equip_gid", "field"), (0x00E, 12, "equip_row", "field"),
    (0x01A, 2, "pad_1a", "unknown"), (0x01C, 12, "equip_box_index", "field"), (0x028, 0xA0, "armour_stat_cache", "derived"),
    (0x0C8, 0x20, "weapon_stat_cache", "derived"), (0x0E8, 0x30, "art_levels", "field"), (0x118, 1, "palette_flag", "unknown"),
    (0x119, 8, "palette", "field"), (0x121, 8, "palette_monado", "field"), (0x129, 7, "talent_arts", "field"),
    (0x130, 0x48, "unk_130", "unknown"), (0x178, 2, "unk_178", "unknown"), (0x17A, 2, "pad_17a", "unknown"),
    (0x17C, 4, "level", "field"), (0x180, 0x74, "runtime_stats", "derived"), (0x1F4, 0x8F, "skill_rows", "field"),
    (0x283, 1, "pad_283", "unknown"), (0x284, 4, "affinity_coins", "field"), (0x288, 20, "skill_sp", "field"),
    (0x29C, 4, "skill_selected_tree", "field"), (0x2A0, 4, "exp_accum", "field"), (0x2A4, 4, "exp", "field"),
    (0x2A8, 4, "ap", "field"), (0x2AC, 0x14, "unk_2ac", "unknown"), (0x2C0, 1, "flag_2c0", "unknown"),
    (0x2C1, 0x43, "zero_tail", "unknown")]


def decode_char(d, k):
    b = d[CHAR_BASE + CHAR_SIZE * k:CHAR_BASE + CHAR_SIZE * (k + 1)]
    gids = struct.unpack_from(">6H", b, 0x02)
    rows = struct.unpack_from(">6H", b, 0x0E)
    idx = struct.unpack_from(">6H", b, 0x1C)
    rows_sk = []
    for j in range(11):  # 0x80260D58: 11 rows x 13 bytes; rows 0-4 skill trees, rows 5-10 skill-link rows
        r = b[0x1F4 + 13 * j:0x1F4 + 13 * j + 13]
        rows_sk.append({"e0": [r[0], r[1]], "nodes": [[r[2 + 2 * e], r[3 + 2 * e]] for e in range(5)], "b12": r[12]})
    rec = {
        "id": be("H", b, 0), "name": CHAR_NAMES.get(k, f"#{k}"),
        "equipment": {s: {"gid": gids[i], "row": rows[i], "box_index": None if idx[i] == 0xFFFF else idx[i]}
                      for i, s in enumerate(EQUIP_SLOTS)},
        "level": be("I", b, 0x17C),
        "exp": be("I", b, 0x2A4), "exp_accum": be("I", b, 0x2A0), "ap": be("I", b, 0x2A8),
        "affinity_coins": be("I", b, 0x284),
        "skill_sp": list(struct.unpack_from(">5I", b, 0x288)), "skill_selected_tree": be("I", b, 0x29C),
        "skill_rows": rows_sk,
        "art_levels": [[b[0xE8 + 2 * i], b[0xE9 + 2 * i]] for i in range(24)],
        "palette": list(b[0x119:0x121]), "palette_monado": list(b[0x121:0x129]), "talent_arts": list(b[0x129:0x130]),
        "hp_max": be("f", b, 0x180), "stats_str_agi_eth": list(struct.unpack_from(">3h", b, 0x198)),
        "raw": {name: b[o:o + n].hex() for o, n, name, kind in CHAR_FIELDS if kind != "field"},
    }
    return rec


def encode_char(rec, original):
    """Rebuild a record from IR fields + raw spans (for round-trip tests)."""
    b = bytearray(original)
    struct.pack_into(">H", b, 0, rec["id"])
    eq = rec["equipment"]
    struct.pack_into(">6H", b, 0x02, *[eq[s]["gid"] for s in EQUIP_SLOTS])
    struct.pack_into(">6H", b, 0x0E, *[eq[s]["row"] for s in EQUIP_SLOTS])
    struct.pack_into(">6H", b, 0x1C, *[0xFFFF if eq[s]["box_index"] is None else eq[s]["box_index"] for s in EQUIP_SLOTS])
    struct.pack_into(">I", b, 0x17C, rec["level"])
    struct.pack_into(">III", b, 0x2A0, rec["exp_accum"], rec["exp"], rec["ap"])
    struct.pack_into(">I", b, 0x284, rec["affinity_coins"])
    struct.pack_into(">5I", b, 0x288, *rec["skill_sp"])
    struct.pack_into(">I", b, 0x29C, rec["skill_selected_tree"])
    for j, r in enumerate(rec["skill_rows"]):
        o = 0x1F4 + 13 * j
        b[o:o + 2] = bytes(r["e0"])
        for e, (v, s) in enumerate(r["nodes"]):
            b[o + 2 + 2 * e], b[o + 3 + 2 * e] = v, s
        b[o + 12] = r["b12"]
    for i, (lv, fl) in enumerate(rec["art_levels"]):
        b[0xE8 + 2 * i], b[0xE9 + 2 * i] = lv, fl
    b[0x119:0x121], b[0x121:0x129], b[0x129:0x130] = bytes(rec["palette"]), bytes(rec["palette_monado"]), bytes(rec["talent_arts"])
    for o, n, name, kind in CHAR_FIELDS:
        if kind != "field":
            b[o:o + n] = bytes.fromhex(rec["raw"][name])
    return bytes(b)


def decode_items(d):
    out = {}
    for name, typ, off, size, n in BOXES:
        recs = []
        for i in range(n):
            o = ITEM + off + size * i
            r = decode_record(name, d[o:o + size])
            if r is not None:
                r["index"] = i
                if size == 0x34:
                    r["area"] = "inventory" if i < EQUIP_INVENTORY_SLOTS else f"staging_char{i - EQUIP_INVENTORY_SLOTS}"
                recs.append(r)
        out[name] = recs
    tail = d[ITEM + ITEM_TAIL:ITEM + 0x12120]
    out["tail"] = {
        "char_gem_records_raw": tail[:0x580].hex(),       # 0x11AB8: [11][8] x 16 (0x80158308 type 3)
        "u16x88": list(struct.unpack_from(">88H", tail, 0x580)),
        "money": be("I", d, ITEM + 0x120E8),             # clamp 999,999,999 at 0x80157C50
        "u16x14_120ec": list(struct.unpack_from(">14H", d, ITEM + 0x120EC)),
        "new_mask_chars_12108": be("I", d, ITEM + 0x12108), "new_mask_weapon_1210c": be("I", d, ITEM + 0x1210C),
        "capacity_bonus_12110": be("I", d, ITEM + 0x12110),   # +60 base, capped 30 (0x80158438)
        "new_mask_armour_12114": list(struct.unpack_from(">5H", d, ITEM + 0x12114)),
        "pad_1211e": d[ITEM + 0x1211E:ITEM + 0x12120].hex(),
    }
    return out


def decode(path):
    return decode_bytes(load(path), path)


def decode_bytes(d, source="<bytes>"):
    if d[:4] != b"USRD":
        raise ValueError("not a Wii XC1 save")
    path = source
    party = [be("H", d, PARTY + 4 * i) for i in range(12)]
    return {
        "source": path, "crc_ok": check_crcs(d),
        "scenario": be("H", d, 0xA0B2), "map": be("I", d, GAME), "play_time_s": be("I", d, 0x11EB0),
        "party": [p for p in party if p],
        "characters": [decode_char(d, k) for k in range(N_CHARS)],
        "items": decode_items(d),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ir = decode(sys.argv[1])
    if len(sys.argv) > 2:
        json.dump(ir, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
    else:
        print(json.dumps({k: v for k, v in ir.items() if k not in ("characters", "items")}, indent=1))
