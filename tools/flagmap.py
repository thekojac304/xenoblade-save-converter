"""Exact game-flag accessors for XC1 Wii and XC1 DE saves, by global flag id (read-only).

Derived from code, not from data:
  Wii  main.dol (SX4E01): resolver 0x8009DB04, getter 0x8009DBD0, setter 0x8009DCA0.
       Flag array = FLAG section payload, file offset 0xA030, big-endian u32 words.
         id 0x000-0x01F  32-bit  word id
         id 0x020-0x21F  16-bit  s=id-0x20,  word 0x20+(s>>1),  shift 16*(s&1)
         id 0x220-0xA1F   8-bit  s=id-0x220, word 0x120+(s>>2), shift 8*(s&3)
         id 0xA20-0x36CF  1-bit  n=id-0xA20, word 0x320+(n>>5), shift n&31   (n <= 0x2CAF)
  DE   main (build 7E1DF8E08D60544B): getter 0xB2620, setter 0xAEB10. Runtime ctx+0x6B0 = save offset 0.
         id 0x000-0x01F  32-bit  ctx+0x18A0 + 4*id        -> save 0x11F0 + 4*id   (LE u32)
         id 0x020-0x21F  16-bit  ctx+0x14A0 + 2*(id-0x20) -> save 0x0DF0 + 2*s    (LE u16)
         id 0x220-0xA1F   8-bit  ctx+0x0CA0 + (id-0x220)  -> save 0x05F0 + s
         id 0xA20-0x371F  1-bit  ctx+0x0700 word (n>>5)    -> save 0x0050 + 4*(n>>5), bit n&31 (n < 0x2D00)
"""
import struct

WII_P = 0xA030


def kind(gid):
    if gid < 0x20:
        return 32
    if gid < 0x220:
        return 16
    if gid < 0xA20:
        return 8
    return 1


def wii_get(d, gid):
    if gid < 0x20:
        return struct.unpack_from(">I", d, WII_P + 4 * gid)[0]
    if gid < 0x220:
        s = gid - 0x20
        w = struct.unpack_from(">I", d, WII_P + 4 * (0x20 + (s >> 1)))[0]
        return w >> (16 * (s & 1)) & 0xFFFF
    if gid < 0xA20:
        s = gid - 0x220
        w = struct.unpack_from(">I", d, WII_P + 4 * (0x120 + (s >> 2)))[0]
        return w >> (8 * (s & 3)) & 0xFF
    n = gid - 0xA20
    if n > 0x2CAF:
        raise IndexError(gid)
    w = struct.unpack_from(">I", d, WII_P + 4 * (0x320 + (n >> 5)))[0]
    return w >> (n & 31) & 1


def de_get(d, gid):
    if gid < 0x20:
        return struct.unpack_from("<I", d, 0x11F0 + 4 * gid)[0]
    if gid < 0x220:
        return struct.unpack_from("<H", d, 0xDF0 + 2 * (gid - 0x20))[0]
    if gid < 0xA20:
        return d[0x5F0 + gid - 0x220]
    n = gid - 0xA20
    if n >= 0x2D00:
        raise IndexError(gid)
    w = struct.unpack_from("<I", d, 0x50 + 4 * (n >> 5))[0]
    return w >> (n & 31) & 1


WII_RANGE = {32: (0x000, 0x020), 16: (0x020, 0x220), 8: (0x220, 0xA20), 1: (0xA20, 0xA20 + 0x2CB0)}
DE_RANGE = {32: (0x000, 0x020), 16: (0x020, 0x220), 8: (0x220, 0xA20), 1: (0xA20, 0xA20 + 0x2D00)}


def nonzero(d, game, width):
    lo, hi = (WII_RANGE if game == "wii" else DE_RANGE)[width]
    get = wii_get if game == "wii" else de_get
    return {g: v for g in range(lo, hi) if (v := get(d, g))}


def load(path):
    d = open(path, "rb").read()
    return ("wii" if d[:4] == b"USRD" else "de"), d
