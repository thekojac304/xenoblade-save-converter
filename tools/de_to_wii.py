"""DE (v10 / v7) -> Wii (SX4E monadoNN) converter, Phase 2E. Pure functions: bytes in, bytes out; nothing is written.

The Wii file is produced by patching a BASE Wii image:
  * lineage base  - the Wii save this playthrough came from (sidecar of a Wii->DE export, or the Wii file a previous
                    DE->Wii export produced). Every shared field is written from the DE state; where the DE value equals
                    what the base itself converts to (canon.from_wii), the base's exact bytes are kept, so unchanged
                    data round-trips byte for byte and Wii-only details (item header bits, crystal bytes, EXP-earned
                    counters, award lead slots, quest counter bytes) survive.
  * foreign base  - any valid Wii save used only as a structural template (DE-native playthroughs). Wii-only regions
                    that would describe the other playthrough are reset (minimap bits, field chests TBOX, collection
                    cooldowns MINE, story-scene costume snapshot) and every shared field is re-encoded.
Rules (code-backed, see XC_WII_TO_DE_PHASE2B/2C/2D/2E and BIDIRECTIONAL_DESIGN.md): flags = inverse Phase 2B map;
achievements = tools/achievements.de_to_wii; quest counters = tools/quest_counters.de_to_wii; characters, arts,
skills, links, palettes, equipment and inventory = inverse of tools/convert.py; minimap = tools/minimap.de_to_wii
(strict); clock = DE hour/minute/day -> Wii float (1800 per hour) / day.

Compatibility: build() raises IncompatibleError for states the Wii cannot represent (Future Connected maps or
characters, DE-only items that are equipped, scenario beyond the Wii's, ...). DE-only data that is not needed to
play (cosmetics, Expert Mode reserve, DE-only flags, Future Connected quest bytes, unequipped DE-only items, favourite
marks) is reported in `deferred` for the sidecar; nothing is dropped silently.
"""
import hashlib
import struct

import achievements
import canon
import de_save
import flag_transplant_eval as fte
import flagmap as fm
import minimap
import quest_counters as qc
import stored_gear
import wii_save

EQUIP =("head", "body", "arm", "legs", "feet", "weapon")
KIND = {"head": 1, "body": 2, "arm": 3, "legs": 4, "feet": 5, "weapon": 6}
CRAFTED_GEM_GID = 3747
WII_CAP = {"head": 150, "body": 150, "arm": 150, "legs": 150, "feet": 150, "weapon": 150, "crystal": 300, "gem": 300,
           "artmanual": 240, "collectable": 300, "material": 300, "keyitem": 200}
WII_BOX = {n: (t, off, size, slots) for n, t, off, size, slots in wii_save.BOXES}
ITEM = wii_save.ITEM
CHAR_BASE, CHAR_SIZE = wii_save.CHAR_BASE, wii_save.CHAR_SIZE
PARTY = wii_save.PARTY
WII_MAX_SCENARIO = 486          # MNU_scenario rows shared by both games (story ids above are Future Connected / DE)
FC_AREAS = range(50, 70)        # ma5001..ma6001: Future Connected
LEADER_NAME = {1: "Shulk", 2: "Reyn", 3: "Fiora", 4: "Dunban", 5: "Sharla", 6: "Riki", 7: "Melia", 8: "Fiora"}  # NTSC-U


class IncompatibleError(Exception):
    pass


_WII_MAPS = None


def wii_maps():
    """{(area, sub)} of the Wii's FLD_maplist (ma0000 .. ma2401 and ma0102); DE adds ma2501/2601/2701/4001 and FC."""
    global _WII_MAPS
    if _WII_MAPS is None:
        import json
        import paths
        with open(paths.data("bdat_wii.json"), encoding="utf-8") as f:
            rows = json.load(f)["FLD_maplist"]["rows"]
        _WII_MAPS = {(int(r["resource"][2:4]), int(r["resource"][4:6])) for r in rows} - {(0, 0)}
    return _WII_MAPS


def wii_capacity(base):
    """Per-box usable capacity of the Wii save (box getter 0x80158490): weapons, armour and materials hold
    10 x (bits 1..11 set in ITEM+0x12108) + 60 + min(ITEM+0x12110, 30); the other boxes are fixed."""
    mask = struct.unpack_from(">I", base, ITEM + 0x12108)[0]
    bonus = min(struct.unpack_from(">I", base, ITEM + 0x12110)[0], 30)
    var = 10 * sum(1 for b in range(1, 12) if mask >> b & 1) + 60 + bonus
    cap = dict(WII_CAP)
    for b in EQUIP + ("material",):
        cap[b] = min(cap[b], var)
    return cap


class WiiImage:
    def __init__(self, data):
        self.b = bytearray(data)
        self.ranges = []

    def put(self, off, fmt, *vals):
        struct.pack_into(">" + fmt, self.b, off, *vals)
        self.ranges.append((off, struct.calcsize(">" + fmt)))

    def raw(self, off, data):
        self.b[off:off + len(data)] = data
        self.ranges.append((off, len(data)))


