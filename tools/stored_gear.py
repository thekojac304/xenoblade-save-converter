"""Stored equipment of temporarily absent party members (Phase 3D defect D2; translated from Phase 3E).

When a main character leaves the party in a story event, both games park the gear he/she wears and give it back at
the return. Layouts (STORED_EQUIPMENT_MAPPING.md has the evidence):

  * DE: table at 0x3BB50, 7 entries x 0xB4 per character (k = 1..35), entry j = equipment slot (head, body, arm,
    legs, feet, weapon; the 7th is unused): the 0x30 equipment record as it was in the inventory (+0 its old box slot,
    sockets: normal = 3<<16 | gem slot, fixed = 1<<16 | gem id) followed by verbatim copies of the gem records it
    referenced (3 x 0x2C, matched by their own +0 slot field). The character's equipment references become (0, 0).
    At the return the DE re-adds every item and gem in free slots with new serials and clears the entries
    [game: public saves 283 -> 288 -> 291; 3C Monado runs 156 -> 158 -> 160].
  * Wii / New 3DS (same layout): routine 0x8007F368 (leave = 0, join = 1). Leave, per slot: the equipped 0x34-byte
    inventory record is copied to the staging record at box slot 150 + k (k = 1..11, getter 0x80158308), every
    socketed gem is copied to the character's staged-gem table (8 records of 16 bytes at item +0x11AB8 +
    16 * (8 * (k - 1) + i), getter 0x80158308 type 3) with a 2-byte link at item +0x12038 + 2 * (8 * (k - 1) + i)
    (byte 0 = slot + 1, byte 1 = socket; getter 0x80158414), originals deleted, the reference keeps only the gear id
    (row 0, box index 0xFFFF). Join, per slot: a NEW item is created from the reference's gear id (empty weapon ->
    default weapon), its socket count taken from the staging record (max 4), the staged gems re-added to the gem box
    and socketed by their links, links cleared. Staging records are not cleared (stale ones remain).

Canonical form (canon shared["stored_gear"], only for characters it applies to): {k: {"slots": {slot: equipment
record or None}, "gems": [gem records]}} - equipment records as in the inventory, a socketed gem = ["gem", i] with i
an index into "gems" (slot order, then socket order = the Wii's link order).

Characters it applies to ("stored characters"): main characters of the current era (canon.main_chars) absent from the
party, other than Fiora's retired record 3, who have joined already (scenario >= first scenario in the party journal
JNL_PCrelatelist: Shulk/Reyn 1, Sharla 70, Dunban 100, Melia 128, Riki 137, Fiora 8 275 - before that the slot holds
scripted prologue gear, e.g. Dunban's prologue Monado at stories 6-23, which the converter leaves to the base as
before)."""
import struct

import canon

STASH, ENTRY, PER_CHAR, STASH_END = 0x3BB50, 0xB4, 7, 0x46900
SLOTS = ("head", "body", "arm", "legs", "feet", "weapon")
DE_TYPE = {"head": 4, "body": 5, "arm": 6, "legs": 7, "feet": 8, "weapon": 2}
W_GEMS, W_LINKS, W_MAX_GEMS = 0x11AB8, 0x12038, 8      # relative to wii_save.ITEM
DEF_COLS = ("def_wpn", "def_head", "def_body", "def_arm", "def_waist", "def_legg",
            "melia_def_wpn", "melia_def_head", "melia_def_body", "melia_def_arm", "melia_def_waist", "melia_def_legg")
