"""Phase 2C: Wii character/inventory IR -> DE v10 mapping dry run and per-category completion report (read-only).

Builds the Wii IR (wii_save.py), checks every entry against the Wii and DE game tables, and computes the DE
value each entry would take. Nothing is written to any save: outputs go to data/ and tables/ only.

  python phase2c.py <wii monadoNN> [<DE v10 template.sav>]

Outputs: data/phase2c_ir.json (IR + planned DE values), tables/phase2c_completion.tsv, tables/phase2c_entries.tsv
"""
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import de_save  # noqa: E402
import flagmap  # noqa: E402
import wii_save  # noqa: E402

ROOT = os.path.join(HERE, "..")
MAIN = [1, 2, 3, 4, 5, 6, 7, 8]
RANKS = "EDCBAS"
BOX_TYPE = {"head": 4, "body": 5, "arm": 6, "legs": 7, "feet": 8, "weapon": 2, "crystal": 9, "gem": 3,
            "collectable": 10, "material": 11, "keyitem": 12, "artmanual": 13}
DE_SLOTS = 500
CRAFTED_GEM_GID = 3747  # Wii placeholder item for crafted gems; DE stores 0 (hashcade gems.md, 0xC259C)
MEDIUM_SKILLS, HEAVY_SKILLS = {1, 26, 51, 76, 101}, {31, 98, 115, 141}


def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def tables():
    import paths
    w = _load_json(paths.data("bdat_wii.json"))
    d = _load_json(paths.data("bdat_de.json"))
    rows = lambda t, n: {r["id"]: r for r in t[n]["rows"]}
    return w, d, {
        "w_item": rows(w, "ITM_itemlist"), "d_item": rows(d, "ITM_itemlist"),
        "w_arts": rows(w, "pc_arts"), "d_arts": rows(d, "pc_arts"),
        "w_psv": rows(w, "BTL_PSVskill"), "d_psv": rows(d, "BTL_PSVskill"),
        "w_skill": rows(w, "BTL_skilllist"), "d_skill": rows(d, "BTL_skilllist"),
        "w_grow": rows(w, "BTL_growlist"), "w_equip": rows(w, "ITM_equiplist"), "w_wpn": rows(w, "ITM_wpnlist"),
        "w_drop": rows(w, "ITM_dropcrystallist"), "w_crys": rows(w, "ITM_crystallist"),
        "d_equip": rows(d, "ITM_equiplist"), "d_wpn": rows(d, "ITM_wpnlist"), "w_link": rows(w, "BTL_PSVlink"),
    }


class Tally:
    """Per-category counters: present / decoded / mapped / unresolved + evidence label."""

    def __init__(self):
        self.c = collections.OrderedDict()
        self.rows = []

    def add(self, cat, ident, decoded, mapped, note="", evidence="", de_value=None):
        e = self.c.setdefault(cat, {"present": 0, "decoded": 0, "mapped": 0, "unresolved": 0, "evidence": set(),
                                    "notes": collections.Counter()})
        e["present"] += 1
        e["decoded"] += bool(decoded)
        e["mapped"] += bool(mapped)
        e["unresolved"] += not mapped
        if evidence:
            e["evidence"].add(evidence)
        if note:
            e["notes"][note] += 1
        self.rows.append((cat, ident, int(bool(decoded)), int(bool(mapped)), note, evidence,
                          json.dumps(de_value, separators=(",", ":")) if de_value is not None else ""))


