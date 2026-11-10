"""Child process for crash tests: runs Scan + Sync on a hub and kills itself (os._exit, no cleanup, no finally
blocks) at one fault point - the closest simulation of a power cut / killed window.

  python crash_child.py <hub> <point> [source-key-substring]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hubfix  # noqa: E402,F401
from xcsync import store, scan, sync  # noqa: E402

hub = store.Hub.open(sys.argv[1])
point = sys.argv[2]


def fault(p, detail=""):
    if p == point:
        os._exit(77)


sync.FAULT = fault
res = scan.scan(hub, delay=0, settle=0.5)
key = res.decision.source
if len(sys.argv) > 3:
    key = next(o.key for o in res.saves() if sys.argv[3] in o.key)
sync.sync(hub, res, key, delay=0)
sys.exit(0)