NAMES = {1: "Shulk", 2: "Reyn", 3: "Fiora", 4: "Dunban", 5: "Sharla", 6: "Riki", 7: "Melia", 8: "Fiora"}
# characters whose stored equipment has been converted and returned by a game in a played reunion (REUNION_VALIDATION
# .md: 1, 2, 4, 5, 6 returned on the Wii / 3DS / DE; 7 stored by the Wii and 3DS games themselves and read back equal
# to the DE's). Phase 3F: Fiora's later form (8) - the 288 -> 291 reunion played on the DE (native) and on the 3DS from
# a converted save (FIORA_REUNION_GAMEPLAY_TESTS.md); the join routine has no character-specific path and her
# first-join initialisation is gated by the join mask (see first_join_problems).
VALIDATED = {1, 2, 4, 5, 6, 7, 8}
# Phase 3F: the Wii/3DS party update (0x8007FB98) runs a one-time initialisation for character 8 (level, seed from
# record 3) when bit 8 of the join mask (Wii flag 0x108 = DE 32-bit flag 0 = canonical flag_bitmask_0, read and set by
# 0x80082D28) is clear. A stored Fiora-8 with that bit clear would be re-initialised at her return: refused.
FIRST_JOIN_GUARDED = (8,)


class StoredGearError(Exception):
    """Stored gear that cannot be read or represented without guessing."""


def _rows(t):
    rows = t["rows"] if isinstance(t, dict) and "rows" in t else t
    return rows if isinstance(rows, list) else list(rows.values())


def defaults(T):
    return {r["id"]: {r[c] for c in DEF_COLS if c in r} for r in _rows(T["de"]["BTL_pclist"])}


def joined_from(T):
    """{character: first scenario in the party journal} (JNL_PCrelatelist flg_s1/flg_s2)."""
    out = {}
    for r in _rows(T["de"]["JNL_PCrelatelist"]):
        starts = [v for v in (r.get("flg_s1"), r.get("flg_s2")) if v]
        if starts:
            out[r["pc_id"]] = min(starts + [out.get(r["pc_id"], 10 ** 6)])
    return out


def stored_chars(story, party, T):
    joined = joined_from(T)
    return [k for k in canon.main_chars(story)
            if k not in party and k != 3 and story >= joined.get(k, 10 ** 6)]


# ------------------------------------------------------------------------------------------------- gear-id views
def de_stored(de, k):
    """{slot: gear id} of character k's DE stored-equipment entries (0 = empty)."""
    out = {}
    for j, sl in enumerate(SLOTS):
        o = STASH + ENTRY * (PER_CHAR * (k - 1) + j)
        out[sl] = struct.unpack_from("<H", de, o + 4)[0] if any(de[o:o + ENTRY]) else 0   # +0 slot, +2 type, +4 id
    return out


def wii_stored(ir, k):
    """{slot: gear id} of character k's Wii staging records (slot 150 + k), from wii_save.decode_bytes."""
    out = {sl: 0 for sl in SLOTS}
    if not 1 <= k <= 11:
        return out
    for sl in SLOTS:
        for r in ir["items"][sl]:
            if r["index"] == 150 + k:
                out[sl] = r["header"]["gid"]
    return out


def departed(stored_of, story, party, T):
    """{k: {slot: gid}} of stored characters holding non-default gear (3D refusal rule, kept for reports)."""
    dfl = defaults(T)
    out = {}
    for k in stored_chars(story, party, T):
        g = stored_of(k)
        if any(v and v not in dfl.get(k, ()) for v in g.values()):
            out[k] = g
    return out


# ------------------------------------------------------------------------------------------------- canonical readers
def _de_gem(g):
    return {"gid": struct.unpack_from("<H", g, 4)[0], "qty": 1, "effect": struct.unpack_from("<H", g, 0x1C)[0],
            "rank": g[0x16], "strength": g[0x1E], "chance": g[0x1F]}


