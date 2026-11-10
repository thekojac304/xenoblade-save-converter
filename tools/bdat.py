"""Legacy BDAT reader for XC1 Wii (big-endian) and XC1 DE (little-endian) game data (read-only).

Parses every table found in a file (Wii .pkb archives are scanned for the BDAT magic; DE .bdat collections use
their offset table). Table header (Wii offsets; DE has the same fields, little-endian, with column infos at 0x40):
  0x04 u8 flags (bit 1 = names/strings scrambled)  0x06 names  0x08 row size  0x0A hash table  0x0C hash slots
  0x0E rows  0x10 row count  0x12 base id  0x16 scramble key  0x18 strings offset  0x1C strings length
Name nodes after the table name: u16 info, u16 next, name. Info: u8 cell (1 value, 2 array, 3 flag), then
value/array: u8 type, u16 offset [, u16 count]; flag: u8 bit index, u32 mask, u16 parent info.
Value types: 1 u8, 2 u16, 3 u32, 4 i8, 5 i16, 6 i32, 7 string, 8 float.

Usage:  python bdat.py dump <file> <out.json>      (all tables)
        python bdat.py list <file>
"""
import json
import struct
import sys

FMT = {1: "B", 2: "H", 3: "I", 4: "b", 5: "h", 6: "i", 7: "I", 8: "f"}


def unscramble(b, key):
    b = bytearray(b)
    k1, k2 = ((key >> 8) & 0xFF) ^ 0xFF, (key & 0xFF) ^ 0xFF
    for i in range(0, len(b) - 1, 2):
        a, c = b[i], b[i + 1]
        b[i], b[i + 1] = a ^ k1, c ^ k2
        k1, k2 = (k1 + a) & 0xFF, (k2 + c) & 0xFF
    return bytes(b)


def cstr(b, off):
    end = b.index(b"\0", off)
    return b[off:end].decode("utf-8", "replace")


def parse_table(t, e):
    """t = bytes of one table, e = '>' (Wii) or '<' (DE)."""
    u16 = lambda o: struct.unpack_from(e + "H", t, o)[0]
    u32 = lambda o: struct.unpack_from(e + "I", t, o)[0]
    flags = t[4]
    names, rsize, hsh, rows_off, nrows, base = u16(6), u16(8), u16(0xA), u16(0xE), u16(0x10), u16(0x12)
    key, soff, slen = u16(0x16), u32(0x18), u32(0x1C)
    t = bytearray(t)
    if flags & 2:
        t[names:hsh] = unscramble(t[names:hsh], key)
        t[soff:soff + slen] = unscramble(t[soff:soff + slen], key)
    t = bytes(t)
    name = cstr(t, names)
    nodes = []  # (info pointer, column name)
    if e == "<":  # DE: node table at u16 0x20, count u16 0x22; node = u16 info, u16 next, u16 name offset
        for k in range(u16(0x22)):
            n = u16(0x20) + 6 * k
            nodes.append((u16(n), cstr(t, u16(n + 4))))
    else:  # Wii: nodes inline after the table name; node = u16 info, u16 next, name
        p = names + len(name) + 1
        p += p & 1
        while p + 4 < hsh:
            cname = cstr(t, p + 4)
            nodes.append((u16(p), cname))
            q = p + 4 + len(cname) + 1
            p = q + (q & 1)
    cols = []
    for info, cname in nodes:
        if info == 0 or info >= len(t):
            continue
        cell = t[info]
        if cell == 1:
            cols.append(dict(name=cname, cell=1, type=t[info + 1], off=u16(info + 2)))
        elif cell == 2:
            cols.append(dict(name=cname, cell=2, type=t[info + 1], off=u16(info + 2), count=u16(info + 4)))
        elif cell == 3:
            cols.append(dict(name=cname, cell=3, bit=t[info + 1], mask=u32(info + 2), parent=u16(info + 6)))
    by_info = dict(nodes)  # resolves flag parents by info pointer
    rows = []
    for r in range(nrows):
        ro = rows_off + r * rsize
        row = {"id": base + r}
        vals = {}
        for c in cols:
            if c["cell"] == 3:
                continue
            fmt = e + FMT[c["type"]]
            n = c.get("count", 1)
            sz = struct.calcsize(fmt)
            out = []
            for k in range(n):
                v = struct.unpack_from(fmt, t, ro + c["off"] + k * sz)[0]
                if c["type"] == 7:
                    v = cstr(t, v) if 0 < v < len(t) else ""
                elif c["type"] == 8:
                    v = round(v, 6)
                out.append(v)
            vals[c["name"]] = out if c["cell"] == 2 else out[0]
        for c in cols:
            if c["cell"] == 3:
                parent = by_info.get(c["parent"])
                if parent in vals and isinstance(vals[parent], int):
                    vals[c["name"]] = 1 if vals[parent] & c["mask"] else 0
        row.update(vals)
        rows.append(row)
    return name, dict(base=base, rows=rows, cols=[c["name"] for c in cols], row_size=rsize)


def tables_in(path):
    d = open(path, "rb").read()
    out = {}
    if d[:4] == b"BDAT":
        offs = [0]
    elif struct.unpack_from("<I", d, 0)[0] < 0x1000 and d[struct.unpack_from("<I", d, 8)[0]:][:4] == b"BDAT":
        n = struct.unpack_from("<I", d, 0)[0]  # DE collection: count, size, offsets
        offs = [struct.unpack_from("<I", d, 8 + 4 * i)[0] for i in range(n)]
    else:
        offs = []
        i = d.find(b"BDAT")
        while i >= 0:
            offs.append(i)
            i = d.find(b"BDAT", i + 4)
    big = None
    for k, o in enumerate(offs):
        end = offs[k + 1] if k + 1 < len(offs) else len(d)
        t = d[o:end]
        if big is None:  # Wii is big-endian: names offset reads small in BE
            big = struct.unpack_from(">H", t, 6)[0] < struct.unpack_from("<H", t, 6)[0]
        try:
            name, tab = parse_table(t, ">" if big else "<")
        except Exception as ex:  # keep going; report broken tables
            name, tab = f"__error_{o:X}", dict(error=str(ex))
        out[name] = tab
    return out


def load_many(paths):
    out = {}
    for p in paths:
        out.update(tables_in(p))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    tabs = tables_in(sys.argv[2])
    if sys.argv[1] == "list":
        for k, v in tabs.items():
            print(k, len(v.get("rows", [])), v.get("cols", v.get("error")))
    else:
        json.dump(tabs, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
