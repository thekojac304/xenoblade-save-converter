import sys
files = {"3DS8": "fixtures/3ds_user_s008.raw", "W6": "fixtures/wii_d7_s006.bin", "W18": "fixtures/wii_user_s018.bin", "W150": "fixtures/wii_user_s150.bin", "W232": r"..\phase2f\runs\dolphin\d2_s232_fiora_fix\user\Wii\title\00010000\53583445\data\monado01"}
D = {k: open(v, "rb").read() for k, v in files.items()}
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
for o in range(lo, hi, 16):
    rows = {k: v[o:o+16] for k, v in D.items()}
    if not any(any(r) for r in rows.values()): continue
    print(f"{o:05x} " + " | ".join(f"{k} {r.hex(' ',4)}" for k, r in rows.items()))