def wii_set_flag(img, gid, v):
    P = fm.WII_P
    if gid < 0x20:
        img.put(P + 4 * gid, "I", v)
        return
    if gid < 0x220:
        s = gid - 0x20
        o, sh, mask = P + 4 * (0x20 + (s >> 1)), 16 * (s & 1), 0xFFFF
    elif gid < 0xA20:
        s = gid - 0x220
        o, sh, mask = P + 4 * (0x120 + (s >> 2)), 8 * (s & 3), 0xFF
    else:
        n = gid - 0xA20
        o, sh, mask = P + 4 * (0x320 + (n >> 5)), n & 31, 1
    if v > mask:
        raise IncompatibleError(f"flag {gid:#x} value {v} does not fit the Wii bank")
    w = struct.unpack_from(">I", img.b, o)[0]
    w = (w & ~(mask << sh) & 0xFFFFFFFF) | (v << sh)
    img.put(o, "I", w)


def fix_crcs(img):
    for tag, hdr, s, e in wii_save.SECTIONS:
        crc = wii_save.crc16_arc(bytes(img.b[s:e]))
        if struct.unpack_from(">H", img.b, hdr + 0xE)[0] != crc:
            img.put(hdr + 0xE, "H", crc)


# ------------------------------------------------------------------------------------------------- encoders
def gem_desc_bytes(gid, strength, rank, chance, effect, category=1, flag=0):
    w0 = ((gid - 2048) & 0x7FF if gid else 0) << 21 | strength << 10 | rank << 7 | chance
    return struct.pack(">IHH", w0, effect << 4 | category << 1 | flag, 0)


def header_bytes(gid, typ, row, low5, serial, qty, flags):
    return struct.pack(">IHBB", gid << 20 | typ << 16 | row << 5 | low5, serial, qty, flags)


def fixed_gem_desc(gid, T):
    wi = T["w_item"][gid]
    if wi["itemType"] != 3:
        raise IncompatibleError(f"built-in gem {gid} is not a gem item")
    return gem_desc_bytes(gid, wi["percent"], wi["rankType"], 0, wi["itemID"], 1, 1)


def wii_row(gid, typ, T, box):
    wi = T["w_item"].get(gid)
    if wi is None or wi["itemType"] != typ:
        raise IncompatibleError(f"{box} item {gid} does not exist on the Wii")
    return wi["itemID"]


def find_drop_row(c, T):
    """ITM_dropcrystallist row matching a DE drop crystal (rank, attribute, cylinder flag, effects)."""
    effs = [e for e, v in c["effects"]]
    for rid, t in sorted(T["w_drop"].items()):
        want = [t["skill1"]] + ([] if t["cylinder"] else [t["skill2"]])
        if (t["rank"], t["atr_type"], t["cylinder"]) == (c["rank"], c["attribute"], c["cylinder"]) and effs == want:
            return rid
    raise IncompatibleError(f"no Wii drop-crystal row for {c}")


def encode_record(box, rec, T, gem_desc_by_slot, base_raw=None, age=0):
    """age: the Wii header u16 +4 (acquisition age, 0/1 = newest; see canon.order_ranks)."""
    typ, off, size, _ = WII_BOX[box]
    if box in EQUIP:
        row = wii_row(rec["gid"], typ, T, box)
        low5 = base_raw[3] & 31 if base_raw is not None and base_raw[:4] and \
            struct.unpack_from(">I", base_raw)[0] >> 20 == rec["gid"] else 0
        out = bytearray(header_bytes(rec["gid"], typ, row, low5, age, max(rec["qty"], 1), 0))
        descs, refs = [], []
        socks = list(rec["sockets"]) + [None] * (4 - len(rec["sockets"]))
        for s in socks[:4]:
            if s is None:
                descs.append(bytes(8))
                refs.append(0xFFFF)
            elif s[0] == "fixed":
                descs.append(fixed_gem_desc(s[1], T))
                refs.append(0xFFFF)
            else:
                descs.append(gem_desc_by_slot[s[1]])
                refs.append(s[1])
        out += b"".join(descs) + struct.pack(">4H", *refs) + struct.pack(">BBH", rec["socket_count"], KIND[box], 0)
        return bytes(out)
    if box == "gem":
        crafted = rec["gid"] == 0
        gid = CRAFTED_GEM_GID if crafted else rec["gid"]
        if not crafted:
            wii_row(gid, 3, T, box)
        return header_bytes(gid, 3, rec["effect"], rec["rank"] << 2, age, 1, 3 if crafted else 0) + \
            gem_desc_bytes(gid, rec["strength"], rec["rank"], rec["chance"], rec["effect"], 1, 0)
    if box == "crystal":
        if rec["gid"]:
            kind, gid, row = 1, rec["gid"], wii_row(rec["gid"], 9, T, box)
        elif rec["cylinder"] and rec["source"] == 1:
            kind, gid = 3, rec["effects"][0][0]
            row = gid
        else:
            kind = 2
            gid = row = find_drop_row(rec, T)
        h = header_bytes(gid, 9, row, rec["rank"] << 2 | (1 if kind == 2 else 0), age, 1,
                         rec["attribute"] << 2 | kind)
        effs = list(rec["effects"])[:4] + [[0, 0]] * (4 - min(len(rec["effects"]), 4))
        body = struct.pack(">4H", *[(e << 4 | 2) if e else 0 for e, v in effs])
        src = rec["source"] | (rec["cylinder"] << 15)
        body += struct.pack(">H", 0 if rec["cylinder"] else rec["source"] % 100)
        body += bytes(v for e, v in effs) + bytes([1, 0]) + struct.pack(">HH", src, 0)
        return h + body
    gid = rec["gid"]
    if rec["qty"] > 99 or rec["qty"] < 1:
        raise IncompatibleError(f"{box} {gid} quantity {rec['qty']} outside 1..99")
    return header_bytes(gid, typ, wii_row(gid, typ, T, box), 0, age, rec["qty"], 0)


