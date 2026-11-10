"""Canonical XC1 game state ("xc1-canon/1"), read from either a Wii (SX4E) or a DE (v7/v10) save (read-only).

The canonical state separates:
  shared   - gameplay state both games hold, in one representation (DE conventions where the encodings differ:
             flag ids in DE numbering, crafted gems gid 0, drop/cylinder crystals gid 0, arts by art id, quest
             counters in DE byte encoding, angle in radians, play time in seconds; item acquisition order as a rank
             within the box, oldest = 1 - Phase 2F, see order_ranks);
  wii_only - Wii fields with no DE counterpart, or Wii raw bytes a lossy mapping cannot rebuild;
  de_only  - DE fields with no Wii counterpart (Expert Mode, cosmetics, Future Connected, DE-only flags, ...);
  derived  - values each game recomputes or keeps in a derived form (compared loosely).
Nothing here writes a file. compare() lists field-level differences; fingerprint() hashes the shared part.

Used by: the DE->Wii converter (de_to_wii.py), the sidecar (sidecar.py) and the round-trip checks.
"""
import hashlib
import json
import math
import struct

import de_save
import flag_transplant_eval as fte
import flagmap as fm
import quest_counters as qc
import wii_save

SCHEMA = "xc1-canon/2"   # /2 (Phase 2F): item "serial" replaced by the acquisition-order rank "order"
EQUIP = ("head", "body", "arm", "legs", "feet", "weapon")
SUPPORTED_PARTY = range(1, 8)   # up to 3C; Phase 3D: era-aware, see main_chars()
# Phase 3D: Fiora is character 3 for scenarios 11..274 and character 8 ("Fiora", later form) from 275 on - the
# affinity-chart table JNL_PCrelatelist says so in both games (pc 3: flg_s2 35..flg_e2 274; pc 8: flg_s1 275..404).
# The other form's record is dormant (8 before 275: initial level 40, staging gear) or frozen (3 from 275).
FIORA_ERA = 275
GUESTS = range(9, 14)            # Dickson, Mumkhar, Alvis, Dunban x2: BTL_pclist guest=1 (prologue/scene characters)
BOX_TYPE = {"head": 4, "body": 5, "arm": 6, "legs": 7, "feet": 8, "weapon": 2, "crystal": 9, "gem": 3,
            "collectable": 10, "material": 11, "keyitem": 12, "artmanual": 13}
CRAFTED_GEM_GID = 3747
ACH_IDS = range(0x40, 0x108)       # 16-bit achievement counters (special rule, see convert.achievement_groups)
MAIN_CHARS = range(1, 8)
DE_COLLECT = 0x148D6C
_IMAGE = None


def shared_flag_map():
    """{DE id: Wii id} for every flag both games hold (Phase 2B rules), excluding achievement counters."""
    global _IMAGE
    if _IMAGE is None:
        _IMAGE = {}
        for width in (32, 16, 8, 1):
            lo, hi = fm.WII_RANGE[width]
            for g in range(lo, hi):
                t = fte.map_wii_to_de(g)
                if t is None or t == "overflow":
                    continue
                if fm.kind(t) == 1 and (t == 0x1E70 or fte.in_ranges(t, fte.DE_ONLY_1BIT)):
                    continue
                if fm.kind(t) == 16 and t in ACH_IDS:
                    continue
                _IMAGE[t] = g
    return _IMAGE


def de_only_flag_ids():
    m = shared_flag_map()
    out = []
    for width in (32, 16, 8, 1):
        lo, hi = fm.DE_RANGE[width]
        out += [g for g in range(lo, hi) if g not in m and not (fm.kind(g) == 16 and (g in ACH_IDS or g == 0x108))]
    return out


