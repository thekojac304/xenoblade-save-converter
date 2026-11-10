"""Parse Monado's XCDE_ENT_SCAN / XCDE_PARTY_PROBE log lines from a run's stderr.log -> characters with positions."""
import re
import sys

p = sys.argv[1]
t = open(p, "rb").read().decode("utf-8", "replace")
for ln in t.splitlines():
    if ln.startswith(("[ents]", "[party]")):
        print(ln[:200])
