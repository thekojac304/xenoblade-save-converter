"""Tiny DSL -> Monado input-replay route ("# xcde input v1": <frame> <buttons hex> <lx> <ly> <rx> <ry>).

Script lines (one command per line, '#' comments):
  load                      title/menu/list/slot/Yes A presses (60 fps timing); leaves the cursor at frame 4300
  at <frame>                jump the cursor to an absolute frame (must not go backwards)
  wait <frames>
  tap <btn>[+<btn>] [xN] [every F]   press for 6 frames (default spacing 30 frames)
  hold <btn> <frames>
  stick <lx> <ly> <frames>  left stick (-32767..32767; up = +ly)
  rstick <rx> <ry> <frames>
  shot [label]              capture at the current frame
Buttons: A B X Y L R ZL ZR PLUS MINUS LEFT UP RIGHT DOWN.

  python route.py <script.txt> <out_route.txt>   -> prints the capture frames (comma list) and labels
"""
import json
import sys

BTN = {"A": 0x1, "B": 0x2, "X": 0x4, "Y": 0x8, "L": 0x40, "R": 0x80, "ZL": 0x100, "ZR": 0x200, "PLUS": 0x400,
       "MINUS": 0x800, "LEFT": 0x1000, "UP": 0x2000, "RIGHT": 0x4000, "DOWN": 0x8000}


def compile_script(lines):
    ev, shots, f = [(1, 0, 0, 0, 0, 0)], [], 1

    def mask(s):
        m = 0
        for b in s.upper().split("+"):
            m |= BTN[b]
        return m

    for raw in lines:
        ln = raw.split("#", 1)[0].strip()
        if not ln:
            continue
        p = ln.split()
        c = p[0].lower()
        if c == "load":
            # 60 fps: title (600), menu (1000), load list (1400), slot (2700) -> confirm dialog, Yes (3300); the
            # A at 3900 is a spare in case the dialog was late (harmless in the open field at the save point)
            for t in (600, 1000, 1400, 2700, 3300, 3900):
                ev += [(t, 1, 0, 0, 0, 0), (t + 6, 0, 0, 0, 0, 0)]
            f = 4300
        elif c == "at":
            n = int(p[1])
            if n < f:
                raise ValueError(f"'at {n}' goes backwards (cursor {f})")
            f = n
        elif c == "wait":
            f += int(p[1])
        elif c == "tap":
            m, n, every = mask(p[1]), 1, 30
            for i, tok in enumerate(p[2:], 2):
                if tok.startswith("x"):
                    n = int(tok[1:])
                elif tok == "every":
                    every = int(p[i + 1])
            for _ in range(n):
                ev += [(f, m, 0, 0, 0, 0), (f + 6, 0, 0, 0, 0, 0)]
                f += every
        elif c == "hold":
            m, n = mask(p[1]), int(p[2])
            ev += [(f, m, 0, 0, 0, 0), (f + n, 0, 0, 0, 0, 0)]
            f += n
        elif c in ("stick", "rstick"):
            x, y, n = int(p[1]), int(p[2]), int(p[3])
            ev += [(f, 0, x, y, 0, 0) if c == "stick" else (f, 0, 0, 0, x, y), (f + n, 0, 0, 0, 0, 0)]
            f += n
        elif c == "shot":
            shots.append((f, " ".join(p[1:]) or f"f{f}"))
        else:
            raise ValueError(f"unknown command: {ln}")
    ev.sort(key=lambda e: e[0])
    # collapse same-frame events: later wins
    out = {}
    for e in ev:
        out[e[0]] = e
    return [out[k] for k in sorted(out)], shots


def main(src, dst):
    ev, shots = compile_script(open(src, encoding="utf-8").read().splitlines())
    with open(dst, "w", newline="\n") as fo:
        fo.write("# xcde input v1\n# compiled from %s by tools/route.py\n" % src.replace("\\", "/"))
        for e in ev:
            fo.write("%d %x %d %d %d %d\n" % e)
    json.dump({"shots": shots}, open(dst + ".shots.json", "w"), indent=1)
    print(",".join(str(s[0]) for s in shots))
    for s in shots:
        print(s[0], s[1], file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