def order_ranks(keys):
    """{slot: sort key} -> {slot: rank 1..N}, oldest first; ties broken by slot.

    The two games encode acquisition order in opposite directions (Phase 2F, [C]):
      Wii: header u16 +4 is an AGE. Adding an item ages every record of boxes 2..13 by 1 and gives the new one 0
           (0x80159080..0x80159100); 0x80159488 renumbers a box 1..N by ascending age. Smaller = newer.
      DE : record u32 +0xC is an acquisition number from the per-type counter at 0x46900. Larger = newer.
    The canonical model keeps only the order, so equal canonical state does not depend on the encoding."""
    return {sl: i for i, sl in enumerate(sorted(keys, key=lambda s: (keys[s], s)), 1)}


def rerank(box):
    """Recompute dense ranks for a {slot: record} box after records were removed (relative order kept)."""
    r = order_ranks({sl: rec["order"] for sl, rec in box.items()})
    return {sl: dict(rec, order=r[sl]) for sl, rec in box.items()}


def strip_order(rec):
    return {k: v for k, v in rec.items() if k != "order"}


def item_key(box, rec):
    """Identity of an item that survives acquisition-order changes (used by the descent check)."""
    if box == "gem":
        return (box, rec["gid"], rec["effect"], rec["rank"], rec["strength"])
    if box == "crystal":
        return (box, rec["gid"], rec["rank"], rec["attribute"], tuple(tuple(e) for e in rec["effects"]))
    return (box, rec["gid"])


def fiora(story):
    """The character id that is Fiora at this scenario (3 before FIORA_ERA, 8 from it)."""
    return 8 if story >= FIORA_ERA else 3


def main_chars(story):
    """The seven playable characters at this scenario, in link-row order (Fiora at position 3)."""
    return (1, 2, fiora(story), 4, 5, 6, 7)


def unsupported_party(shared):
    """Party members that cannot exist at this scenario: guests 9-13 (prologue/scene characters, never in a saved party
    in 359 real saves), DE-only 14+, and the inactive Fiora form (8 before scenario 275, 3 from 275)."""
    allowed = set(main_chars(shared.get("story", 0)))
    return [p for p in shared["party"] if p not in allowed]


def wii_achievements(wii, T, arts):
    """Per-award DE counter values implied by the Wii save (exact rules, tools/achievements.py), keyed by DE slot."""
    import achievements
    return {g - 0x40: v for g, v in achievements.wii_to_de(wii, arts, T).items()}


def de_achievements(de, T):
    import achievements
    return {g - 0x40: fm.de_get(de, g) for g in sorted({achievements.de_slot(i) for i, r in achievements.rules(T).items()
                                                        if r["kind"] != "event"} - achievements.HOLD16)}