def de_read(de, k):
    """Canonical stored gear of character k from the DE table."""
    slots, gems = {}, []
    for j, sl in enumerate(SLOTS):
        o = STASH + ENTRY * (PER_CHAR * (k - 1) + j)
        e = de[o:o + ENTRY]
        gid = struct.unpack_from("<H", e, 4)[0]
        if not e[0x10] or gid == 0:
            slots[sl] = None
            continue
        grec = {}
        for g in range(3):
            gb = e[0x30 + 0x2C * g:0x30 + 0x2C * (g + 1)]
            if gb[0x10]:              # present byte, as in the inventory (leftover bytes of empty records are ignored)
                gi = struct.unpack_from("<H", gb, 0)[0]
                if gi in grec:
                    raise StoredGearError(f"{NAMES.get(k, k)} {sl}: two stored gems with the same slot number")
                grec[gi] = gb
        socks, used = [], set()
        for s in range(3):
            normal, fixed = struct.unpack_from("<II", e, 0x18 + 8 * s)
            if fixed >> 16 == 1:
                socks.append(["fixed", fixed & 0xFFFF])
            elif normal >> 16 == 3:
                gb = grec.get(normal & 0xFFFF)
                if gb is None:
                    raise StoredGearError(f"{NAMES.get(k, k)} {sl}: socket {s} names a gem that is not stored with it")
                used.add(normal & 0xFFFF)
                gems.append(_de_gem(gb))
                socks.append(["gem", len(gems) - 1])
            else:
                socks.append(None)
        if set(grec) - used:
            raise StoredGearError(f"{NAMES.get(k, k)} {sl}: a stored gem belongs to no socket")
        while socks and socks[-1] is None:
            socks.pop()
        slots[sl] = {"gid": gid, "qty": max(struct.unpack_from("<H", e, 8)[0], 1), "socket_count": e[0x15],
                     "sockets": socks}
    return {"slots": slots, "gems": gems}


def wii_read(wii, ir, k):
    """Canonical stored gear of character k from the Wii/3DS layout (reference gear ids, staging records, staged gems).
    The game rebuilds an item from the reference's gear id, so a staging record with another id is not guessed at."""
    import wii_save
    I = wii_save.ITEM
    refs = ir["characters"][k]["equipment"]
    links = {}
    for i in range(W_MAX_GEMS):
        a, b = wii[I + W_LINKS + 2 * (W_MAX_GEMS * (k - 1) + i):I + W_LINKS + 2 * (W_MAX_GEMS * (k - 1) + i) + 2]
        if a:
            if (a - 1, b) in links:
                raise StoredGearError(f"{NAMES.get(k, k)}: two staged gems for slot {a - 1} socket {b}")
            links[(a - 1, b)] = i
    slots, gems, used = {}, [], set()
    for j, sl in enumerate(SLOTS):
        gid = refs[sl]["gid"]
        if not gid or refs[sl]["box_index"] is not None:
            if refs[sl]["box_index"] is not None:
                raise StoredGearError(f"{NAMES.get(k, k)} is away but still has {sl} equipped from the inventory")
            slots[sl] = None
            continue
        st = next((r for r in ir["items"][sl] if r["index"] == 150 + k), None)
        if st is None or st["header"]["gid"] != gid:
            raise StoredGearError(f"{NAMES.get(k, k)} {sl}: the staging record does not hold gear {gid}")
        socks = []
        for s, sock in enumerate(st["sockets"]):
            if (j, s) in links:
                i = links[(j, s)]
                gb = wii[I + W_GEMS + 16 * (W_MAX_GEMS * (k - 1) + i):I + W_GEMS + 16 * (W_MAX_GEMS * (k - 1) + i + 1)]
                h, g = wii_save.item_header(gb), wii_save.gem_desc(gb[8:16])
                if h["type"] != 3 or not h["gid"]:
                    raise StoredGearError(f"{NAMES.get(k, k)} {sl}: staged gem {i} is empty")
                gems.append({"gid": 0 if h["gid"] == canon.CRAFTED_GEM_GID else h["gid"], "qty": 1,
                             "effect": g["effect"], "rank": g["rank"], "strength": g["strength"], "chance": g["chance"]})
                socks.append(["gem", len(gems) - 1])
                used.add(i)
            elif sock["desc"] is not None and sock["gem_box_ref"] is None:
                socks.append(["fixed", sock["desc"]["gid"]])
            elif sock["desc"] is not None:
                raise StoredGearError(f"{NAMES.get(k, k)} {sl}: socketed gem {s} has no staged copy")
            else:
                socks.append(None)
        while socks and socks[-1] is None:
            socks.pop()
        if len(socks) > 3:
            raise StoredGearError(f"{NAMES.get(k, k)} {sl}: a 4th socket is used (the DE has 3)")
        slots[sl] = {"gid": gid, "qty": max(st["header"]["qty"], 1), "socket_count": st["slot_count"], "sockets": socks}
    if set(links.values()) - used:
        raise StoredGearError(f"{NAMES.get(k, k)}: a staged gem belongs to no stored item")
    return {"slots": slots, "gems": gems}


