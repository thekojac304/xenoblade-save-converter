import sys
d3 = open("fixtures/3ds_user_s008.raw","rb").read()
ws = [open(p,"rb").read() for p in [r"..\work\originals\monado01", r"..\work\originals\monado03", r"..\phase2f\runs\dolphin\d1_s232_load_save\user\Wii\title\00010000\53583445\data\monado01", r"..\work\phase2e\dolphin\d7_native\user\Wii\title\00010000\53583445\data\monado01"]]
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
step = 16
for o in range(lo, hi, step):
    rows = [d3[o:o+step]] + [w[o:o+step] for w in ws]
    if not any(any(r) for r in rows): continue
    print(f"{o:05x} 3DS {rows[0].hex(' ',4)} | " + " | ".join(r.hex(' ',4) for r in rows[1:3]))