# ------------------------------------------------------------------------------------------------- Wii side
def from_wii(wii, T, name="<wii>"):
    ir = wii_save.decode_bytes(wii, name)
    flags = {}
    for t, g in shared_flag_map().items():
        v = fm.wii_get(wii, g)
        if v:
            flags[t] = v
    chars = {}
    mc = main_chars(fm.wii_get(wii, 0x20))
    for k in mc:
        c = ir["characters"][k]
        arts = {}
        for a in T["w_arts"].values():
            if a["pc"] == k:
                arts[a["id"]] = list(c["art_levels"][a["idx"]])
        others = [x for x in mc if x != k]   # link rows 5..10: the other six in id order (Fiora's row shared by 3/8)
        links = {src: [n[0] for n in c["skill_rows"][5 + j]["nodes"]] for j, src in enumerate(others)}
        # unlocked link slots (paid with affinity coins): Wii = node state bytes set, DE = index of the last one
        unlock = {src: max(sum(1 for n in c["skill_rows"][5 + j]["nodes"] if n[1]) - 1, 0) for j, src in enumerate(others)}
        chars[k] = {
            "level": c["level"], "exp": c["exp"], "ap": c["ap"], "affinity_coins": c["affinity_coins"],
            "equipment": {s: c["equipment"][s]["box_index"] for s in EQUIP},
            "palette": [c["talent_arts"][0]] + c["palette"],
            "skill_selected_tree": c["skill_selected_tree"], "skill_sp": list(c["skill_sp"]),
            "skill_learned": [sum(1 for n in c["skill_rows"][t]["nodes"] if n[0]) for t in range(5)],
            "links": links, "link_unlock": unlock, "arts": arts,
        }
        if k == 1:
            chars[k]["palette2"] = list(c["palette_monado"])
    inv, ages = {}, {}
    for box, recs in ir["items"].items():
        if box == "tail":
            continue
        out, age = {}, {}
        for r in recs:
            if r.get("area", "inventory") != "inventory":
                continue
            h = r["header"]
            if box in EQUIP:
                socks = []
                for s in r["sockets"]:
                    if s["desc"] is None:
                        socks.append(None)
                    elif s["gem_box_ref"] is None:
                        socks.append(["fixed", s["desc"]["gid"]])
                    else:
                        socks.append(["gem", s["gem_box_ref"]])
                while socks and socks[-1] is None:
                    socks.pop()
                rec = {"gid": h["gid"], "qty": h["qty"], "socket_count": r["slot_count"], "sockets": socks}
            elif box == "gem":
                g = r["desc"]
                rec = {"gid": 0 if h["gid"] == CRAFTED_GEM_GID else h["gid"], "qty": 1,
                       "effect": g["effect"], "rank": g["rank"], "strength": g["strength"], "chance": g["chance"]}
            elif box == "crystal":
                c = r["crystal"]
                rec = {"gid": h["gid"] if c["kind"] == "list" else 0, "qty": 1,
                       "source": c["source"], "rank": c["rank"], "attribute": c["atr_type"], "cylinder": c["cylinder"],
                       "effects": [[e, v] for e, v in zip(c["effects"], c["values"]) if e]}
            else:
                rec = {"gid": h["gid"], "qty": h["qty"]}
            out[r["index"]] = rec
            age[r["index"]] = h["serial"]
        ranks = order_ranks({sl: -a for sl, a in age.items()})   # larger age = older = lower rank
        inv[box] = {sl: dict(rec, order=ranks[sl]) for sl, rec in out.items()}
        ages[box] = age
    x, y, z, ang = struct.unpack_from(">4f", wii, 0x11EE0)
    pt = ir["play_time_s"]
    collect = [cid for cid in range(1, 301) if wii[0xEAC6 + (cid >> 3)] >> (cid & 7) & 1]
    art_table = [(0, 0)] * 188
    for k in chars:
        for aid, lv in chars[k]["arts"].items():
            art_table[aid - 1] = tuple(lv)
    t = struct.unpack_from(">f", wii, 0x11EB4)[0]
    for k in chars:
        if k not in ir["party"]:
            chars[k]["equipment"] = None
    shared = {
        "story": fm.wii_get(wii, 0x20), "flags": flags, "achievements": wii_achievements(wii, T, art_table),
        "clock": {"hour": int(t // 1800) % 24, "minute": int(t // 30) % 60,
                  "day": max(struct.unpack_from(">H", wii, 0x11EB8)[0], 1)},
        "flag_bitmask_0": fm.wii_get(wii, 0x108),
        "money": ir["items"]["tail"]["money"], "play_time_s": (pt >> 12) * 3600 + (pt >> 6 & 63) * 60 + (pt & 63),
        "party": ir["party"], "map": ir["map"], "position": [round(x, 3), round(y, 3), round(z, 3)],
        "angle_rad": round(math.radians(ang), 5), "characters": chars, "inventory": inv, "collectopaedia": collect,
        "quest_counters": {q: list(qc.wii_to_de(wii, q)) for q in range(qc.WII_N)
                           if fm.wii_get(wii, 0x220 + q) not in (254, 255) and any(qc.wii_to_de(wii, q))},
    }
    _stored_gear(shared, "wii", wii, T, ir)
    wii_only = {
        "exp_accum": {k: ir["characters"][k]["exp_accum"] for k in mc},
        "hold16": {g: fm.wii_get(wii, g) for g in fte.HOLD16},
        "high_1bit": [g for g in range(0x352C, 0x36D0) if fm.wii_get(wii, g)],   # no DE slot (see flag_transplant_eval)
        "item_ages": ages,   # raw Wii acquisition ages (the order is in shared)
        "time": {"day_time": struct.unpack_from(">f", wii, 0x11EB4)[0], "day": struct.unpack_from(">H", wii, 0x11EB8)[0],
                 "year": struct.unpack_from(">H", wii, 0x11EBA)[0]},
    }
    return {"schema": SCHEMA, "source": {"game": "wii", "format": "sx4e", "sha256": hashlib.sha256(wii).hexdigest()},
            "shared": shared, "wii_only": wii_only, "de_only": {}, "derived": {}}


# -------------------------------------------------------------------------------------------------- DE side
def de_version(de):
    return 10 if len(de) == de_save.V10 else 7 if len(de) == de_save.V7 else None


def from_de(de, T, name="<de>"):
    d = de_save.decode_bytes(de, name)
    L = d["layout"]
    flags = {}
    for t in shared_flag_map():
        v = fm.de_get(de, t)
        if v:
            flags[t] = v
    chars, de_only_chars = {}, {}
    mc = main_chars(d["story"])
    for k in mc:
        c = d["characters"][k]
        arts = {}
        for a in T["w_arts"].values():
            if a["pc"] == k:
                arts[a["id"]] = list(d["arts"][a["id"] - 1])
        others = [x for x in mc if x != k]     # DE: link slot = source id (slot 8 = Fiora's later form)
        eq = {}
        for s in EQUIP:
            e = c["equipment"][s]
            eq[s] = None if (e["index"], e["type"]) == (0, 0) else e["index"]
        chars[k] = {
            "level": c["level"], "exp": c["exp"], "ap": c["ap"], "affinity_coins": c["affinity_coins"],
            "equipment": eq, "palette": c["palette"], "skill_selected_tree": c["skill_selected_tree"],
            "skill_sp": c["skill_sp"], "skill_learned": c["skill_learned"],
            "links": {src: c["links"][src - 1] for src in others},
            "link_unlock": {src: c["link_unlock_index"][src - 1] for src in others}, "arts": arts,
        }
        if k == 1:
            chars[k]["palette2"] = c["palette2"][1:]
        de_only_chars[k] = {"palette2_slot0": c["palette2"][0], "cosmetic": c["cosmetic"], "highest_level": c["highest_level"],
                            "highest_level_exp": c["highest_level_exp"], "reserve_exp": c["reserve_exp"],
                            "link_unlock_index": c["link_unlock_index"], "raw": c["raw"]}
    inv, de_only_items, serials = {}, {}, {}
    for box, recs in d["boxes"].items():
        out, ser = {}, {}
        for r in recs:
            if box in EQUIP:
                socks = []
                for s in r["sockets"]:
                    if s["fixed"] >> 16 == 1:
                        socks.append(["fixed", s["fixed"] & 0xFFFF])
                    elif s["normal"] >> 16 == 3:
                        socks.append(["gem", s["normal"] & 0xFFFF])
                    else:
                        socks.append(None)
                while socks and socks[-1] is None:
                    socks.pop()
                rec = {"gid": r["gid"], "qty": r["qty"], "socket_count": r["socket_count"], "sockets": socks}
            elif box == "gem":
                rec = {"gid": r["gid"], "qty": 1, "effect": r["effect"], "rank": r["rank"],
                       "strength": r["strength"], "chance": r["chance"]}
            elif box == "crystal":
                o = 0x26D90 + 0x2C * r["slot"]
                n = de[o + 0x1A]
                src = struct.unpack_from("<H", de, o + 0x14)[0]
                if r["gid"] == 0 and de[o + 0x19] and src == 0:
                    src = 1   # crafting cylinder: DE writes source 0, the Wii 1 (its kind-3 record); one item, one value
                rec = {"gid": r["gid"], "qty": 1, "source": src,
                       "rank": de[o + 0x16], "attribute": de[o + 0x17], "cylinder": de[o + 0x19],
                       "effects": [list(struct.unpack_from("<HB", de, o + 0x1C + 4 * i)) for i in range(min(n, 4))]}
            else:
                rec = {"gid": r["gid"], "qty": r["qty"]}
            out[r["slot"]] = rec
            ser[r["slot"]] = r["serial"]
            if r["favorite"] or (r.get("u0a") not in (None, 0x3FFF, 0)):
                de_only_items.setdefault(box, {})[r["slot"]] = {"favorite": r["favorite"], "u0a": r.get("u0a")}
        ranks = order_ranks(ser)
        inv[box] = {sl: dict(rec, order=ranks[sl]) for sl, rec in out.items()}
        serials[box] = ser
    for k in chars:
        if k not in d["party"]:
            chars[k]["equipment"] = None
    x, y, z = struct.unpack_from("<3f", de, 0x149C10)
    ang = struct.unpack_from("<f", de, 0x149C20)[0]
    collect = [cid for cid in range(1, 301) if de[DE_COLLECT + ((0x19E9 + cid) >> 3)] >> ((0x19E9 + cid) & 7) & 1]
    shared = {
        "story": d["story"], "flags": flags,
        "achievements": de_achievements(de, T),
        "clock": {"hour": struct.unpack_from("<H", de, 0x149C04)[0], "minute": struct.unpack_from("<H", de, 0x149C06)[0],
                  "day": struct.unpack_from("<H", de, 0x149C24)[0]},
        "flag_bitmask_0": fm.de_get(de, 0),
        "money": d["money"], "play_time_s": d["play_time_s"], "party": d["party"],
        "map": struct.unpack_from("<I", de, 0x149C00)[0], "position": [round(x, 3), round(y, 3), round(z, 3)],
        "angle_rad": round(ang, 5), "characters": chars, "inventory": inv, "collectopaedia": collect,
        "quest_counters": {q: list(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8]) for q in range(qc.WII_N)
                           if fm.de_get(de, 0x220 + q) not in (254, 255) and any(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8])},
    }
    _stored_gear(shared, "de", de, T)
    de_flags = {g: fm.de_get(de, g) for g in de_only_flag_ids()}
    de_only = {
        "version": d["version"], "characters": de_only_chars, "items": de_only_items,
        "flags": {g: v for g, v in de_flags.items() if v},
        "quest_counters_fc": {q: list(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8]) for q in range(qc.WII_N, qc.DE_N)
                              if any(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8])},
        "header": de[:0x50].hex(), "location_words": de[0x149C04:0x149C10].hex(),
        "serial_counters": d["serial_counters"], "item_serials": serials,
    }
    return {"schema": SCHEMA, "source": {"game": "de", "format": f"de-v{d['version']}",
                                          "sha256": hashlib.sha256(de).hexdigest()},
            "shared": shared, "wii_only": {}, "de_only": de_only, "derived": {}}


