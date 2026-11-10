"""Phase 3C test helpers: DE-only per-item metadata on game-written saves, and SYNTHETIC Wii-side inventory
mutations that mimic the game's own rules (the Wii/3DS keep every item in its slot; an added or stacked-up item
becomes the newest - 0x80159080..0x80159100; saved ages are dense ranks 1..N with 1 = newest - 0x80159488).
Synthetic edits are used only where no game-written equivalent exists; they are labelled as such in the reports."""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P3C = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3C)
for p in (os.path.join(ROOT, "phase3b", "tests"), os.path.join(ROOT, "phase3b", "src"),
          os.path.join(ROOT, "phase3a", "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import hubfix as H  # noqa: E402
import canon  # noqa: E402
import de_save  # noqa: E402
import wii_save  # noqa: E402
import xc3d  # noqa: E402
import xcservice as xs  # noqa: E402

T = H.T
rd = H.rd
WORK = os.path.join(P3C, "work", "tests")
DBOX = {n: (t, o, s) for n, t, o, s, _ in de_save.BOXES}
WBOX = {n: (t, o, s) for n, t, o, s, _ in wii_save.BOXES}


def fresh(name):
    d = os.path.join(WORK, name)
    if os.path.isdir(d):
        import shutil
        shutil.rmtree(d)
    os.makedirs(d)
    return d


# ------------------------------------------------------------------------------------------------- DE side
def de_records(img):
    """{box: {slot: record bytes}} of present DE items."""
    out = {}
    for name, (typ, off, size) in DBOX.items():
        out[name] = {i: bytes(img[off + size * i:off + size * (i + 1)]) for i in range(500) if img[off + size * i + 0x10]}
    return out


def set_fav(img, picks):
    """picks: {box: [slots]} -> DE image with the favourite byte (+0x11) set (synthetic edit; DE has no checksum)."""
    b = bytearray(img)
    for box, slots in picks.items():
        typ, off, size = DBOX[box]
        for sl in slots:
            assert b[off + size * sl + 0x10], (box, sl)
            b[off + size * sl + 0x11] = 1
    return bytes(b)


def favs(img):
    """Favourite items as a multiset of (box, item identity) -> count (slots move, identities do not)."""
    c = canon.from_de(img, T)["shared"]["inventory"]
    out = collections.Counter()
    for box, (typ, off, size) in DBOX.items():
        for sl in range(500):
            if img[off + size * sl + 0x10] and img[off + size * sl + 0x11]:
                out[(box, repr(canon.item_key(box, c[box][sl])))] += 1
    return out


def fav_slots(img, box):
    typ, off, size = DBOX[box]
    return sorted(sl for sl in range(500) if img[off + size * sl + 0x10] and img[off + size * sl + 0x11])


def identity_pairs(a, b, box):
    """Pair items of two DE saves by identity in acquisition order -> [(slot_a, slot_b)]."""
    ca, cb = canon.from_de(a, T)["shared"]["inventory"][box], canon.from_de(b, T)["shared"]["inventory"][box]
    pa, pb = collections.defaultdict(list), collections.defaultdict(list)
    for sl in sorted(ca, key=lambda s: ca[s]["order"]):
        pa[canon.item_key(box, ca[sl])].append(sl)
    for sl in sorted(cb, key=lambda s: cb[s]["order"]):
        pb[canon.item_key(box, cb[sl])].append(sl)
    return [(x, y) for k, v in pa.items() for x, y in zip(v, pb.get(k, []))]


def de_only_bytes_equal(a, b, box):
    """Number of identity-paired records whose bytes match apart from slot index (+0) and serial (+0xC)."""
    typ, off, size = DBOX[box]
    same = diff = 0
    for x, y in identity_pairs(a, b, box):
        ra = bytearray(a[off + size * x:off + size * (x + 1)])
        rb = bytearray(b[off + size * y:off + size * (y + 1)])
        for r in (ra, rb):
            r[0:2] = b"\0\0"
            r[0xC:0x10] = bytes(4)
        same, diff = (same + 1, diff) if ra == rb else (same, diff + 1)
    return same, diff


# ------------------------------------------------------------------------------------------------ Wii side
def _rec(box, slot):
    typ, off, size = WBOX[box]
    return wii_save.ITEM + off + size * slot, size


def wii_items(img, box):
    return canon.from_wii(img, T)["shared"]["inventory"][box]


NSLOTS = {n: (wii_save.EQUIP_INVENTORY_SLOTS if s == 0x34 else c) for n, _, _, s, c in wii_save.BOXES}


def _ages(b, box):
    """{slot: age} of the inventory records of a Wii box (equipment staging records excluded)."""
    out = {}
    for sl in range(NSLOTS[box]):
        o, size = _rec(box, sl)
        if struct.unpack_from(">I", b, o)[0]:
            out[sl] = struct.unpack_from(">H", b, o + 4)[0]
    return out


def make_newest(img, box, slot):
    """The game's 'add': the record becomes the newest (age 1 after renumbering), every newer one ages by one."""
    b = bytearray(img)
    ages = _ages(b, box)
    a = ages[slot]
    for sl, v in ages.items():
        o, _ = _rec(box, sl)
        if sl == slot:
            struct.pack_into(">H", b, o + 4, 1)
        elif v < a:
            struct.pack_into(">H", b, o + 4, v + 1)
    return xc3d.fix_wii_checksums(bytes(b))


def remove(img, box, slot):
    """Sell / use up: the record is cleared, ages renumbered densely."""
    b = bytearray(img)
    ages = _ages(b, box)
    a = ages.pop(slot)
    o, size = _rec(box, slot)
    b[o:o + size] = bytes(size)
    for sl, v in ages.items():
        if v > a:
            struct.pack_into(">H", b, _rec(box, sl)[0] + 4, v - 1)
    return xc3d.fix_wii_checksums(bytes(b))


def add_copy(img, box, src_slot, dst_slot):
    """A new item identical to the one at src_slot, obtained now, placed in the free dst_slot."""
    b = bytearray(img)
    o, size = _rec(box, src_slot)
    d, _ = _rec(box, dst_slot)
    assert not any(b[d:d + size]), "destination slot is not free"
    b[d:d + size] = b[o:o + size]
    for sl, v in _ages(b, box).items():
        if sl != dst_slot:
            struct.pack_into(">H", b, _rec(box, sl)[0] + 4, v + 1)
    struct.pack_into(">H", b, d + 4, 1)
    return xc3d.fix_wii_checksums(bytes(b))


def set_qty(img, box, slot, q):
    b = bytearray(img)
    o, _ = _rec(box, slot)
    b[o + 6] = q
    return xc3d.fix_wii_checksums(bytes(b))


def free_slot(img, box, cap=None):
    used = set(_ages(img, box))
    return next(i for i in range(cap or 150) if i not in used)


# --------------------------------------------------------------------------------------------- conversions
def export(de_path, out, base=H.W150):
    return xs.de_to_wii_convert(xs.DeToWiiRequest(de=de_path, out=out, base=base, overflow="sidecar"))


def reimport(wii_bytes, d, sidecar, current_de, name="cur"):
    p = H.put(os.path.join(d, name, "monado01"), wii_bytes)
    return xs.wii_to_de(xs.WiiToDeRequest(wii=p, out=os.path.join(d, name + "_de"), sidecar=sidecar,
                                          current_de=current_de))


def put_de(d, name, img):
    p = os.path.join(d, name, "bfsgame00.sav")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(img)
    return p


def de_rebuy(img, box, slot):
    """DE: the item at `slot` is sold and an identical one obtained into the same slot - same id and content, a NEW
    acquisition serial from the per-type counter (what the DE allocator 0x9AB70..0x9AB88 does), favourite cleared."""
    b = bytearray(img)
    typ, off, size = DBOX[box]
    o = off + size * slot
    c = de_save.SERIALS + 4 * typ
    n = struct.unpack_from("<I", b, c)[0] + 1
    struct.pack_into("<I", b, c, n)
    struct.pack_into("<I", b, o + 0xC, n)
    b[o + 0x11] = 0
    return bytes(b)


def wii_low5(img, box, slot):
    o, _ = _rec(box, slot)
    return struct.unpack_from(">I", img, o)[0] & 31
