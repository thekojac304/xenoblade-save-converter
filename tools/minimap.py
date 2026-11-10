"""Minimap exploration transfer between XC1 Wii (SX4E01) and XC1 DE (v7/v10) saves -- pure functions, read-only.

Both directions return {file_offset: new_byte} for the TARGET save and never clear a bit (OR-merge): applying the
dict to the target bytes can only add exploration.  Nothing here reads or writes files.

Layouts (see ../re_minimap.md for the evidence; [C] = code address, [D] = reproduced against saves):

Wii (main.dol SX4E01)
  * marker 0x8013B6C0 [C], called from the minimap update 0x8011CB64: player position (x, y, z);
    x' = x / (minimap_rate * 0.1) * 1.5, z' likewise (FLD_maplist minimap_rate);
    floor = first FLD minimaplistMMNN row (1-based) whose `height` > y;
    grid 24 x 24 cells of 64 x'-units; (minimap_origin - 1) = row0 * 24 + col0 is the cell whose reference point is
    world (0, 0); reference point of cell (col, row) = ((col - col0) * 64, (row - row0) * 64) in x'/z' units;
    a cell is marked when |player - ref| <= 32 * sqrt(2) (half the cell diagonal), i.e. the cell whose ref point is
    nearest to the player is always marked.  World cell pitch = 64 * rate / 15.
  * bit index = base(map) + (floor - 1) * 576 + row * 24 + col + 1, base(map) = sum of 576 * floors over the maps
    2 .. map-1 listed in the DOL array 0x80500480 (maps 1, 10, 22 have none; 19 and 20 both use minimaplist1601).
  * bit store: setter 0x8009F56C / getter 0x8009F5C0: byte (*(r13-0x59F8)) + 0x1FFC + (n >> 3), bit n & 7 (LSB first),
    n < 50000.  The game object is memcpy'd to the save at 0xB260, so byte = file 0xD25C + (n >> 3) (GAME section;
    its CRC-16/ARC at 0xB25E covers 0xB260..0x11E88).
  * full-map rule 0x8013C2C0 -> 0x8013BB88 [C]: when every landmarklist row of the map has flag 0x20C8+id, all
    576 * floors bits are set (with an off-by-one: bits base + f*576 + 0..575).
  * floor-map display 0x8024A3D0: icon screen = (painx + x', painy - z'); for every map painx - 64*col0 = -736 and
    painy + 64*row0 = 736, i.e. the 24x24 mask panes (pic_maskNN, 64 apart, centred +-736) are centred on the
    marking reference points, so a marked cell is displayed as the square ref +- 32 x'-units (Voronoi square).

DE (main.bin 2.0.0, image base 0)
  * marker 0x16F8F0 [C], single caller 0x36EB98 (field minimap update); floor chosen at 0x36E69C with the same rule
    (first minimaplist row whose height > y).
  * bitmap info 0x16E290 (per-map switch, jump table 0x9D4E78): image size W x H (hard-coded q-constants at
    0x9D1310.., NOT the BDAT mapimage_size), floors, bytes per floor, offset; buffer = ctx + 0x475F0 (0x7EB80),
    ctx + 0x6B0 = save offset 0  ->  save offset = 0x46F40 + offset + (floor - 1) * floor_bytes.
  * px = (x - minimap_lt_x) / (minimap_rb_x - minimap_lt_x) * W (z likewise with H); one bit per 4 x 4 px;
    row stride = ceil(ceil(W / 4) / 8) bytes, bit (c & 7) of byte (c >> 3) (LSB first);
    reveal = disc of radius 20 cells (80 px) around ((px + 2) / 4, (pz + 2) / 4).
  * full-map rule at display time 0x16CC70 [C]: if every landmark of the map has flag 0x20C8+id the map is drawn
    unmasked; the bitmap itself is not filled.

Geometry of a cell in world units used by the transfer:
  Wii cell (col,row): x in [(col - col0 - 0.5) * P, (col - col0 + 0.5) * P), P = 64 * rate / 15 (z likewise).
  DE  cell (c, r):    x in [lt_x + 4c * sx, lt_x + (4c + 4) * sx), sx = (rb_x - lt_x) / W (z likewise).

Conservative rules:
  wii_to_de: a DE cell is set only if EVERY Wii cell it overlaps is in the 24x24 grid and marked (zero overshoot
             w.r.t. the squares the Wii map displayed).  mode='path' instead sets only DE cells that DE's own
             reveal would certainly have set for any player path consistent with the Wii bits (much smaller; empty
             on maps whose Wii cell radius R_w >= ~70 world units).
  de_to_wii: a Wii cell is set only if it contains >= 1 DE cell lying entirely inside it (and inside the DE image)
             and ALL such DE cells are explored (min_fraction=1.0; overshoot <= one DE cell = ~4 world units at the
             square's border).  Optional: Wii's own full-map rule from flags 0x20C8+id in the DE save.
  Floors map by index (both games have identical floor counts for every shared map).
  Maps without a counterpart are skipped: Wii 20 (ma1602), 26 (ma2201 Memory Space); DE 29, 30 (Future Connected).
"""
import math
import struct

