p = r"C:\Dev\XC_Wii_to_DE_Research\tools\de_to_wii.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''def build(de, base, T, lineage=True, minimap_min_fraction=1.0, de_name="<de>", base_name="<wii base>",
          overflow="refuse"):''', '''def build(de, base, T, lineage=True, minimap_min_fraction=1.0, de_name="<de>", base_name="<wii base>",
          overflow="refuse", instances=None):''')
s = s.replace('''    overflow: 'refuse' (default) - more items than the Wii box holds is an error; 'sidecar' - unequipped,
    unreferenced items beyond the Wii capacity (highest DE slots first) are deferred to the sidecar."""''', '''    overflow: 'refuse' (default) - more items than the Wii box holds is an error; 'sidecar' - unequipped,
    unreferenced items beyond the Wii capacity (highest DE slots first) are deferred to the sidecar.
    instances (Phase 3C): {box: set of DE slots} holding the SAME item as the DE save this base was exported to (same
    slot, same id, same DE acquisition serial - DE never reuses a serial). Only those items keep the base's Wii-only
    record bytes (equipment header low bits, crystal byte +0x16); a different item in that slot - e.g. an identical
    one bought after the old one was sold - is encoded fresh. None = 3B rule (same slot and same content)."""''')
old = '''            b_rec = base_box.get(i)
            if b_rec is not None and (lineage or box == "gem") and \
                    canon.strip_order(b_rec) == canon.strip_order(want_rec):'''
assert old in s, "anchor 1"
s = s.replace(old, '''            b_rec = base_box.get(i)
            same = instances is None or (inv_remap[box].get(i) == i and i in instances.get(box, ()))
            if b_rec is not None and same and (lineage or box == "gem") and \
                    canon.strip_order(b_rec) == canon.strip_order(want_rec):''')
old2 = '''            enc = encode_record(box, want_rec, T, gem_desc, cur, ages[box][i])
            if box == "crystal" and base_box.get(i) is not None:'''
assert old2 in s, "anchor 2"
s = s.replace(old2, '''            enc = encode_record(box, want_rec, T, gem_desc, cur if same else None, ages[box][i])
            if box == "crystal" and base_box.get(i) is not None and same:''')
old3 = '''    nrec = 0
    for box in ("gem",) + tuple(b for b in s["inventory"] if b != "gem"):'''
assert old3 in s, "anchor 3"
s = s.replace(old3, '''    nrec = 0
    inv_remap = {b: {w: d for d, w in m.items()} for b, m in remap.items()}
    for box in ("gem",) + tuple(b for b in s["inventory"] if b != "gem"):''')
open(p, "w", encoding="utf-8").write(s)

p = r"C:\Dev\XC_Wii_to_DE_Research\tools\xcservice.py"
s = open(p, encoding="utf-8").read()
old = '''        lineage, base_name, parent, base_dir = True, "sidecar original Wii", sc, None'''
assert old in s, "anchor 4"
s = s.replace(old, '''        lineage, base_name, parent, base_dir = True, "sidecar original Wii", sc, None
        instances = same_instances(scmod.output_image(sc), de)''')
s = s.replace('''        lineage, base_name, parent = r.same_playthrough, r.base, None''', '''        lineage, base_name, parent, instances = r.same_playthrough, r.base, None, None''')
old = '''    out, log, deferred = de_to_wii.build(de, base, T, lineage=lineage, de_name=r.de, base_name=base_name,
                                         overflow=r.overflow)'''
assert old in s, "anchor 5"
s = s.replace(old, '''    out, log, deferred = de_to_wii.build(de, base, T, lineage=lineage, de_name=r.de, base_name=base_name,
                                         overflow=r.overflow, instances=instances)''')
s = s.replace('''def unchanged_return_diffs(wii, de_out, sc, T):''', '''def same_instances(exported_de, de):
    """Phase 3C: {box: DE slots holding the same item as in the DE save the sidecar exported} - same slot, same item id,
    same DE acquisition serial (the per-type counter never hands out a serial twice)."""
    out = {}
    for name, typ, off, size, n in de_save.BOXES:
        keep = set()
        for i in range(n):
            o = off + size * i
            if de[o + 0x10] and exported_de[o + 0x10] and de[o + 4:o + 6] == exported_de[o + 4:o + 6] and \
                    de[o + 0xC:o + 0x10] == exported_de[o + 0xC:o + 0x10]:
                keep.add(i)
        out[name] = keep
    return out


def unchanged_return_diffs(wii, de_out, sc, T):''')
open(p, "w", encoding="utf-8").write(s)
print("ok")
