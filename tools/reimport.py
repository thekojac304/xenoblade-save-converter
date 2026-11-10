"""Re-import with a sidecar (Phase 2E part D3, hardened in Phase 2F): bring Wii progress back onto the original DE save.

wii_to_de_reimport(current_wii, sidecar, T, current_de=None, branch=None, no_newer_de=False):
  sidecar = the one written when the playthrough was exported DE -> Wii (direction "de_to_wii"); it holds the original
  DE image (source) and the exact Wii file the Wii session started from (output).
  1. integrity / schema (sidecar.load) and direction checks;
  2. descent: the current Wii save must plausibly continue the exported one (sidecar.descent);
  3. the user's current DE save is REQUIRED (Phase 2F) - or no_newer_de=True, an explicit statement that no DE save
     of this playthrough is newer than the export. Without it, DE progress made after the export (or a newer export
     made with a newer sidecar) would be silently replaced;
  4. divergence: if the current DE save changed since the export AND the Wii save did too, stop unless an explicit
     branch is chosen (never silently pick the higher play time or story). Even with a branch, stop when the progress
     the DE save made since this export is also in the Wii save: the sidecar is then older than the user's latest
     DE -> Wii export (sidecar.stale_evidence), and importing it would mix two generations;
  5. convert the current Wii save with tools/convert.build using the DE save as the template (the sidecar's original;
     or the current DE save when it differs only in DE-exclusive fields, so newer DE-only state is kept), so DE-only
     data (Expert Mode, cosmetics, Future Connected, DE-only flags, Time Attack, options, Noponstones...) comes back;
  6. apply only the Wii delta since export to lossy categories (awards, quest counters, minimap, clock, location,
     Shulk's second talent byte) and restore exact DE item / character records whose shared content is unchanged;
     Expert Mode: active level from the Wii, highest level = max(original, new), reserve EXP untouched (no duplication);
  7. put deferred DE-only / overflow items back (original slot when free, else the first free slot);
  8. DE acquisition serials (Phase 2F): items that existed at export keep their DE serial; items picked up on the Wii
     get new serials above the DE counter, in the Wii's acquisition order (canon.order_ranks);
  9. if the Wii save is unchanged since export, the result is byte-identical to the template DE save.
"""
import struct

import canon
import convert
import itemcorr
import de_save
import minimap
import quest_counters as qc
import sidecar as scmod

CHAR, CHAR_SIZE = 0x152728, 0x138
BOX = {n: (t, o, s) for n, t, o, s, _ in de_save.BOXES}


class DivergenceError(Exception):
    pass


def _de_rec_offsets(box):
    t, o, s = BOX[box]
    return o, s


