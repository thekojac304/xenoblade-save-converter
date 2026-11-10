"""Monado route: load, A taps from <start> to <end> (every 84), shots at most <n> spread, then the normal save
sequence (PLUS, A list, A slot, A confirm) and a final shot.   python mkroute2.py <out> <start> <end> [n=14]"""
import sys
out, start, end = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
n = int(sys.argv[4]) if len(sys.argv) > 4 else 14
step = max(84, ((end - start) // n) // 84 * 84)
L = ["load", "shot loaded", f"at {start - 300}", "shot warped", f"at {start}"]
f, nxt = start, start
while f < end:
    if f >= nxt:
        L.append(f"shot t{f}"); nxt += step
    L += ["tap A", "wait 54"]; f += 84
L += ["wait 600", "shot field", "tap PLUS", "wait 120", "shot save_menu", "tap A", "wait 150", "shot save_list",
      "tap A", "wait 150", "shot save_confirm", "tap A", "wait 300", "shot save_done", "tap B", "wait 60", "tap B",
      "wait 60", "tap B", "wait 120", "shot end"]
open(out, "w").write("\n".join(L) + "\n")
