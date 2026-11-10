import sys, struct, hashlib, time
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\phase3a\src")
import qlz
for p in sys.argv[1:]:
    d = open(p, "rb").read()
    magic, dsz, csz = struct.unpack_from("<4sII", d)
    blk = d[12:]
    raw = qlz.decompress(blk)
    t = time.time()
    re = qlz.compress(raw)
    print(p, magic, hex(dsz), hex(csz), len(blk), len(raw), raw[:16].hex(), "recompress identical:", re == blk, round(time.time()-t,2), "s")
    open(p.replace("originals", "fixtures").replace("/", "_") + ".raw", "wb").write(raw)