def wii_to_de_reimport(cur_wii, sc, T, current_de=None, branch=None, no_newer_de=False):
    if sc["direction"] != "de_to_wii":
        raise scmod.SidecarError("this sidecar was not written by a DE -> Wii export")
    if current_de is None and not no_newer_de:
        raise scmod.SidecarError("the current DE save of this playthrough is required (or state explicitly that no DE "
                                 "save is newer than the export); otherwise DE progress could be silently replaced")
    orig_de, exp_wii = scmod.source_image(sc), scmod.output_image(sc)
    ok, reasons, changed = scmod.descent(exp_wii, cur_wii, T, "wii")
    if not ok:
        raise scmod.SidecarError("the Wii save does not continue the exported one: " + "; ".join(reasons))
    diverged, detail = scmod.divergence(sc, current_de, T)
    log = {"descent": reasons, "wii_changed_since_export": changed, "divergence": detail}
    if diverged:
        ratio, nfacts = scmod.stale_evidence(sc, current_de, cur_wii, T)
        log["stale_evidence"] = {"ratio": round(ratio, 3), "facts": nfacts}
        if changed and nfacts >= scmod.STALE_MIN_FACTS and ratio >= scmod.STALE_RATIO:
            raise DivergenceError(
                f"this sidecar looks older than your latest DE -> Wii export: {ratio:.0%} of the progress your current "
                "DE save made since this sidecar's export is already in the Wii save. Use the sidecar written by your "
                "most recent DE -> Wii export. (If you really played the same content in both games, keep using one "
                "of the two saves directly.) Nothing was imported.")
        if changed and branch != "wii":
            raise DivergenceError(
                "your current DE save is not the one this sidecar exported: it changed after the export, and the Wii "
                "save also progressed. Either you played DE after exporting (choose a branch explicitly: branch 'wii' "
                "keeps the Wii progress and DISCARDS the DE progress made after the export), or this sidecar is "
                "older than your latest export (use the newest sidecar). No automatic merge is attempted.")
        if not changed and branch != "wii":
            raise DivergenceError("the Wii save has no progress since the export but the DE save does: nothing to "
                                  "import (your current DE save is the newer one)")
    template = orig_de
    if current_de is not None and current_de != orig_de and not diverged:
        if len(current_de) != len(orig_de):
            raise scmod.SidecarError("the current DE save has a different format version than the exported one")
        template = current_de          # same shared state, newer DE-exclusive state: keep it
        log["template"] = "current DE save (differs from the export only in DE-exclusive fields)"
    if not changed:
        log["result"] = "Wii unchanged since export: the DE save is restored byte for byte"
        return template, log
    if len(template) != convert.V10:
        raise scmod.SidecarError("the exported DE save is not format v10; re-import needs a v10 save (load and save it "
                                 "once in DE 2.0 / Monado first)")
    import stored_gear
    keep = [k for k in range(1, 12) if stored_gear.wii_raw_signature(exp_wii, k) ==
            stored_gear.wii_raw_signature(cur_wii, k)]
    out, clog, fail = convert.build(cur_wii, template, T, convert.FEATURES_2F, minimap_base="merge",
                                    wii_name="current Wii", tpl_name="DE template", lineage_template=True,
                                    stored_keep=keep)
    if fail:
        raise convert.ConvertError(f"read-back failed: {fail[:5]}")
    b = bytearray(out)
    stored_gear_three_way(b, template, exp_wii, cur_wii, T, log)
    exact = restore_exact(b, template, exp_wii, cur_wii, T, log, sc.get("deferred", {}))
    restore_deferred(b, orig_de, sc.get("deferred", {}), log)
    assign_serials(b, template, orig_de, exp_wii, cur_wii, sc.get("deferred", {}), T, log)
    log["convert"] = {k: clog[k] for k in ("bytes_touched", "write_ranges") if k in clog}
    log["restored_exact"] = exact
    return bytes(b), log


def stored_gear_three_way(b, template, exp_wii, cur_wii, T, log):
    """Phase 3E: equipment stored for characters who are away (tools/stored_gear), 3-way like every lossy category.
    * stored gear the Wii/3DS session did not change -> the DE's own entries are kept (also protects returns of files
      exported by converters before 3E, which carried no stored gear);
    * a character stored at export and back in the party now (the reunion was played on the Wii/3DS) -> the DE's
      entries are cleared, as the DE game clears them when it gives the gear back."""
    import stored_gear
    ce, cc = canon.from_wii(exp_wii, T)["shared"], canon.from_wii(cur_wii, T)["shared"]
    es, cs = ce.get("stored_gear") or {}, cc.get("stored_gear") or {}
    span = stored_gear.ENTRY * stored_gear.PER_CHAR
    kept, cleared = [], []
    for k in set(es) | set(cs):
        o = stored_gear.STASH + span * (k - 1)
        if k in cs and (es.get(k) == cs[k] or stored_gear.wii_raw_signature(exp_wii, k) ==
                        stored_gear.wii_raw_signature(cur_wii, k)):
            if b[o:o + span] != template[o:o + span]:
                b[o:o + span] = template[o:o + span]
            kept.append(k)
        elif k in es and k in cc["party"]:
            if any(b[o:o + span]):
                b[o:o + span] = bytes(span)
            cleared.append(k)
    if kept or cleared:
        log["stored_gear"] = {"kept_from_de": sorted(kept), "cleared_returned": sorted(cleared)}


