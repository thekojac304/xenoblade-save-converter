import os
P = r"C:\Dev\XC_Wii_to_DE_Research\tools\canon.py"
s = open(P, encoding="utf-8").read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (a[:60], s.count(a))
    s = s.replace(a, b)
rep('SUPPORTED_PARTY = range(1, 8)   # Fiora\'s second form (8) and the guests (9-13) have no validated mapping\n',
    '''SUPPORTED_PARTY = range(1, 8)   # up to 3C; Phase 3D: era-aware, see main_chars()
# Phase 3D: Fiora is character 3 for scenarios 11..274 and character 8 ("Fiora", later form) from 275 on - the
# affinity-chart table JNL_PCrelatelist says so in both games (pc 3: flg_s2 35..flg_e2 274; pc 8: flg_s1 275..404).
# The other form's record is dormant (8 before 275: initial level 40, staging gear) or frozen (3 from 275).
FIORA_ERA = 275
GUESTS = range(9, 14)            # Dickson, Mumkhar, Alvis, Dunban x2: BTL_pclist guest=1 (prologue/scene characters)
''')
rep('''def unsupported_party(shared):
    """Party members the converter cannot carry (character 8 = Fiora's second form, 9-13 = guests)."""
    return [p for p in shared["party"] if p not in SUPPORTED_PARTY]''',
'''def fiora(story):
    """The character id that is Fiora at this scenario (3 before FIORA_ERA, 8 from it)."""
    return 8 if story >= FIORA_ERA else 3


def main_chars(story):
    """The seven playable characters at this scenario, in link-row order (Fiora at position 3)."""
    return (1, 2, fiora(story), 4, 5, 6, 7)


def unsupported_party(shared):
    """Party members that cannot exist at this scenario: guests 9-13 (prologue/scene characters, never in a saved party
    in 359 real saves), DE-only 14+, and the inactive Fiora form (8 before scenario 275, 3 from 275)."""
    allowed = set(main_chars(shared.get("story", 0)))
    return [p for p in shared["party"] if p not in allowed]''')
# Wii side
rep('''    chars = {}
    for k in MAIN_CHARS:
        c = ir["characters"][k]
        arts = {}
        for a in T["w_arts"].values():
            if a["pc"] == k:
                arts[a["id"]] = list(c["art_levels"][a["idx"]])
        canon_k = k
        others = [x for x in range(1, 8) if x != canon_k]''',
'''    chars = {}
    mc = main_chars(fm.wii_get(wii, 0x20))
    for k in mc:
        c = ir["characters"][k]
        arts = {}
        for a in T["w_arts"].values():
            if a["pc"] == k:
                arts[a["id"]] = list(c["art_levels"][a["idx"]])
        others = [x for x in mc if x != k]   # link rows 5..10: the other six in id order (Fiora's row shared by 3/8)''')
rep('''        "exp_accum": {k: ir["characters"][k]["exp_accum"] for k in MAIN_CHARS},''',
    '''        "exp_accum": {k: ir["characters"][k]["exp_accum"] for k in mc},''')
open(P, "w", encoding="utf-8").write(s)
print("wii side ok")
