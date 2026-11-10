"""Inventory content delta between two saves (any platform): items added / removed per box (content without slot or
order).   python invdelta.py <before> <after>"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gearcmp  # noqa: E402
import canon  # noqa: E402
import xcservice  # noqa: E402

if __name__ == "__main__":
    T = xcservice.tables()
    a, b = gearcmp.load(sys.argv[1], T), gearcmp.load(sys.argv[2], T)
    tot = 0
    for box in a["inventory"]:
        ca = collections.Counter(json.dumps(canon.strip_order(r), sort_keys=True) for r in a["inventory"][box].values())
        cb = collections.Counter(json.dumps(canon.strip_order(r), sort_keys=True) for r in b["inventory"][box].values())
        add, rem = cb - ca, ca - cb
        if add or rem:
            tot += 1
            print(box, "added", sum(add.values()), [json.loads(x).get("gid") for x in add.elements()][:12],
                  "removed", sum(rem.values()), [json.loads(x).get("gid") for x in rem.elements()][:12])
    print("boxes changed:", tot)