def restore_exact(b, orig, exp_wii, cur_wii, T, log, deferred=None):
    """3-way merge of lossy / DE-richer categories: keep the original DE bytes where the Wii did not change."""
    done = {}
    co = canon.from_de(orig, T)["shared"]
    cn = canon.from_de(bytes(b), T)["shared"]
    ce, cc = canon.from_wii(exp_wii, T)["shared"], canon.from_wii(cur_wii, T)["shared"]
    # characters: identical shared content -> exact original record (highest level, reserve, cosmetics, raw fields)
    n = 0
    for k in range(1, 17):
        o = CHAR + CHAR_SIZE * (k - 1)
        if k in cn["characters"] and cn["characters"][k] != co["characters"][k]:
            hi_o, hexp_o = struct.unpack_from("<II", orig, o + 0xEC)
            lv_o, exp_o = struct.unpack_from("<II", orig, o)
            lv, ex = struct.unpack_from("<II", b, o)
            if lv <= hi_o:  # Expert Mode bookkeeping: unless the Wii went above the highest level, DE's own pair stays
                tracking = lv == hi_o == lv_o and hexp_o == exp_o and ex >= exp_o
                # Phase 3C [game]: while a character is at its highest level and the pair tracks its EXP (no EXP banked
                # in Expert Mode), the DE moves +0xF0 with every EXP gain (Monado 154 -> 156 -> 158: +858/+661 for
                # five characters). EXP earned on the Wii/3DS at that level is mirrored the same way.
                struct.pack_into("<II", b, o + 0xEC, hi_o, ex if tracking else hexp_o)
                # (otherwise - e.g. Expert saves where +0xF0 != EXP at the same level - the DE's own pair stays)
            if k == 1 and ce["characters"][1]["palette"][0] == cc["characters"][1]["palette"][0]:
                b[o + 0x5A:o + 0x5C] = orig[o + 0x5A:o + 0x5C]
            continue
        if b[o:o + CHAR_SIZE] != orig[o:o + CHAR_SIZE]:
            b[o:o + CHAR_SIZE] = orig[o:o + CHAR_SIZE]
            n += 1
    done["character_records"] = n
    # inventory (Phase 3C): DE-only per-item bytes come from the original record of the SAME physical item, followed
    # through the export compaction and the Wii/3DS session (tools/itemcorr). Up to 3B this was "same DE slot, same
    # content", which lost them for compacted items and could give them to an identical replacement.
    n, meta = restore_item_metadata(b, orig, co, ce, cc, deferred or {}, T)
    done["item_records"] = n
    done["item_metadata"] = meta
    # awards: where the Wii-derived value did not change since export, keep the original DE counter
    import achievements
    arts_new = [(b[0x153AA8 + 2 * a], b[0x153AA8 + 2 * a + 1]) for a in range(188)]
    art_tab = [(0, 0)] * 188
    for k, ch in ce["characters"].items():
        for aid, lv in ch["arts"].items():
            art_tab[aid - 1] = tuple(lv)
    v_cur, v_exp = achievements.wii_to_de(cur_wii, arts_new, T), achievements.wii_to_de(exp_wii, art_tab, T)
    n = 0
    for g, v in v_cur.items():
        if v_exp.get(g) == v:
            o = 0xDF0 + 2 * (g - 0x20)
            if b[o:o + 2] != orig[o:o + 2]:
                b[o:o + 2] = orig[o:o + 2]
                n += 1
    done["award_counters"] = n
    # quest counters
    n = 0
    for q in range(qc.WII_N):
        if qc.wii_to_de(cur_wii, q) == qc.wii_to_de(exp_wii, q):
            o = qc.DE_QC + 8 * q
            if b[o:o + 8] != orig[o:o + 8]:
                b[o:o + 8] = orig[o:o + 8]
                n += 1
    done["quest_counters"] = n
    # minimap: original DE bitmaps + DE cells that only the new Wii exploration explains
    zero = bytearray(orig)
    for m in minimap.SHARED_MAPS:
        ncol, nrow, stride = minimap.de_dims(m)
        for f in range(1, minimap.DE_MAPS[m][2] + 1):
            o = minimap.de_floor_off(m, f)
            zero[o:o + nrow * stride] = bytes(nrow * stride)
    a = minimap.wii_to_de(cur_wii, bytes(zero))
    e = minimap.wii_to_de(exp_wii, bytes(zero))
    for m in minimap.SHARED_MAPS:
        ncol, nrow, stride = minimap.de_dims(m)
        for f in range(1, minimap.DE_MAPS[m][2] + 1):
            o = minimap.de_floor_off(m, f)
            b[o:o + nrow * stride] = orig[o:o + nrow * stride]
    added = 0
    for o, v in a.items():
        new_bits = v & ~e.get(o, 0)
        if new_bits & ~b[o]:
            b[o] |= new_bits
            added += 1
    done["minimap_bytes_added"] = added
    # clock / location: unchanged on the Wii -> original DE values (keeps seconds-level detail and DE-only words)
    if (ce["clock"], fmw(exp_wii)) == (cc["clock"], fmw(cur_wii)):
        b[0x149C04:0x149C08] = orig[0x149C04:0x149C08]
        b[0x149C24:0x149C28] = orig[0x149C24:0x149C28]
        done["clock"] = "original"
    if (ce["map"], ce["position"], ce["angle_rad"]) == (cc["map"], cc["position"], cc["angle_rad"]):
        b[0x149C00:0x149C04] = orig[0x149C00:0x149C04]
        b[0x149C10:0x149C24] = orig[0x149C10:0x149C24]
        b[0x149C08:0x149C10] = orig[0x149C08:0x149C10]
        done["location"] = "original"
    if ce["play_time_s"] == cc["play_time_s"]:
        b[4:8] = orig[4:8]
    log["three_way"] = done
    return done


