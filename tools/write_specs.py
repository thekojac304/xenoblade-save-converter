"""Write the Phase 2C machine-readable layout specs to specs/ (wii_layout.json, de_v10_layout.json, wii_to_de_rules.json).

Field lists are taken from the decoder modules so the specs and the code cannot drift apart.

  python write_specs.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import de_save  # noqa: E402
import wii_save  # noqa: E402

OUT = os.path.join(HERE, "..", "specs")

CHAR_EVIDENCE = {
    "id": "C 0x8023E4AC", "equip_gid": "C copy; D 36/36 refs resolve", "equip_row": "C copy; D = ITM_itemlist.itemID",
    "equip_box_index": "C copy; D 36/36 refs resolve (0xFFFF = none)", "armour_stat_cache": "D (arm_phy/arm_eth per slot) derived",
    "weapon_stat_cache": "D derived", "art_levels": "C 0x800A2000 (art byte at +0xE8+2*pc_arts.idx); D get_lv 118/118",
    "palette": "C 0x800A2060 (+0x119)", "palette_monado": "C (+0x121)", "talent_arts": "C stb 0x41(r23) (+0x129)",
    "level": "C 0x8023E544 rt+0x17CC", "runtime_stats": "C 0x8023E544..0x8023E670 (HP/stat floats, rebuilt on load)",
    "skill_rows": "C 0x80260D58/0x80260E30 (11 rows x 13 B); learn routine 0x800A34C8",
    "affinity_coins": "C clamp 0..999 at 0x802639C8; link-cost display 0x80268AB0",
    "skill_sp": "C serializer +0x94 (rt skill+0x888 = char+0x3DBC); learn routine compares point_PP*100",
    "skill_selected_tree": "C rt skill+0x89C (= char+0x3DD0)", "exp_accum": "C rt+0x177C; D = cumulative level cost for Shulk/Reyn",
    "exp": "C rt+0x1780; D < next level cost (7/7)", "ap": "C rt+0x1784",
}


def wii_spec():
    return {
        "game": "Xenoblade (Wii) SX4E01", "endianness": "big", "file_size": 0x28000,
        "sections": [{"tag": t, "header": h, "crc_start": s, "crc_end": e} for t, h, s, e in wii_save.SECTIONS],
        "crc": "CRC-16/ARC (poly 0xA001 reflected, init 0) at section header +0xE",
        "game_section": {"base": wii_save.GAME, "game_object_bytes": 0x41F0, "party": {"offset": wii_save.PARTY, "stride": 4, "type": "u16"},
                         "map": {"offset": wii_save.GAME, "type": "u32 (sub<<16)|area"},
                         "serializer": "0x8023E414", "loader": "0x8023F5B8"},
        "character_record": {"base": wii_save.CHAR_BASE, "size": wii_save.CHAR_SIZE, "count": wii_save.N_CHARS,
                             "index": "character ID (0 unused)", "names": wii_save.CHAR_NAMES,
                             "fields": [{"offset": o, "size": n, "name": nm, "class": k, "evidence": CHAR_EVIDENCE.get(nm, "")}
                                        for o, n, nm, k in wii_save.CHAR_FIELDS],
                             "equip_slot_order": wii_save.EQUIP_SLOTS,
                             "skill_rows": {"rows_0_4": "skill trees t: 6 entries; entry0 (b0,b1) header, entries 1-5 = nodes "
                                                        "(u8 learned BTL_PSVskill id or 0, u8 state)",
                                            "rows_5_10": "skill-link rows, source = other main characters 1..7 (excluding self) in ID "
                                                         "order; node = (u8 linked skill id or 0, u8 1 = slot unlocked)",
                                            "after_rows": {"0x284": "u32 affinity coins", "0x288": "u32[5] SP", "0x29C": "u32 selected tree"}},
                             "art_levels": "24 x (u8 level, u8 manual flags) indexed by pc_arts.idx of this character"},
        "time": {"offset": 0x11EB0, "encoding": "u32 hours<<12 | minutes<<6 | seconds", "evidence": "C 0x8023E98C (THUM)"},
        "item_section": {
            "base": wii_save.ITEM, "object_size": 0x12120, "object": "memcpy of item object (r13-0x56C8) at 0x8023EC2C",
            "box_getter": "0x80158490(type) -> base, count, record size",
            "boxes": [{"name": n, "type": t, "object_offset": o, "file_offset": wii_save.ITEM + o, "record_size": s, "slots": c}
                      for n, t, o, s, c in wii_save.BOXES],
            "equipment_slots": "0..149 inventory (visible count 60 + 10 per joined character + bonus <= 30); 150+charId = "
                               "per-character staging record (0x80158308)",
            "record_header": {"bytes": 8, "word0": "gid:12 | type:4 | row:11 | low5:5", "+4": "u16 acquisition serial (kept on re-init)",
                              "+6": "u8 quantity (stack cap 99, 0x801588D8)", "+7": "u8 flags", "init": "0x80158BE4"},
            "equipment_record": {"bytes": 0x34, "+8": "4 x 8-byte gem descriptor (socket contents)",
                                 "+0x28": "4 x u16 gem-box index of a socketed gem (0xFFFF = built-in/fixed or empty)",
                                 "+0x30": "u8 socket count (ITM_*.jwl_slot, 0x80156554)", "+0x31": "u8 kind 1-5 armour part, 6 weapon",
                                 "+0x32": "u16"},
            "gem_record": {"bytes": 0x10, "+0": "header (row = effect; gid 3747 = crafted placeholder)", "+8": "gem descriptor"},
            "gem_descriptor": {"bytes": 8, "word0": "gid-2048:11 | strength:11 | rank:3 (1=E..6=S) | chance:7",
                               "half4": "effect (BTL_skilllist):12 | category:3 | flag:1", "half6": "u16 (0)", "packer": "0x80156380"},
            "crystal_record": {"bytes": 0x1C, "+0": "header (identity encoding unresolved)", "+8": "20-byte payload (raw)"},
            "stack_record": {"bytes": 8, "layout": "header only"},
            "tail": {"0x11AB8": "88 x 16 per-character type-3 records", "0x12038": "u16[88]", "0x120E8": "u32 money (cap 999,999,999)",
                     "0x120EC": "u16[14]", "0x12108": "u32 per-character new-item mask", "0x1210C": "u32 weapon new mask",
                     "0x12110": "u32 capacity bonus (cap 30)", "0x12114": "u16[5] armour new masks"},
        },
    }


def de_spec():
    return {
        "game": "Xenoblade Chronicles DE 2.0.0 (Monado), save format v10", "endianness": "little", "file_size": de_save.V10,
        "v7_relation": "identical below 0x151B44; party/character/art block at v7 + 0x3C0; 0x310 bytes appended",
        "header": {"0x00": "u32 version", "0x04": "u32 play time seconds"}, "money": de_save.MONEY,
        "party": {"offset": 0x1526D8, "type": "u16[12]", "count": "u32 @0x1526F0"},
        "character_record": {"base": 0x152728, "size": 0x138, "count": 16, "index": "character ID - 1", "fields": [
            {"offset": 0x00, "name": "level", "type": "u32"}, {"offset": 0x04, "name": "exp", "type": "u32"},
            {"offset": 0x08, "name": "ap", "type": "u32"}, {"offset": 0x0C, "name": "affinity_coins", "type": "u32 (<=999)"},
            {"offset": 0x10, "name": "unknown_10", "type": "4 B"},
            {"offset": 0x14, "name": "equipment", "type": "6 x (u16 box index, u16 item type), order head body arm legs feet weapon"},
            {"offset": 0x2C, "name": "unknown_2c", "type": "4 B"}, {"offset": 0x30, "name": "cosmetic", "type": "u32[6]"},
            {"offset": 0x48, "name": "palette", "type": "u16[9] (talent + 8)"}, {"offset": 0x5A, "name": "palette2", "type": "u16[9]"},
            {"offset": 0x6C, "name": "unknown_6c", "type": "12 B"}, {"offset": 0x78, "name": "skill_selected_tree", "type": "u32"},
            {"offset": 0x7C, "name": "skill_sp", "type": "u32[5]"}, {"offset": 0x90, "name": "skill_learned", "type": "u32[5]"},
            {"offset": 0xA4, "name": "link_unlock_index", "type": "u32[8] by source id"},
            {"offset": 0xC4, "name": "links", "type": "u8[8][5] skill ids by source id"},
            {"offset": 0xEC, "name": "highest_level", "type": "u32"}, {"offset": 0xF0, "name": "highest_level_exp", "type": "u32"},
            {"offset": 0xF4, "name": "reserve_exp", "type": "u32"}, {"offset": 0xF8, "name": "unknown_f8", "type": "0x40 B"}]},
        "arts": {"offset": 0x153AA8, "count": 188, "record": "u8 level, u8 manual flags (1/3/7 -> caps 7/10/12)", "index": "art id - 1"},
        "boxes": [{"name": n, "type": t, "offset": o, "record_size": s, "slots": c} for n, t, o, s, c in de_save.BOXES],
        "stack_record": {"0x00": "u16 index", "0x02": "u16 type", "0x04": "u16 global item id", "0x06": "u16 type",
                         "0x08": "u16 qty", "0x0A": "u16 unknown (template value, do not invent)", "0x0C": "u32 serial",
                         "0x10": "u8 present", "0x11": "u8 favorite"},
        "equipment_record": {"header": "as stack", "0x14": "u8 armour class", "0x15": "u8 socket count",
                             "0x18/0x20/0x28": "u32 normal gem ref (u16 gem index, u16 type 3)",
                             "0x1C/0x24/0x2C": "u32 fixed gem (u16 global item id, u16 presence)"},
        "gem_record": {"header": "as stack (gid 0 for crafted)", "0x16": "u8 rank 1-6", "0x17": "u8 attribute (atr_type)",
                       "0x19": "u8 cylinder flag", "0x1A": "u16 1", "0x1C": "u16 effect", "0x1E": "u8 strength", "0x1F": "u8 chance"},
        "serial_counters": "u32[type] @0x46900", "collectopaedia": "bit (0x19E9+id) from 0x148D6C (hashcade, v7=v10 region)",
        "sources": "hashcade/xbde-save-editor docs + hanyu1774 PartyMember.cs; re-verified on user v10 and public v7 saves",
    }


def rules():
    return {
        "ids": {"items": "identity for global IDs 1-3765 (all Wii items exist in DE with identical type/row; DE adds 3766-4657)",
                "arts": "identity 1-152", "skills": "identity 1-200 (BTL_PSVskill)", "skill_link_shapes": "identity (MNU_PSset 64/64)",
                "gem_effects": "identity 1-97 (BTL_skilllist)", "crystals": "ITM_crystallist identical (600/600); save identity encoding unresolved"},
        "character": {"level": "copy", "exp": "copy (Wii +0x2A4)", "ap": "copy (Wii +0x2A8)", "affinity_coins": "copy (Wii +0x284)",
                      "highest_level": "= level", "highest_level_exp": "keep template (0 on a template whose level is rewritten)",
                      "reserve_exp": "keep template", "exp_accum (Wii +0x2A0)": "no DE target identified; not written",
                      "equipment": "(index, type) = (Wii box index, box type); inventory slot allocation is identity",
                      "skill_selected_tree": "copy", "skill_sp": "copy", "skill_learned": "count of non-zero nodes in Wii rows 0-4",
                      "links": "Wii row 5+j -> DE source id = j-th other character; node value copied",
                      "link_unlock_index": "(unlocked slots - 1); DE also re-derives from affinity at 0xBC240 (monotonic)",
                      "arts": "DE art[id-1] = Wii art_levels[pc_arts.idx] for pc_arts.pc == character", "palette": "[talent] + Wii palette",
                      "palette2": "Shulk: [talent] + Wii Monado palette; others: keep template",
                      "stats/HP/caches": "derived; not written (DE recomputes on load)", "cosmetic": "keep template (0)",
                      "characters 8-16": "keep template"},
        "inventory": {"slot": "Wii index", "serial": "Wii serial; DE counter @0x46900+4*type = max(template, max serial + 1)",
                      "qty": "copy", "favorite": "0 (Wii has none)", "unknown_0a": "template value",
                      "gem": {"gid": "0 if Wii gid 3747 else Wii gid", "rank/effect/strength/chance": "copy",
                              "attribute": "BTL_skilllist.atr_type"},
                      "sockets": {"normal": "Wii gem_box_ref -> DE normal ref (index, 3)", "fixed": "Wii descriptor gid -> DE fixed (gid, 1)"},
                      "staging slots 150-162": "not converted", "crystals": "unresolved"},
        "progress": {"money": "copy", "play_time": "Wii packed time -> seconds at DE header +0x04",
                     "map": "Wii GAME+0 u32 -> DE 0x149C00", "position": "Wii PCPM slot 0 xyz -> DE 0x149C10",
                     "angle": "radians(Wii degrees) -> DE 0x149C20", "location_word_0x149C04": "template; DE recomputes"},
        "phase2d": {
            "crystal": {"wii": "flags = atr_type<<2 | kind (1 list, 2 drop, 3 crafting cylinder); rank = (w0>>2)&7; "
                                "effects u16[4]@+8 (>>4); values u8[4]@+0x12; +0x18 = cylinder<<15 | source enemy",
                        "de": "gid (list: Wii gid; else 0), +0x14 source, +0x16 rank, +0x17 atr, +0x18 named (drop: 2 if "
                              "DE BTL_enelist*.named else 1; others 1), +0x19 cylinder, +0x1A count, +0x1C+4i (u16 effect, "
                              "u8 value, u8 0)", "evidence": "Wii vtable 0x8052FA48; DE 0xC19D0, 0xBF15C, name 0xC2DBC"},
            "collectopaedia": "Wii game object +0x3866 bit id (0x8009F5F0, id = ITM_collectlist row) -> DE bit 0x19E9+id",
            "highest_level_exp_0xF0": "= current EXP (DE 0xBA9CC adds every battle EXP to both; reset at new highest level)",
            "reserve_exp_0xF4": "template (Expert Mode only, 0xBA9D0)",
            "stack_padding_0x0A": "template slot bytes (no writer in 0x9AB60 / 0xBF350)",
            "achievement_counters": "per tier: comp_value if Wii completion bit, else min(group max, comp_value) "
                                    "(groups = runs of increasing comp_value, comp_type 4)",
            "inventory_box_clear": "template box records replaced by the template's empty-slot pattern before writing Wii records"},
    }


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, obj in (("wii_layout.json", wii_spec()), ("de_v10_layout.json", de_spec()), ("wii_to_de_rules.json", rules())):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)
        print("wrote", name)
