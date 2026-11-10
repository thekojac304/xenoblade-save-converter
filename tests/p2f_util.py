"""Phase 2F test helpers: fixtures and a library of VALID gameplay mutations for both save formats.

Everything produced here is SYNTHETIC: a real save of the user's (or a public DE save) with game-plausible changes
written by the same byte rules the games use (Wii item pickup ages every item, code 0x80159080; DE pickup takes the
per-type counter 0x46900). They test the converter's logic, not game behaviour. Mutations never create states the
games cannot produce (levels 1..99 with EXP below the next level cost, quantities 1..99, item ids valid for their
box, quest bytes in each game's encoding).
"""
import json
import os
import random
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import canon  # noqa: E402
import convert  # noqa: E402
import de_save  # noqa: E402
import de_to_wii  # noqa: E402
import flagmap as fm  # noqa: E402
import quest_counters as qc  # noqa: E402
import wii_save  # noqa: E402

O = os.path.join(ROOT, "work", "originals")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
PUBLIC = os.path.join(ROOT, "public", "blobs")
FIXTURES = os.path.join(ROOT, "phase2f", "fixtures")
_T = None


def tables():
    global _T
    if _T is None:
        _T = convert.load_tables()
    return _T


def rd(p):
    with open(p, "rb") as f:
        return f.read()


def wii01():
    return rd(os.path.join(O, "monado01"))


def wii03():
    return rd(os.path.join(O, "monado03"))


def tpl():
    return rd(TPL)


_DE0 = None


def de0():
    """The 2F Wii -> DE conversion of monado01 (scenario 150): the DE side of the user's playthrough."""
    global _DE0
    if _DE0 is None:
        out, log, fail = convert.build(wii01(), tpl(), tables())
        assert not fail, fail
        _DE0 = out
    return _DE0


BOX_TYPE = canon.BOX_TYPE
EQUIP = canon.EQUIP
WBOX = {n: (t, off, size, slots) for n, t, off, size, slots in wii_save.BOXES}
DBOX = {n: (t, off, size) for n, t, off, size, _ in de_save.BOXES}
DE_CHAR = 0x152728
WII_STACKABLE = ("collectable", "material", "keyitem", "artmanual")


def valid_gids(box, game="wii"):
    T = tables()
    typ = BOX_TYPE[box]
    src = T["w_item"] if game == "wii" else T["d_item"]
    return sorted(g for g, r in src.items() if r["itemType"] == typ and g)


def de_only_gids(box):
    T = tables()
    typ = BOX_TYPE[box]
    return sorted(g for g, r in T["d_item"].items() if r["itemType"] == typ and g and
                  (g not in T["w_item"] or T["w_item"][g]["itemType"] != typ))


