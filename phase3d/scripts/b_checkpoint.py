"""Story checkpoint validation (Part B3 steps 8-10): canonical state of a game-written save, its difference from the
previous checkpoint, and the next legitimate objective (EVT_sev rows for the current scenario).
  python b_checkpoint.py <prev save> <new save> [label]   (DE saves or Wii/3DS saves)"""
import json
import os
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3b", "tests"))
import hubfix as H  # noqa: E402
import canon  # noqa: E402
import xc3d  # noqa: E402

T = H.T
EVT = json.load(open(os.path.join(ROOT, "data", "bdat_de.json"), encoding="utf-8"))["EVT_sev"]
EVT = EVT["rows"] if isinstance(EVT, dict) else EVT


def load(p):
    b = H.rd(p)
    if b[:4] == b"USRD":
        return "wii", canon.from_wii(b, T)
    if len(b) in (0x153F30, 0x153860):
        return "de", canon.from_de(b, T)
    return "3ds", canon.from_wii(xc3d.transcode(xc3d.unpack(b), "wii"), T)


def main(a, b, label=""):
    ga, ca = load(a)
    gb, cb = load(b)
    sa, sb = ca["shared"], cb["shared"]
    flags_set = sorted(k for k, v in sb["flags"].items() if sa["flags"].get(k) != v)
    flags_cleared = sorted(k for k in sa["flags"] if k not in sb["flags"])
    inv = {box: (len(sa["inventory"][box]), len(sb["inventory"][box])) for box in sb["inventory"]
           if len(sa["inventory"][box]) != len(sb["inventory"][box])}
    lv = {k: (sa["characters"][k]["level"], sb["characters"][k]["level"]) for k in sb["characters"]
          if sa["characters"][k]["level"] != sb["characters"][k]["level"]}
    nxt = [r for r in EVT if r.get("scenario_flag") == sb["story"]]
    rep = {"label": label, "games": [ga, gb], "story": [sa["story"], sb["story"]], "party": [sa["party"], sb["party"]],
           "map": [sa["map"], sb["map"]], "position": [sa["position"], sb["position"]],
           "play_time_s": [sa["play_time_s"], sb["play_time_s"]], "money": [sa["money"], sb["money"]],
           "flags_changed": len(flags_set), "flags_cleared": len(flags_cleared), "levels_changed": lv,
           "inventory_counts_changed": inv,
           "quests_changed": sorted(q for q in set(sa["quest_counters"]) | set(sb["quest_counters"])
                                    if sa["quest_counters"].get(q) != sb["quest_counters"].get(q)),
           "next_objective_EVT_sev": [{k: r.get(k) for k in ("script", "map", "scenario_flag", "evth_pos_x",
                                                             "evth_pos_y", "evth_pos_z")} for r in nxt]}
    print(json.dumps(rep, indent=1))
    return rep


if __name__ == "__main__":
    main(*sys.argv[1:])