def _meta_record(box, built, src):
    """The original DE record of the same item, with the fields the Wii/3DS save owns taken from the converted one:
    slot index, quantity (stacks), acquisition serial (assign_serials), and for equipment the armour class, socket
    count and sockets (gems can be changed on the Wii; references point at the converted gem box)."""
    rec = bytearray(src)
    rec[0:4] = built[0:4]
    rec[8:10] = built[8:10]
    rec[0xC:0x10] = built[0xC:0x10]
    if box in itemcorr.EQUIP:
        rec[0x14:0x16] = built[0x14:0x16]
        rec[0x18:0x30] = built[0x18:0x30]
    return bytes(rec)


def restore_item_metadata(b, orig, co, ce, cc, deferred, T):
    """Give each converted item the DE-only bytes of its original record when it is certainly the same item
    (itemcorr.correspondence). The canonical shared state must not change; a box that would change it is left as
    converted and reported (never expected; tested)."""
    corr, rep = itemcorr.correspondence(co["inventory"], ce["inventory"], cc["inventory"], deferred)
    before = canon.from_de(bytes(b), T)["shared"]
    changed = {}
    for box, pairs in corr.items():
        off, size = _de_rec_offsets(box)
        for w, d in pairs.items():
            p = off + size * w
            if not b[p + 0x10]:
                continue
            rec = _meta_record(box, bytes(b[p:p + size]), orig[off + size * d:off + size * (d + 1)])
            if rec != b[p:p + size]:
                changed.setdefault(box, []).append((p, bytes(b[p:p + size])))
                b[p:p + size] = rec
    after = canon.from_de(bytes(b), T)["shared"]
    if after != before:
        for box, undo in changed.items():
            if after["inventory"][box] != before["inventory"][box] or after["characters"] != before["characters"]:
                for p, old in undo:
                    b[p:p + len(old)] = old
                rep["unresolved_boxes"][box] = "restoring DE-only bytes would change shared state (left as converted)"
                after = canon.from_de(bytes(b), T)["shared"]
        if after != before:
            raise convert.ConvertError("internal error: item metadata restoration changed the shared state")
    rep["records_rewritten"] = {k: len(v) for k, v in changed.items() if k not in rep["unresolved_boxes"]}
    return sum(rep["records_rewritten"].values()), rep


def fmw(w):
    import flagmap as fm
    return fm.wii_get(w, 0xAF)


def restore_deferred(b, orig, deferred, log):
    """Put DE-only / overflow items deferred at export back into their box (original slot if free)."""
    put = []
    for kind in ("de_only_items", "overflow_items"):
        for box, slots in (deferred or {}).get(kind, {}).items():
            off, size = _de_rec_offsets(box)
            for sl in sorted(int(s) for s in slots):
                src = orig[off + size * sl:off + size * (sl + 1)]
                if not src[0x10]:
                    raise convert.ConvertError(f"deferred {box} item {sl} is missing from the sidecar's DE snapshot")
                target = sl if b[off + size * sl + 0x10] == 0 else next(
                    (i for i in range(500) if b[off + size * i + 0x10] == 0), None)
                if target is None:
                    raise convert.ConvertError(f"no free DE {box} slot to restore deferred item {sl}")
                rec = bytearray(src)
                struct.pack_into("<H", rec, 0, target)
                b[off + size * target:off + size * (target + 1)] = rec
                put.append((kind, box, sl, target))
    log["deferred_restored"] = put
    return put