# --------------------------------------------------------------------------------------------- Wii mutations
class Wii:
    def __init__(self, data):
        self.img = de_to_wii.WiiImage(data)

    @property
    def b(self):
        return bytes(self.img.b)

    def done(self):
        """Emulate the Wii's own save: the THUM preview (leader level 0x84, play time 0x2A/0x23) is rewritten from
        the game state, then the section CRCs. Without this a fixture would be a state the game never writes."""
        party = [struct.unpack_from(">H", self.img.b, wii_save.PARTY + 4 * i)[0] for i in range(12)]
        if party[0]:
            lv = self.u32(wii_save.CHAR_BASE + wii_save.CHAR_SIZE * party[0] + 0x17C)
            if struct.unpack_from(">H", self.img.b, 0x84)[0] != lv:
                self.img.put(0x84, "H", lv)
        pt = self.u32(0x11EB0)
        if (struct.unpack_from(">HH", self.img.b, 0x2A), self.img.b[0x23]) != ((pt >> 12, pt >> 6 & 63), pt & 63):
            self.img.put(0x2A, "HH", pt >> 12, pt >> 6 & 63)
            self.img.put(0x23, "B", pt & 63)
        de_to_wii.fix_crcs(self.img)
        return bytes(self.img.b)

    def u32(self, o):
        return struct.unpack_from(">I", self.img.b, o)[0]

    def money(self, delta):
        o = wii_save.ITEM + 0x120E8
        self.img.put(o, "I", max(0, min(self.u32(o) + delta, 999_999_999)))

    def play(self, seconds):
        pt = self.u32(0x11EB0)
        s = (pt >> 12) * 3600 + (pt >> 6 & 63) * 60 + (pt & 63) + seconds
        self.img.put(0x11EB0, "I", (s // 3600) << 12 | (s // 60 % 60) << 6 | s % 60)

    def char(self, k, off, fmt, v):
        self.img.put(wii_save.CHAR_BASE + wii_save.CHAR_SIZE * k + off, fmt, v)

    def level_up(self, k, levels=1):
        T = tables()
        o = wii_save.CHAR_BASE + wii_save.CHAR_SIZE * k
        lv = min(self.u32(o + 0x17C) + levels, 99)
        gained = sum(T["w_grow"][x]["level_exp"] for x in range(self.u32(o + 0x17C) + 1, lv + 1))
        self.img.put(o + 0x17C, "I", lv)
        self.img.put(o + 0x2A4, "I", 0)
        self.img.put(o + 0x2A0, "I", self.u32(o + 0x2A0) + gained)

    def flag(self, gid, v):
        de_to_wii.wii_set_flag(self.img, gid, v)

    def slot_free(self, box):
        typ, off, size, slots = WBOX[box]
        cap = de_to_wii.wii_capacity(bytes(self.img.b))[box]
        for i in range(cap):
            if not any(self.img.b[wii_save.ITEM + off + size * i:wii_save.ITEM + off + size * (i + 1)]):
                return i
        return None

    def age_all(self):
        """The Wii's pickup rule (0x80159080): every record of boxes 2..13 ages by one (saturating at 0xFFFF)."""
        for name, (typ, off, size, slots) in WBOX.items():
            for i in range(slots):
                o = wii_save.ITEM + off + size * i
                if struct.unpack_from(">I", self.img.b, o)[0]:
                    a = struct.unpack_from(">H", self.img.b, o + 4)[0]
                    if a < 0xFFFF:
                        self.img.put(o + 4, "H", a + 1)

    def pickup(self, box, gid, qty=1, slot=None):
        """New record (stackables: qty) in the first free slot, aged like the game does. -> slot."""
        T = tables()
        typ, off, size, _ = WBOX[box]
        sl = self.slot_free(box) if slot is None else slot
        if sl is None:
            raise ValueError(f"{box} full")
        self.age_all()
        row = T["w_item"][gid]["itemID"]
        o = wii_save.ITEM + off + size * sl
        if box in EQUIP:
            rec = de_to_wii.header_bytes(gid, typ, row, 0, 0, 1, 0) + bytes(32) + struct.pack(">4H", *[0xFFFF] * 4) + \
                struct.pack(">BBH", 0, de_to_wii.KIND[box], 0)
        else:
            rec = de_to_wii.header_bytes(gid, typ, row, 0, 0, qty, 0) + bytes(size - 8)
        self.img.raw(o, rec)
        return sl

    def remove(self, box, sl):
        typ, off, size, _ = WBOX[box]
        self.img.raw(wii_save.ITEM + off + size * sl, bytes(size))

    def quest_byte(self, q, s, v):
        self.img.raw(qc.WII_QC + 8 * q + s, bytes([v & 0xFF]))

    def clock(self, hour, minute, day):
        self.img.put(0x11EB4, "f", 1800.0 * hour + 30.0 * minute)
        self.img.put(0x11EB8, "H", day)


# --------------------------------------------------------------------------------------------- DE mutations
class DE:
    def __init__(self, data):
        self.b = bytearray(data)

    def done(self):
        return bytes(self.b)

    def u32(self, o):
        return struct.unpack_from("<I", self.b, o)[0]

    def money(self, delta):
        struct.pack_into("<I", self.b, de_save.MONEY, max(0, min(self.u32(de_save.MONEY) + delta, 99_999_999)))

    def play(self, seconds):
        struct.pack_into("<I", self.b, 4, self.u32(4) + seconds)

    def level_up(self, k, levels=1):
        o = DE_CHAR + 0x138 * (k - 1)
        lv = min(self.u32(o) + levels, 99)
        struct.pack_into("<II", self.b, o, lv, 0)
        if self.u32(o + 0xEC) < lv:
            struct.pack_into("<II", self.b, o + 0xEC, lv, 0)

    def flag(self, gid, v):
        img = convert.Image(bytes(self.b))
        convert.de_set_flag(img, gid, v)
        self.b = img.b

    def slot_free(self, box):
        typ, off, size = DBOX[box]
        return next((i for i in range(500) if self.b[off + size * i + 0x10] == 0), None)

    def pickup(self, box, gid, qty=1, socket_count=0):
        """New DE record with the next acquisition number of its type. -> slot."""
        T = tables()
        typ, off, size = DBOX[box]
        sl = self.slot_free(box)
        ctr = de_save.SERIALS + 4 * typ
        serial = self.u32(ctr) + 1
        struct.pack_into("<I", self.b, ctr, serial)
        pat = bytes(self.b[off + size * 499:off + size * 500]) if not self.b[off + size * 499 + 0x10] else bytes(size)
        rec = bytearray(pat)
        struct.pack_into("<HHHHH", rec, 0, sl, typ, gid, typ, qty)
        struct.pack_into("<I", rec, 0xC, serial)
        rec[0x10], rec[0x11] = 1, 0
        if box in EQUIP:
            if box != "weapon":
                rec[0x14] = T["w_equip"].get(T["d_item"][gid]["itemID"], {}).get("arm_type", 0)
            rec[0x15] = socket_count
        self.b[off + size * sl:off + size * (sl + 1)] = rec
        return sl

    def remove(self, box, sl):
        typ, off, size = DBOX[box]
        free = next(i for i in range(499, -1, -1) if self.b[off + size * i + 0x10] == 0)
        self.b[off + size * sl:off + size * (sl + 1)] = self.b[off + size * free:off + size * (free + 1)]

    def quest_byte(self, q, s, v):
        self.b[qc.DE_QC + 8 * q + s] = v

    def clock(self, hour, minute, day):
        struct.pack_into("<HH", self.b, 0x149C04, hour, minute)
        struct.pack_into("<H", self.b, 0x149C24, day)


def referenced(shared):
    """{(box, slot)} referenced by equipment or sockets (must not be removed)."""
    out = set()
    for c in shared["characters"].values():
        if c["equipment"]:
            out |= {(s, v) for s, v in c["equipment"].items() if v is not None}
    for box in EQUIP:
        for r in shared["inventory"][box].values():
            out |= {("gem", x[1]) for x in r["sockets"] if x and x[0] == "gem"}
    return out


# --------------------------------------------------------------------------------------------- random mutations
def random_mutations(rng, n, game):
    """A list of n mutation descriptors (JSON-able, replayable). game: 'wii' | 'de'."""
    T = tables()
    muts = []
    boxes = list(WII_STACKABLE) + ["weapon", "head", "gem"] if game == "wii" else \
        list(WII_STACKABLE) + ["weapon", "head"]
    quests = sorted(q for q in qc.quests() if q < qc.WII_N)
    for _ in range(n):
        kind = rng.choice(["money", "play", "level", "flag", "pickup", "remove", "quest", "clock", "art"])
        if kind == "money":
            muts.append(["money", rng.choice([-500, -1, 1, 37, 1000, 25000])])
        elif kind == "play":
            muts.append(["play", rng.randint(1, 7200)])
        elif kind == "level":
            muts.append(["level", rng.randint(1, 7), rng.randint(1, 3)])
        elif kind == "flag":   # landmark / collectopaedia-range 1-bit flags shared by both games
            muts.append(["flag", rng.randint(0xA20 + 64, 0x2000), 1])
        elif kind == "pickup":
            box = rng.choice(boxes)
            if box == "gem":
                continue
            muts.append(["pickup", box, rng.choice(valid_gids(box)), rng.randint(1, 5) if box in WII_STACKABLE else 1])
        elif kind == "remove":
            muts.append(["remove", rng.choice(list(WII_STACKABLE)), rng.random()])
        elif kind == "quest":
            q = rng.choice(quests)
            r = qc.quests()[q]
            sl = [(s, t, n_) for s, t, c, n_ in qc.slots(r) if t]
            if not sl:
                continue
            s, t, n_ = rng.choice(sl)
            muts.append(["quest", q, s, t, n_, rng.random()])
        elif kind == "clock":
            muts.append(["clock", rng.randint(0, 23), rng.randint(0, 59), rng.randint(1, 400)])
        elif kind == "art":
            arts = [a for a in T["w_arts"].values() if 1 <= a["pc"] <= 7]
            a = rng.choice(arts)
            muts.append(["art", a["pc"], a["idx"], a["id"], rng.randint(1, 10)])
    return muts


def apply(data, muts, game):
    """Apply mutation descriptors to save bytes (skipping ones that do not apply, e.g. a full box)."""
    T = tables()
    m = Wii(data) if game == "wii" else DE(data)
    for mu in muts:
        k = mu[0]
        if k == "money":
            m.money(mu[1])
        elif k == "play":
            m.play(mu[1])
        elif k == "level":
            m.level_up(mu[1], mu[2])
        elif k == "flag":
            m.flag(mu[1], mu[2])
        elif k == "pickup":
            if m.slot_free(mu[1]) is not None:
                m.pickup(mu[1], mu[2], mu[3])
        elif k == "remove":
            cur = canon.from_wii(m.b, T) if game == "wii" else canon.from_de(bytes(m.b), T)
            ref = referenced(cur["shared"])
            cand = sorted(sl for sl in cur["shared"]["inventory"][mu[1]] if (mu[1], sl) not in ref)
            if cand:
                m.remove(mu[1], cand[int(mu[2] * len(cand))])
        elif k == "quest":
            q, s, t, n_, x = mu[1:]
            st = fm.wii_get(m.b, 0x220 + q) if game == "wii" else fm.de_get(bytes(m.b), 0x220 + q)
            if st in (254, 255):
                continue          # closed quests are inert; their counters are not changed by play
            if game == "wii":
                v = int(x * (n_ + 1)) if t == 1 else int(x * 2)
                m.quest_byte(q, s, v)
            else:
                v = int(x * n_) if t == 1 else 0
                m.quest_byte(q, s, 0xFF if x > 0.7 else v)
        elif k == "clock":
            m.clock(*mu[1:])
        elif k == "art":
            pc, idx, aid, lv = mu[1:]
            if game == "wii":
                m.char(pc, 0xE8 + 2 * idx, "B", lv)
            else:
                m.b[0x153AA8 + 2 * (aid - 1)] = lv
    return m.done()


def save_fixture(name, payload):
    os.makedirs(FIXTURES, exist_ok=True)
    p = os.path.join(FIXTURES, name + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, default=str)
    return p


def minimize(muts, fails):
    """Delta debugging (one-at-a-time removal until fixpoint): smallest sub-list of muts for which fails() holds."""
    cur = list(muts)
    changed = True
    while changed and len(cur) > 1:
        changed = False
        for i in range(len(cur)):
            trial = cur[:i] + cur[i + 1:]
            if fails(trial):
                cur, changed = trial, True
                break
    return cur


def rng(seed):
    return random.Random(seed)
