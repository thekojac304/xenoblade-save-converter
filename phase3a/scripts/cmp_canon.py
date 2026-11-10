"""Compare the canonical state of two saves (Wii monadoNN or 3DS monadoNN files)."""
import sys
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\tools"); sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\phase3a\src")
import xc3d, canon, convert
def load(p):
    d = open(p, "rb").read()
    return xc3d.transcode(xc3d.unpack(d), "wii") if xc3d.is_3ds_file(d) else d
T = convert.load_tables()
a, b = load(sys.argv[1]), load(sys.argv[2])
ca, cb = canon.from_wii(a, T), canon.from_wii(b, T)
for part in ("shared", "wii_only"):
    diffs = canon.compare(ca[part], cb[part])
    print(part, "differences:", len(diffs))
    for p, x, y in diffs[:60]:
        print("  ", p, "|", str(x)[:80], "->", str(y)[:80])