def assign_serials(b, template, orig, exp_wii, cur_wii, deferred, T, log):
    """DE acquisition serials after a re-import (Phase 2F). An item that existed at export (same slot and id in the
    template DE save and in the exported Wii file, or a restored deferred item) keeps its DE serial; items picked up
    on the Wii get serials above the DE counter in the Wii's acquisition order. If the Wii order contradicts the kept
    serials (it never should), the whole box is renumbered in Wii order so the order stays exact."""
    cc = canon.from_wii(cur_wii, T)["shared"]["inventory"]
    ew = canon.from_wii(exp_wii, T)["shared"]["inventory"]
    ct = canon.from_de(template, T)
    restored = {(p[1], p[3]) for p in log.get("deferred_restored", [])}
    rep = {}
    for box, (typ, off, size) in BOX.items():
        slots = [sl for sl in range(500) if b[off + size * sl + 0x10]]
        if not slots:
            continue
        ctr_o = de_save.SERIALS + 4 * typ
        known, new = {}, []
        # items that existed at export: the exported Wii file holds each of them (possibly at a compacted slot); pair
        # them with the template's items of the same identity in acquisition order (both keep the relative order)
        tser = ct["de_only"]["item_serials"][box]
        parked = {int(s) for kind in ("de_only_items", "overflow_items")
                  for s in (deferred or {}).get(kind, {}).get(box, {})}       # restored from the sidecar instead
        pools = {}
        for sl, r in sorted(ct["shared"]["inventory"][box].items(), key=lambda x: x[1]["order"]):
            if sl not in parked:
                pools.setdefault(canon.item_key(box, r), []).append(tser[sl])
        exported = {}
        for sl, r in ew[box].items():
            k = canon.item_key(box, r)
            exported[k] = exported.get(k, 0) + 1
        wii_items = sorted(((sl, r) for sl, r in cc[box].items() if sl in slots), key=lambda x: x[1]["order"])
        for sl, r in wii_items:
            k = canon.item_key(box, r)
            if exported.get(k) and pools.get(k):
                exported[k] -= 1
                known[sl] = pools[k].pop(0)
            else:
                new.append(sl)
        for sl in slots:
            if (box, sl) in restored:
                known[sl] = struct.unpack_from("<I", b, off + size * sl + 0xC)[0]
            elif sl not in cc[box] and sl not in known:
                new.append(sl)
        wii_order = {sl: cc[box][sl]["order"] for sl in slots if sl in cc[box]}
        kept = sorted((sl for sl in known if sl in wii_order), key=lambda s: wii_order[s])
        consistent = all(known[x] < known[y] for x, y in zip(kept, kept[1:])) and \
            all(wii_order[n] > max((wii_order[k] for k in kept), default=0) for n in new if n in wii_order) and \
            len(set(known.values())) == len(known)
        if consistent:
            nxt = max([struct.unpack_from("<I", b, ctr_o)[0], struct.unpack_from("<I", template, ctr_o)[0]] +
                      list(known.values()))
            final = dict(known)
            for sl in sorted(new, key=lambda s: (wii_order.get(s, 0), s)):
                nxt += 1
                final[sl] = nxt
            mode = "kept"
        else:   # renumber in Wii order; deferred-only items (not on the Wii) after them, in their DE order
            seq = sorted(slots, key=lambda s: (s not in wii_order, wii_order.get(s, 0), known.get(s, 0), s))
            final = {sl: i for i, sl in enumerate(seq, 1)}
            mode = "renumbered"
        for sl, v in final.items():
            struct.pack_into("<I", b, off + size * sl + 0xC, v)
        top = max(final.values())
        if struct.unpack_from("<I", b, ctr_o)[0] < top:
            struct.pack_into("<I", b, ctr_o, top)
        rep[box] = {"mode": mode, "kept": len(known), "new": len(new)}
    log["serials"] = rep