def map_items(ir, T, tal):
    """Inventory boxes. DE slot = Wii index (identity allocation; 150 <= 500), DE serial = Wii serial."""
    planned = {}
    gem_index = {g["index"]: g for g in ir["items"]["gem"]}
    for box, recs in ir["items"].items():
        if box == "tail":
            continue
        typ = BOX_TYPE[box]
        out = []
        for r in recs:
            h = r["header"]
            cat = f"inventory:{box}"
            if r.get("area", "inventory") != "inventory":
                tal.add(f"staging:{box}", r["index"], True, False, "Wii per-character staging slot (150+charId); "
                        "not player inventory, no DE counterpart", "C:0x80158308")
                continue
            if box == "crystal":
                c = r["crystal"]
                effs = [e for e in c["effects"] if e]
                if c["kind"] == "drop":  # ITM_dropcrystallist row in the header
                    t = T["w_drop"][h["row"]]
                    ok = (t["rank"], t["atr_type"], t["cylinder"]) == (c["rank"], c["atr_type"], c["cylinder"]) and                         effs == [t["skill1"]] + ([] if t["cylinder"] else [t["skill2"]])
                elif c["kind"] == "list":  # global crystal item
                    wi = T["w_item"].get(gid := h["gid"])
                    t = T["w_crys"].get(wi["itemID"]) if wi and wi["itemType"] == 9 else None
                    ok = bool(t) and t["atr_type"] == c["atr_type"] and t["rank_type_low"] <= c["rank"] <=                         t["rank_type_up"] and len(effs) <= t["skill_max"] and c["source"] == 0
                elif c["kind"] == "cylinder":  # crafting cylinder: header id = effect
                    ok = h["gid"] == h["row"] == effs[0] and len(effs) == 1 and c["cylinder"] == 1 and                         T["w_skill"][effs[0]]["atr_type"] == c["atr_type"]
                else:
                    ok = False
                ok = ok and all(T["w_skill"].get(e) and T["d_skill"].get(e) for e in effs) and h["qty"] == 1
                tal.add(cat, r["index"], ok, ok, "" if ok else "crystal table check failed",
                        "C:0x8052FA48 vtable, DE 0xC19D0/0xBF15C D:BDAT", {"kind": c["kind"], "effects": effs})
                continue
            gid = h["gid"]
            wi, di = T["w_item"].get(gid), T["d_item"].get(gid)
            hdr_ok = wi is not None and wi["itemType"] == typ == h["type"] and wi["itemID"] == h["row"]
            if box == "gem":
                g = r["desc"]
                hdr_ok = h["type"] == 3 and h["row"] == g["effect"] and (
                    gid == CRAFTED_GEM_GID or (wi is not None and wi["itemType"] == 3 and wi["itemID"] == g["effect"]))
                sk = T["w_skill"].get(g["effect"])
                ok = sk is not None and 1 <= g["rank"] <= 6 and g["chance"] == sk["percent_" + RANKS[g["rank"] - 1]]
                in_range = ok and sk["lower_" + RANKS[g["rank"] - 1]] <= g["strength"] <= sk["upper_" + RANKS[g["rank"] - 1]]
                crafted = gid == CRAFTED_GEM_GID
                dsk = T["d_skill"].get(g["effect"])
                de = {"slot": r["index"], "gid": 0 if crafted else gid, "rank": g["rank"],
                      "attribute": dsk["atr_type"] if dsk else None, "effect": g["effect"], "strength": g["strength"],
                      "chance": g["chance"], "serial": h["serial"], "qty": 1}
                mapped = hdr_ok and ok and dsk is not None and (crafted or di is not None)
                tal.add(cat, r["index"], hdr_ok and ok, mapped,
                        "" if in_range else "strength outside table range for rank (kept verbatim)",
                        "C:0x80156380 D:BDAT", de)
                out.append(de)
                continue
            same = di is not None and wi is not None and (di["itemType"], di["itemID"]) == (wi["itemType"], wi["itemID"])
            de = {"slot": r["index"], "index": r["index"], "type": typ, "gid": gid, "qty": h["qty"], "serial": h["serial"]}
            if box in ("head", "body", "arm", "legs", "feet", "weapon"):
                sockets, bad = [], False
                for s, sock in enumerate(r["sockets"]):
                    if sock["desc"] is None:
                        continue
                    if s >= 3:
                        bad = True  # DE has three sockets
                    if sock["gem_box_ref"] is None:
                        sockets.append({"socket": s, "fixed_gid": sock["desc"]["gid"]})
                    else:
                        tgt = gem_index.get(sock["gem_box_ref"])
                        same_desc = tgt is not None and tgt["raw8"] == sock["raw"]
                        bad |= not same_desc
                        sockets.append({"socket": s, "normal_gem_index": sock["gem_box_ref"], "desc_matches_box": same_desc})
                de.update(socket_count=r["slot_count"], sockets=sockets)
                mapped = hdr_ok and same and not bad
                tal.add(cat, r["index"], hdr_ok, mapped, "" if mapped else "socket/ID check failed", "C:0x80158490 D", de)
            else:
                mapped = hdr_ok and same and 1 <= h["qty"] <= 99
                tal.add(cat, r["index"], hdr_ok, mapped, "" if mapped else "ID/qty check failed", "C:0x80158838 D", de)
            out.append(de)
        planned[box] = out
    return planned


