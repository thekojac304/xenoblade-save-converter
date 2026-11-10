P = r"C:\Dev\XC_Wii_to_DE_Research\tools\phase2c.py"
s = open(P, encoding="utf-8").read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
rep('''def map_characters(ir, T, tal, d_wii):
    planned = {}
    joined = set(ir["party"])  # at scenario 150 the joined main characters are exactly the party (Phase 2B)
    inv = {b: {r["index"]: r for r in ir["items"][b]} for b in ("head", "body", "arm", "legs", "feet", "weapon")}
    for c in ir["characters"]:
        k = c["id"]
        if k == 8:
            tal.add("characters:inactive", k, True, False, "Mechon Fiora not joined at scenario 150; Wii record 8 "
                    "holds a copy of record 3's skill object (0x800A366C) -> keep DE template", "C")
            continue''',
'''def map_characters(ir, T, tal, d_wii):
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
            continue''')
rep('''        # skill trees (rows 0-4) — learn routine 0x800A34C8: node value = learned PSV skill id
        base = (k - 1) * 25  # BTL_PSVskill rows 1-200 = characters 1-8 x 25''',
'''        # skill trees (rows 0-4) — learn routine 0x800A34C8: node value = learned PSV skill id
        base = (k - 1) * 25  # BTL_PSVskill rows 1-200 = characters 1-8 x 25
        alt = SKILL_ID_ALT.get(k)    # Phase 3D: see SKILL_ID_ALT''')
rep('''            ids_ok = all(v == 0 or (T["w_psv"].get(v) and base < v <= base + 25 and (v - base - 1) // 5 == t) for v in nodes)''',
'''            ids_ok = all(v == 0 or (T["w_psv"].get(v) and any(b_ < v <= b_ + 25 and (v - b_ - 1) // 5 == t
                                                               for b_ in (base,) + ((alt,) if alt is not None else ())))
                         for v in nodes)''')
rep('''        canon = 3 if k == 8 else k
        others = [x for x in range(1, 8) if x != canon]''',
'''        others = [x for x in mc if x != k]''')
rep('''            sbase = (src - 1) * 25
            ok = all(v == 0 or sbase < v <= sbase + 25 for v in ids)''',
'''            sbase = (src - 1) * 25
            salt = SKILL_ID_ALT.get(src)
            ok = all(v == 0 or sbase < v <= sbase + 25 or (salt is not None and salt < v <= salt + 25) for v in ids)''')
rep('''def map_characters(ir, T, tal, d_wii):''', '''# Phase 3D: skill ids Fiora's later form may legitimately carry in her (mirrored) skill object, besides her own
# (176-200): set from the post-rejoin game saves (see XC_PHASE3D_REPORT.md). {character: alternative id base}
SKILL_ID_ALT = {}


def map_characters(ir, T, tal, d_wii):''')
open(P, "w", encoding="utf-8").write(s)
print("ok")