# ------------------------------------------------------------------------------------------------- checks
def compatibility(cd, de, T):
    """Hard incompatibilities (raise) and DE-only data to defer to the sidecar (returned)."""
    s = cd["shared"]
    problems, deferred = [], {}
    area = s["map"] & 0xFFFF
    if (area, s["map"] >> 16) not in wii_maps():
        problems.append(f"current map ma{area:02d}{s['map'] >> 16:02d} is not a Wii map (DE-only or Future Connected)")
    if not 1 <= s["story"] <= WII_MAX_SCENARIO:
        problems.append(f"story scenario {s['story']} is not a Wii scenario")
    bad_party = [p for p in s["party"] if not 1 <= p <= 13]
    if bad_party or not s["party"]:
        problems.append(f"party {s['party']} cannot exist on the Wii")
    elif canon.unsupported_party(s):
        problems.append(f"party member(s) {canon.unsupported_party(s)} cannot be in the party at scenario "
                        f"{s['story']} (9-13 are prologue guests; Fiora is character 3 before scenario 275 and "
                        "character 8 from 275)")
    for k, c in s["characters"].items():
        if not 1 <= c["level"] <= 99:
            problems.append(f"character {k} level {c['level']}")
            continue
        nxt = T["w_grow"].get(c["level"] + 1, {}).get("level_exp")
        if nxt is not None and c["exp"] >= nxt:    # Phase 2F: states the game never writes are refused, not repaired
            problems.append(f"character {k} EXP {c['exp']} is not below the cost of level {c['level'] + 1} ({nxt})")
        if c["affinity_coins"] > 999 or c["ap"] > 99_999_999:
            problems.append(f"character {k} affinity coins {c['affinity_coins']} / AP {c['ap']} above the game limits")
    if s["money"] > 999_999_999:
        problems.append(f"money {s['money']} above the Wii limit 999,999,999")
    for q in range(qc.WII_N):     # open quests: objective bytes must be a DE encoding (0xFF done, kill 0..num, else 0)
        if fm.de_get(de, 0x220 + q) in (254, 255) or q not in qc.quests():
            continue
        raw = de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8]
        for sl, t, cnd, n in qc.slots(qc.quests()[q]):
            v = raw[sl]
            if t and not (v == 0xFF or v == 0 or (t == 1 and v <= n)):
                problems.append(f"quest {q} objective {sl} counter {v} is not a valid DE value (type {t}, num {n})")
    for box in EQUIP:             # references must resolve (a dangling one is a damaged save, never guessed)
        for slot, r in s["inventory"][box].items():
            for x in r["sockets"]:
                if x and x[0] == "gem" and x[1] not in s["inventory"]["gem"]:
                    problems.append(f"{box} slot {slot} socket references empty gem slot {x[1]}")
    for k, c in s["characters"].items():
        for sl, v in (c["equipment"] or {}).items():
            if v is not None and v not in s["inventory"][sl]:
                problems.append(f"character {k} {sl} references empty {sl} slot {v}")
    for slot, r in s["inventory"]["gem"].items():
        if r["rank"] > 7 or r["chance"] > 127 or r["strength"] > 2047 or r["effect"] > 4095:
            problems.append(f"gem slot {slot} values {r} do not fit the Wii gem fields")
    for slot, r in s["inventory"]["crystal"].items():
        n_eff = de[0x26D90 + 0x2C * slot + 0x1A]
        if n_eff > 4 or r["rank"] > 7 or r["source"] > 0x7FFF or any(e > 4095 for e, v in r["effects"]):
            problems.append(f"crystal slot {slot} ({n_eff} effects, {r}) does not fit the Wii crystal record")
    if cd["de_only"]["quest_counters_fc"]:
        deferred["future_connected_quest_counters"] = cd["de_only"]["quest_counters_fc"]
    if any(fm.de_get(de, g) for g in range(0x608, 0x734)):
        deferred["future_connected_quest_states"] = {g: fm.de_get(de, g) for g in range(0x608, 0x734) if fm.de_get(de, g)}
    # DE-only items: unequipped -> sidecar; equipped by anyone -> incompatible
    equipped = {(sl, c["equipment"][sl]) for c in s["characters"].values() if c["equipment"] for sl in EQUIP
                if c["equipment"][sl] is not None}
    for box, recs in s["inventory"].items():
        for slot, r in recs.items():
            gid, typ = r["gid"], canon.BOX_TYPE[box]
            ok = True
            if gid:
                wi = T["w_item"].get(gid)
                ok = wi is not None and wi["itemType"] == typ
            if box in EQUIP:
                for sk in r["sockets"]:
                    if sk and sk[0] == "fixed" and (T["w_item"].get(sk[1]) or {}).get("itemType") != 3:
                        ok = False
            if not ok:
                if box in EQUIP and (box, slot) in equipped:
                    problems.append(f"DE-only item {gid} is equipped ({box} slot {slot})")
                else:
                    deferred.setdefault("de_only_items", {}).setdefault(box, {})[slot] = r
    for k, c in s["characters"].items():
        for aid, lv in c["arts"].items():
            pass
    return problems, deferred


