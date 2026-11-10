"""Read-only helpers for a decrypted (NoCrypto) 3DS NCSD/NCCH image (Phase 3A research tool).

Extracts the ExeFS .code (BLZ-decompressed when the ExHeader says so), the ExHeader, and files from the RomFS.
The image is only opened for reading.  Used on the user's own dump of Xenoblade Chronicles 3D.

  python ctr.py <game.3ds> code <out.bin>
  python ctr.py <game.3ds> list [substring]
  python ctr.py <game.3ds> get <romfs path> <out>
"""
import struct
import sys

MU = 0x200


class Image:
    def __init__(self, path):
        self.f = open(path, "rb")
        hdr = self._read(0x100, 0x100)
        if hdr[:4] != b"NCSD":
            raise ValueError("not an NCSD image")
        part0_off = struct.unpack_from("<I", hdr, 0x20)[0] * MU
        self.ncch = part0_off
        n = self._read(part0_off + 0x100, 0x100)
        if n[:4] != b"NCCH":
            raise ValueError("partition 0 is not NCCH")
        if not n[0x8F] & 0x04:
            raise ValueError("NCCH is encrypted; a decrypted dump is required")
        self.exefs_off = part0_off + struct.unpack_from("<I", n, 0xA0)[0] * MU
        self.romfs_off = part0_off + struct.unpack_from("<I", n, 0xB0)[0] * MU
        self.romfs_size = struct.unpack_from("<I", n, 0xB4)[0] * MU
        self.exheader = self._read(part0_off + 0x200, 0x400)
        self._romfs = None

    def _read(self, off, size):
        self.f.seek(off)
        return self.f.read(size)

    def exefs_file(self, name):
        hdr = self._read(self.exefs_off, 0x200)
        for i in range(10):
            nm, off, size = struct.unpack_from("<8sII", hdr, i * 16)
            if nm.rstrip(b"\0").decode() == name:
                return self._read(self.exefs_off + 0x200 + off, size)
        raise KeyError(name)

    def code(self):
        raw = self.exefs_file(".code")
        if self.exheader[0xD] & 1:       # SCI flags: bit0 = compressed ExeFS code
            raw = blz_decompress(raw)
        return raw

    def code_layout(self):
        e = self.exheader
        text = struct.unpack_from("<III", e, 0x10)
        ro = struct.unpack_from("<III", e, 0x20)
        data = struct.unpack_from("<III", e, 0x30)
        return {"text": text, "ro": ro, "data": data, "bss": struct.unpack_from("<I", e, 0x3C)[0]}

    # ---- RomFS (IVFC level 3) ----
    def _l3(self):
        if self._romfs is None:
            ivfc = self._read(self.romfs_off, 0x60)
            if ivfc[:4] != b"IVFC":
                raise ValueError("bad RomFS")
            master_size = struct.unpack_from("<I", ivfc, 0x08)[0]
            bs3 = 1 << struct.unpack_from("<I", ivfc, 0x4C)[0]
            l3 = (0x60 + master_size + bs3 - 1) // bs3 * bs3
            base = self.romfs_off + l3
            h = self._read(base, 0x28)
            vals = struct.unpack_from("<10I", h)
            self._romfs = dict(base=base, dir_meta=(vals[3], vals[4]), file_meta=(vals[7], vals[8]), data=vals[9])
        return self._romfs

    def walk(self):
        r = self._l3()
        dmeta = self._read(r["base"] + r["dir_meta"][0], r["dir_meta"][1])
        fmeta = self._read(r["base"] + r["file_meta"][0], r["file_meta"][1])

        def files(foff, prefix):
            while foff != 0xFFFFFFFF:
                parent, sib, doff, dsize, _, nlen = struct.unpack_from("<IIQQII", fmeta, foff)
                name = fmeta[foff + 0x20:foff + 0x20 + nlen].decode("utf-16-le")
                yield prefix + name, r["base"] + r["data"] + doff, dsize
                foff = sib

        def dirs(doff, prefix):
            parent, sib, child, first_file, _, nlen = struct.unpack_from("<6I", dmeta, doff)
            name = dmeta[doff + 0x18:doff + 0x18 + nlen].decode("utf-16-le")
            p = prefix + name + "/" if doff else "/"
            yield from files(first_file, p)
            c = child
            while c != 0xFFFFFFFF:
                yield from dirs(c, p)
                c = struct.unpack_from("<I", dmeta, c + 4)[0]
        yield from dirs(0, "")

    def get(self, path):
        for p, off, size in self.walk():
            if p == path:
                return self._read(off, size)
        raise KeyError(path)


def blz_decompress(data):
    """Nintendo 'bottom LZ' (backwards LZSS) used for compressed ExeFS .code."""
    data = bytearray(data)
    footer_off = len(data) - 8
    bufdelta, = struct.unpack_from("<I", data, footer_off + 4)
    v, = struct.unpack_from("<I", data, footer_off)
    hdrlen, complen = v >> 24, v & 0xFFFFFF
    out_len = len(data) + bufdelta
    out = bytearray(out_len)
    out[:len(data)] = data
    start = len(data) - complen
    src = len(data) - hdrlen
    dst = out_len
    while src > start:
        src -= 1
        ctrl = out[src]
        for _ in range(8):
            if src <= start:
                break
            if ctrl & 0x80:
                src -= 2
                seg = out[src] | (out[src + 1] << 8)
                disp = (seg & 0x0FFF) + 2
                n = ((seg >> 12) & 0xF) + 3
                for _ in range(n):
                    dst -= 1
                    out[dst] = out[dst + disp + 1]
            else:
                src -= 1
                dst -= 1
                out[dst] = out[src]
            ctrl = (ctrl << 1) & 0xFF
            if dst <= start:
                break
    return bytes(out)


if __name__ == "__main__":
    img = Image(sys.argv[1])
    cmd = sys.argv[2]
    if cmd == "code":
        c = img.code()
        open(sys.argv[3], "wb").write(c)
        print(len(c), img.code_layout())
    elif cmd == "list":
        sub = sys.argv[3] if len(sys.argv) > 3 else ""
        for p, off, size in img.walk():
            if sub in p:
                print(size, p)
    elif cmd == "get":
        open(sys.argv[4], "wb").write(img.get(sys.argv[3]))