# ---------------------------------------------------------------------------------------------- Wii constants
WII_BITS_FILE = 0xB260 + 0x1FFC   # file offset of bit 0 (game object +0x1FFC)
WII_BITS_MAX = 50000              # 0xC350, bound check in 0x8009F56C / 0x8009F5C0
WII_GAME_HDR, WII_GAME_START, WII_GAME_END = 0xB250, 0xB260, 0x11E88
WII_GRID = 24
WII_MAPS = {  # map_id: (resource, minimap_rate, minimap_origin, floors, first_bit_base)  [C]+[D] see self-test
    2: ('ma0101', 25, 253, 1, 0),
    3: ('ma0201', 12, 355, 4, 576),
    4: ('ma0301', 40, 267, 2, 2880),
    5: ('ma0401', 22, 277, 1, 4032),
    6: ('ma0402', 15, 176, 5, 4608),
    7: ('ma0501', 30, 150, 1, 7488),
    8: ('ma0601', 60, 299, 1, 8064),
    9: ('ma0701', 6, 302, 10, 8640),
    11: ('ma0901', 10, 292, 3, 14400),
    12: ('ma1001', 80, 300, 1, 16128),
    13: ('ma1101', 21, 298, 3, 16704),
    14: ('ma1201', 13, 304, 3, 18432),
    15: ('ma1202', 13, 304, 7, 20160),
    16: ('ma1301', 50, 357, 2, 24192),
    17: ('ma1401', 48, 274, 1, 25344),
    18: ('ma1501', 9, 282, 5, 25920),
    19: ('ma1601', 32, 233, 2, 28800),
    20: ('ma1602', 32, 233, 2, 29952),
    21: ('ma1701', 25, 180, 7, 31104),
    23: ('ma1901', 18, 286, 4, 35136),
    24: ('ma2001', 20, 255, 6, 37440),
    25: ('ma2101', 20, 420, 2, 40896),
    26: ('ma2201', 20, 301, 1, 42048),
    27: ('ma2301', 2, 277, 1, 42624),
    28: ('ma2401', 10, 301, 1, 43200),
}

