"""One-off patch helper (Phase 2F): serial order + party checks in tools/de_to_wii.py. Asserts each anchor once."""
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "de_to_wii.py")
s = open(P, encoding="utf-8").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('def encode_record(box, rec, T, gem_desc_by_slot, base_raw=None):\n    typ, off, size, _ = WII_BOX[box]',
    'def encode_record(box, rec, T, gem_desc_by_slot, base_raw=None, age=0):\n'
    '    """age: the Wii header u16 +4 (acquisition age, 0/1 = newest; see canon.order_ranks)."""\n'
    '    typ, off, size, _ = WII_BOX[box]')
rep('out = bytearray(header_bytes(rec["gid"], typ, row, low5, rec["serial"], max(rec["qty"], 1), 0))',
    'out = bytearray(header_bytes(rec["gid"], typ, row, low5, age, max(rec["qty"], 1), 0))')
rep('return header_bytes(gid, 3, rec["effect"], rec["rank"] << 2, rec["serial"], 1, 3 if crafted else 0)',
    'return header_bytes(gid, 3, rec["effect"], rec["rank"] << 2, age, 1, 3 if crafted else 0)')
rep('h = header_bytes(gid, 9, row, rec["rank"] << 2 | (1 if kind == 2 else 0), rec["serial"], 1,',
    'h = header_bytes(gid, 9, row, rec["rank"] << 2 | (1 if kind == 2 else 0), age, 1,')
rep('return header_bytes(gid, typ, wii_row(gid, typ, T, box), 0, rec["serial"], rec["qty"], 0)',
    'return header_bytes(gid, typ, wii_row(gid, typ, T, box), 0, age, rec["qty"], 0)')
rep('''    if bad_party or not s["party"]:
        problems.append(f"party {s['party']} cannot exist on the Wii")
''', '''    if bad_party or not s["party"]:
        problems.append(f"party {s['party']} cannot exist on the Wii")
    elif canon.unsupported_party(s):
        problems.append(f"party member(s) {canon.unsupported_party(s)} are not supported (character 8 is Fiora's "
                        "second form, 9-13 are guests): their progress has no validated mapping")
''')
rep('''    # serials: Wii u16; renumber by acquisition order only if a DE serial does not fit
    for box, recs in new_recs.items():
        if any(r["serial"] > 0xFFFF for r in recs.values()):
            order = sorted(recs, key=lambda sl: recs[sl]["serial"])
            for i, sl in enumerate(order, 1):
                recs[sl] = dict(recs[sl], serial=i)
            log.setdefault("serials_renumbered", []).append(box)
''', '''    # acquisition order -> Wii ages (Phase 2F): dense 1..N with 1 = newest, as the Wii's own renumbering (0x80159488)
    # writes them. A box whose order is unchanged keeps the base's exact ages; otherwise every age of the box is
    # rewritten, so kept and re-encoded records never mix two numberings.
    ages, same_order = {}, {}
    for box in new_recs:
        new_recs[box] = canon.rerank(new_recs[box])
        n = len(new_recs[box])
        ages[box] = {sl: n + 1 - r["order"] for sl, r in new_recs[box].items()}
        same_order[box] = {sl: r["order"] for sl, r in sb["inventory"][box].items()} == \\
            {sl: r["order"] for sl, r in new_recs[box].items()}
    log["ages_rewritten"] = sorted(b for b in new_recs if not same_order[b])
''')
rep('''            if base_box.get(i) == want_rec and lineage:
                continue  # identical canonical record at the same slot: keep the exact base bytes
            if box == "gem" and base_box.get(i) == want_rec:
                continue
            enc = encode_record(box, want_rec, T, gem_desc, cur)''', '''            b_rec = base_box.get(i)
            if b_rec is not None and (lineage or box == "gem") and \\
                    canon.strip_order(b_rec) == canon.strip_order(want_rec):
                if not same_order[box] and struct.unpack_from(">H", cur, 4)[0] != ages[box][i]:
                    img.put(o + 4, "H", ages[box][i])   # same item, same bytes: only its age changes
                    nrec += 1
                continue  # identical canonical record at the same slot: keep the exact base bytes
            enc = encode_record(box, want_rec, T, gem_desc, cur, ages[box][i])''')
rep('''    for box, m in remap.items():
        cd["inventory"][box] = {m.get(sl, sl): r for sl, r in cd["inventory"][box].items()}
''', '''    for box, m in remap.items():
        cd["inventory"][box] = {m.get(sl, sl): r for sl, r in cd["inventory"][box].items()}
    for box in cd["inventory"]:
        cd["inventory"][box] = canon.rerank(cd["inventory"][box])
''')
open(P, "w", encoding="utf-8").write(s)
print("patched", P)
