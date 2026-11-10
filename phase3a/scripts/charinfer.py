import sys, struct, math
sys.path.insert(0, r"..\tools")
import wii_save as W
d = open("fixtures/3ds_user_s008.raw","rb").read()
ws = [open(p,"rb").read() for p in ["fixtures/wii_d7_s006.bin","fixtures/wii_user_s018.bin","fixtures/wii_user_s150.bin", r"..\phase2f\runs\dolphin\d2_s232_fiora_fix\user\Wii\title\00010000\53583445\data\monado01"]]
lo, hi = int(sys.argv[1],16), int(sys.argv[2],16)
recs3 = [d[W.CHAR_BASE+W.CHAR_SIZE*k: W.CHAR_BASE+W.CHAR_SIZE*(k+1)] for k in range(14)]
recsw = [w[W.CHAR_BASE+W.CHAR_SIZE*k: W.CHAR_BASE+W.CHAR_SIZE*(k+1)] for w in ws for k in range(14)]
for o in range(lo, hi, 4):
    s3 = [r[o:o+4] for r in recs3]; sw = [r[o:o+4] for r in recsw]
    if not any(any(x) for x in s3+sw): continue
    out = []
    for name, fmt in (("u32","I"),("u16","HH"),("u8","BBBB")):
        v3 = [struct.unpack("<"+fmt, x) for x in s3]; vw = [struct.unpack(">"+fmt, x) for x in sw]
        m3 = max(max(v) for v in v3); mw = max(max(v) for v in vw)
        exact = len(set(v3) & set(vw) - {tuple([0]*len(fmt))})
        out.append(f"{name}: max3={m3:<10} maxW={mw:<10} sharedvals={exact}")
    f3 = [struct.unpack("<f", x)[0] for x in s3]; fw = [struct.unpack(">f", x)[0] for x in sw]
    print(f"+{o:03x} " + " | ".join(out) + f" | 3ds {s3[1].hex()} {s3[4].hex()}  wii {sw[15].hex()} {sw[18].hex()}")
