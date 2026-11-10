"""Summary of every Phase 3C emulator run: status, duration, isolation/protection results, save states.
  python runs_summary.py [--json out.json]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.normpath(os.path.join(HERE, "..", "runs"))
out = {}
for emu in ("monado", "dolphin", "azahar"):
    d = os.path.join(RUNS, emu)
    if not os.path.isdir(d):
        continue
    for name in sorted(os.listdir(d)):
        for fn in ("run_manifest.json", "result.json"):
            p = os.path.join(d, name, fn)
            if os.path.exists(p):
                m = json.load(open(p))
                out[f"{emu}/{name}"] = {k: m.get(k) for k in ("status", "seconds", "protected_unchanged", "live_unchanged",
                                                             "watchdog_violation", "save_changed", "input_state",
                                                             "output_states") if k in m}
                if "install_changes" in m:
                    out[f"{emu}/{name}"]["install_changed"] = m["install_changes"].get("changed")
                break
for k, v in out.items():
    print(k, json.dumps({x: v.get(x) for x in ("status", "seconds", "protected_unchanged", "live_unchanged",
                                                 "watchdog_violation", "install_changed")}))
if "--json" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
