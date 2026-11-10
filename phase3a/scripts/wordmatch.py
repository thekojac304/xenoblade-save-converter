import sys, struct
sys.path.insert(0, r"..\tools")
import wii_save as W
d = open(sys.argv[1],"rb").read(); w = open(sys.argv[2],"rb").read()
H = {"4": lambda b: b[::-1], "22": lambda b: b[1::-1]+b[3:1:-1], "1111": lambda b: b, "211": lambda b: b[1::-1]+b[2:4], "112": lambda b: b[:2]+b[3:1:-1]}
def classify(o):
    a, b = w[o:o+4], d[o:o+4]
    if a == b and a in (b"\0"*4, b"\xff"*4): return "zero"
    ok = [h for h, f in H.items() if f(a) == b]
    return ",".join(ok) if ok else ("pad" if b"\xe3" in b else "diff")
for tag, hdr, s, e in W.SECTIONS:
    from collections import Counter
    c = Counter(classify(o) for o in range(s, e - 3, 4))
    print(tag, dict(c))
