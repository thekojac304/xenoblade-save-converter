import os, struct, sys, collections
ROOT = r"C:\Dev\XC_Wii_to_DE_Research"
sys.path.insert(0, os.path.join(ROOT, "phase3b", "tests"))
import hubfix as H, canon, glob
T = H.T
# crystal +0x18 vs source/named table on all real saves
c = collections.Counter()
for f in glob.glob(os.path.join(ROOT, "phase2f", "fixtures", "real", "*.sav")):
    d = open(f, "rb").read()
    for i in range(500):
        o = 0x26D90 + 0x2C * i
        if not d[o + 0x10]: continue
        gid = struct.unpack_from("<H", d, o + 4)[0]
        src = struct.unpack_from("<H", d, o + 0x14)[0]
        named = d[o + 0x18]
        pred = 2 if T["named"].get(src) else 1
        c[(gid == 0, d[o+0x19], named, pred)] += 1
        if gid == 0 and d[o+0x19] == 0 and named != pred:
            print(os.path.basename(f), i, "src", src, "named", named, "pred", pred, d[o:o+0x2C].hex())
print(c)
print("--- list crystals")
cc = collections.Counter()
for f in glob.glob(os.path.join(ROOT, "phase2f", "fixtures", "real", "*.sav")):
    d = open(f, "rb").read()
    for i in range(500):
        o = 0x26D90 + 0x2C * i
        if not d[o + 0x10]: continue
        gid = struct.unpack_from("<H", d, o + 4)[0]
        if gid == 0: continue
        src = struct.unpack_from("<H", d, o + 0x14)[0]
        cc[(gid, src, d[o+0x18])] += 1
for k, v in sorted(cc.items()): print(k, v, T["named"].get(k[1]))