# ------------------------------------------------------------------------------------------------- main build
def _char_exp_total(T, level, exp):
    return sum(T["w_grow"][lv]["level_exp"] for lv in range(2, level + 1) if lv in T["w_grow"]) + exp


SHULK_ARTS_FLAG_STORY = 20      # Phase 3D (defect D1), see build()


def _base_char(base, k):
    """Phase 3D: canonical-like view of a base record that is outside the base save's own era (e.g. record 8 of a
    Wii base from before scenario 275): only the values the writer compares; links/unlocks never 'same'."""
    o = CHAR_BASE + CHAR_SIZE * k
    return {"level": struct.unpack_from(">I", base, o + 0x17C)[0], "exp": struct.unpack_from(">I", base, o + 0x2A4)[0],
            "links": {}, "link_unlock": {}}


def build(de, base, T, lineage=True, minimap_min_fraction=1.0, de_name="<de>", base_name="<wii base>",
          overflow="refuse", instances=None):
    """-> (wii bytes, log, deferred). Raises IncompatibleError on states the Wii cannot represent.
    overflow: 'refuse' (default) - more items than the Wii box holds is an error; 'sidecar' - unequipped,
    unreferenced items beyond the Wii capacity (highest DE slots first) are deferred to the sidecar.
    instances (Phase 3C): {box: set of DE slots} holding the SAME item as the DE save this base was exported to (same
    slot, same id, same DE acquisition serial - DE never reuses a serial). Only those items keep the base's Wii-only
    record bytes (equipment header low bits, crystal byte +0x16); a different item in that slot - e.g. an identical
    one bought after the old one was sold - is encoded fresh. None = the 3B rule (same slot and same content)."""
    if de_save.layout(de)["version"] not in (7, 10):
        raise IncompatibleError("not a DE v7/v10 save")
    if base[:4] != b"USRD" or wii_save.check_container(base):
        raise IncompatibleError("the Wii base is not a valid used XC1 save (CRC/slot check)")
    cd = canon.from_de(de, T, de_name)
    cb = canon.from_wii(base, T, base_name)
    problems, deferred = compatibility(cd, de, T)
    # Phase 3E (3D defect D2): gear the DE keeps for party members who are away in a story event is translated into
    # the Wii's staging records (tools/stored_gear); data that cannot be read without guessing is refused
    sg_src, sg_bad = stored_gear.read_all("de", de, cd["shared"]["story"], cd["shared"]["party"], T)
    for k, why in sg_bad.items():
        problems.append(f"{stored_gear.NAMES.get(k, k)} is away from the party and the stored equipment cannot be "
                        f"converted without guessing ({why})")
    problems += stored_gear.first_join_problems(sg_src, cd["shared"]["flag_bitmask_0"])    # Phase 3F
    if problems:
        raise IncompatibleError("; ".join(problems))
    s, sb = cd["shared"], cb["shared"]
    img = WiiImage(base)
    log = {"de": [de_name, hashlib.sha256(de).hexdigest()], "base": [base_name, hashlib.sha256(base).hexdigest()],
           "lineage": lineage, "kept_from_base": [], "rewritten": []}

    def note(cat, kept):
        log["kept_from_base" if kept else "rewritten"].append(cat)

    # ---- flags (inverse Phase 2B map); story is flag 0x20
    fmap = canon.shared_flag_map()
    nflag = 0
    for t, g in fmap.items():
        v = s["flags"].get(t, 0)
        if fm.wii_get(base, g) != v:
            wii_set_flag(img, g, v)
            nflag += 1
    if fm.wii_get(base, 0x108) != (s["flag_bitmask_0"] & 0xFFFF):
        if s["flag_bitmask_0"] > 0xFFFF:
            raise IncompatibleError("DE 32-bit flag 0 does not fit the Wii 16-bit flag 0x108")
        wii_set_flag(img, 0x108, s["flag_bitmask_0"])
    log["flags_changed"] = nflag
    # ---- achievements
    if s["achievements"] == sb["achievements"]:
        note("achievements", True)
    else:
        note("achievements", False)
        for g, v in achievements.de_to_wii(de, T).items():
            if fm.wii_get(img.b, g) != v:
                wii_set_flag(img, g, min(v, 0xFFFF))
    # ---- quest counters: 3-way per quest (keep the base bytes when the DE bytes equal what the base converts to,
    # or when the quest is closed in both saves - counters of a closed quest are inert)
    nq = 0
    for q in range(qc.WII_N):
        o = qc.WII_QC + 8 * q
        de8 = de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8]
        st_de, st_b = fm.de_get(de, 0x220 + q), fm.wii_get(base, 0x220 + q)
        if lineage and (de8 == qc.wii_to_de(base, q) or (st_de in (254, 255) and st_de == st_b)):
            continue
        want = qc.de_to_wii(de, q)
        if bytes(img.b[o:o + 8]) != want:
            img.raw(o, want)
            nq += 1
    log["quest_counters_rewritten"] = nq
    # ---- inventory (slot identity when it fits; otherwise lossless compaction with reference remapping)
    remap, new_recs = {}, {}
    caps = wii_capacity(base)
    log["wii_capacity"] = caps
    referenced = {(sl, c["equipment"][sl]) for c in s["characters"].values() if c["equipment"] for sl in EQUIP
                  if c["equipment"][sl] is not None}
    for box in EQUIP:
        for r in s["inventory"][box].values():
            referenced |= {("gem", x[1]) for x in r["sockets"] if x and x[0] == "gem"}
    # Phase 3F (F1): while characters are away, keep the slots free that the game needs to give their gear back (a full
    # box makes the Wii/3DS skip a character's return); empty for every save without stored characters
    room = stored_gear.reunion_room(sg_src)
    if room:
        log["reunion_room"] = room
    for box, recs in s["inventory"].items():
        cap = caps[box]
        lim = cap - room.get(box, 0)
        deferred_slots = set(deferred.get("de_only_items", {}).get(box, {}))
        keep = {sl: r for sl, r in recs.items() if sl not in deferred_slots}
        if len(keep) > lim:
            why = f"the Wii capacity of this save ({cap})" if lim == cap else \
                f"the Wii capacity of this save ({cap}) less the {cap - lim} slots the game needs free to give the " \
                "stored equipment back at the party's reunion"
            if overflow != "sidecar":
                raise IncompatibleError(f"{box}: {len(keep)} items exceed {why}; "
                                        "rerun with overflow='sidecar' to keep the extra unequipped items in the sidecar")
            extra = [sl for sl in sorted(keep, reverse=True) if (box, sl) not in referenced][:len(keep) - lim]
            if len(keep) - len(extra) > lim:
                raise IncompatibleError(f"{box}: equipped/referenced items alone exceed {why}")
            for sl in extra:
                deferred.setdefault("overflow_items", {}).setdefault(box, {})[sl] = keep.pop(sl)
        used = {sl for sl in keep if sl < cap}
        free = (i for i in range(cap) if i not in used)
        m = {}
        for sl in sorted(keep):
            if sl < cap:
                m[sl] = sl
            else:
                try:
                    m[sl] = next(free)
                except StopIteration:
                    raise IncompatibleError(f"{box}: {len(keep)} items do not fit the Wii box ({cap} slots)")
        remap[box] = m
        new_recs[box] = {m[sl]: r for sl, r in keep.items()}
    log["compacted"] = {b: {o: n for o, n in m.items() if o != n} for b, m in remap.items() if any(o != n for o, n in m.items())}
    # acquisition order -> Wii ages (Phase 2F): dense 1..N with 1 = newest, as the Wii's own renumbering (0x80159488)
    # writes them. A box whose order is unchanged keeps the base's exact ages; otherwise every age of the box is
    # rewritten, so kept and re-encoded records never mix two numberings.
    ages, same_order = {}, {}
    for box in new_recs:
        new_recs[box] = canon.rerank(new_recs[box])
        n = len(new_recs[box])
        ages[box] = {sl: n + 1 - r["order"] for sl, r in new_recs[box].items()}
        same_order[box] = {sl: r["order"] for sl, r in sb["inventory"][box].items()} == \
            {sl: r["order"] for sl, r in new_recs[box].items()}
    log["ages_rewritten"] = sorted(b for b in new_recs if not same_order[b])
    gem_remap = remap["gem"]
    for box in EQUIP:  # equipment gem references follow the gem compaction
        for sl, r in new_recs[box].items():
            r["sockets"] = [["gem", gem_remap[x[1]]] if x and x[0] == "gem" else x for x in r["sockets"]]
    gem_desc = {}
    for sl, r in new_recs["gem"].items():
        gem_desc[sl] = encode_record("gem", r, T, {})[8:16]
    nrec = 0
    inv_remap = {b: {w: d for d, w in m.items()} for b, m in remap.items()}
    for box in ("gem",) + tuple(b for b in s["inventory"] if b != "gem"):
        typ, off, size, slots = WII_BOX[box]
        base_box = sb["inventory"][box]
        for i in range(WII_CAP[box]):  # physical slots: also clears stale base records beyond the usable capacity
            o = ITEM + off + size * i
            want_rec = new_recs[box].get(i)
            cur = bytes(img.b[o:o + size])
            if want_rec is None:
                if any(cur):
                    img.raw(o, bytes(size))
                    nrec += 1
                continue
            b_rec = base_box.get(i)
            # Phase 3C: with instance information, only the same physical item keeps the base's Wii-only bytes
            same = instances is None or (inv_remap[box].get(i) == i and i in instances.get(box, ()))
            if b_rec is not None and same and (lineage or box == "gem") and \
                    canon.strip_order(b_rec) == canon.strip_order(want_rec):
                if not same_order[box] and struct.unpack_from(">H", cur, 4)[0] != ages[box][i]:
                    img.put(o + 4, "H", ages[box][i])   # same item, same bytes: only its age changes
                    nrec += 1
                continue  # identical canonical record at the same slot: keep the exact base bytes
            enc = encode_record(box, want_rec, T, gem_desc, cur if same else None, ages[box][i])
            if box == "crystal" and base_box.get(i) is not None and same:
                enc = enc[:0x16] + cur[0x16:0x17] + enc[0x17:]   # keep the unknown base byte +0x16 when present
            if enc != cur:
                img.raw(o, enc)
                nrec += 1
    log["inventory_records_written"] = nrec
    # ---- characters 1..7
    mc = canon.main_chars(s["story"])      # Phase 3D: Fiora = 3 before scenario 275, 8 from 275
    for k, c in s["characters"].items():
        bc = sb["characters"].get(k) or _base_char(base, k)   # base from the other era: raw record values
        o = CHAR_BASE + CHAR_SIZE * k
        if c == bc:
            note(f"char{k}", True)
            continue
        note(f"char{k}", False)
        img.put(o + 0x17C, "I", c["level"])
        img.put(o + 0x2A4, "I", c["exp"])
        img.put(o + 0x2A8, "I", c["ap"])
        img.put(o + 0x284, "I", min(c["affinity_coins"], 999))
        img.put(o + 0x288, "5I", *c["skill_sp"])
        img.put(o + 0x29C, "I", c["skill_selected_tree"])
        old_acc = struct.unpack_from(">I", base, o + 0x2A0)[0]
        if lineage:
            gained = _char_exp_total(T, c["level"], c["exp"]) - _char_exp_total(T, bc["level"], bc["exp"])
            acc = max(0, old_acc + gained)
        else:
            acc = _char_exp_total(T, c["level"], c["exp"])
        img.put(o + 0x2A0, "I", acc)
        # equipment (party members only; others keep the base record's references, see canon)
        for i, sl in enumerate(EQUIP if c["equipment"] is not None else ()):
            bi = c["equipment"][sl]
            if bi is None:
                img.put(o + 0x02 + 2 * i, "H", 0)
                img.put(o + 0x0E + 2 * i, "H", 0)
                img.put(o + 0x1C + 2 * i, "H", 0xFFFF)
            else:
                ni = remap[sl].get(bi)
                if ni is None:
                    raise IncompatibleError(f"character {k} {sl} references DE slot {bi} with no item")
                r = new_recs[sl][ni]
                img.put(o + 0x02 + 2 * i, "H", r["gid"])
                img.put(o + 0x0E + 2 * i, "H", wii_row(r["gid"], WII_BOX[sl][0], T, sl))
                img.put(o + 0x1C + 2 * i, "H", ni)
        # arts (per character art index)
        for a in T["w_arts"].values():
            if a["pc"] == k and a["id"] in c["arts"]:
                lv, fl = c["arts"][a["id"]]
                img.put(o + 0xE8 + 2 * a["idx"], "BB", lv, fl)
        # palettes
        img.put(o + 0x129, "B", c["palette"][0])
        img.raw(o + 0x119, bytes(x & 0xFF for x in c["palette"][1:9]))
        if k == 1 and "palette2" in c:
            img.raw(o + 0x121, bytes(x & 0xFF for x in c["palette2"][:8]))
        # skill trees: node ids (learned count) + state bytes (base kept where the node is unchanged)
        for t in range(5):
            ro = o + 0x1F4 + 13 * t
            for e in range(5):
                nid = (k - 1) * 25 + 5 * t + e + 1 if e < c["skill_learned"][t] else 0
                old_id, old_st = base[ro + 2 + 2 * e], base[ro + 3 + 2 * e]
                st = old_st if old_id == nid else (2 if nid else 0)
                img.put(ro + 2 + 2 * e, "BB", nid, st)
        # skill links: rows 5..10 = the other six main characters in id order (Fiora's row shared by 3 and 8)
        others = [x for x in mc if x != k]
        for j, src in enumerate(others):
            ro = o + 0x1F4 + 13 * (5 + j)
            ids = c["links"].get(src, c["links"].get(str(src), [0] * 5))
            unl = c["link_unlock"].get(src, c["link_unlock"].get(str(src), 0))
            same = unl == bc["link_unlock"].get(src, bc["link_unlock"].get(str(src))) and \
                ids == bc["links"].get(src, bc["links"].get(str(src)))
            for e in range(5):   # Phase 2F: slots unlocked in DE (affinity coins) are unlocked on the Wii too
                st = base[ro + 3 + 2 * e] if same else (1 if ids[e] or e <= unl else 0)
                img.put(ro + 2 + 2 * e, "BB", ids[e], st)
    # ---- Fiora's skill object (record +0x1F4..+0x29F: skill trees, link rows, affinity coins, SP, selected tree) has a
    # copy in record 8 (identical in every real Wii save; 0x800A366C). The Wii game restores record 3 from that copy
    # when it loads a save (Phase 2F run d1_s232: DE skill progress reverted), so the copy must follow record 3.
    # Phase 3D: the copy goes both ways (0x800A3644: 3 -> 8, 0x800A366C: 8 -> 3); from scenario 275 the active
    # Fiora is record 8, so record 3 receives record 8's skill object.
    o3, o8 = CHAR_BASE + CHAR_SIZE * 3, CHAR_BASE + CHAR_SIZE * 8
    src_o, dst_o = (o8, o3) if canon.fiora(s["story"]) == 8 else (o3, o8)
    if img.b[o3 + 0x1F4:o3 + 0x2A0] != img.b[o8 + 0x1F4:o8 + 0x2A0]:
        img.raw(dst_o + 0x1F4, bytes(img.b[src_o + 0x1F4:src_o + 0x2A0]))
        log["fiora_skill_copy_synced"] = "8->3" if src_o == o8 else True
    # ---- Phase 3D defect D1: Wii-only character byte +0x118 (2C: "palette flag, unknown, low"). In every game-written
    # Wii/3DS save it is 1 for each character that has arts (2-10 from the start; 11-13 have none: 0); Shulk alone
    # starts at 0 and is 1 by story 150 (0 at stories 6, 8, 18 while he has no battle arts; his DE palette holds
    # them by story 20). The DE has no counterpart, so it came from the Wii base: an early base (e.g. the user's
    # story-8 3DS save used as 3DS template) left 0, and with Shulk leading at Fallen Arm (story 269) the 3DS game
    # overflows its stack on load and the Wii game hangs on the loading screen (runs x_s269_rejoin, wd_s269_flag0;
    # bisected to this byte, bs10_flag118). Set it to 1 from story 20 when the base still has 0.
    o1 = CHAR_BASE + CHAR_SIZE * 1
    if s["story"] >= SHULK_ARTS_FLAG_STORY and img.b[o1 + 0x118] == 0:
        img.put(o1 + 0x118, "B", 1)
        log["shulk_flag_118_set"] = f"base had 0 (base story {sb['story']}); set to 1 for story {s['story']}"
    # ---- characters outside the DE party: DE holds no equipment for them; a base reference into the regular
    # inventory (box index set) would now point at whatever item occupies that slot -> clear it. Wii staging
    # references (box index 0xFFFF with a gear id, slots 150+id) are kept.
    for k in mc:
        if k in s["party"]:
            continue
        o = CHAR_BASE + CHAR_SIZE * k
        for i, sl in enumerate(EQUIP):
            if struct.unpack_from(">H", img.b, o + 0x1C + 2 * i)[0] != 0xFFFF:
                img.put(o + 0x02 + 2 * i, "H", 0)
                img.put(o + 0x0E + 2 * i, "H", 0)
                img.put(o + 0x1C + 2 * i, "H", 0xFFFF)
                log.setdefault("absent_character_equipment_cleared", []).append(f"{k}.{sl}")
    # ---- Phase 3E: stored equipment of characters who are away -> references, staging records, staged gems (what the
    # Wii's leave routine 0x8007F368 writes); identical stored gear in the base keeps the base's bytes
    if sg_src:
        bir = wii_save.decode_bytes(base)
        dst = {}
        for k in sg_src:
            try:
                dst[k] = stored_gear.wii_read(base, bir, k)
            except stored_gear.StoredGearError:
                pass
        try:
            log["stored_gear_written"] = stored_gear.apply(
                "de_to_wii", sg_src, {}, dst, lambda k, g: stored_gear.write_wii(img, k, g, T))
        except stored_gear.StoredGearError as e:
            raise IncompatibleError(str(e))
    if s["story"] < sb["story"] and not lineage:
        log.setdefault("warnings", []).append(
            f"the Wii base is at a later story point ({sb['story']}) than the DE save ({s['story']}): Wii-only staging "
            "gear of characters who have not joined yet comes from the base; prefer a base from the same chapter")
    # ---- party, money, play time, map, position, collectopaedia, clock
    party = s["party"] + [0] * (12 - len(s["party"]))
    if s["party"] != sb["party"]:
        for i, p in enumerate(party):
            img.put(PARTY + 4 * i, "H", p)
    img.put(ITEM + 0x120E8, "I", min(s["money"], 999_999_999))
    pt = min(s["play_time_s"], 35999999)
    h, m, sec = pt // 3600, pt // 60 % 60, pt % 60
    if s["play_time_s"] != sb["play_time_s"]:
        img.put(0x11EB0, "I", h << 12 | m << 6 | sec)
        img.put(0x2A, "HH", h, m)
        img.put(0x23, "B", sec)
    area, sub = s["map"] & 0xFFFF, s["map"] >> 16
    if s["map"] != sb["map"]:
        name = ("%02d%02df" % (area, sub)).encode()
        for go in (0xB260, 0xB284):
            img.put(go, "I", s["map"])
            img.raw(go + 4, name + bytes(8 - len(name)))
        img.put(0x2E, "HH", area, sub)
    if s["position"] != sb["position"] or s["angle_rad"] != sb["angle_rad"]:
        x, y, z = s["position"]
        deg = struct.unpack(">f", struct.pack(">f", s["angle_rad"] * 57.29577951308232))[0]
        for i in range(3):
            img.put(0x11EE0 + 16 * i, "4f", x, y, z, deg)
    if s["collectopaedia"] != sb["collectopaedia"]:
        bits = bytearray(40)
        for cid in s["collectopaedia"]:
            bits[cid >> 3] |= 1 << (cid & 7)
        img.raw(0xEAC6, bytes(bits))
    if s["clock"] != sb["clock"]:
        c = s["clock"]
        img.put(0x11EB4, "f", 1800.0 * c["hour"] + 30.0 * c["minute"])
        img.put(0x11EB8, "H", c["day"])
    # THUM: scenario, play time, map, party portraits, leader level
    if s["story"] != sb["story"]:
        img.put(0x20, "H", s["story"])
    if s["party"] != sb["party"]:
        for i in range(7):
            img.put(0x34 + 4 * i, "I", party[i])
    lead = s["party"][0]
    img.put(0x84, "H", s["characters"][lead]["level"] if lead in s["characters"] else struct.unpack_from(">H", base, 0x84)[0])
    if s["party"][:1] != sb["party"][:1] and lead in LEADER_NAME:
        # THUM +0x64: the save-list leader name (first NUL-terminated string; the game rewrites it on every save)
        nm = LEADER_NAME[lead].encode() + bytes(1)
        img.raw(0x64, nm)
    # ---- foreign base: reset Wii-only per-playthrough regions
    if not lineage:
        for m_ in minimap.SHARED_MAPS + [20, 26]:
            if m_ in minimap.WII_MAPS:
                b0 = minimap.WII_MAPS[m_][4]
                n = 576 * minimap.WII_MAPS[m_][3] + 1
                for bit in range(b0, b0 + n):
                    o = minimap.WII_BITS_FILE + (bit >> 3)
                    if img.b[o] >> (bit & 7) & 1:
                        img.b[o] &= ~(1 << (bit & 7)) & 0xFF
                        img.ranges.append((o, 1))
        for tag, hdr, s0, e0 in wii_save.SECTIONS:
            if tag in ("TBOX", "MINE"):
                img.raw(s0, bytes(e0 - s0))
        log["foreign_base_reset"] = ["minimap", "TBOX", "MINE"]
    # ---- minimap exploration (strict, OR-merge)
    fix_crcs(img)
    ch = minimap.de_to_wii(de, bytes(img.b), min_fraction=minimap_min_fraction)
    for o_, v in ch.items():
        img.b[o_] = v
        img.ranges.append((o_, 1))
    log["minimap_bytes"] = len(ch)
    fix_crcs(img)
    out = bytes(img.b)
    reimport_blockers(out, T)
    log["bytes_changed_vs_base"] = sum(1 for a, b in zip(out, base) if a != b)
    log["deferred_categories"] = sorted(deferred)
    log["remap"] = {b: m for b, m in remap.items()}
    return out, log, deferred


