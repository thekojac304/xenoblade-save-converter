"""Quest objective counters, both games (Phase 2E A2; derived in work/phase2e/re_wii_game.md, re_wii/qconv.py).

Storage (8 bytes per quest id; byte s = 4*branch + objective, branch 0 = A, 1 = B):
  Wii  GAME object +0x58 + 8*q  -> file 0xB2B8 + 8*q, q < 1000, signed counters    [C] 0x80140304, 0x80141258
  DE   save 0x1270 + 8*q, q < 1300 (ends at the weapon box 0x3B10)                  [C] getter 0xB8460 (ctx+0x1920)
Semantics:
  Wii: objective done <=> kill (type 1): counter >= num; item/talk/other (2,3,5,6): counter >= 1;
       sub-quest (4): counter >= 1 or the sub-quest's state is 254/255.
  DE : objective done <=> byte == 0xFF; kill progress 0..num-1; on completion (state 254/255) the winning branch is
       filled with 0xFF by the flag listener (0x4D02EC..0x4D03D0).
Rules:
  Wii -> DE: done -> 0xFF; kill in progress keeps its count; else 0; completed quests: winning branch filled as DE does.
  DE -> Wii: 0xFF -> num (kill) or 1 (other types); kill in progress keeps its count (capped at num); q >= 1000 is DE-only
             (Future Connected) and has no Wii slot.
"""
import json
import os

import flagmap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
WII_QC, DE_QC, WII_N, DE_N = 0xB2B8, 0x1270, 1000, 1300
_Q = None


def quests():
    global _Q
    if _Q is None:
        import paths
        with open(paths.data("bdat_wii.json"), encoding="utf-8") as f:
            B = json.load(f)
        _Q = {}
        for k in B:
            if k.startswith("JNL_quest"):
                for r in B[k]["rows"]:
                    _Q[r["id"]] = r
    return _Q


def slots(r):
    for b, br in enumerate("AB"):
        for j in range(4):
            yield 4 * b + j, r["type_succ_%s%d" % (br, j + 1)], r["cnd_succ_%s%d" % (br, j + 1)], \
                r["num_succ_%s%d" % (br, j + 1)]


def _s8(w):
    return w - 256 if w > 127 else w


def wii_done(d, t, cnd, n, w):
    w = _s8(w)
    if t == 1:
        return w >= n
    if t in (2, 3, 5, 6):
        return w >= 1
    if t == 4:
        return w >= 1 or (cnd < 0x800 and flagmap.wii_get(d, 0x220 + cnd) in (254, 255))
    return False


def wii_to_de(d, q):
    """Wii save bytes -> the 8 DE counter bytes of quest q (q < 1000)."""
    r = quests().get(q)
    raw = d[WII_QC + 8 * q:WII_QC + 8 * q + 8]
    st = flagmap.wii_get(d, 0x220 + q)
    out = bytearray(8)
    if r is None:
        return bytes(out)
    for s, t, cnd, n in slots(r):
        if not t:
            continue
        w = raw[s]
        if wii_done(d, t, cnd, n, w):
            out[s] = 0xFF
        elif t == 1:
            out[s] = max(0, _s8(w))
    if st in (254, 255):  # completed: DE's flag listener fills the winning branch
        b = 0 if st == 254 else 4
        if r["no_report"] == 0 or any(t == 3 for s, t, c, n in slots(r) if b <= s < b + 4):
            out[b:b + 4] = b"\xff" * 4
        else:
            for s, t, cnd, n in slots(r):
                if t and b <= s < b + 4:
                    out[s] = 0xFF
    return bytes(out)


def de_to_wii(de, q):
    """DE save bytes -> the 8 Wii counter bytes of quest q (q < 1000)."""
    r = quests().get(q)
    raw = de[DE_QC + 8 * q:DE_QC + 8 * q + 8]
    out = bytearray(8)
    if r is None:
        return bytes(out)
    for s, t, cnd, n in slots(r):
        if not t:
            continue
        v = raw[s]
        if v == 0xFF:
            out[s] = n if t == 1 else 1
        elif t == 1:
            out[s] = min(v, n)
    return bytes(out)
