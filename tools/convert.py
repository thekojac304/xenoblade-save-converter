"""Phase 2D integrated Wii (SX4E monadoNN) -> XC1 DE v10 converter. Writes only inside the research work directory.

  python convert.py <wii monadoNN> <DE v10 template bfsgameNN.sav> <out dir under work/> [slot] [--baseline-2d]

Phase 2E adds quest objective counters and minimap exploration (FEATURES_2E); --baseline-2d reproduces the
Phase 2D output byte for byte.

Starts from a byte copy of the template and overwrites only the fields listed in specs/wii_to_de_rules.json and
XC_WII_TO_DE_PHASE2D.md. Unknown DE fields keep template bytes. Every mapping is validated first; any
inconsistency raises ConvertError and nothing is written. After writing, the output is re-decoded by an independent
reader (de_save.py / flagmap.py) and every planned value is compared; the byte ranges touched are logged and all
other bytes are checked to equal the template. A JSON manifest (inputs' SHA-256, every write range, every check)
is written next to the save.
"""
import hashlib
import json
import math
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import de_save  # noqa: E402
import flag_transplant_eval as fte  # noqa: E402
import flagmap as fm  # noqa: E402
import minimap  # noqa: E402
import phase2c  # noqa: E402
import quest_counters as qc  # noqa: E402
import wii_save  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
WORK = os.path.join(ROOT, "work")
V10 = 0x153F30
CHAR, CHAR_SIZE, ARTS, PARTY = 0x152728, 0x138, 0x153AA8, 0x1526D8
MAP, POS, ANGLE = 0x149C00, 0x149C10, 0x149C20
COLLECTOPAEDIA = 0x148D6C
BOX = {n: (t, o, s) for n, t, o, s, _ in de_save.BOXES}
EQUIP = ("head", "body", "arm", "legs", "feet", "weapon")


class ConvertError(Exception):
    pass


class Image:
    """Template copy that records every byte range written."""

    def __init__(self, data):
        self.b = bytearray(data)
        self.ranges = []

    def put(self, off, fmt, *vals):
        struct.pack_into("<" + fmt, self.b, off, *vals)
        self.ranges.append((off, struct.calcsize("<" + fmt)))

    def raw(self, off, data):
        self.b[off:off + len(data)] = data
        self.ranges.append((off, len(data)))

    def set_bit(self, off, bit, v):
        cur = self.b[off]
        self.b[off] = (cur | 1 << bit) if v else (cur & ~(1 << bit) & 0xFF)
        self.ranges.append((off, 1))


