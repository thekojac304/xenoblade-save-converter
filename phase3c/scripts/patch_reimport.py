p = r"C:\Dev\XC_Wii_to_DE_Research\tools\reimport.py"
s = open(p, encoding="utf-8").read()
old = s[s.index("    # inventory records with unchanged shared content at the same slot"):s.index("    done[\"item_records\"] = n\n") + len("    done[\"item_records\"] = n\n")]
s = s.replace(old, '''    # inventory (Phase 3C): DE-only per-item bytes come from the original record of the SAME physical item, followed
    # through the export compaction and the Wii/3DS session (tools/itemcorr). Up to 3B this was "same DE slot, same
    # content", which lost them for compacted items and could give them to an identical replacement.
    n, meta = restore_item_metadata(b, orig, co, ce, cc, deferred or {}, T)
    done["item_records"] = n
    done["item_metadata"] = meta
''')
s = s.replace("def restore_exact(b, orig, exp_wii, cur_wii, T, log):", "def restore_exact(b, orig, exp_wii, cur_wii, T, log, deferred=None):")
s = s.replace("    exact = restore_exact(b, template, exp_wii, cur_wii, T, log)",
              "    exact = restore_exact(b, template, exp_wii, cur_wii, T, log, sc.get(\"deferred\", {}))")
s = s.replace("import canon\nimport convert\n", "import canon\nimport convert\nimport itemcorr\n")
s = s.replace('''def fmw(w):''', '''def _meta_record(box, built, src):
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


def fmw(w):''')
open(p, "w", encoding="utf-8").write(s)
