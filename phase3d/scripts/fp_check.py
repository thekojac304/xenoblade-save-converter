import sys, os, json
base = sys.argv[1]
sys.path.insert(0, os.path.join(base, "tools"))
os.environ.setdefault("XCCONV_DATA", r"C:\Dev\XC_Wii_to_DE_Research\data")
import canon, xcservice as xs
T = xs.tables()
out = {}
for p in sys.argv[2:]:
    b = open(p, "rb").read()
    c = canon.from_wii(b, T) if b[:4] == b"USRD" else canon.from_de(b, T)
    out[os.path.basename(p)] = canon.fingerprint(c)
print(json.dumps(out))
