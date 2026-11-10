import sys, json
from collections import Counter
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\tools")
import canon, convert
T = convert.load_tables()
def load(p):
    b = open(p, "rb").read()
    return canon.from_de(b, T)
a, b = load(sys.argv[1]), load(sys.argv[2])
def ms(c):
    out = {}
    for box, recs in c["shared"]["inventory"].items():
        out[box] = Counter(json.dumps({k: v for k, v in r.items() if k not in ("order",)}, sort_keys=True) for r in recs.values())
    return out
A, B = ms(a), ms(b)
for box in sorted(set(A) | set(B)):
    x, y = A.get(box, Counter()), B.get(box, Counter())
    if x != y:
        print(box, "only in first:", sum((x - y).values()), "only in second:", sum((y - x).values()), list((x - y).items())[:3], list((y - x).items())[:3])
    else:
        print(box, "same multiset", sum(x.values()))
sa, sb = a["shared"], b["shared"]
for k in ("story", "money", "party", "flags", "quest_counters", "collectopaedia", "achievements"):
    print(k, "same" if sa[k] == sb[k] else "DIFF")
for c in sa["characters"]:
    ca, cb = dict(sa["characters"][c]), dict(sb["characters"][c]); ca.pop("equipment", None); cb.pop("equipment", None)
    print("char", c, "same (excluding equipment slot refs)" if ca == cb else canon.compare(ca, cb)[:4])
print("de_only flags same:", a["de_only"]["flags"] == b["de_only"]["flags"], "| de_only chars same:", a["de_only"]["characters"] == b["de_only"]["characters"])
