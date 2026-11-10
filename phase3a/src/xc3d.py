"""Xenoblade Chronicles 3D (New 3DS, CTR-P-CAFE) save format: container codec and Wii <-> 3DS payload transcoder.

Phase 3A.  Evidence for every rule is cited in XC3D_SAVE_FORMAT.md (code addresses are in the 3DS code.bin of
KTR-P-CAFE v1.0, loaded at 0x100000).

File  (monado01 / monado02 / monado03 in the title's save archive)
  0x00 "!qzb"  u32 LE decompressed size (0x28000)  u32 LE block size;  then ONE QuickLZ level-3 block (qlz.py).
Payload (0x28000 bytes) = the Wii SX4E save layout, byte for byte the same offsets, but
  * little-endian scalars (ARM11);
  * C bitfields allocated LSB-first (armcc) instead of MSB-first (CodeWarrior/PPC), same declaration order;
  * section checksum = CRC-16/XMODEM stored as u32 at header+0xC (Wii: u16 0 + CRC-16/ARC at +0xE);
  * file-header version 0x00070003 (Wii 0x00070002);
  * struct padding and the space between sections hold the heap fill byte 0xE3 (the Wii writes 0);
  * THUM carries a 116x164 thumbnail picture at +0x80 (the Wii leaves it zero).
An empty slot is "DMMY" + zeros (+0xE3 tail), like the Wii's DMMY file.

transcode(src, "3ds"|"wii", template=None) converts a decompressed payload between the two layouts; every byte of
the payload is covered by SCHEMA (checked at import), so nothing is dropped or guessed silently.  Spans whose type
is inferred from data rather than from code are listed in UNVERIFIED.
"""
import struct

import qlz

MAGIC = b"!qzb"
RAW_SIZE = 0x28000
PAYLOAD_END = 0x248F0
WII_VERSION, CTR_VERSION = 0x00070002, 0x00070003
FILL_3DS = 0xE3
SECTIONS = [("THUM", 0x10, 0x20, 0x9CA0), ("FLAG", 0xA020, 0xA030, 0xB244), ("GAME", 0xB250, 0xB260, 0x11E88),
            ("TIME", 0x11EA0, 0x11EB0, 0x11EBC), ("PCPM", 0x11ED0, 0x11EE0, 0x11F14), ("CAMD", 0x11F20, 0x11F30, 0x11F40),
            ("ITEM", 0x11F50, 0x11F60, 0x24080), ("WTHR", 0x24080, 0x24090, 0x240A0), ("SNDS", 0x240B0, 0x240C0, 0x240D0),
            ("MINE", 0x240E0, 0x240F0, 0x24474), ("TBOX", 0x24490, 0x244A0, 0x246D4), ("OPTD", 0x248A0, 0x248B0, 0x248F0)]
SECTION_SIZES = {"THUM": 0xA010, "FLAG": 0x1230, "GAME": 0x6C50, "TIME": 0x30, "PCPM": 0x50, "CAMD": 0x30,
                 "ITEM": 0x12130, "WTHR": 0x30, "SNDS": 0x30, "MINE": 0x3B0, "TBOX": 0x410, "OPTD": 0x50}
THUM_IMAGE = (0x20 + 0x80, 0x9CA0)   # thumbnail picture (3DS); the Wii keeps only a fixed 0x40-byte header there
WII_IMAGE_HEADER = bytes.fromhex("0020af30000000010000000c000000140000000000740 0a40000000400000040".replace(" ", "")
                                 + "0000000000000000000000010000000100000000000000000000000000000000")
# identical in every Wii save examined (6 game-written saves, story 6 .. 232)
ITEM = 0x11F60


class FormatError(ValueError):
    pass