def wii_raw_signature(wii, k):
    """Every Wii/3DS byte that defines character k's stored gear: equipment references, the six staging records and
    the character's staged-gem records and links (used to tell whether a Wii/3DS session changed it)."""
    import de_to_wii as d2w
    import wii_save
    I = wii_save.ITEM
    o = d2w.CHAR_BASE + d2w.CHAR_SIZE * k
    parts = [wii[o + 0x02:o + 0x0E], wii[o + 0x0E:o + 0x1A], wii[o + 0x1C:o + 0x28]]
    if 1 <= k <= 11:
        for sl in SLOTS:
            typ, off, size, _ = d2w.WII_BOX[sl]
            parts.append(wii[I + off + size * (150 + k):I + off + size * (151 + k)])
        n = W_MAX_GEMS * (k - 1)
        parts.append(wii[I + W_GEMS + 16 * n:I + W_GEMS + 16 * (n + W_MAX_GEMS)])
        parts.append(wii[I + W_LINKS + 2 * n:I + W_LINKS + 2 * (n + W_MAX_GEMS)])
    return b"".join(parts)


def read_all(game, raw, story, party, T, ir=None):
    """-> ({k: canonical stored gear} for the stored characters, {k: error text})."""
    out, bad = {}, {}
    for k in stored_chars(story, party, T):
        try:
            out[k] = de_read(raw, k) if game == "de" else wii_read(raw, ir, k)
        except StoredGearError as e:
            bad[k] = str(e)
    return out, bad


# ------------------------------------------------------------------------------------------------- reunion room (3F)
def reunion_room(stored):
    """{box: free slots the Wii/3DS game needs when the stored characters come back} (Phase 3F defect F1).

    Join routine 0x8007F368 creates one NEW item per stored slot (an empty weapon slot gets the default weapon,
    0x8003B148) through 0x80158EEC and re-adds every staged gem to the gem box. When a box is full the add fails, the
    routine returns 0 at once and the game skips the rest of that character's return: the character is back in the
    party while the references still name staged gear [code; game: Azahar x2_s288_reunion - Shulk and Reyn skipped in
    a 3DS save whose boxes were converted full]. The box capacity (getter 0x80158490: 60 + 10 per bit of item
    +0x12108 + bonus) only grows when characters 3, 5, 6, 7, 8 or 11 join (0x80157CD8, table 0x8052F6B8), so the
    converter keeps this many slots free instead of relying on that."""
    need = {}
    for g in stored.values():
        for sl in SLOTS:
            if g["slots"].get(sl) is not None or sl == "weapon":
                need[sl] = need.get(sl, 0) + 1
        if g["gems"]:
            need["gem"] = need.get("gem", 0) + len(g["gems"])
    return need


def first_join_problems(stored, bitmask, names=NAMES):
    """Refusal texts for stored characters whose first-join bit is clear in the join mask (FIRST_JOIN_GUARDED)."""
    return [f"{names.get(k, k)} is away from the party, but the save does not record her first joining (join flag "
            f"bit {k} is clear); the game would reset her at the return, so the stored equipment is not converted"
            for k in stored if k in FIRST_JOIN_GUARDED and not (bitmask >> k) & 1]