# ----------------------------------------------------------------------------------------------- DE constants
DE_BUF_SAVE = 0x46F40             # save offset of runtime ctx+0x475F0 (0x7EB80); ctx+0x6B0 == save offset 0
DE_MAPS = {  # map_id: (img_w, img_h, floors, floor_bytes, (offset per floor), lt_x, lt_z, rb_x, rb_z)
    2: (1620, 1250, 1, 0x3F00, (0x28C,), -908, -482, 706, 770),
    3: (776, 654, 4, 0x1100, (0x418C, 0x528C, 0x638C, 0x748C), -700, -456, 72, 195),
    4: (3568, 1504, 2, 0xA500, (0x858C, 0x12A8C), -235, -680, 3333, 824),
    5: (856, 1906, 1, 0x3300, (0x1CF8C,), -475, -936, 374, 964),
    6: (632, 1204, 5, 0x1800, (0x2028C, 0x21A8C, 0x2328C, 0x24A8C, 0x2628C), -52, -296, 580, 908),
    7: (1800, 1800, 1, 0x6500, (0x27A8C,), -121, -230, 1680, 1570),
    8: (4200, 2952, 1, 0x17D00, (0x2DF8C,), -1690, -1528, 2510, 1424),
    9: (336, 316, 10, 0x400, (0x45C8C, 0x4608C, 0x4648C, 0x4688C, 0x46C8C, 0x4708C, 0x4748C, 0x4788C, 0x47C8C,
                              0x4808C), -191, -160, 138, 150),
    11: (952, 320, 3, 0xA00, (0x4848C, 0x48E8C, 0x4988C), -127, -160, 825, 160),
    12: (6400, 3520, 1, 0x2B000, (0x4A28C,), -3111, -1796, 3288, 1724),
    13: (1200, 1284, 3, 0x3000, (0x7528C, 0x7828C, 0x7B28C), -375, -723, 825, 557),
    14: (944, 605, 3, 0x1200, (0x7E28C, 0x7F48C, 0x8068C), -648, -308, 296, 297),
    15: (944, 605, 7, 0x1200, (0x8188C, 0x82A8C, 0x83C8C, 0x84E8C, 0x8608C, 0x8728C, 0x8848C), -648, -308, 296, 297),
    16: (3900, 2100, 2, 0xFB00, (0x8968C, 0x9918C), -3712, -1601, 188, 499),
    17: (3456, 2304, 1, 0xF300, (0xA8C8C,), -1152, -978, 2304, 1326),
    18: (776, 323, 5, 0x800, (0xB7F8C, 0xB878C, 0xB8F8C, 0xB978C, 0xB9F8C), -578, -160, 190, 160),
    19: (2360, 1462, 2, 0x6A00, (0xBA78C, 0xC118C), -1751, -422, 605, 1038),
    21: (1016, 2102, 7, 0x4200, (0xC7B8C, 0xCBD8C, 0xCFF8C, 0xD418C, 0xD838C, 0xDC58C, 0xE078C), -448, -568, 564, 1524),
    23: (1560, 520, 4, 0x1900, (0xE498C, 0xE628C, 0xE7B8C, 0xE948C), -1518, -260, 35, 260),
    24: (1000, 1432, 6, 0x2D00, (0xEAD8C, 0xEDA8C, 0xF078C, 0xF348C, 0xF618C, 0xF8E8C), -719, -612, 280, 816),
    25: (1000, 1256, 2, 0x2800, (0xFBB8C, 0xFE38C), -425, -1066, 575, 184),
    27: (80, 80, 1, 0x100, (0x100B8C,), -40, -40, 40, 40),
    28: (178, 178, 1, 0x200, (0x100C8C,), -90, -119, 90, 61),
    # 29 (ma2501) and 30 (ma2601) are Future Connected maps; their offsets alias 12/8 in this buffer -> excluded.
}
SHARED_MAPS = sorted(set(WII_MAPS) & set(DE_MAPS))
DE_SIZES = (0x153860, 0x153F30)   # v7, v10 (identical offsets below 0x151B44)

# landmark rows per map (landmarklist mapID, identical ids in both games) for the Wii full-map rule (flag 0x20C8+id)
FULLMAP_FLAG_BASE = 0x20C8


# ---------------------------------------------------------------------------------------------------- helpers
def wii_origin(m):
    _, rate, origin, _, _ = WII_MAPS[m]
    row0, col0 = divmod(origin - 1, WII_GRID)
    return col0, row0, 64.0 * rate / 15.0          # col0, row0, world pitch P


def wii_bit(m, floor, col, row):
    """Bit index (marker semantics, floor 1-based)."""
    return WII_MAPS[m][4] + (floor - 1) * 576 + row * WII_GRID + col + 1


def wii_get_grid(wii, m, floor):
    """24x24 list of bools [row][col]."""
    out = []
    for row in range(WII_GRID):
        line = []
        for col in range(WII_GRID):
            n = wii_bit(m, floor, col, row)
            line.append(bool(wii[WII_BITS_FILE + (n >> 3)] >> (n & 7) & 1))
        out.append(line)
    return out


def de_dims(m):
    W, H, floors, fbytes, offs, ltx, ltz, rbx, rbz = DE_MAPS[m]
    ncol, nrow = (W + 3) >> 2, (H + 3) >> 2
    stride = (ncol + 7) >> 3
    return ncol, nrow, stride


def de_floor_off(m, floor):
    return DE_BUF_SAVE + DE_MAPS[m][4][floor - 1]


def de_rows(de, m, floor):
    """Explored DE cells as one int per row (bit c = column c), padding bits beyond ncol masked off."""
    ncol, nrow, stride = de_dims(m)
    base = de_floor_off(m, floor)
    full = (1 << ncol) - 1
    return [int.from_bytes(de[base + r * stride: base + (r + 1) * stride], 'little') & full for r in range(nrow)]


