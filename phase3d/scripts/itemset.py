"""Item multiset check: same items (content without order/slot) in every box, and every character's equipment points
at an item with the same content as before (slots may differ - limitation 6).
  python itemset.py <de a> <de b>"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import canon  # noqa: E402
import xcservice  # noqa: E402


def key(r):
    return json.dumps(canon.strip_order(r), sort_keys=True)


def check(pa, pb, T):
    a = canon.from_de(open(pa, "rb").read(), T)["shared"]
    b = canon.from_de(open(pb, "rb").read(), T)["shared"]
    out = {}
    for box in a["inventory"]:
        ma = collections.Counter(key(r) for r in a["inventory"][box].values())
        mb = collections.Counter(key(r) for r in b["inventory"][box].values())
        out[box] = {"a": sum(ma.values()), "b": sum(mb.values()), "same": ma == mb}
    eq = {}
    for k, c in a["characters"].items():
        for sl, i in (c.get("equipment") or {}).items():
            j = (b["characters"][k].get("equipment") or {}).get(sl)
            ra = a["inventory"][sl].get(i) if i is not None else None
            rb = b["inventory"][sl].get(j) if j is not None else None
            eq[f"{k}.{sl}"] = (ra is None and rb is None) or (ra is not None and rb is not None and key(ra) == key(rb))
    return out, eq


if __name__ == "__main__":
    out, eq = check(sys.argv[1], sys.argv[2], xcservice.tables())
    bad = {k: v for k, v in out.items() if not v["same"]}
    print("boxes same:", len(out) - len(bad), "/", len(out), "differ:", bad)
    print("equipment same content:", sum(eq.values()), "/", len(eq), [k for k, v in eq.items() if not v])