def unfinished_returns(ir, story):
    """{k: [slots]} of current-era main characters IN the party whose Wii/3DS equipment references still name staged
    gear (gear id with box index 0xFFFF): the game skipped their return (F1). Converting would drop that gear."""
    out = {}
    for k in ir["party"]:
        if k not in canon.main_chars(story):
            continue
        eq = ir["characters"][k]["equipment"]
        slots = [sl for sl in SLOTS if eq[sl]["gid"] and eq[sl]["box_index"] is None]
        if slots:
            out[k] = slots
    return out


def unfinished_message(unfinished, names=NAMES):
    who = ", ".join(names.get(k, f"character {k}") for k in unfinished)
    return (f"{who}: back in the party, but the game has not given back the equipment it kept during the story "
            "separation (it is still held in the game's stored-equipment records). The Wii/3DS game skips a return "
            "when an equipment pocket is full at that moment. Converting this save would lose that equipment, so it "
            "is not converted (nothing written)")


# ------------------------------------------------------------------------------------------------- writers
def write_wii(img, k, sg, T):
    """Character k's stored gear into a WiiImage (de_to_wii.WiiImage): references, staging records, staged gems -
    exactly what the Wii's leave routine writes."""
    import de_to_wii as d2w
    import wii_save
    if len(sg["gems"]) > W_MAX_GEMS:
        raise d2w.IncompatibleError(f"{NAMES.get(k, k)} has {len(sg['gems'])} socketed gems stored; the Wii keeps "
                                    f"at most {W_MAX_GEMS} for an absent character")
    I = wii_save.ITEM
    o = d2w.CHAR_BASE + d2w.CHAR_SIZE * k
    gdesc = {i: d2w.encode_record("gem", g, T, {})[8:16] for i, g in enumerate(sg["gems"])}
    links = []
    for j, sl in enumerate(SLOTS):
        r = sg["slots"][sl]
        typ, off, size, _ = d2w.WII_BOX[sl]
        so = I + off + size * (150 + k)
        if r is None:
            img.put(o + 0x02 + 2 * j, "H", 0)
            img.put(o + 0x0E + 2 * j, "H", 0)
            img.put(o + 0x1C + 2 * j, "H", 0xFFFF)
            img.raw(so, bytes(size))
            continue
        if any(s and s[0] == "gem" for s in r["sockets"][3:]):
            raise d2w.IncompatibleError(f"{NAMES.get(k, k)} {sl}: 4th socket")
        enc = bytearray(d2w.encode_record(sl, r, T, gdesc, None, 0))
        for s in range(4):                                   # staged copies carry no gem-box reference
            struct.pack_into(">H", enc, 0x28 + 2 * s, 0xFFFF)
        img.raw(so, bytes(enc))
        img.put(o + 0x02 + 2 * j, "H", r["gid"])
        img.put(o + 0x0E + 2 * j, "H", 0)                    # row 0 while staged (game-written saves)
        img.put(o + 0x1C + 2 * j, "H", 0xFFFF)
        for s, sock in enumerate(r["sockets"]):
            if sock and sock[0] == "gem":
                links.append((j, s, sock[1]))
    for i in range(W_MAX_GEMS):
        lo = I + W_LINKS + 2 * (W_MAX_GEMS * (k - 1) + i)
        go = I + W_GEMS + 16 * (W_MAX_GEMS * (k - 1) + i)
        if i < len(links):
            j, s, gi = links[i]
            img.raw(lo, bytes([j + 1, s]))
            img.raw(go, d2w.encode_record("gem", sg["gems"][gi], T, {}))
        else:
            img.raw(lo, bytes(2))
            img.raw(go, bytes(16))


