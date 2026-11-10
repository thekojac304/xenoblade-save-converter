"""Story route script: load the save, then A every 84 frames (dialogue) with a capture every `shot_every` frames, for
`minutes` minutes after the load; optional in-game save sequence at the end (PLUS, A, A, A).
  python mkstory.py <out.txt> <minutes> [shot_every=1200] [--save] [--a-from FRAME]"""
import sys

out, minutes = sys.argv[1], float(sys.argv[2])
every = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 1200
a_from = int(sys.argv[sys.argv.index("--a-from") + 1]) if "--a-from" in sys.argv else 4800
end = 4300 + int(minutes * 3600)
lines = ["load", "shot loaded", f"at {a_from}"]
f, next_shot = a_from, a_from + every
while f < end:
    lines.append("tap A")
    lines.append("wait 84")
    f += 90
    if f >= next_shot:
        lines.append(f"shot t{f}")
        next_shot += every
if "--save" in sys.argv:
    lines += ["wait 300", "tap PLUS", "wait 120", "shot save_menu", "tap A", "wait 150", "shot save_list", "tap A",
              "wait 150", "shot save_confirm", "tap A", "wait 300", "shot save_done", "tap B", "wait 60", "tap B",
              "wait 60", "tap B", "wait 120", "shot end"]
open(out, "w").write("\n".join(lines) + "\n")
print(len(lines), "lines; end frame", f)
