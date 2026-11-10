"""A1: DE character records 3 (Fiora) and 8 (Fiora, later form) across the public late-game saves (v7/v10)."""
import glob, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import de_save
fs = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "public_v7", "*.sav")))
prev = None
for f in fs:
    d = open(f, "rb").read()
    ir = de_save.decode_bytes(d)
    c3, c8 = ir["characters"][3], ir["characters"][8]
    def brief(c):
        return {k: c[k] for k in ("level", "exp", "ap", "affinity_coins", "skill_selected_tree", "skill_sp", "skill_learned",
                                  "link_unlock_index", "highest_level", "highest_level_exp", "reserve_exp")} | \
               {"equip": {s: (e["index"], e["type"]) for s, e in c["equipment"].items()}, "palette": c["palette"],
                "cosmetic": c["cosmetic"], "links": c["links"]}
    b3, b8 = brief(c3), brief(c8)
    print("==", os.path.basename(f), "story", ir["story"], "party", ir["party"])
    if prev is None:
        print(" c3", json.dumps(b3)); print(" c8", json.dumps(b8))
    else:
        for name, b, p in (("c3", b3, prev[0]), ("c8", b8, prev[1])):
            ch = {k: (p[k], b[k]) for k in b if b[k] != p[k]}
            print(" ", name, "changed:", json.dumps(ch) if ch else "-")
    # arts of 8 vs 3: art level table is per art id; which arts belong to pc 8?
    prev = (b3, b8)
