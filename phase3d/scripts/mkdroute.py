"""Dolphin story route (droute DSL, ms): load, optional walk, A every 1.5 s through the scenes with a capture every
`shot_every` ms, then (optionally) the in-game save sequence proven in 3B (X, RIGHT x3, A, A, A, UP, A) and captures.
  python mkdroute.py <out.dsl> --walk "0 1 12000" --scene-s 150 [--shot-every 15000] [--save] [--no-load-shot]"""
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--walk", default="")
ap.add_argument("--scene-s", type=int, default=120)
ap.add_argument("--shot-every", type=int, default=15000)
ap.add_argument("--save", action="store_true")
a = ap.parse_args()
L = ["load", "shot", "at 86000", "shot"]
t = 86200
if a.walk:
    x, y, ms = a.walk.split()
    L += [f"at {t}", f"stick {x} {y} {ms}"]
    t += int(ms) + 200
    L += [f"at {t}", "shot"]
    t += 600
end = t + a.scene_s * 1000
nxt = t + a.shot_every
while t < end:
    L += [f"at {t}", "tap A"]
    t += 1500
    if t >= nxt:
        L += [f"at {t - 700}", "shot"]
        nxt += a.shot_every
if a.save:
    t += 1500
    for dt, cmd in ((0, "tap B"), (1900, "tap B"), (3800, "shot"), (4000, "tap X"), (5900, "tap RIGHT x3 every 600"),
                    (8500, "tap A"), (10900, "tap A"), (13800, "tap A"), (16700, "tap UP"), (17900, "shot"),
                    (18100, "tap A"), (24500, "shot"), (24700, "tap A"), (27100, "tap B"), (29000, "tap B"),
                    (32500, "shot")):
        L += [f"at {t + dt}", cmd]
    t += 33000
L += [f"at {t + 2000}", "shot"]
open(a.out, "w").write("\n".join(L) + "\n")
print(len(L), "lines, ends at", t + 2200, "ms")