def de_set_flag(img, gid, v):
    if gid < 0x20:
        img.put(0x11F0 + 4 * gid, "I", v)
    elif gid < 0x220:
        img.put(0xDF0 + 2 * (gid - 0x20), "H", v)
    elif gid < 0xA20:
        img.put(0x5F0 + gid - 0x220, "B", v)
    else:
        n = gid - 0xA20
        img.set_bit(0x50 + 4 * (n >> 5) + (n & 31) // 8, (n & 31) % 8, v)


# ---------------------------------------------------------------- flags (Phase 2B rules + achievement counters)
def achievement_groups(T):
    """Runs of consecutive comp_type-4 awards with strictly increasing comp_value = one metric's tiers."""
    ma = {r["id"]: r for r in T["de"]["MNU_playaward"]["rows"]}
    groups, cur = [], []
    for i in range(1, 201):
        r = ma[i]
        if r["comp_type"] == 4 and cur and ma[cur[-1]]["comp_type"] == 4 and r["genre"] == ma[cur[-1]]["genre"] \
                and r["comp_value"] > ma[cur[-1]]["comp_value"]:
            cur.append(i)
        else:
            if cur:
                groups.append(cur)
            cur = [i]
    groups.append(cur)
    return groups, ma


def convert_flags(img, wii, tpl, T, log):
    state, written, notes = fte.build(wii, tpl)
    bad = [n for n in notes if n[0].startswith(("OVERFLOW", "CONFLICT"))]
    if bad:
        raise ConvertError(f"flag rule violations: {bad[:5]}")
    groups, ma = achievement_groups(T)
    ach = []
    for g in groups:
        g = [i for i in g if 0x40 + i < 0x108]  # 0x108 is the bitmask flag moved to DE 32-bit[0]
        if not g or ma[g[0]]["comp_type"] != 4:
            continue
        total = max(fm.wii_get(wii, 0x40 + i) for i in g)
        for i in g:
            done = fm.wii_get(wii, 0x312C + i)
            comp = ma[i]["comp_value"]
            v = comp if done else min(total, comp)
            if done and total < comp:
                ach.append((i, "completed tier without Wii total; set comp_value", total, comp))
            if not done and total >= comp:
                ach.append((i, "Wii total reaches tier but tier not completed; capped at comp-1", total, comp))
                v = comp - 1
            state[0x40 + i] = v
    for gid, v in state.items():
        if fm.de_get(tpl, gid) != v:
            de_set_flag(img, gid, v)
    log["flags"] = {"notes": {k: sum(1 for n in notes if n[0] == k) for k in {n[0] for n in notes}},
                    "achievement_exceptions": ach, "story": state[0x20]}
    return state


# ---------------------------------------------------------------- inventory
def empty_pattern(tpl, off, size, n):
    """Bytes of the template's first empty slot (keeps DE's padding convention, e.g. +0x0A = 0x3FFF)."""
    for i in range(n):
        o = off + size * i
        if tpl[o + 0x10] == 0:
            return bytes(tpl[o:o + size])
    raise ConvertError("box has no empty slot")


def canon_ranks(keys):
    import canon
    return canon.order_ranks(keys)


def convert_inventory(img, tpl, ir, plan, T, log, serial_order=False):
    """serial_order (Phase 2F): the Wii header serial is an age (0 = newest, see canon.order_ranks); DE expects an
    acquisition number (larger = newer). The DE serial becomes the item's acquisition rank in its box (oldest = 1).
    Without it (Phase 2D/2E) the Wii value is copied, which reverses the order shown by DE's 'newest' sort."""
    w_equip, d_skill = T["w_equip"], T["d_skill"]
    serial_max = {}
    counts = {}
    for name, recs in ir["items"].items():
        if name == "tail":
            continue
        typ, off, size = BOX[name]
        inv = [r for r in recs if r.get("area", "inventory") == "inventory"]
        rank = canon_ranks({r["index"]: -r["header"]["serial"] for r in inv}) if serial_order else None
        pattern = empty_pattern(tpl, off, size, 500)
        for i in range(500):  # clear the template's box: Wii inventory replaces it
            o = off + size * i
            if tpl[o + 0x10]:
                img.raw(o, pattern)
        n = 0
        for r in recs:
            if r.get("area", "inventory") != "inventory":
                continue
            h, idx = r["header"], r["index"]
            if idx >= 500:
                raise ConvertError(f"{name} index {idx} >= 500")
            rec = bytearray(pattern)
            gid = h["gid"]
            if name == "gem":
                g = r["desc"]
                if g["strength"] > 255 or g["chance"] > 255:   # DE stores both as bytes (Phase 2F explicit check)
                    raise ConvertError(f"gem [{idx}] strength {g['strength']} / chance {g['chance']} exceed the DE "
                                       "byte fields")
                gid = 0 if gid == phase2c.CRAFTED_GEM_GID else gid
                struct.pack_into("<HHHHH", rec, 0, idx, typ, gid, typ, 1)
                rec[0x16], rec[0x17] = g["rank"], d_skill[g["effect"]]["atr_type"]
                rec[0x19] = 0
                struct.pack_into("<HHBB", rec, 0x1A, 1, g["effect"], g["strength"], g["chance"])
            elif name == "crystal":
                c = r["crystal"]
                de_gid = gid if c["kind"] == "list" else 0
                struct.pack_into("<HHHHH", rec, 0, idx, typ, de_gid, typ, 1)
                effs = [(e, v) for e, v in zip(c["effects"], c["values"]) if e]
                named = 1
                if c["kind"] == "drop":
                    named = 2 if T["named"].get(c["source"]) else 1
                struct.pack_into("<HBBBBB", rec, 0x14, c["source"], c["rank"], c["atr_type"], named, c["cylinder"],
                                 len(effs))
                for k, (e, v) in enumerate(effs):
                    struct.pack_into("<HBB", rec, 0x1C + 4 * k, e, v, 0)
            else:
                struct.pack_into("<HHHHH", rec, 0, idx, typ, gid, typ, h["qty"])
                if size == 0x30:
                    rec[0x14] = w_equip[h["row"]]["arm_type"] if name != "weapon" else rec[0x14]
                    rec[0x15] = r["slot_count"]
                    for s, sock in enumerate(r["sockets"][:3]):
                        if sock["desc"] is None:
                            continue
                        if sock["gem_box_ref"] is None:
                            struct.pack_into("<HH", rec, 0x1C + 8 * s, sock["desc"]["gid"], 1)
                        else:
                            struct.pack_into("<HH", rec, 0x18 + 8 * s, sock["gem_box_ref"], 3)
                    if any(s["desc"] for s in r["sockets"][3:]):
                        raise ConvertError(f"{name}[{idx}] uses a 4th socket")
            serial = rank[idx] if serial_order else h["serial"]
            struct.pack_into("<I", rec, 0xC, serial)
            rec[0x10], rec[0x11] = 1, 0
            img.raw(off + size * idx, bytes(rec))
            serial_max[typ] = max(serial_max.get(typ, 0), serial)
            n += 1
        counts[name] = n
    for typ, m in serial_max.items():
        o = de_save.SERIALS + 4 * typ
        cur = struct.unpack_from("<I", tpl, o)[0]
        img.put(o, "I", max(cur, m + 1))
    log["inventory_counts"] = counts


# ---------------------------------------------------------------- characters
def convert_characters(img, tpl, ir, plan, T, log, all_chars=False):
    """all_chars (Phase 2E): progression of all seven main characters (a Wii save made in a temporary party, e.g.
    Melia alone, or before a character joins, still carries everyone's record); equipment only for party members."""
    w_arts = T["w_arts"]
    post = 8 in {int(x) for x in plan["characters"]}    # Phase 3D: Fiora is character 8 (scenario >= 275)
    for k_str, p in plan["characters"].items():
        k = int(k_str)
        if k not in ir["party"] and k != 3 and not all_chars:
            continue
        o = CHAR + CHAR_SIZE * (k - 1)
        c = ir["characters"][k]
        img.put(o, "IIII", p["level"], p["exp"], p["ap"], p["affinity_coins"])
        if k in ir["party"]:
            for i, s in enumerate(EQUIP):
                e = p["equipment"][s]
                img.put(o + 0x14 + 4 * i, "HH", *((e["index"], e["type"]) if e else (0, 0)))
        elif all_chars and any(struct.unpack_from("<12H", tpl, o + 0x14)):
            # absent character: DE keeps no equipment (refs 0,0; the join script equips); template refs would point
            # into the replaced inventory
            img.put(o + 0x14, "12H", *([0] * 12))
        img.put(o + 0x48, "9H", *p["palette"])
        if "palette2" in p:
            img.put(o + 0x5A, "9H", *p["palette2"])
        img.put(o + 0x78, "I", p["skill_selected_tree"])
        img.put(o + 0x7C, "5I", *p["skill_sp"])
        img.put(o + 0x90, "5I", *p["skill_learned"])
        # unlocked link slots are shared state (Phase 2F): the Wii value for the six other main characters (not the
        # 2E max with the template, which could inherit unlocks from the template's playthrough); the self and
        # character-8 entries have no Wii counterpart and keep the template value
        tpl_unl = struct.unpack_from("<8I", tpl, o + 0xA4)
        links = bytearray(tpl[o + 0xC4:o + 0xEC])
        if not post:
            img.put(o + 0xA4, "8I", *[p["link_unlock_index"][i] if i + 1 != k and i + 1 <= 7 else tpl_unl[i]
                                      for i in range(8)])
            for src in range(1, 8):
                links[5 * (src - 1):5 * src] = bytes(p["links"][src - 1])
        else:
            # Phase 3D: the Wii's single "Fiora" row is DE slot 8 from scenario 275; DE slot 3 (her first form) keeps
            # its template value, except the unlock level, which the DE keeps equal in slots 3 and 8 (s276-s291)
            others = [x for x in (1, 2, 8, 4, 5, 6, 7) if x != k]
            unl = list(tpl_unl)
            for src in others:
                unl[src - 1] = p["link_unlock_index"][src - 1]
                links[5 * (src - 1):5 * src] = bytes(p["links"][src - 1])
            if k != 8:
                unl[2] = unl[7]
            img.put(o + 0xA4, "8I", *unl)
        img.raw(o + 0xC4, bytes(links))
        img.put(o + 0xEC, "II", p["level"], p["exp"])  # highest level = level; +0xF0 accumulator = current EXP
        for art, (lv, fl) in p["arts"].items():
            img.put(ARTS + 2 * (int(art) - 1), "BB", lv, fl)
        _ = c, w_arts
    if post:   # Phase 3D: the DE keeps Fiora's two records' link-unlock arrays equal (s260-s291)
        o3, o8 = CHAR + CHAR_SIZE * 2, CHAR + CHAR_SIZE * 7
        img.raw(o3 + 0xA4, bytes(img.b[o8 + 0xA4:o8 + 0xC4]))
    party = ir["party"]
    img.put(PARTY, "12H", *(party + [0] * (12 - len(party))))
    img.put(PARTY + 0x18, "I", len(party))


def convert_misc(img, tpl, ir, plan, wii, log):
    img.put(de_save.MONEY, "I", plan["money"])
    img.put(4, "I", plan["play_time_s"])
    img.put(MAP, "I", ir["map"])
    x, y, z, ang = struct.unpack_from(">4f", wii, 0x11EE0)
    img.put(POS, "fff", x, y, z)
    img.put(ANGLE, "f", math.radians(ang))
    for cid in range(1, 301):  # Collectopaedia: Wii bit id (0x8009F5F0) -> DE bit 0x19E9+id (0x81310)
        v = wii[0xEAC6 + (cid >> 3)] >> (cid & 7) & 1
        bit = 0x19E9 + cid
        if (tpl[COLLECTOPAEDIA + (bit >> 3)] >> (bit & 7) & 1) != v:
            img.set_bit(COLLECTOPAEDIA + (bit >> 3), bit & 7, v)
    log["location"] = {"map": hex(ir["map"]), "pos": [x, y, z], "angle_deg": ang}


# ---------------------------------------------------------------- verification
def verify(out_path, tpl, ir, plan, state, img, T, extra=None):
    """Independent read-back with de_save/flagmap; returns list of failures."""
    with open(out_path, "rb") as f:
        out = f.read()
    return verify_bytes(out, tpl, ir, plan, state, img, T, extra)


def verify_bytes(out, tpl, ir, plan, state, img, T, extra=None):
    fail = []
    if len(out) != V10 or struct.unpack_from("<I", out, 0)[0] != 10:
        fail.append("size/version")
    de = de_save.decode_bytes(out)
    for gid, v in state.items():
        if fm.de_get(out, gid) != v:
            fail.append(f"flag {gid:#x}")
    if de["story"] != ir["scenario"] or de["party"] != ir["party"] or de["money"] != plan["money"]:
        fail.append("story/party/money")
    for k_str, p in plan["characters"].items():
        k = int(k_str)
        if k not in ir["party"]:
            continue
        c = de["characters"][k]
        for f_ in ("level", "exp", "ap", "affinity_coins", "skill_sp", "skill_learned", "skill_selected_tree", "palette"):
            if c[f_] != p[f_]:
                fail.append(f"char {k} {f_}")
        for s in EQUIP:
            e = p["equipment"][s]
            if e:
                recs = {r["slot"]: r for r in de["boxes"][s]}
                r = recs.get(e["index"])
                wrec = next(x for x in ir["items"][s] if x["index"] == e["index"])
                if not r or (r["index"], r["type"], r["gid"]) != (e["index"], e["type"], wrec["header"]["gid"]):
                    fail.append(f"char {k} {s} ref")
        for art, lvfl in p["arts"].items():
            if de["arts"][int(art) - 1] != list(lvfl):
                fail.append(f"art {art}")
    for name, recs in ir["items"].items():
        if name == "tail":
            continue
        want = {r["index"] for r in recs if r.get("area", "inventory") == "inventory"}
        got = {r["slot"] for r in de["boxes"][name]}
        if want != got:
            fail.append(f"box {name} slots differ")
    gems = {r["slot"]: r for r in de["boxes"]["gem"]}
    for r in ir["items"]["gem"]:
        g, d = r["desc"], gems[r["index"]]
        if (d["effect"], d["rank"], d["strength"], d["chance"]) != (g["effect"], g["rank"], g["strength"], g["chance"]):
            fail.append(f"gem {r['index']}")
    for off, want in (extra or {}).items():  # Phase 2E steps: exact expected bytes
        if out[off:off + len(want)] != want:
            fail.append(f"phase2e bytes at {off:#x}")
    touched = bytearray(len(out))
    for o, n in img.ranges:
        touched[o:o + n] = b"\1" * n
    stray = sum(1 for i in range(len(out)) if not touched[i] and out[i] != tpl[i])
    if stray:
        fail.append(f"{stray} bytes changed outside logged ranges")
    return fail, sum(touched)


# ---------------------------------------------------------------- Phase 2E steps
FEATURES_2E = ("quest_counters", "minimap", "clock", "achievements_exact", "all_characters")
FEATURES_2F = FEATURES_2E + ("serial_order", "template_reset", "party_check")
NOPONSTONES = 0x10        # DE header u32 (Phase 2E re_time_achievements_deonly section 4)


def reset_template_playthrough(img, tpl, log):
    """First export only (Phase 2F): the template is ANOTHER playthrough. Its per-playthrough DE-only resources would
    otherwise be inherited by the converted save: Expert Mode reserve EXP (+0xF4, a spendable EXP pool [C] 0xA6FAC),
    cosmetic/fashion slots (+0x2C..+0x47, [C] 0xA6E20) and Noponstones (header 0x10, a DE currency). They are set to
    their new-game value 0. Options and the Expert Mode switch stay (settings, not progress)."""
    done = {}
    for k in range(1, 8):
        o = CHAR + CHAR_SIZE * (k - 1)
        if struct.unpack_from("<I", tpl, o + 0xF4)[0]:
            img.put(o + 0xF4, "I", 0)
            done.setdefault("reserve_exp_cleared", []).append(k)
        if any(tpl[o + 0x2C:o + 0x48]):
            img.raw(o + 0x2C, bytes(0x1C))
            done.setdefault("cosmetics_cleared", []).append(k)
    if struct.unpack_from("<I", tpl, NOPONSTONES)[0]:
        img.put(NOPONSTONES, "I", 0)
        done["noponstones_cleared"] = struct.unpack_from("<I", tpl, NOPONSTONES)[0]
    fc = [g for g in range(0x608, 0x734) if fm.de_get(tpl, g)]
    if fc or any(tpl[qc.DE_QC + 8 * qc.WII_N:qc.DE_QC + 8 * qc.DE_N]):
        done["warning"] = ("the template has Future Connected progress; it is kept (DE-only) but belongs to the "
                           "template's playthrough - prefer an early-game template")
    log["template_reset"] = done


def unsupported_wii_party(ir, story=None):
    """Phase 3D: era-aware (canon.unsupported_party); story = the Wii scenario (flag 0x20)."""
    import canon
    return canon.unsupported_party({"party": ir["party"], "story": story if story is not None else ir.get("story", 0)})
CLOCK = 0x149C04          # u16 hour, u16 minute (field block; serializer 0x5936C0, loader 0x593800)
CLOCK_DAY = 0x149C24      # u16 day, u16 last day award 129 was counted


def convert_clock(img, wii, log):
    """Wii TIME float (2-game-second units, 1800/hour) -> DE hour/minute; day; Wii 16-bit 0xAF -> last sunrise day."""
    t = struct.unpack_from(">f", wii, 0x11EB4)[0]
    day = struct.unpack_from(">H", wii, 0x11EB8)[0]
    h, m = int(t // 1800) % 24, int(t // 30) % 60
    img.put(CLOCK, "HH", h, m)
    img.put(CLOCK_DAY, "HH", max(day, 1), fm.wii_get(wii, 0xAF))
    log["clock"] = {"wii_day_time": t, "hour": h, "minute": m, "day": day, "last_sunrise_day": fm.wii_get(wii, 0xAF)}
    return {CLOCK: struct.pack("<HH", h, m), CLOCK_DAY: struct.pack("<HH", max(day, 1), fm.wii_get(wii, 0xAF))}


def convert_achievements_exact(img, wii, tpl, T, state, log):
    """Exact award counters (tools/achievements.py) over the Phase 2B/2D approximation; uses the converted art table."""
    import achievements
    arts = [(img.b[ARTS + 2 * a], img.b[ARTS + 2 * a + 1]) for a in range(188)]
    vals = achievements.wii_to_de(wii, arts, T)
    changed = []
    for gid, v in sorted(vals.items()):
        if state.get(gid) != v:
            changed.append((hex(gid), state.get(gid), v))
        state[gid] = v
        if fm.de_get(bytes(img.b), gid) != v:
            de_set_flag(img, gid, v)
    log["achievements_exact"] = {"counters": len(vals), "changed_vs_2d_rule": changed}


def convert_quest_counters(img, wii, tpl, log, extra):
    """Quest objective counters q < 1000 (Wii file 0xB2B8+8q -> DE 0x1270+8q); DE q >= 1000 (Future Connected) kept."""
    changed = 0
    for q in range(qc.WII_N):
        want = qc.wii_to_de(wii, q)
        o = qc.DE_QC + 8 * q
        if tpl[o:o + 8] != want:
            img.raw(o, want)
            changed += 1
        extra[o] = want
    log["quest_counters"] = {"quests_written": changed}


def _ranges(changes):
    out, run = [], None
    for o in sorted(changes):
        if run and o == run[0] + len(run[1]):
            run[1].append(changes[o])
        else:
            if run:
                out.append((run[0], bytes(run[1])))
            run = [o, [changes[o]]]
    if run:
        out.append((run[0], bytes(run[1])))
    return out


def convert_minimap(img, wii, log, base="clear"):
    """Exploration bitmaps (tools/minimap.py, display mode). base='clear': the template's bitmaps of shared maps are
    cleared first (the template is another playthrough); 'merge': OR onto them (re-import onto the same playthrough)."""
    cleared = 0
    if base == "clear":
        for m in minimap.SHARED_MAPS:
            ncol, nrow, stride = minimap.de_dims(m)
            for f in range(1, minimap.DE_MAPS[m][2] + 1):
                o, n = minimap.de_floor_off(m, f), nrow * stride
                if any(img.b[o:o + n]):
                    img.raw(o, bytes(n))
                    cleared += 1
    rep_ = {}
    ch = minimap.wii_to_de(wii, bytes(img.b), mode="display", report=rep_)
    for o, data in _ranges(ch):
        img.raw(o, data)
    log["minimap"] = {"base": base, "floors_cleared": cleared, "bytes_set": len(ch),
                      "cells_per_map_floor": {f"{m}.{f}": n for (m, f), n in rep_.get("wii_to_de", {}).items() if n}}
    return ch


def load_tables():
    _, _, T = phase2c.tables()
    import paths
    with open(paths.data("bdat_de.json"), encoding="utf-8") as f:
        T["de"] = json.load(f)
    T["named"] = {}
    for name, t in T["de"].items():
        if name.startswith("BTL_enelist") and "named" in t.get("cols", []):
            for r in t["rows"]:
                T["named"][r["id"]] = T["named"].get(r["id"], 0) or r["named"]
    return T


def build(wii, tpl, T, features=FEATURES_2F, minimap_base="clear", wii_name="<wii>", tpl_name="<template>",
          lineage_template=False, stored_keep=()):
    """Pure conversion: Wii save bytes + DE v10 template bytes -> (out bytes, log, failures). Nothing is written.
    lineage_template: the template is this playthrough's own DE save (sidecar re-import), so its DE-only state is
    kept; otherwise (first export) the template's per-playthrough DE-only resources are reset (FEATURES_2F)."""
    if len(tpl) != V10 or struct.unpack_from("<I", tpl, 0)[0] != 10:
        raise ConvertError("template is not a v10 save")
    if len(wii) != 0x28000 or wii[:4] != b"USRD":
        raise ConvertError("Wii input is not a used XC1 save slot (empty DMMY slot, wrong size or other file)")
    if wii_save.check_container(wii):
        raise ConvertError(f"Wii container damaged: {wii_save.check_container(wii)}")
    pc, tal = phase2c.main(wii_name, write=False, wii_bytes=wii, T=T)
    ir, plan = pc["wii"], pc["planned_de"]
    story = fm.wii_get(wii, 0x20)
    if "party_check" in features and unsupported_wii_party(ir, story):
        raise ConvertError(f"party member(s) {unsupported_wii_party(ir, story)} cannot be in the party at scenario "
                           f"{story} (characters 9-13 are prologue guests; Fiora is character 3 before scenario 275 "
                           "and character 8 from 275)")
    # Phase 3E (3D defect D2): gear the Wii keeps for party members who are away in a story event (staging slots 150+id,
    # staged gems) is translated into the DE's stored-equipment table (tools/stored_gear); unreadable data is refused
    import stored_gear
    sg_src, sg_bad = stored_gear.read_all("wii", wii, story, ir["party"], T, ir=ir) if "party_check" in features \
        else ({}, {})
    for k in stored_keep:         # Phase 3E re-import: stored gear the Wii session did not touch -> the DE's own entries
        sg_src.pop(k, None)
        sg_bad.pop(k, None)
    if sg_bad:
        raise ConvertError("; ".join(f"{stored_gear.NAMES.get(k, k)} is away from the party and the stored equipment "
                                     f"cannot be converted without guessing ({v})" for k, v in sg_bad.items()))
    if "party_check" in features:   # Phase 3F (F1): a return the game skipped (full pocket) - refuse, never lose the gear
        unfinished = stored_gear.unfinished_returns(ir, story)
        if unfinished:
            raise ConvertError(stored_gear.unfinished_message(unfinished))
        fj = stored_gear.first_join_problems(sg_src, fm.wii_get(wii, 0x108))      # Phase 3F: Fiora-8 first join
        if fj:
            raise ConvertError("; ".join(fj))
    blockers = [c for c, e in tal.c.items() if e["unresolved"] and c.startswith(("inventory:", "char:"))
                and c not in ("char:exp_accum", "char:equipment_ref(inactive)")]
    if blockers:
        raise ConvertError(f"unresolved mappings: {blockers}")
    log = {"inputs": {"wii": [wii_name, hashlib.sha256(wii).hexdigest()],
                      "template": [tpl_name, hashlib.sha256(tpl).hexdigest()]}, "features": list(features)}
    img = Image(tpl)
    extra = {}
    state = convert_flags(img, wii, tpl, T, log)
    convert_inventory(img, tpl, ir, plan, T, log, "serial_order" in features)
    convert_characters(img, tpl, ir, plan, T, log, "all_characters" in features)
    if sg_src:     # Phase 3E: stored equipment of characters who are away (identical template entries are kept)
        dst = {}
        for k in sg_src:
            try:
                dst[k] = stored_gear.de_read(tpl, k)
            except stored_gear.StoredGearError:
                pass

        def _w(k, g):
            stored_gear.write_de(img.b, k, g, T, tpl)
            img.ranges.append((stored_gear.STASH + stored_gear.ENTRY * stored_gear.PER_CHAR * (k - 1),
                               stored_gear.ENTRY * stored_gear.PER_CHAR))
            img.ranges.append((de_save.SERIALS, 4 * 14))
        try:
            log["stored_gear_written"] = stored_gear.apply("wii_to_de", sg_src, {}, dst, _w)
        except (stored_gear.StoredGearError, Exception) as e:
            if isinstance(e, ConvertError):
                raise
            raise ConvertError(f"stored equipment: {e}")
    if "template_reset" in features and not lineage_template:
        reset_template_playthrough(img, tpl, log)
    convert_misc(img, tpl, ir, plan, wii, log)
    if "quest_counters" in features:
        convert_quest_counters(img, wii, tpl, log, extra)
    if "minimap" in features:
        for o, data in _ranges(convert_minimap(img, wii, log, minimap_base)):
            extra[o] = data
    if "clock" in features:
        extra.update(convert_clock(img, wii, log))
    if "achievements_exact" in features:
        convert_achievements_exact(img, wii, tpl, T, state, log)
    out = bytes(img.b)
    fail, touched = verify_bytes(out, tpl, ir, plan, state, img, T, extra)
    log.update(bytes_touched=touched, write_ranges=len(img.ranges), verification_failures=fail)
    return out, log, fail


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main(wii_path, tpl_path, out_dir, slot="bfsgame00.sav", features=FEATURES_2E, minimap_base="clear"):
    out_dir = os.path.abspath(out_dir)
    if not out_dir.lower().startswith(WORK.lower() + os.sep):
        raise ConvertError(f"output must be inside {WORK}")
    T = load_tables()
    tpl = open(tpl_path, "rb").read()
    wii = open(wii_path, "rb").read()
    out, log, fail = build(wii, tpl, T, features, minimap_base, wii_path, tpl_path)
    save_dir = os.path.join(out_dir, "save_0")
    os.makedirs(save_dir, exist_ok=True)
    out_path = os.path.join(save_dir, slot)
    with open(out_path, "wb") as f:
        f.write(out)
    tdir = os.path.dirname(tpl_path)
    for extra in (slot.replace(".sav", ".tmb"), "bfssystem.sav"):
        src = os.path.join(tdir, extra)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(save_dir, extra))
    log.update(output=[out_path, sha(out_path)])
    log["inputs"] = {"wii": [wii_path, sha(wii_path)], "template": [tpl_path, sha(tpl_path)]}
    json.dump(log, open(os.path.join(out_dir, "manifest.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in log.items() if k not in ("flags", "minimap")}, indent=1, default=str)[:3000])
    if fail:
        raise ConvertError(f"read-back verification failed: {fail[:10]}")
    return out_path


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        sys.exit(__doc__)
    feats = () if "--baseline-2d" in sys.argv else FEATURES_2E
    main(*args[:3], *(args[3:4]), features=feats)
