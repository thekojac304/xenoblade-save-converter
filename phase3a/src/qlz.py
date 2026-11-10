"""QuickLZ 1.5.x level-3 block codec (no streaming buffer), clean-room Python implementation (Phase 3A).

Xenoblade Chronicles 3D wraps each save in a "!qzb" header followed by ONE QuickLZ level-3 block with the 9-byte
("long") header.  This module implements the block format from its published description: decompress() accepts any
valid level-3 block, compress() reproduces the reference compressor's greedy level-3 parse (16 hash candidates per
4096-entry bucket, unsigned-char bucket counters) so a decompress -> compress cycle of a game-written block is
byte-identical (verified on every game-written save, see tests/test_phase3a_qlz.py).

Block header (little-endian):
  byte 0  flags: bit0 compressed, bit1 9-byte header, bits2-3 level (3), bit6 always set, bits4-5 streaming (0)
  u32     total block size including the header
  u32     decompressed size
Body: 32-bit control words (bit 31 is a sentinel; bits consumed LSB first, 1 = match), literals and matches.
"""
import struct

MINOFFSET = 2
UNCONDITIONAL_MATCHLEN = 6
UNCOMPRESSED_END = 4
CWORD_LEN = 4
POINTERS = 16
HASH_VALUES = 4096


class QLZError(ValueError):
    pass


def header(block):
    if len(block) < 9:
        raise QLZError("QuickLZ block too short")
    flags = block[0]
    if not flags & 0x40 or not flags & 0x02:
        raise QLZError(f"unsupported QuickLZ header flags 0x{flags:02x}")
    level = (flags >> 2) & 3
    if level != 3 or (flags >> 4) & 3:
        raise QLZError(f"unsupported QuickLZ level {level} / streaming mode {(flags >> 4) & 3}")
    csize, dsize = struct.unpack_from("<II", block, 1)
    return flags, csize, dsize


def decompress(block):
    flags, csize, dsize = header(block)
    if csize > len(block) or csize < 9:
        raise QLZError("QuickLZ block truncated")
    if not flags & 1:
        if csize != dsize + 9:
            raise QLZError("stored QuickLZ block has inconsistent sizes")
        return bytes(block[9:csize])
    src, end = 9, csize
    out = bytearray()
    cword = 1
    try:
        while len(out) < dsize:
            if cword == 1:
                cword = struct.unpack_from("<I", block, src)[0]
                src += 4
                if not cword & 0x80000000:
                    raise QLZError("QuickLZ control word without sentinel")
            if cword & 1:
                cword >>= 1
                f = int.from_bytes(block[src:src + 4].ljust(4, b"\0"), "little")
                if f & 3 == 0:
                    off, ml, src = (f & 0xFF) >> 2, 3, src + 1
                elif f & 2 == 0:
                    off, ml, src = (f & 0xFFFF) >> 2, 3, src + 2
                elif f & 1 == 0:
                    off, ml, src = (f & 0xFFFF) >> 6, ((f >> 2) & 15) + 3, src + 2
                elif f & 127 != 3:
                    off, ml, src = (f >> 7) & 0x1FFFF, ((f >> 2) & 0x1F) + 2, src + 3
                else:
                    off, ml, src = f >> 15, ((f >> 7) & 255) + 3, src + 4
                if off == 0 or off > len(out) or len(out) + ml > dsize:
                    raise QLZError("QuickLZ match out of range")
                s = len(out) - off
                for i in range(ml):            # overlapping copy
                    out.append(out[s + i])
            else:
                cword >>= 1
                if src >= end:
                    raise QLZError("QuickLZ literal past end of block")
                out.append(block[src])
                src += 1
            if src > end:
                raise QLZError("QuickLZ block overrun")
    except struct.error as e:
        raise QLZError("QuickLZ block truncated") from e
    return bytes(out)


def _hash(v):
    return ((v >> 12) ^ v) & (HASH_VALUES - 1)