def _de_axis(m, axis):
    W, H, _, _, _, ltx, ltz, rbx, rbz = DE_MAPS[m]
    if axis == 0:
        return ltx, (rbx - ltx) / W, (W + 3) >> 2
    return ltz, (rbz - ltz) / H, (H + 3) >> 2


def _wii_range_for_de_cells(m, axis):
    """Per DE cell index along an axis: (first, last) Wii cell index it overlaps (may be outside 0..23)."""
    col0, row0, P = wii_origin(m)
    o = col0 if axis == 0 else row0
    lt, s, n = _de_axis(m, axis)
    res = []
    for c in range(n):
        x0, x1 = lt + 4 * c * s, lt + (4 * c + 4) * s
        a = math.floor(x0 / P + o + 0.5)
        b = math.ceil(x1 / P + o + 0.5) - 1
        res.append((a, max(a, b)))
    return res


def _de_interior_for_wii_cells(m, axis):
    """Per Wii cell index along an axis: (first, last) DE cell lying entirely inside it, or None."""
    col0, row0, P = wii_origin(m)
    o = col0 if axis == 0 else row0
    lt, s, n = _de_axis(m, axis)
    res = []
    for k in range(WII_GRID):
        a, b = (k - o - 0.5) * P, (k - o + 0.5) * P           # world interval [a, b)
        lo = math.ceil(((a - lt) / s) / 4 - 1e-9)
        hi = math.floor(((b - lt) / s) / 4 + 1e-9) - 1
        lo, hi = max(lo, 0), min(hi, n - 1)
        res.append((lo, hi) if lo <= hi else None)
    return res


def _check_de(de):
    if len(de) not in DE_SIZES:
        raise ValueError('not a DE v7/v10 save (size 0x%X)' % len(de))


def _check_wii(wii):
    if wii[:4] != b'USRD' or len(wii) < WII_GAME_END:
        raise ValueError('not a Wii XC1 save')