# Phase 3D: skill ids Fiora's later form may legitimately carry in her (mirrored) skill object, besides her own
# (176-200): set from the post-rejoin game saves (see XC_PHASE3D_REPORT.md). {character: alternative id base}
SKILL_ID_ALT = {}


def map_characters(ir, T, tal, d_wii):
    import canon
    import flagmap as fm
    planned = {}
    joined = set(ir["party"])  # at scenario 150 the joined main characters are exactly the party (Phase 2B)
    inv = {b: {r["index"]: r for r in ir["items"][b]} for b in ("head", "body", "arm", "legs", "feet", "weapon")}
    story = fm.wii_get(d_wii, 0x20)
    mc = canon.main_chars(story)          # Phase 3D: Fiora is 3 before scenario 275, 8 from 275
    for c in ir["characters"]:
        k = c["id"]
        if k in (3, 8) and k not in mc:
            tal.add("characters:inactive", k, True, False, ("Fiora's later form not joined yet (before scenario 275); "
                    if k == 8 else "Fiora's first form, frozen since she became character 8 (scenario >= 275); ") +
                    "its skill object is the Wii mirror of the active one (0x800A3644..0x800A3690) -> keep DE template",
                    "C")
            continue
        if k not in MAIN:
            if k:
                tal.add("characters:guest", k, True, False, "guest record (Dickson/Mumkhar/Alvis/prologue Dunban): "
                        "keep DE template", "C:0x8023E414")
            continue
        de = {}
        lv = c["level"]
        nxt = T["w_grow"].get(lv + 1, {}).get("level_exp", 0)
        tal.add("char:level", k, True, 1 <= lv <= 99, "", "C:0x8023E544/0x8023F660; DE 0xA6DD0", lv)
        tal.add("char:exp", k, True, c["exp"] < max(nxt, 1) or lv == 99, "", "C(copy) D:<next level cost", c["exp"])
        tal.add("char:ap", k, True, c["ap"] <= 99_999_999, "", "C(copy 0x8023E6E8) D", c["ap"])
        tal.add("char:affinity_coins", k, True, c["affinity_coins"] <= 999, "", "C:clamp 999 @0x802639C8; DE clamp 999",
                c["affinity_coins"])
        tal.add("char:exp_accum", k, True, False, "Wii +0x2A0 EXP-earned counter; DE +0xF0/+0xF4 semantics differ",
                "C(copy) D")
        de.update(level=lv, exp=c["exp"], ap=c["ap"], affinity_coins=c["affinity_coins"], highest_level=lv)
        # equipment
        eq = {}
        for s, e in c["equipment"].items():
            if e["box_index"] is None:
                if k not in joined and e["gid"]:
                    tal.add("char:equipment_ref(inactive)", f"{k}.{s}", True, False, "not joined: default gear in "
                            "staging slot 150+id; keep DE template", "C:0x80158308")
                else:
                    tal.add("char:equipment_ref", f"{k}.{s}", True, e["gid"] == 0, "empty slot" if e["gid"] == 0 else
                            "gid without box index", "C D")
                eq[s] = None
                continue
            rec = inv[s].get(e["box_index"])
            ok = rec is not None and rec["header"]["gid"] == e["gid"] and rec["header"]["row"] == e["row"]
            if ok and s != "weapon":
                cls = T["w_equip"][e["row"]]["arm_type"]
                if cls in (2, 3):  # DE: medium/heavy armour needs a learned or linked equipment skill
                    have = {n[0] for row in c["skill_rows"] for n in row["nodes"] if n[0]}
                    need = MEDIUM_SKILLS if cls == 2 else HEAVY_SKILLS
                    tal.add("char:armour_permission", f"{k}.{s}", True, bool(have & need),
                            "" if have & need else f"class {cls} worn without skill in {sorted(need)}", "D:hashcade rule")
            eq[s] = {"index": e["box_index"], "type": BOX_TYPE[s]}
            tal.add("char:equipment_ref", f"{k}.{s}", True, ok, "", "C:0x8023E4AC (+0x1C idx) D:36/36 resolve", eq[s])
        de["equipment"] = eq
        # skill trees (rows 0-4) — learn routine 0x800A34C8: node value = learned PSV skill id
        base = (k - 1) * 25  # BTL_PSVskill rows 1-200 = characters 1-8 x 25
        alt = SKILL_ID_ALT.get(k)    # Phase 3D: see SKILL_ID_ALT
        learned = []
        for t in range(5):
            nodes = [n[0] for n in c["skill_rows"][t]["nodes"]]
            cnt = sum(1 for v in nodes if v)
            contiguous = all(nodes[i] for i in range(cnt))
            ids_ok = all(v == 0 or (T["w_psv"].get(v) and any(b_ < v <= b_ + 25 and (v - b_ - 1) // 5 == t
                                                               for b_ in (base,) + ((alt,) if alt is not None else ())))
                         for v in nodes)
            learned.append(cnt)
            tal.add("char:skill_tree", f"{k}.t{t}", True, contiguous and ids_ok, "" if contiguous and ids_ok else
                    "non-contiguous or foreign skill ID", "C:0x800A34C8/0x80260D58 D", {"learned": cnt, "sp": c["skill_sp"][t]})
        de.update(skill_learned=learned, skill_sp=c["skill_sp"], skill_selected_tree=c["skill_selected_tree"])
        # skill links: rows 5-10 = other main characters 1..7 (excl. self) in ID order (verified vs pair affinity)
        others = [x for x in mc if x != k]
        links, unlock = [[0] * 5 for _ in range(8)], [0] * 8
        for j, src in enumerate(others):
            row = c["skill_rows"][5 + j]
            n_unl = sum(1 for n in row["nodes"] if n[1])
            ids = [n[0] for n in row["nodes"]]
            sbase = (src - 1) * 25
            salt = SKILL_ID_ALT.get(src)
            ok = all(v == 0 or sbase < v <= sbase + 25 or (salt is not None and salt < v <= salt + 25) for v in ids)
            links[src - 1] = ids
            unlock[src - 1] = max(n_unl - 1, 0)
            tal.add("char:skill_link_row", f"{k}<-{src}", True, ok, "", "C:0x80268AB0(6 rows) D:affinity 13/14", {
                "linked": ids, "unlocked_slots": n_unl})
        de.update(links=links, link_unlock_index=unlock)
        # arts: Wii (char, pc_arts.idx) -> DE art id-1, same (level, manual-flags) encoding
        arts = {}
        for a in T["w_arts"].values():
            if a["pc"] != k:
                continue
            lv_a, fl = c["art_levels"][a["idx"]]
            shared = sum(1 for x in T["w_arts"].values() if x["pc"] == k and x["idx"] == a["idx"]) > 1
            consistent = a["get_type"] != 1 or a["arts_type"] == 1 or (lv_a == 0) == (a["get_lv"] > lv)
            same_de = T["d_arts"].get(a["id"], {}).get("pc") == k
            arts[a["id"]] = [lv_a, fl]
            # Phase 2E: the get_lv check is a plausibility heuristic, not a mapping condition (story-gated arts such as
            # Shulk's Monado arts at scenario 18 stay at 0 above their get_lv); the bytes are copied exactly either way.
            note = "talent pair shares idx: same value written to both DE records" if shared else ""
            if not consistent:
                note = (note + "; " if note else "") + "level/get_lv mismatch (story-gated art?) - copied verbatim"
            tal.add("char:art", f"{k}.{a['id']}", True, same_de, note, "C:0x800A2000(idx*2) D:get_lv", [lv_a, fl])
        de["arts"] = arts
        # palettes: DE palette[0] = talent, [1..8] = Wii palette; Shulk's second palette = Monado palette
        de["palette"] = [c["talent_arts"][0]] + c["palette"]
        tal.add("char:palette", k, True, True, "slot order verify in game", "C:0x800A2060 D", de["palette"])
        if k == 1:
            de["palette2"] = [c["talent_arts"][0]] + c["palette_monado"]
            tal.add("char:palette_monado", k, True, True, "Wii slot0 empty -> DE slot1 0; verify", "D", de["palette2"])
        planned[k] = de
    return planned