def write_de(b, k, sg, T, tpl):
    """Character k's stored gear into a DE image (bytearray): table entries as the DE writes them at a leave. Old-slot
    numbers (+0) are free slots of the output's boxes; serials come from the DE counters."""
    import convert
    import de_save
    import de_to_wii as d2w
    boxes = {n: (t, off, size) for n, t, off, size, _ in de_save.BOXES}
    used = {}

    def free(box):
        t, off, size = boxes[box]
        u = used.setdefault(box, {i for i in range(500) if b[off + size * i + 0x10]})
        i = next(x for x in range(500) if x not in u)
        u.add(i)
        return i

    def serial(typ):
        so = de_save.SERIALS + 4 * typ
        v = struct.unpack_from("<I", b, so)[0]
        struct.pack_into("<I", b, so, v + 1)
        return v

    gt, goff, gsize = boxes["gem"]
    gpat = convert.empty_pattern(tpl, goff, gsize, 500)
    for j, sl in enumerate(SLOTS):
        o = STASH + ENTRY * (PER_CHAR * (k - 1) + j)
        r = sg["slots"][sl]
        if r is None:
            b[o:o + ENTRY] = bytes(ENTRY)
            continue
        typ, off, size = boxes[sl]
        rec = bytearray(convert.empty_pattern(tpl, off, size, 500))
        struct.pack_into("<HHHHH", rec, 0, free(sl), typ, r["gid"], typ, r["qty"])
        if sl != "weapon":
            rec[0x14] = T["w_equip"][d2w.wii_row(r["gid"], DE_TYPE[sl], T, sl)]["arm_type"]
        rec[0x15] = r["socket_count"]
        gems = []
        for s, sock in enumerate(r["sockets"][:3]):
            if sock is None:
                continue
            if sock[0] == "fixed":
                struct.pack_into("<HH", rec, 0x1C + 8 * s, sock[1], 1)
            else:
                g = sg["gems"][sock[1]]
                gi = free("gem")
                grec = bytearray(gpat)
                struct.pack_into("<HHHHH", grec, 0, gi, gt, g["gid"], gt, 1)
                grec[0x16], grec[0x17] = g["rank"], T["d_skill"][g["effect"]]["atr_type"]
                grec[0x19] = 0
                struct.pack_into("<HHBB", grec, 0x1A, 1, g["effect"], g["strength"], g["chance"])
                struct.pack_into("<I", grec, 0xC, serial(gt))
                grec[0x10], grec[0x11] = 1, 0
                gems.append(bytes(grec))
                struct.pack_into("<HH", rec, 0x18 + 8 * s, gi, 3)
        struct.pack_into("<I", rec, 0xC, serial(typ))
        rec[0x10], rec[0x11] = 1, 0
        ent = bytes(rec) + b"".join(gems) + bytes(0x2C * (3 - len(gems)))
        b[o:o + ENTRY] = ent


def apply(direction, src_stored, src_bad, dest_stored, write, names=NAMES):
    """Shared policy. Writes each stored character whose canonical stored gear differs from the destination's (equal
    ones keep the destination's bytes: unchanged returns stay byte-identical). Refuses on unreadable source data.
    -> list of characters written."""
    if src_bad:
        raise StoredGearError("; ".join(f"{names.get(k, k)}: {v}" for k, v in src_bad.items()) +
                              " - the stored equipment of this character cannot be converted without guessing")
    todo = [k for k, sg in src_stored.items() if dest_stored.get(k) != sg]
    unproven = [k for k in todo if k not in VALIDATED and any(src_stored[k]["slots"].values())]
    if unproven:
        raise StoredGearError(
            f"{', '.join(names.get(k, f'character {k}') for k in unproven)} is away from the party in a story event "
            "and the game is keeping that equipment until the return. Converting stored equipment is validated in "
            "real reunions for Shulk, Reyn, Dunban, Sharla, Riki, Melia and Fiora's later form only, so this save is "
            "not converted (nothing written). Convert after the reunion, or keep playing this save on the same "
            "platform until then")
    done = []
    for k in todo:
        sg = src_stored[k]
        write(k, sg)
        done.append(k)
    return done