def crc16_arc(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


# ------------------------------------------------------------------------------------------------ Wii -> DE
def wii_full_filled(wii, m):
    """True if map m carries the exact pattern of the Wii full-map fill 0x8013BB88 (bits base+f*576+0..575)."""
    b, floors = WII_MAPS[m][4], WII_MAPS[m][3]
    for n in range(b, b + floors * 576):
        if not wii[WII_BITS_FILE + (n >> 3)] >> (n & 7) & 1:
            return False
    return True


def _set_de_cells(changes, de_bytes, m, floor, cells_by_row):
    ncol, nrow, stride = de_dims(m)
    base = de_floor_off(m, floor)
    for r, mask in cells_by_row.items():
        if not mask or not 0 <= r < nrow:
            continue
        add = (mask & ((1 << ncol) - 1)).to_bytes(stride, 'little')
        for i, v in enumerate(add):
            if v:
                o = base + r * stride + i
                new = changes.get(o, de_bytes[o]) | v
                if new != de_bytes[o]:
                    changes[o] = new


DE_REVEAL_CELLS = 20              # 0x16F8F0: radius^2 = 400 cells^2
WII_MARK_RADIUS_X = 32 * math.sqrt(2.0)   # 0x8013B6C0: (0.5*64*sqrt 2)^2 = 2048 x'-units^2


def _wii_to_de_path(wii_bytes, de_bytes, report):
    """Strictly path-conservative variant: for each marked Wii cell the player was within R_w of its reference point
    (marker semantics), so DE would have revealed the disc of radius R_de - R_w around it; set only DE cells lying
    entirely inside that disc (minus a 2-cell margin for the DE reveal-centre bias and rasterisation)."""
    changes = {}
    for m in SHARED_MAPS:
        if wii_full_filled(wii_bytes, m):
            if report is not None:
                report.setdefault('path_skipped_full_fill', []).append(m)
            continue
        nxt = min((k for k in WII_MAPS if k > m and WII_MAPS[k][3]), default=None)
        leak_next = nxt is not None and wii_full_filled(wii_bytes, nxt)
        W, H, floors, _, _, ltx, ltz, rbx, rbz = DE_MAPS[m]
        sx, sz = (rbx - ltx) / W * 4, (rbz - ltz) / H * 4          # world size of one DE cell
        col0, row0, Pw = wii_origin(m)
        rw = WII_MARK_RADIUS_X * WII_MAPS[m][1] / 15.0
        rsafe = DE_REVEAL_CELLS * min(sx, sz) - rw - 2 * max(sx, sz)
        ncol, nrow, _ = de_dims(m)
        for floor in range(1, floors + 1):
            grid = wii_get_grid(wii_bytes, m, floor)
            rows = {}
            n = 0
            if rsafe > 0:
                for row in range(WII_GRID):
                    for col in range(WII_GRID):
                        if not grid[row][col]:
                            continue
                        if leak_next and floor == floors and row == col == WII_GRID - 1:
                            continue
                        px, pz = (col - col0) * Pw, (row - row0) * Pw
                        r_lo = max(0, math.floor((pz - rsafe - ltz) / sz))
                        r_hi = min(nrow - 1, math.floor((pz + rsafe - ltz) / sz))
                        for r in range(r_lo, r_hi + 1):
                            z0, z1 = ltz + r * sz, ltz + (r + 1) * sz
                            dz = max(abs(z0 - pz), abs(z1 - pz))
                            if dz > rsafe:
                                continue
                            hx = math.sqrt(rsafe * rsafe - dz * dz)
                            # same clamp at the image edges: a negative start column keeps its (c & 7) mask in
                            # byte 0, and the bbox byte is capped at (W-1)//32 -> first/last byte not guaranteed
                            c_lo = max(8, math.ceil((px - hx - ltx) / sx))
                            c_cap = 8 * ((W - 1) // 32) - 1
                            # DE quirk (0x16FD78..0x16FDB0): the last byte of a disc row is clamped to the bbox byte
                            # floor(ceil(px+80)/32) while its mask still uses the unclamped end column, so up to one
                            # byte (8 cells) at the disc's right edge can stay unrevealed; only cells whose right
                            # edge is <= 44 px right of the leftmost possible player position are guaranteed.
                            xr = min(px + hx, px - rw + 44 * sx / 4)
                            c_hi = min(ncol - 1, c_cap, math.floor((xr - ltx) / sx) - 1)
                            if c_lo <= c_hi:
                                rows[r] = rows.get(r, 0) | (((1 << (c_hi - c_lo + 1)) - 1) << c_lo)
            for v in rows.values():
                n += bin(v).count('1')
            _set_de_cells(changes, de_bytes, m, floor, rows)
            if report is not None:
                report.setdefault('wii_to_de', {})[(m, floor)] = n
                report.setdefault('path_radius', {})[m] = rsafe
    return changes


def wii_to_de(wii_bytes: bytes, de_bytes: bytes, mode='display', report=None) -> dict:
    """DE save offsets -> new byte values (OR-merged; only changed bytes).

    mode='display' (default): a DE cell is set iff every Wii cell it overlaps is marked -- reproduces, at DE
        resolution, exactly the squares the Wii map displayed as explored (zero overshoot w.r.t. the Wii squares).
    mode='path': only DE cells that DE itself would certainly have revealed for any player path consistent with
        the Wii bits (disc of radius 20 DE cells - R_w - margin around each marked reference point); empty where
        the Wii cell is coarser than the DE reveal (R_w >= ~70 world units); maps with the Wii full-map fill are
        skipped (DE shows them fully through its own landmark rule 0x16CC70 when flags 0x20C8+id are set).
    """
    _check_wii(wii_bytes)
    _check_de(de_bytes)
    if mode == 'path':
        return _wii_to_de_path(wii_bytes, de_bytes, report)
    if mode != 'display':
        raise ValueError(mode)
    changes = {}
    for m in SHARED_MAPS:
        ncol, nrow, stride = de_dims(m)
        colr, rowr = _wii_range_for_de_cells(m, 0), _wii_range_for_de_cells(m, 1)
        # group DE columns into runs with the same Wii column range
        runs = []
        for c, rg in enumerate(colr):
            if runs and runs[-1][0] == rg:
                runs[-1][2] = c
            else:
                runs.append([rg, c, c])
        for floor in range(1, DE_MAPS[m][2] + 1):
            grid = wii_get_grid(wii_bytes, m, floor)
            nset = 0
            cache = {}
            rows = {}
            for r in range(nrow):
                ra, rb = rowr[r]
                key = (ra, rb)
                if key not in cache:
                    if ra < 0 or rb >= WII_GRID:
                        cache[key] = 0
                    else:
                        ok_cols = [all(grid[k][col] for k in range(ra, rb + 1)) for col in range(WII_GRID)]
                        mask = 0
                        for (ca, cb), c0, c1 in runs:
                            if ca >= 0 and cb < WII_GRID and all(ok_cols[ca:cb + 1]):
                                mask |= ((1 << (c1 - c0 + 1)) - 1) << c0
                        cache[key] = mask
                mask = cache[key]
                if not mask:
                    continue
                nset += bin(mask).count('1')
                rows[r] = mask
            _set_de_cells(changes, de_bytes, m, floor, rows)
            if report is not None:
                report.setdefault('wii_to_de', {})[(m, floor)] = nset
    return changes


# ------------------------------------------------------------------------------------------------ DE -> Wii
def de_to_wii(de_bytes: bytes, wii_bytes: bytes, min_fraction=1.0, apply_full_map_rule=False,
              landmark_maps=None, report=None) -> dict:
    """Wii save offsets -> new byte values (OR-merged; only changed bytes; GAME CRC-16/ARC included).

    min_fraction: fraction of the interior DE cells of a Wii cell that must be explored (1.0 = all, conservative).
    apply_full_map_rule: also reproduce Wii 0x8013BB88 for maps whose landmarks all have flag 0x20C8+id in the DE
    save; needs landmark_maps = {map_id: [landmark ids]} (landmarklist, identical in both games).
    """
    _check_wii(wii_bytes)
    _check_de(de_bytes)
    bits = set()
    for m in SHARED_MAPS:
        ci, ri = _de_interior_for_wii_cells(m, 0), _de_interior_for_wii_cells(m, 1)
        for floor in range(1, DE_MAPS[m][2] + 1):
            rows = de_rows(de_bytes, m, floor)
            n = 0
            for row in range(WII_GRID):
                if ri[row] is None:
                    continue
                r0, r1 = ri[row]
                for col in range(WII_GRID):
                    if ci[col] is None:
                        continue
                    c0, c1 = ci[col]
                    w = c1 - c0 + 1
                    msk = (1 << w) - 1
                    tot = (r1 - r0 + 1) * w
                    got = 0
                    for r in range(r0, r1 + 1):
                        seg = (rows[r] >> c0) & msk
                        if min_fraction >= 1.0 and seg != msk:
                            got = -1
                            break
                        got += bin(seg).count('1')
                    if got >= 0 and got >= min_fraction * tot and got > 0:
                        bits.add(wii_bit(m, floor, col, row))
                        n += 1
            if report is not None:
                report.setdefault('de_to_wii', {})[(m, floor)] = n
    if apply_full_map_rule:
        if landmark_maps is None:
            raise ValueError('landmark_maps required for apply_full_map_rule')
        for m in SHARED_MAPS:
            ids = landmark_maps.get(m, [])
            if ids and all(_de_flag(de_bytes, FULLMAP_FLAG_BASE + i) for i in ids):
                b = WII_MAPS[m][4]
                for f in range(WII_MAPS[m][3]):
                    for c in range(576):                       # exact Wii fill incl. its off-by-one
                        bits.add(b + f * 576 + c)
                if report is not None:
                    report.setdefault('full_map', []).append(m)
    changes = {}
    for n in bits:
        if n >= WII_BITS_MAX:
            continue
        o = WII_BITS_FILE + (n >> 3)
        old = changes.get(o, wii_bytes[o])
        new = old | (1 << (n & 7))
        if new != wii_bytes[o]:
            changes[o] = new
    if changes:
        img = bytearray(wii_bytes[WII_GAME_START:WII_GAME_END])
        for o, v in changes.items():
            img[o - WII_GAME_START] = v
        crc = struct.pack('>H', crc16_arc(img))
        for i in range(2):
            o = WII_GAME_HDR + 0xE + i
            if crc[i] != wii_bytes[o]:
                changes[o] = crc[i]
    return changes


def _de_flag(d, gid):
    n = gid - 0xA20
    w = struct.unpack_from('<I', d, 0x50 + 4 * (n >> 5))[0]
    return w >> (n & 31) & 1


def apply(target: bytes, changes: dict) -> bytes:
    out = bytearray(target)
    for o, v in changes.items():
        out[o] = v
    return bytes(out)


if __name__ == '__main__':
    import os
    import runpy
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'selftest_minimap_xform.py'),
                   run_name='__main__')