# --------------------------------------------------------------------------------------------- checksums
def crc16_xmodem(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def crc16_arc(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


# --------------------------------------------------------------------------------------------- container
def is_3ds_file(data):
    return len(data) >= 21 and data[:4] == MAGIC


def unpack(data):
    """3DS save file -> 0x28000-byte payload.  Raises FormatError for anything that is not a valid XC3D save."""
    if len(data) < 12 + 9 or data[:4] != MAGIC:
        raise FormatError("not a Xenoblade Chronicles 3D save (no !qzb header)")
    dsize, bsize = struct.unpack_from("<II", data, 4)
    if dsize != RAW_SIZE:
        raise FormatError(f"unexpected decompressed size 0x{dsize:X}")
    if 12 + bsize != len(data):
        raise FormatError(f"file size {len(data)} does not match the block size {bsize} (truncated or padded file)")
    try:
        _, csize, qd = qlz.header(data[12:])
        if csize != bsize or qd != dsize:
            raise FormatError("QuickLZ header disagrees with the !qzb header")
        raw = qlz.decompress(data[12:])
    except qlz.QLZError as e:
        raise FormatError(f"damaged compressed data: {e}") from e
    if len(raw) != RAW_SIZE:
        raise FormatError("decompressed size mismatch")
    return raw


def pack(raw):
    if len(raw) != RAW_SIZE:
        raise FormatError("payload must be 0x28000 bytes")
    blk = qlz.compress(raw)
    return MAGIC + struct.pack("<II", RAW_SIZE, len(blk)) + blk


def kind(raw):
    """'save', 'empty' (DMMY slot) or None."""
    if raw[:4] == b"DRSU":
        return "save"
    if raw[:4] == b"YMMD" and not any(raw[0x20:PAYLOAD_END]):
        return "empty"
    return None


def file_header(version=CTR_VERSION):
    return struct.pack("<4sIII", b"DRSU", PAYLOAD_END, 0x10, version)


def check_container(raw):
    """Problems of a decompressed 3DS payload: header, every section header, every checksum."""
    if len(raw) != RAW_SIZE:
        return [f"payload size {len(raw)}"]
    bad = [] if raw[:16] == file_header() else ["file header"]
    for tag, hdr, s, e in SECTIONS:
        t, size, hs = struct.unpack_from("<4sII", raw, hdr)
        if t != tag.encode()[::-1] or size != SECTION_SIZES[tag] or hs != 0x10:
            bad.append(f"section header {tag}")
        elif struct.unpack_from("<I", raw, hdr + 0xC)[0] != crc16_xmodem(raw[s:e]):
            bad.append(f"section {tag} checksum")
    return bad


def fix_checksums(raw):
    b = bytearray(raw)
    for tag, hdr, s, e in SECTIONS:
        struct.pack_into("<I", b, hdr + 0xC, crc16_xmodem(b[s:e]))
    return bytes(b)


def fix_wii_checksums(raw):
    b = bytearray(raw)
    for tag, hdr, s, e in SECTIONS:
        struct.pack_into(">HH", b, hdr + 0xC, 0, crc16_arc(b[s:e]))
    return bytes(b)


# --------------------------------------------------------------------------------------------- schema
# span kinds: ("b",)  bytes as is | ("u16",) ("u32",) arrays of scalars (f32 is "u32") | ("bf", size, widths) a C
# bitfield container of `size` bytes, fields in declaration order | ("pad",) padding (Wii 0, 3DS 0xE3) |
# ("gap",) space between sections (Wii 0, 3DS 0xE3) | ("hdr",) file header | ("sect",) section header |
# ("img",) THUM picture (Wii 0, 3DS from the template or 0)
SCHEMA = []          # (start, end, kind)
UNVERIFIED = []      # (start, end, note): type chosen from data, not from code


def _add(start, length, *k):
    SCHEMA.append((start, start + length, k))
    return start + length


def _unverified(start, length, note):
    UNVERIFIED.append((start, start + length, note))


HEADER_BF = ("bf", 4, (12, 4, 11, 3, 2))    # gid, type, row, rank, sub  [3DS getters 0x450CBC, data]
FLAGS_BF = ("bf", 1, (6, 2))                # atr_type, kind            [0x1982DC: ldrb +7; lsr #6]
GEMD_W0 = ("bf", 4, (11, 11, 3, 7))         # gid-2048, strength, rank, chance   [0x19F3CC]
GEMD_H4 = ("bf", 2, (12, 3, 1))             # effect, category, flag    [0x19F3DC, 0x44FA24]
CRY_EFF = ("bf", 2, (12, 4))                # crystal effect slot       [0x450014, 0x450124]
CRY_SRC = ("bf", 2, (1, 15))                # cylinder, source          [0x376B14 and #1 / 0x376B68 lsr #1]
PLAYTIME = ("bf", 4, (20, 6, 6))            # hours, minutes, seconds   [THUM writer 0x3512B4]


def _item_header(o):
    o = _add(o, 4, *HEADER_BF)
    o = _add(o, 2, "u16")                  # acquisition serial
    o = _add(o, 1, "b")                    # quantity
    return _add(o, 1, *FLAGS_BF)


def _gem_desc(o):
    o = _add(o, 4, *GEMD_W0)
    o = _add(o, 2, *GEMD_H4)
    return _add(o, 2, "u16")


def _record(kind_, o):
    o = _item_header(o)
    if kind_ == "equip":                   # 0x34
        for _ in range(4):
            o = _gem_desc(o)
        o = _add(o, 8, "u16")              # socket -> gem box index
        o = _add(o, 2, "b")                # socket count, kind
        o = _add(o, 2, "u16")
    elif kind_ == "gem":                   # 0x10
        o = _gem_desc(o)
    elif kind_ == "crystal":               # 0x1C
        for _ in range(4):
            o = _add(o, 2, *CRY_EFF)
        o = _add(o, 2, "u16")              # +0x10
        o = _add(o, 6, "b")                # values x4, +0x16, +0x17
        o = _add(o, 2, *CRY_SRC)
        o = _add(o, 2, "u16")
    return o


def _char(o):
    s = o
    o = _add(o, 26, "u16")                 # id, equip gid x6, equip row x6       [serializer 0x34EDF4]
    o = _add(o, 2, "pad")
    o = _add(o, 12, "u16")                 # equip box index x6
    o = _add(o, 0xA0, "u16")               # armour stat cache (5 x 16 u16)        [data: 14 records x 5 saves]
    o = _add(o, 12, "u32")                 # weapon stat cache: f32 x3
    o = _add(o, 16, "u16")                 # dmg low/high, att_lev, 0, block, phys/ether def, 0
    o = _add(o, 2, "b")                    # weapon type, element
    o = _add(o, 2, "u16")                  # weapon flag  [3DS 0x277330 ldrh +0xE6; tst #4 = Monado scaling]
    o = _add(o, 0x90, "b")                 # art levels, palettes, talent arts, unk_130    [data]
    o = _add(o, 2, "u16")                  # +0x178
    o = _add(o, 2, "pad")
    o = _add(o, 4, "u32")                  # level
    o = _add(o, 0x18, "u32")               # +0x180 f32 x6 (HP etc., clamped by the serializer)
    o = _add(o, 0x20, "u16")               # +0x198 stats u16 x16
    o = _add(o, 0x3C, "u32")               # +0x1B8 f32/u32 x15
    o = _add(o, 0x8F, "b")                 # skill rows 11 x 13 bytes              [0x377430]
    o = _add(o, 1, "pad")
    o = _add(o, 0x28, "u32")               # affinity coins, SP x5, tree, exp accum, exp, ap  [0x377430, 0x34EEF4]
    o = _add(o, 4, "u16")
    o = _add(o, 5, "b")
    o = _add(o, 3, "pad")
    o = _add(o, 8, "u32")                  # f32 x2
    o = _add(o, 2, "b")                    # +0x2C0 flag, +0x2C1
    o = _add(o, 0x3E, "u16")               # +0x2C2 u16 list (record 0)           [0x34942C]
    o = _add(o, 1, "b")
    o = _add(o, 3, "pad")
    assert o - s == 0x304
    _unverified(s + 0x1A0, 0x14, "char +0x1A0 u16 (always 0 in samples)")
    _unverified(s + 0x1B8, 0x3C, "char +0x1B8 4-byte words (mostly 0 in samples)")
    return o


def _build():
    o = _add(0, 16, "hdr")
    for i, (tag, hdr, s, e) in enumerate(SECTIONS):
        if o < hdr:
            o = _add(o, hdr - o, "gap")
        o = _add(hdr, 16, "sect")
        if tag == "THUM":
            o = _add(o, 2, "u16")           # scenario                              [THUM writer 0x351238]
            o = _add(o, 2, "b")             # minute, second
            o = _add(o, 4, "u16")           # year, month
            o = _add(o, 2, "b")             # hour, day
            o = _add(o, 6, "u16")           # play hours, play minutes, map area
            o = _add(o, 4, "b")             # 0, map sub, 2 x 0
            o = _add(o, 0x30, "u32")        # party x8, +0x34 x3, +0x40
            o = _add(o, 0x20, "b")          # leader name
            o = _add(o, 2, "u16")           # leader level
            o = _add(o, 0x1A, "b")
            o = _add(o, e - o, "img")
        elif tag == "FLAG":
            o = _add(o, e - s, "u32")       # flag words                             [data: banks 1/8/16 bits]
        elif tag == "GAME":
            for _ in range(2):              # map: u16 sub, u16 area, name[0x20]     [THUM writer ldrh +0/+2]
                o = _add(o, 4, "u16")
                o = _add(o, 0x20, "b")
            o = _add(o, 12, "u32")
            _unverified(o - 12, 12, "GAME +0x48 (always 0 in samples)")
            o = _add(o, 4, "u16")
            _unverified(o - 4, 4, "GAME +0x54 u16 x2 vs u32 (value 0x00010001 in every sample: same bytes either way)")
            o = _add(o, 8000, "b")          # quest objective counters (s8)          [data]
            o = _add(o, 1, "b")
            o = _add(o, 3, "pad")
            o = _add(o, 0x30, "u32")        # party x8, +0x20 x4                     [THUM writer copies words]
            o = _add(o, 0x30, "u32")
            _unverified(o - 0x30, 0x30, "GAME 0xD22C..0xD25C (always 0 in samples)")
            o = _add(o, 0xEAEE - o, "b")    # minimap + Collectopaedia bit arrays    [data; Wii byte+bit accessors]
            o = _add(o, 2, "pad")
            o = _add(o, 0x500, "b")         # 0xEAF0 u8 x 0x500                      [data]
            o = _add(o, 0x400, "u32")       # 0xEFF0 u32 x 256                       [data]
            o = _add(o, 0x20, "b")          # 0xF3F0
            _unverified(0xF3F0, 0x20, "GAME 0xF3F0..0xF410 bytes")
            o = _add(o, 0x40, "u16")        # 0xF410 u16 x 32                        [data]
            assert o == 0xF450, hex(o)
            for _ in range(14):
                o = _char(o)
            assert o == e
        elif tag == "TIME":
            o = _add(o, 4, *PLAYTIME)
            o = _add(o, 4, "u32")           # f32 time of day
            o = _add(o, 4, "u16")           # day, year                              [0x34F5A8]
        elif tag == "PCPM":
            o = _add(o, e - s, "u32")       # 3 x (f32 x, y, z, angle), u32          [0x34F63C]
        elif tag == "CAMD":
            o = _add(o, 16, "u32")          # f32 x3, +0xC                            [0x3231D8]
        elif tag == "ITEM":
            from_boxes = [("equip", 0x34, 163)] * 6 + [("crystal", 0x1C, 300), ("gem", 0x10, 300)] + \
                         [("stack", 8, 240), ("stack", 8, 300), ("stack", 8, 300), ("stack", 8, 200)]
            for k, size, n in from_boxes:
                for _ in range(n):
                    o2 = _record(k, o)
                    assert o2 - o == size, (k, o2 - o)
                    o = o2
            assert o == ITEM + 0x11AB8, hex(o)
            for _ in range(88):
                o = _record("gem", o)
            o = _add(o, 0xB0, "b")          # 88 x (u8 slot+1, u8 socket): staged-gem links, read as bytes by the game (Wii 0x8007F5B4 lbz +0/+1); 3E fix D3 (was u16)
            o = _add(o, 4, "u32")           # money
            o = _add(o, 0x1C, "u16")        # u16 x14
            o = _add(o, 12, "u32")          # masks, capacity bonus
            o = _add(o, 10, "u16")
            o = _add(o, 2, "b")             # padding, zero in both (the item object is cleared)
            assert o == e, hex(o)
        elif tag == "WTHR":
            o = _add(o, 4, "u32")
            o = _add(o, 12, "u16")          # [0x3B8C84]
        elif tag == "SNDS":
            o = _add(o, 16, "u32")          # f32 x3, u32                             [0x34F788]
        elif tag == "MINE":
            for _ in range(150):            # u16, u8 x4                              [0x379E50]
                o = _add(o, 2, "u16")
                o = _add(o, 4, "b")
        elif tag == "TBOX":
            o = _add(o, 4, "u32")           # count                                   [0x34F838]
            for _ in range(20):             # field treasure chests: layouts differ (an enum is 4 bytes on the
                o = _add(o, 0x14, "u32")    # Wii, 2 on the 3DS): Wii +0x14 u32, u16, u8, u8;  3DS +0x14 u16, u16,
                o = _add(o, 8, "tbox")      # u8, u8, 2 x 0  [3DS game re-save of a converted save, run a1]
        elif tag == "OPTD":
            o = _add(o, e - s, "b")         # option bytes                            [data: identical defaults]
        assert o == e, (tag, hex(o), hex(e))
    o = _add(o, RAW_SIZE - o, "gap")
    # coverage check
    pos = 0
    for s, e, k in SCHEMA:
        assert s == pos, hex(s)
        pos = e
    assert pos == RAW_SIZE


_build()


# --------------------------------------------------------------------------------------------- transcoder
def _bf_convert(v, widths, size, to_3ds):
    bits = size * 8
    vals = []
    if to_3ds:                         # read MSB-first, write LSB-first
        pos = bits
        for w in widths:
            pos -= w
            vals.append(v >> pos & ((1 << w) - 1))
        out, pos = 0, 0
        for x, w in zip(vals, widths):
            out |= x << pos
            pos += w
    else:
        pos = 0
        for w in widths:
            vals.append(v >> pos & ((1 << w) - 1))
            pos += w
        out, pos = 0, bits
        for x, w in zip(vals, widths):
            pos -= w
            out |= x << pos
    return out


def _swap(src, s, e, unit):
    b = src[s:e]
    if unit == 2:
        out = bytearray(len(b))
        out[0::2], out[1::2] = b[1::2], b[0::2]
        return bytes(out)
    out = bytearray(len(b))
    out[0::4], out[1::4], out[2::4], out[3::4] = b[3::4], b[2::4], b[1::4], b[0::4]
    return bytes(out)


def transcode(src, to, template=None):
    """Convert a decompressed payload. to='3ds': Wii (BE) -> 3DS (LE); to='wii': 3DS -> Wii.
    template (a decompressed 3DS payload, to='3ds' only) supplies the THUM picture; otherwise it is left blank.
    Checksums are recomputed for the destination format."""
    if len(src) != RAW_SIZE:
        raise FormatError("payload must be 0x28000 bytes")
    to_3ds = to == "3ds"
    if to_3ds and src[:4] != b"USRD" or not to_3ds and src[:4] != b"DRSU":
        raise FormatError("source is not a " + ("Wii" if to_3ds else "3DS") + " save payload")
    sfmt, dfmt = (">", "<") if to_3ds else ("<", ">")
    out = bytearray(RAW_SIZE)
    for s, e, k in SCHEMA:
        t = k[0]
        if t == "b":
            out[s:e] = src[s:e]
        elif t == "u16":
            out[s:e] = _swap(src, s, e, 2)
        elif t == "u32":
            out[s:e] = _swap(src, s, e, 4)
        elif t == "bf":
            size, widths = k[1], k[2]
            fmt = {1: "B", 2: "H", 4: "I"}[size]
            v = struct.unpack_from(sfmt + fmt, src, s)[0]
            struct.pack_into(dfmt + fmt, out, s, _bf_convert(v, widths, size, to_3ds))
        elif t in ("pad", "gap"):
            out[s:e] = bytes([FILL_3DS]) * (e - s) if to_3ds else bytes(e - s)
        elif t == "hdr":
            tag, size, hs, ver = struct.unpack_from(sfmt + "4sIII", src, s)
            struct.pack_into(dfmt + "4sIII", out, s, tag, size, hs, CTR_VERSION if to_3ds else WII_VERSION)
            if to_3ds:
                out[s:s + 4] = b"DRSU"
            else:
                out[s:s + 4] = b"USRD"
        elif t == "sect":
            tag = src[s:s + 4][::-1]
            size, hs = struct.unpack_from(sfmt + "II", src, s + 4)
            out[s:s + 4] = tag
            struct.pack_into(dfmt + "II", out, s + 4, size, hs)
        elif t == "tbox":
            if to_3ds:
                a, b2, c, d = struct.unpack_from(">IHBB", src, s)
                if a > 0xFFFF:
                    raise FormatError(f"treasure-chest record at 0x{s:X} has a value the 3DS cannot hold")
                struct.pack_into("<HHBBH", out, s, a, b2, c, d, 0)
            else:
                a, b2, c, d, z = struct.unpack_from("<HHBBH", src, s)
                struct.pack_into(">IHBB", out, s, a, b2, c, d)
        elif t == "img":
            if to_3ds:
                out[s:e] = template[s:e] if template is not None else bytes(e - s)
            else:
                out[s:e] = WII_IMAGE_HEADER + bytes(e - s - len(WII_IMAGE_HEADER))
    return fix_checksums(bytes(out)) if to_3ds else fix_wii_checksums(bytes(out))


def wii_header_ok(src):
    return src[:16] == struct.pack(">4sIII", b"USRD", PAYLOAD_END, 0x10, WII_VERSION)


def pad_report(raw3):
    """Positions where a 3DS payload's padding/gap bytes are not the heap fill (they are not carried by the
    transcoder; reported so a byte-exact 3DS -> Wii -> 3DS round trip can be judged)."""
    out = []
    for s, e, k in SCHEMA:
        if k[0] in ("pad", "gap") and raw3[s:e] != bytes([FILL_3DS]) * (e - s):
            out.append((s, e))
    return out
