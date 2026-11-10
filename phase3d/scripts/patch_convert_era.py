P = r"C:\Dev\XC_Wii_to_DE_Research\tools\convert.py"
s = open(P, encoding="utf-8").read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
rep('''    w_arts = T["w_arts"]
    for k_str, p in plan["characters"].items():
        k = int(k_str)''', '''    w_arts = T["w_arts"]
    post = 8 in {int(x) for x in plan["characters"]}    # Phase 3D: Fiora is character 8 (scenario >= 275)
    for k_str, p in plan["characters"].items():
        k = int(k_str)''')
rep('''        tpl_unl = struct.unpack_from("<8I", tpl, o + 0xA4)
        img.put(o + 0xA4, "8I", *[p["link_unlock_index"][i] if i + 1 != k and i + 1 <= 7 else tpl_unl[i]
                                  for i in range(8)])
        links = bytearray(tpl[o + 0xC4:o + 0xEC])
        for src in range(1, 8):
            links[5 * (src - 1):5 * src] = bytes(p["links"][src - 1])
        img.raw(o + 0xC4, bytes(links))''', '''        tpl_unl = struct.unpack_from("<8I", tpl, o + 0xA4)
        links = bytearray(tpl[o + 0xC4:o + 0xEC])
        if not post:
            img.put(o + 0xA4, "8I", *[p["link_unlock_index"][i] if i + 1 != k and i + 1 <= 7 else tpl_unl[i]
                                      for i in range(8)])
            for src in range(1, 8):
                links[5 * (src - 1):5 * src] = bytes(p["links"][src - 1])
        else:
            # Phase 3D: the Wii's single "Fiora" row is DE slot 8 from scenario 275; DE slot 3 (her first form) keeps
            # its template value, except the unlock level, which the DE keeps equal in slots 3 and 8 (s276-s291)
            others = [x for x in (1, 2, 8, 4, 5, 6, 7) if x != k]
            unl = list(tpl_unl)
            for src in others:
                unl[src - 1] = p["link_unlock_index"][src - 1]
                links[5 * (src - 1):5 * src] = bytes(p["links"][src - 1])
            if k != 8:
                unl[2] = unl[7]
            img.put(o + 0xA4, "8I", *unl)
        img.raw(o + 0xC4, bytes(links))''')
rep('''    party = ir["party"]
    img.put(PARTY, "12H", *(party + [0] * (12 - len(party))))''', '''    if post:   # Phase 3D: the DE keeps Fiora's two records' link-unlock arrays equal (s260-s291)
        o3, o8 = CHAR + CHAR_SIZE * 2, CHAR + CHAR_SIZE * 7
        img.raw(o3 + 0xA4, bytes(img.b[o8 + 0xA4:o8 + 0xC4]))
    party = ir["party"]
    img.put(PARTY, "12H", *(party + [0] * (12 - len(party))))''')
rep('''def unsupported_wii_party(ir):
    import canon
    return [p for p in ir["party"] if p not in canon.SUPPORTED_PARTY]''', '''def unsupported_wii_party(ir, story=None):
    """Phase 3D: era-aware (canon.unsupported_party); story = the Wii scenario (flag 0x20)."""
    import canon
    return canon.unsupported_party({"party": ir["party"], "story": story if story is not None else ir.get("story", 0)})''')
rep('''    if "party_check" in features and unsupported_wii_party(ir):
        raise ConvertError(f"party member(s) {unsupported_wii_party(ir)} are not supported (character 8 is Fiora's "
                           "second form, 9-13 are guests); their progress has no validated mapping")''',
'''    story = fm.wii_get(wii, 0x20)
    if "party_check" in features and unsupported_wii_party(ir, story):
        raise ConvertError(f"party member(s) {unsupported_wii_party(ir, story)} cannot be in the party at scenario "
                           f"{story} (characters 9-13 are prologue guests; Fiora is character 3 before scenario 275 "
                           "and character 8 from 275)")''')
open(P, "w", encoding="utf-8").write(s)
print("ok")
