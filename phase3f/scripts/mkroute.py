"""Write a Monado route script: load, then A taps every <every> frames from <start> to <end>, shot every <shotevery>.
   python mkroute.py <out.txt> <start> <end> [every=84] [shotevery=600] [btn=A]"""
import sys
out, start, end = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
every = int(sys.argv[4]) if len(sys.argv) > 4 else 84
se = int(sys.argv[5]) if len(sys.argv) > 5 else 600
btn = sys.argv[6] if len(sys.argv) > 6 else "A"
L = ["load", "shot loaded", f"at {start - 300}", "shot warped", f"at {start}"]
f, nxt = start, start
while f < end:
    if f >= nxt:
        L.append(f"shot t{f}")
        nxt += se
    L += [f"tap {btn}", f"wait {every - 30}"]
    f += every
L.append("shot end")
open(out, "w").write("\n".join(L) + "\n")
