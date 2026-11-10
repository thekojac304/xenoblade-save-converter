import sys, struct
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\tools")
import wii_save as W
d = open(sys.argv[1], "rb").read()
le = lambda f, o: struct.unpack_from("<"+f, d, o)[0]
print("scenario LE u16 @A0B2", le("H", 0xA0B2), "@A0B0", le("H",0xA0B0))
print("map u32 @GAME", hex(le("I", W.GAME)), d[W.GAME:W.GAME+16])
print("playtime", hex(le("I", 0x11EB0)), d[0x11EB0:0x11EBC].hex())
for k in range(1, 14):
    b = W.CHAR_BASE + W.CHAR_SIZE * k
    print(k, "id", le("H", b), "lvl", le("I", b+0x17C), "exp", le("I", b+0x2A4), "ap", le("I", b+0x2A8), "equip_gid", struct.unpack_from("<6H", d, b+2))
print("party", [le("H", W.PARTY + 4*i) for i in range(7)], d[W.PARTY-2:W.PARTY+28].hex())
print("money", le("I", W.ITEM + 0x120E8))
print(d[0x10:0x100].hex())
