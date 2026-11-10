P = r"C:\Dev\XC_Wii_to_DE_Research\tools\de_to_wii.py"
s = open(P, encoding="utf-8").read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
rep('''    for k, c in s["characters"].items():
        bc = sb["characters"][k]
        o = CHAR_BASE + CHAR_SIZE * k
        if c == bc:''', '''    mc = canon.main_chars(s["story"])      # Phase 3D: Fiora = 3 before scenario 275, 8 from 275
    for k, c in s["characters"].items():
        bc = sb["characters"].get(k) or _base_char(base, k)   # base from the other era: raw record values
        o = CHAR_BASE + CHAR_SIZE * k
        if c == bc:''')
rep('''        # skill links: rows 5..10 = other main characters in id order
        others = [x for x in range(1, 8) if x != k]''', '''        # skill links: rows 5..10 = the other six main characters in id order (Fiora's row shared by 3 and 8)
        others = [x for x in mc if x != k]''')
rep('''    o3, o8 = CHAR_BASE + CHAR_SIZE * 3, CHAR_BASE + CHAR_SIZE * 8
    if img.b[o3 + 0x1F4:o3 + 0x2A0] != img.b[o8 + 0x1F4:o8 + 0x2A0]:
        img.raw(o8 + 0x1F4, bytes(img.b[o3 + 0x1F4:o3 + 0x2A0]))
        log["fiora_skill_copy_synced"] = True''', '''    # Phase 3D: the copy goes both ways (0x800A3644: 3 -> 8, 0x800A366C: 8 -> 3); from scenario 275 the active
    # Fiora is record 8, so record 3 receives record 8's skill object.
    o3, o8 = CHAR_BASE + CHAR_SIZE * 3, CHAR_BASE + CHAR_SIZE * 8
    src_o, dst_o = (o8, o3) if canon.fiora(s["story"]) == 8 else (o3, o8)
    if img.b[o3 + 0x1F4:o3 + 0x2A0] != img.b[o8 + 0x1F4:o8 + 0x2A0]:
        img.raw(dst_o + 0x1F4, bytes(img.b[src_o + 0x1F4:src_o + 0x2A0]))
        log["fiora_skill_copy_synced"] = "8->3" if src_o == o8 else True''')
rep('''    for k in range(1, 8):
        if k in s["party"]:
            continue
        o = CHAR_BASE + CHAR_SIZE * k''', '''    for k in mc:
        if k in s["party"]:
            continue
        o = CHAR_BASE + CHAR_SIZE * k''')
rep('''def build(de, base, T, lineage=True,''', '''def _base_char(base, k):
    """Phase 3D: canonical-like view of a base record that is outside the base save's own era (e.g. record 8 of a
    Wii base from before scenario 275): only the values the writer compares; links/unlocks never 'same'."""
    o = CHAR_BASE + CHAR_SIZE * k
    return {"level": struct.unpack_from(">I", base, o + 0x17C)[0], "exp": struct.unpack_from(">I", base, o + 0x2A4)[0],
            "links": {}, "link_unlock": {}}


def build(de, base, T, lineage=True,''')
open(P, "w", encoding="utf-8").write(s)
print("ok")