def reimport_blockers(out, T):
    """Closure check (Phase 2F): the Wii file must pass the same mapping checks a later Wii -> DE conversion applies
    (tools/phase2c: gem rank/chance against BTL_skill, crystal table rows, skill-tree ids, levels, references...).
    Otherwise a DE state could be exported to the Wii and then never come back."""
    import phase2c
    pc, tal = phase2c.main("<de_to_wii output>", write=False, wii_bytes=out, T=T)
    bad = {c: e for c, e in tal.c.items() if e["unresolved"] and c.startswith(("inventory:", "char:"))
           and c not in ("char:exp_accum", "char:equipment_ref(inactive)")}
    if bad:
        rows = [f"{r[0]} {r[1]}: {r[4]}" for r in tal.rows if r[0] in bad and not r[3]][:5]
        raise IncompatibleError("the Wii file would not convert back to DE (state the Wii mapping does not accept): "
                                + "; ".join(rows))


def verify(out, de, T, deferred=None, remap=None):
    """Independent read-back: canonical(Wii out) vs canonical(DE) over the shared fields. Returns [(path, wii, de)].
    DE inventory slots are mapped through the compaction remap (and gem/equipment references with them); deferred
    items (sidecar) are removed from the DE side; award counters are compared separately (achievements.de_to_wii
    is a documented lossy projection)."""
    cw = canon.from_wii(out, T)["shared"]
    cd = canon.from_de(de, T)["shared"]
    remap = remap or {}
    for kind in ("de_only_items", "overflow_items"):
        for box, slots in (deferred or {}).get(kind, {}).items():
            for sl in slots:
                cd["inventory"][box].pop(sl, None)
    for box, m in remap.items():
        cd["inventory"][box] = {m.get(sl, sl): r for sl, r in cd["inventory"][box].items()}
    for box in cd["inventory"]:
        cd["inventory"][box] = canon.rerank(cd["inventory"][box])
    gm = remap.get("gem", {})
    for box in EQUIP:
        for r in cd["inventory"][box].values():
            r["sockets"] = [["gem", gm.get(x[1], x[1])] if x and x[0] == "gem" else x for x in r["sockets"]]
    for c in cd["characters"].values():
        if c["equipment"] is not None:
            c["equipment"] = {sl: (remap.get(sl, {}).get(v, v) if v is not None else None) for sl, v in c["equipment"].items()}
    cw.pop("achievements"), cd.pop("achievements")
    return canon.compare(cw, cd)
