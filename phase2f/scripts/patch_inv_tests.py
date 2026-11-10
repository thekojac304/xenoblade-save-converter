"""Fixture corrections in tests/test_phase2f_inventory.py (valid game states only; assertions unchanged):
gems are built from BTL_skill (rank 1..6, chance = table value, strength within the rank's range), crystal boxes are
filled by copying the user's real crystal records, equipped test weapons go to party members only."""
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests", "test_phase2f_inventory.py")
s = open(P, encoding="utf-8").read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''def fill(de, box, slots, gids=None):
    b = bytearray(clear_de_box(de, box))
    gids = gids or U.valid_gids(box)
    for i, sl in enumerate(slots):
        if box == "gem":
            de_set_record(b, box, sl, 0, 1, i + 1, gem=(1, 2, 10, 0))
        else:
            de_set_record(b, box, sl, gids[i % len(gids)], 1, i + 1)
    return bytes(b)''', '''def gem(effect, rank, top=False):
    """A gem the game can produce: rank 1..6, chance from BTL_skill, strength at the low (or top) end of the rank."""
    sk = T["w_skill"][effect]
    r = "EDCBAS"[rank - 1]
    return effect, rank, sk["upper_" + r] if top else sk["lower_" + r], sk["percent_" + r]


def fill(de, box, slots, gids=None):
    src = canon.from_de(de, T)["shared"]["inventory"]["crystal"] if box == "crystal" else None
    real = [s for s in sorted(src)] if src else []
    typ, off, size = U.DBOX[box]
    orig = bytes(de)
    b = bytearray(clear_de_box(de, box))
    gids = gids or U.valid_gids(box)
    for i, sl in enumerate(slots):
        if box == "gem":
            de_set_record(b, box, sl, 0, 1, i + 1, gem=gem(1 + i % 20, 1 + i % 6))
        elif box == "crystal":          # copies of the user's real crystal records
            r = real[i % len(real)]
            rec = bytearray(orig[off + size * r:off + size * (r + 1)])
            struct.pack_into("<H", rec, 0, sl)
            struct.pack_into("<I", rec, 0xC, i + 1)
            b[off + size * sl:off + size * (sl + 1)] = rec
        else:
            de_set_record(b, box, sl, gids[i % len(gids)], 1, i + 1)
    if box == "crystal":
        struct.pack_into("<I", b, U.de_save.SERIALS + 4 * typ, len(slots))
    return bytes(b)''')
rep('''        de_set_record(b, "gem", gem_sl, 0, 1, 999, gem=(5, 3, 20, 4))''',
    '''        de_set_record(b, "gem", gem_sl, 0, 1, 999, gem=gem(5, 3))''')
rep('''        self.assertEqual((g["desc"]["effect"], g["desc"]["rank"], g["desc"]["strength"], g["desc"]["chance"]), (5, 3, 20, 4))''',
    '''        self.assertEqual((g["desc"]["effect"], g["desc"]["rank"], g["desc"]["strength"], g["desc"]["chance"]), gem(5, 3))''')
rep('''        for k, sl in enumerate(range(caps["weapon"], caps["weapon"] + 5), 1):
            struct.pack_into("<HH", b, U.DE_CHAR + 0x138 * (k - 1) + 0x14 + 4 * 5, sl, 2)''',
    '''        party = canon.from_de(d, T)["shared"]["party"]           # absent characters hold no equipment in DE
        for k, sl in zip(party, range(caps["weapon"], caps["weapon"] + 5)):
            struct.pack_into("<HH", b, U.DE_CHAR + 0x138 * (k - 1) + 0x14 + 4 * 5, sl, 2)''')
rep('''            de_set_record(b, "gem", sl, 0, 1, 2000 + i, gem=(10 + i, i, 50 + i, i))''',
    '''            de_set_record(b, "gem", sl, 0, 1, 2000 + i, gem=gem(10 + i, 1 + i))''')
rep('''        de_set_record(b, "gem", 473, 0, 1, 2003, gem=(20, 7, 255, 100))              # loose gem, extreme values''',
    '''        de_set_record(b, "gem", 473, 0, 1, 2003, gem=gem(20, 6, top=True))           # loose gem, top of rank S''')
rep('''        de_set_record(b, "gem", 474, 0, 1, 2004, gem=(20, 8, 10, 1))                 # rank 8 > 3 bits''',
    '''        de_set_record(b, "gem", 474, 0, 1, 2004, gem=(20, 8, 10, 1))                 # rank 8 > 3 bits
        with self.assertRaises(de_to_wii.IncompatibleError):
            de_to_wii.build(bytes(b), U.wii01(), T, lineage=True)
        b = bytearray(U.de0())
        de_set_record(b, "gem", 474, 0, 1, 2004, gem=(20, 3, 10, 99))                # chance not the table's''')
open(P, "w", encoding="utf-8").write(s)
print("patched")
