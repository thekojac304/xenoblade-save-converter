"""Award (achievement) counters, Wii <-> DE, code-derived (Phase 2E A4; evidence in
work/phase2e/re_time_achievements_deonly.md, scratch re_time/ach_rules.py).

Counter slots: Wii 16-bit flag 0x40 + id (no modulo, 0x80083018); DE 16-bit flag 0x40 + (id % 200) (descriptor
0x004000C8, getter 0xB2620), so award 200 lives in DE slot 0x40. Completion bits: Wii 1-bit 0x312C + id (DE +300).
Metric sources per award (source_of): native lead counter with tier thresholds (Wii 0x8028130c sites, specs/
wii_award_tiers.json), counts of flags (unique monsters 0x1D44+k, landmarks 0xA20+k), max art level, arts at level 10,
Colony 6 population/development (8-bit 0x7FD/0x7FC), fevers (Wii slot 124; slot 125 is per crafting session).
Wii -> DE: completed tier -> comp_value (DE freezes it); else min(metric, comp_value - 1).
DE -> Wii: lead slot = max of the DE tier counters, other tier slots 0; flag/art/Colony-6-derived slots 0 (the Wii
recomputes them). Lossy: totals above the top tier, fevers above 3, per-session fever counter.
"""
import json
import os

import flagmap as fm
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
UNIQUE_EXCL = set(range(0xF, 0x14)) | set(range(0x6D, 0x70)) | set(range(0x8B, 0x8E)) | set(range(0xE3, 0xE8))
GROUPS_PER_TIER = [[121, 122, 123], [135], [137], [139, 140], [141], [159, 160, 161, 162], [172, 173, 174],
                   [180, 181, 182, 183, 184], [187, 188, 189]]
PER_TIER = {i for g in GROUPS_PER_TIER for i in g}
HOLD16 = {0xB7, 0xBE, 0xBF, 0xC3, 0xF9}   # Phase 2B: Wii-used, never set by DE -> keep the DE template value
_R = None


def _spec(name):
    with open(paths.spec(name), encoding="utf-8") as f:
        return json.load(f)


def rules(T):
    """{award id: {kind, comp_type, comp_value, lead?}} from MNU_playaward + the Wii tier table."""
    global _R
    if _R is not None:
        return _R
    ma = {r["id"]: r for r in T["de"]["MNU_playaward"]["rows"]}
    tiers = {int(k): [tuple(x) for x in v] for k, v in
             _spec("wii_award_tiers.json").items()}
    lead = {}
    for ld, lst in tiers.items():
        if ld in (111, 2, 3):
            continue
        for aid, thr in lst:
            if (ld == 28 and aid == 93) or (aid in (32, 33, 34) and ld == 29) or aid == 118:
                continue
            lead.setdefault(aid, ld)
    out = {}
    for i in range(1, 201):
        ct, cv = ma[i]["comp_type"], ma[i]["comp_value"]
        if ct != 4:
            k = {"kind": "event"}
        elif i in (8, 9, 10):
            k = {"kind": "unique_monsters"}
        elif i in (148, 149, 150, 151):
            k = {"kind": "landmark_flags"}
        elif i in (72, 73, 74):
            k = {"kind": "art_max_level"}
        elif i in (75, 76):
            k = {"kind": "arts_lv10"}
        elif i in (195, 196, 197):
            k = {"kind": "c6_population"}
        elif i in (198, 199, 200):
            k = {"kind": "c6_development"}
        elif i == 87:
            k = {"kind": "lead", "lead": 60}
        elif i in (124, 125):
            k = {"kind": "fever"}
        elif i in lead:
            k = {"kind": "lead", "lead": lead[i]}
        elif i in PER_TIER:
            k = {"kind": "per_tier", "group": next(g for g in GROUPS_PER_TIER if i in g)}
        else:
            k = {"kind": "identity"}
        k.update(comp_type=ct, comp_value=cv)
        out[i] = k
    _R = out
    return out


def de_slot(i):
    return 0x40 + (i % 200)


def wii_slot(i):
    return 0x40 + i


def _metric(r, i, wii, arts):
    k = r["kind"]
    if k == "unique_monsters":
        return sum(1 for n in range(300) if n not in UNIQUE_EXCL and fm.wii_get(wii, 0x1D44 + n))
    if k == "landmark_flags":
        return sum(1 for n in range(300) if fm.wii_get(wii, 0xA20 + n))
    if k == "art_max_level":
        return max(lv for lv, _ in arts)
    if k == "arts_lv10":
        return sum(1 for lv, _ in arts if lv >= 10)
    if k == "c6_population":
        return fm.wii_get(wii, 0x7FD)
    if k == "c6_development":
        return fm.wii_get(wii, 0x7FC)
    if k == "lead":
        return fm.wii_get(wii, wii_slot(r["lead"]))
    if k == "fever":
        return fm.wii_get(wii, wii_slot(124))
    if k == "per_tier":
        return max(fm.wii_get(wii, wii_slot(j)) for j in r["group"])
    return fm.wii_get(wii, wii_slot(i)) if wii_slot(i) < 0x220 else 0


def wii_to_de(wii, arts, T):
    """{DE 16-bit flag id: value} for every counted award. arts = converted DE art table [(level, flags)] x 188."""
    out = {}
    for i, r in rules(T).items():
        if r["kind"] == "event":
            continue
        slot = de_slot(i)
        if slot in HOLD16:
            continue
        done = fm.wii_get(wii, 0x312C + i) if i < 200 else 0
        t = _metric(r, i, wii, arts)
        cv = r["comp_value"]
        out[slot] = cv if done else (cv - 1 if t >= cv else t)
    return out


def de_to_wii(de, T):
    """{Wii 16-bit flag id: value} for the counter slots the Wii keeps (lead slots and per-tier/identity slots).
    Flag-, art- and Colony-6-derived awards are recomputed by the Wii, so their slots are 0."""
    R = rules(T)
    out = {}
    for i, r in R.items():
        if wii_slot(i) >= 0x108 or r["kind"] == "event":
            continue
        if r["kind"] in ("lead", "fever"):
            ld = r.get("lead", 124)
            v = fm.de_get(de, de_slot(i))
            out[wii_slot(ld)] = max(out.get(wii_slot(ld), 0), v)
        elif r["kind"] in ("per_tier", "identity"):
            if wii_slot(i) not in HOLD16:
                out[wii_slot(i)] = fm.de_get(de, de_slot(i))
    for i, r in R.items():   # tier slots that are not their own lead are 0 on the Wii
        if r["kind"] in ("lead", "fever") and wii_slot(i) < 0x108:
            out.setdefault(wii_slot(i), 0)
    for i, r in R.items():
        if r["kind"] in ("unique_monsters", "landmark_flags", "art_max_level", "arts_lv10", "c6_population",
                         "c6_development") and wii_slot(i) < 0x108:
            out.setdefault(wii_slot(i), 0)
    return out
