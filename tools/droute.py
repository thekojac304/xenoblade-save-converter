"""Dolphin route DSL -> ms route for dolphin_harness.py. Commands: load | at <ms> | wait <ms> | tap <BTN>[+BTN] [xN]
[every <ms>] | hold <BTN> <ms> | stick <lx> <ly> <ms> | rstick <rx> <ry> <ms> | shot. Times in milliseconds."""
import sys


def compile_script(lines):
    ev, t = [], 0

    def press(names, ms=150):
        ev.append((t, names))
        ev.append((t + ms, "0"))
    for raw in lines:
        ln = raw.split("#", 1)[0].strip()
        if not ln:
            continue
        p = ln.split()
        c = p[0].lower()
        if c == "load":   # title, load list, slot dialog, Yes (default is No), A
            for s in (26000, 32000, 38000):
                t = s
                press("A")
            t = 43000
            press("SHOT", 120)   # the load list (slot summary from THUM)
            t = 44000
            press("A")
            t = 45500
            press("UP")
            t = 46500
            press("A")
            t = 53000          # "Load Complete" dialog: A closes it
            press("A")
            t = 85000          # the field appears ~72-75 s after the first poll
        elif c == "at":
            t = int(p[1])
        elif c == "wait":
            t += int(p[1])
        elif c == "tap":
            n, every = 1, 400
            for i, tok in enumerate(p[2:], 2):
                if tok.startswith("x"):
                    n = int(tok[1:])
                elif tok == "every":
                    every = int(p[i + 1])
            for _ in range(n):
                press(p[1].upper())
                t += every
        elif c == "hold":
            press(p[1].upper(), int(p[2]))
            t += int(p[2])
        elif c in ("stick", "rstick"):
            x, y, ms = float(p[1]), float(p[2]), int(p[3])
            vals = f"{x} {y} 0 0" if c == "stick" else f"0 0 {x} {y}"
            ev.append((t, "0 " + vals))
            ev.append((t + ms, "0"))
            t += ms
        elif c == "shot":
            press("SHOT", 120)
            t += 200
        else:
            raise ValueError(ln)
    return ev


if __name__ == "__main__":
    ev = compile_script(open(sys.argv[1], encoding="utf-8").read().splitlines())
    with open(sys.argv[2], "w") as f:
        f.write(f"# compiled from {sys.argv[1]}\n")
        for t, b in sorted(ev, key=lambda e: e[0]):
            f.write(f"{t} {b}\n")