def _core(s):
    """Reference level-3 compress_core; returns body bytes or None when the data is not compressible enough."""
    size = len(s)
    last_byte = size - 1
    last_matchstart = last_byte - UNCONDITIONAL_MATCHLEN - UNCOMPRESSED_END
    dst = bytearray(4)
    cword_ptr = 0
    cword = 1 << 31
    counters = [0] * HASH_VALUES
    table = [[0] * POINTERS for _ in range(HASH_VALUES)]
    src = 0
    rd3 = lambda p: s[p] | (s[p + 1] << 8) | (s[p + 2] << 16)
    while src <= last_matchstart:
        if cword & 1:
            if src > (size >> 1) and len(dst) > src - (src >> 5):
                return None
            struct.pack_into("<I", dst, cword_ptr, (cword >> 1) | (1 << 31))
            cword_ptr = len(dst)
            dst += b"\0\0\0\0"
            cword = 1 << 31
        remaining = min(255, last_byte - src + 1 - UNCOMPRESSED_END)
        fetch = rd3(src)
        h = _hash(fetch)
        c = counters[h]
        row = table[h]
        o2 = row[0]
        if c > 0 and o2 < src - MINOFFSET and rd3(o2) == fetch:
            matchlen = 3
            if s[o2 + 3] == s[src + 3]:
                matchlen = 4
                while s[o2 + matchlen] == s[src + matchlen] and matchlen < remaining:
                    matchlen += 1
        else:
            matchlen = 0
        k = 1
        while k < POINTERS and c > k:
            o = row[k]
            if rd3(o) == fetch and o < src - MINOFFSET:
                m = 3
                while s[o + m] == s[src + m] and m < remaining:
                    m += 1
                if m > matchlen or (m == matchlen and o > o2):
                    o2, matchlen = o, m
            k += 1
        row[c & (POINTERS - 1)] = src
        counters[h] = (c + 1) & 0xFF
        if matchlen > 2 and src - o2 < 131071:
            for u in range(1, matchlen):
                hu = _hash(rd3(src + u))
                cu = counters[hu]
                counters[hu] = (cu + 1) & 0xFF
                table[hu][cu & (POINTERS - 1)] = src + u
            offset = src - o2
            cword = (cword >> 1) | (1 << 31)
            src += matchlen
            if matchlen == 3 and offset <= 63:
                dst.append((offset << 2) & 0xFF)
            elif matchlen == 3 and offset <= 16383:
                dst += ((offset << 2) | 1).to_bytes(2, "little")
            elif matchlen <= 18 and offset <= 1023:
                dst += (((matchlen - 3) << 2) | (offset << 6) | 2).to_bytes(2, "little")
            elif matchlen <= 33:
                dst += (((matchlen - 2) << 2) | (offset << 7) | 3).to_bytes(3, "little")
            else:
                dst += (((matchlen - 3) << 7) | (offset << 15) | 3).to_bytes(4, "little")
        else:
            dst.append(s[src])
            src += 1
            cword >>= 1
    while src <= last_byte:
        if cword & 1:
            struct.pack_into("<I", dst, cword_ptr, (cword >> 1) | (1 << 31))
            cword_ptr = len(dst)
            dst += b"\0\0\0\0"
            cword = 1 << 31
        dst.append(s[src])
        src += 1
        cword >>= 1
    while cword & 1 != 1:
        cword >>= 1
    struct.pack_into("<I", dst, cword_ptr, (cword >> 1) | (1 << 31))
    if len(dst) < 9:
        dst += bytes(9 - len(dst))
    return bytes(dst)


def compress(data):
    data = bytes(data)
    if len(data) < 216:
        raise QLZError("blocks shorter than 216 bytes use the 3-byte header (not used by Xenoblade 3D)")
    body = _core(data)
    flags = 0x40 | (3 << 2) | 2
    if body is None:
        body = data
    else:
        flags |= 1
    return bytes([flags]) + struct.pack("<II", len(body) + 9, len(data)) + body