def _stored_gear(shared, game, raw, T, ir=None):
    """Phase 3E: equipment stored for party members who are away (tools/stored_gear). Present only when the save has
    such characters, so every other save's canonical state is unchanged."""
    import stored_gear
    sg, bad = stored_gear.read_all(game, raw, shared["story"], shared["party"], T, ir=ir)
    if sg or bad:
        shared["stored_gear"] = {**sg, **{k: {"unreadable": v} for k, v in bad.items()}}


# ------------------------------------------------------------------------------------------------- utilities
def jsonable(c):
    """Canonical state as JSON-compatible data (int dict keys become strings)."""
    return json.loads(json.dumps(c, sort_keys=True, default=str))


def fingerprint(c, part="shared"):
    return hashlib.sha256(json.dumps(jsonable(c[part]), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compare(a, b, path=""):
    """Field-level differences between two canonical (sub)trees: [(path, a, b)]."""
    a, b = jsonable(a), jsonable(b)
    out = []

    def rec(x, y, p):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y), key=str):
                rec(x.get(k), y.get(k), f"{p}/{k}")
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y) and \
                any(isinstance(v, (dict, list)) for v in x + y):
            for i, (u, v) in enumerate(zip(x, y)):
                rec(u, v, f"{p}[{i}]")
        elif x != y:
            out.append((p, x, y))

    rec(a, b, path)
    return out
