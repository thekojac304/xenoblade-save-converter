"""Item-instance correspondence across a DE -> Wii/3DS -> DE trip (Phase 3C, DE metadata fidelity).

DE item records carry bytes the Wii/3DS record cannot hold: the favourite mark (+0x11), the crystal "named" byte
(+0x18) of list crystals, and record bytes the DE never initialises (+0x0A..0x0B, +0x12..0x13, unused crystal effect
slots; copied from a caller's stack buffer by the item-add routine 0xBF454..0xBF46C). Up to 3B they came back only
for an item that returned to the same DE slot with the same content. An item the export had to compact into another
Wii slot (DE slots beyond the Wii box) therefore lost them, and a *replacement* item at the original slot could
receive them.

This module decides, per output slot, which original DE record is the same physical item:

  1. export map (DE slot -> exported Wii slot): reconstructed from the sidecar's two snapshots with the exporter's own
     rule (de_to_wii.build: same slot when it fits, otherwise the free Wii slots in ascending order), then validated
     item by item (content and acquisition order). A box whose map does not validate is unresolved.
  2. survivors (exported Wii slot -> current Wii slot): the Wii/3DS games never move an item between slots (verified on
     every game-written pair: Dolphin d2, Azahar a5/3B a1), so an item that still exists is at the same slot with the
     same item. Two identical items are never assumed to be one: a candidate (same slot, same item) is accepted only
     if it lies on EVERY longest chain that keeps the exported acquisition order. The Wii makes an added item the
     newest (0x80159080..0x80159100: every record ages by one, the new or stacked-up record gets age 0), so a
     replacement bought or found later, or a stack that was added to, falls off the chain. The newest chain member is
     indistinguishable from a replacement that took its place, so it is accepted only when the box is unchanged.
  3. the converted DE item at Wii slot w then gets its original record's DE-only bytes; shared content stays exactly
     as the Wii/3DS save has it (checked by the caller: the canonical shared state must not change).

Nothing here adds or removes items: it only selects source bytes for items the Wii/3DS save already holds.
"""
import canon

EQUIP = ("weapon", "head", "body", "arm", "legs", "feet")
STACK = ("collectable", "material", "keyitem", "artmanual")


def _content(box, r, gem_map=None):
    """Canonical content without order (and without quantity for stacks: consumption keeps the same stack)."""
    c = canon.strip_order(r)
    if box in STACK:
        c = {k: v for k, v in c.items() if k != "qty"}
    if box in EQUIP and gem_map is not None:
        c = dict(c, sockets=[["gem", gem_map.get(x[1])] if x and x[0] == "gem" else x for x in c["sockets"]])
    return c


def export_map(de_inv, exp_inv, deferred):
    """-> ({box: {de_slot: wii_slot}} for boxes that validate, {box: reason} for unresolved boxes)."""
    maps, bad = {}, {}
    parked = {box: {int(s) for kind in ("de_only_items", "overflow_items")
                    for s in (deferred or {}).get(kind, {}).get(box, {})} for box in de_inv}
    for box, recs in de_inv.items():
        keep = sorted(sl for sl in recs if sl not in parked[box])
        wii = exp_inv.get(box, {})
        if len(keep) != len(wii):
            bad[box] = f"{len(keep)} DE items vs {len(wii)} exported Wii items"
            continue
        m = {}
        for sl in keep:
            if sl in wii and wii[sl]["gid"] == recs[sl]["gid"]:
                m[sl] = sl
        rest_de = [sl for sl in keep if sl not in m]
        rest_w = sorted(sl for sl in wii if sl not in m.values())
        m.update(zip(rest_de, rest_w))
        maps[box] = m
    gm = maps.get("gem")
    for box, m in list(maps.items()):
        recs, wii = de_inv[box], exp_inv[box]
        if box in EQUIP and gm is None and any(x and x[0] == "gem" for r in recs.values() for x in r["sockets"]):
            bad[box], _ = "gem box unresolved (socket references cannot be followed)", maps.pop(box)
            continue
        ok = all(_content(box, recs[d], gm if box in EQUIP else None) ==
                 _content(box, wii[w]) for d, w in m.items())
        de_order = sorted(m, key=lambda d: recs[d]["order"])
        ok = ok and [m[d] for d in de_order] == sorted(m.values(), key=lambda w: wii[w]["order"])
        if not ok:
            bad[box] = "exported items do not match the DE items in content or acquisition order"
            maps.pop(box)
    return maps, bad


def _in_every_lis(seq):
    """seq: list of values (distinct). -> set of indexes lying on every longest strictly increasing subsequence."""
    n = len(seq)
    f = [1] * n
    for i in range(n):
        for j in range(i):
            if seq[j] < seq[i] and f[j] + 1 > f[i]:
                f[i] = f[j] + 1
    g = [1] * n
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n):
            if seq[j] > seq[i] and g[j] + 1 > g[i]:
                g[i] = g[j] + 1
    L = max(f, default=0)
    on = [i for i in range(n) if f[i] + g[i] - 1 == L]
    by_level = {}
    for i in on:
        by_level.setdefault(f[i], []).append(i)
    return {v[0] for v in by_level.values() if len(v) == 1}


def survivors(box, exp, cur):
    """exp/cur: {wii_slot: canonical record}. -> (set of certain wii slots, {slot: reason} for the others)."""
    cand = [sl for sl in exp if sl in cur and exp[sl]["gid"] == cur[sl]["gid"] and
            (box in STACK or canon.item_key(box, exp[sl]) == canon.item_key(box, cur[sl]))]
    why = {sl: "item no longer at this slot" for sl in exp if sl not in cand}
    cand.sort(key=lambda s: exp[s]["order"])
    seq = [cur[s]["order"] for s in cand]
    keep = _in_every_lis(seq)
    sure = {cand[i] for i in keep}
    for i, s in enumerate(cand):
        if i not in keep:
            why[s] = "acquisition order changed (added to, or a later item of the same kind)"
    changed = {sl: canon.strip_order(r) for sl, r in exp.items()} != {sl: canon.strip_order(r) for sl, r in cur.items()} \
        or [s for s in sorted(exp, key=lambda s: exp[s]["order"])] != [s for s in sorted(cur, key=lambda s: cur[s]["order"])]
    if changed and sure:
        # the newest chain member could be an identical item that replaced it in the same slot (removed, then a new
        # one obtained before any other change of order): the save cannot tell them apart, so it stays unresolved
        top = max(sure, key=lambda s: cur[s]["order"])
        sure.discard(top)
        why[top] = "newest surviving item of a box that changed: indistinguishable from an identical replacement"
    return sure, why


def correspondence(de_inv, exp_inv, cur_inv, deferred):
    """-> ({box: {wii_slot: original de_slot}}, report). Only items that are certainly the same physical item."""
    maps, bad = export_map(de_inv, exp_inv, deferred)
    out, rep = {}, {"unresolved_boxes": bad, "boxes": {}}
    for box, m in maps.items():
        sure, why = survivors(box, exp_inv[box], cur_inv.get(box, {}))
        inv = {w: d for d, w in m.items()}
        out[box] = {w: inv[w] for w in sure if w in inv}
        rep["boxes"][box] = {"matched": len(out[box]), "exported": len(m), "uncertain": len(why),
                             "moved_at_export": sum(1 for d, w in m.items() if d != w)}
        rep.setdefault("uncertain", {})[box] = {str(k): v for k, v in sorted(why.items())[:20]}
    return out, rep
