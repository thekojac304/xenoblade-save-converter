"""Read-only inspector for the XC1 Wii -> DE feasibility study (Phase 1).

Opens files read-only and prints facts used in XC_WII_TO_DE_FEASIBILITY.md. Writes nothing.
Run on COPIES of saves:  python -I inspect_saves.py <wii monadoNN> [<DE bfsgameNN.sav>]

Offsets: Wii from enderslash1010/xc1-save-editor-cpp (src/SaveFile.cpp, SaveFile.h);
DE from hashcade/xbde-save-editor (v7 layout) and Monado docs/party_switch_research.md (v10 file).
"""
import struct
import sys

WII_SECTIONS = [  # (tag header offset, CRC range start, CRC range end)
    (0x10, 0x20, 0x9CA0), (0xA020, 0xA030, 0xB244), (0xB250, 0xB260, 0x11E88), (0x11EA0, 0x11EB0, 0x11EBC),
    (0x11ED0, 0x11EE0, 0x11F14), (0x11F20, 0x11F30, 0x11F40), (0x11F50, 0x11F60, 0x24080), (0x24080, 0x24090, 0x240A0),
    (0x240B0, 0x240C0, 0x240D0), (0x240E0, 0x240F0, 0x24474), (0x24490, 0x244A0, 0x246D4), (0x248A0, 0x248B0, 0x248F0),
]
WII_CHARS = ["Shulk", "Reyn", "Fiora", "Dunban", "Sharla", "Riki", "Melia", "Fiora(M)", "Dickson", "Mumkhar", "Alvis",
             "Dunban(prologue)"]


def crc16_arc(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def wii(path):
    d = open(path, "rb").read()
    be = lambda fmt, off: struct.unpack_from(">" + fmt, d, off)[0]
    print(f"== Wii {path}: {len(d)} bytes, magic {d[:4]!r}")
    if d[:4] != b"USRD":
        return
    for hdr, start, end in WII_SECTIONS:
        ok = be("H", hdr + 0xE) == crc16_arc(d[start:end])
        print(f"  {d[hdr:hdr + 4].decode()} @0x{hdr:05X} size 0x{be('I', hdr + 4):X} crc {'OK' if ok else 'BAD'}")
    print(f"  scenario (FLAG+0x82) = {be('H', 0xA0B2)}")
    print(f"  map = 0x{be('I', 0xB260):08X} '{d[0xB264:0xB268].decode()}'  play time (THUM) {be('H', 0x2A)}h{be('H', 0x2C):02}m")
    print(f"  money = {be('i', 0x24048)}")
    print(f"  party ids = {[be('H', 0xD1FE + 4 * i) for i in range(7)]}")
    print("  levels = " + ", ".join(f"{n} {be('I', 0xF8D0 + 0x304 * i)}" for i, n in enumerate(WII_CHARS)))
    print("  u16 bank around scenario: " + " ".join(str(be("H", 0xA0B2 + 2 * i)) for i in range(16)))


def de(path):
    d = open(path, "rb").read()
    le = lambda fmt, off: struct.unpack_from("<" + fmt, d, off)[0]
    print(f"== DE {path}: {len(d)} bytes (0x{len(d):X}), format version {le('I', 0)}, play time {le('I', 4)} s")
    print(f"  story u16 @0xDF0 = {le('H', 0xDF0)}")
    if len(d) == 0x153F30:  # 2.0.0 / v10 file as written by Monado
        print(f"  party @0x1526D8 = {[le('H', 0x1526D8 + 2 * i) for i in range(12)]} count {le('I', 0x1526F0)}")
        print(f"  position @0x149C10 = {[round(le('f', 0x149C10 + 4 * i), 1) for i in range(3)]}")
    elif len(d) == 0x153860:  # v7 layout used by the community editors
        print(f"  party @0x152318 = {[le('H', 0x152318 + 2 * i) for i in range(12)]} count {d[0x152330]}")
        print(f"  money @0x151B40 = {le('I', 0x151B40)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    wii(sys.argv[1])
    if len(sys.argv) > 2:
        de(sys.argv[2])