def main(wii_path, de_path=None, write=True, wii_bytes=None, T=None):
    """wii_bytes: decode these instead of reading wii_path; write=False: no data/ or tables/ outputs (library use)."""
    if T is None:
        w, d, T = tables()
    raw = wii_bytes if wii_bytes is not None else wii_save.load(wii_path)
    ir = wii_save.decode_bytes(raw, wii_path or "<bytes>")
    tal = Tally()
    items = map_items(ir, T, tal)
    chars = map_characters(ir, T, tal, raw)
    t = ir["items"]["tail"]
    tal.add("progress:money", "money", True, t["money"] <= 999_999_999, "", "C:0x80157C50; DE 0xBC7F0", t["money"])
    pt = ir["play_time_s"]
    secs = (pt >> 12) * 3600 + (pt >> 6 & 63) * 60 + (pt & 63)
    tal.add("progress:play_time", "time", True, True, "Wii packed h<<12|m<<6|s", "C:0x8023E98C", secs)
    tal.add("progress:party", "party", True, True, "", "Phase 2B", ir["party"])
    nreg = sum(bin(raw[0xEAC6 + i]).count("1") for i in range(40))
    tal.add("collection:collectopaedia", f"{nreg} registered", True, True, "Wii bitmap 0x8009F5F0 -> DE bit 0x19E9+id",
            "C:0x8009F5F0/0x802561CC; DE 0x81310")
    if any(bytes.fromhex(t["char_gem_records_raw"])):
        tal.add("tail:char_gem_records", "88x16", True, False, "non-zero per-character type-3 records", "C:0x80158308")
    out = {"wii": ir, "planned_de": {"characters": chars, "items": items, "money": t["money"], "play_time_s": secs}}
    if de_path:
        out["de_template"] = {k: v for k, v in de_save.decode(de_path).items() if k in ("version", "story", "party",
                                                                                         "serial_counters")}
    if not write:
        return out, tal
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "data", "phase2c_ir.json"), "w", encoding="utf-8"), indent=1)
    with open(os.path.join(ROOT, "tables", "phase2c_entries.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("category\tentry\tdecoded\tmapped\tnote\tevidence\tplanned_de\n")
        for r in tal.rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    with open(os.path.join(ROOT, "tables", "phase2c_completion.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("category\tpresent\tdecoded\tmapped\tunresolved\tevidence\tnotes\n")
        for cat, e in tal.c.items():
            f.write(f"{cat}\t{e['present']}\t{e['decoded']}\t{e['mapped']}\t{e['unresolved']}\t"
                    f"{'; '.join(sorted(e['evidence']))}\t{'; '.join(f'{k} x{v}' for k, v in e['notes'].items())}\n")
            print(f"{cat:28s} present {e['present']:4d} decoded {e['decoded']:4d} mapped {e['mapped']:4d} "
                  f"unresolved {e['unresolved']:4d}  {dict(e['notes']) if e['notes'] else ''}")
    return out, tal


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
