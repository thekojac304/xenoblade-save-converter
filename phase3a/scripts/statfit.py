import sys, struct, json, math
sys.path.insert(0, r"..\tools"); sys.path.insert(0, "src")
import xc3d, wii_save as W
B = json.load(open(r"..\data\bdat_wii.json", encoding="utf-8"))
pc = {r["id"]: r for r in B["BTL_pclist"]["rows"]}
saves = {"s150": open("fixtures/wii_user_s150.bin","rb").read(), "s018": open("fixtures/wii_user_s018.bin","rb").read(),
         "x008": xc3d.transcode(xc3d.unpack(open("originals/azahar_live/00000001/monado01","rb").read()), "wii")}
pts = set()
for name, d in saves.items():
    for k in range(1, 8):
        o = W.CHAR_BASE + W.CHAR_SIZE*k
        lv = struct.unpack_from(">I", d, o+0x17C)[0]
        hp = struct.unpack_from(">f", d, o+0x18C)[0]
        st = struct.unpack_from(">3H", d, o+0x198)
        pts.add((k, lv, int(hp)) + st)
pts = sorted(pts)
for p in pts: print(p)
cands = {
 "lin": lambda x: x,
 "2x-x2": lambda x: 2*x - x*x,
 "sqrt": lambda x: math.sqrt(x),
 "sin": lambda x: math.sin(x*math.pi/2),
}
for cn, f in cands.items():
    err = []
    for k, lv, hp, s, a, e in pts:
        p = pc[k]; x = (lv - 1) / 98
        for v, lo, hi in ((hp, p["hp"], p["hp_lv99"]), (s, p["str"], p["str_lv99"]), (a, p["agi"], p["agi_lv99"]), (e, p["eth"], p["eth_lv99"])):
            pred = lo + (hi - lo) * f(x)
            err.append(abs(pred - v))
    print(cn, "mean abs err", round(sum(err)/len(err),2), "max", round(max(err),1))
print("fractions per level (hp, str, agi, eth):")
from collections import defaultdict
byL = defaultdict(list)
for k, lv, hp, s, a, e in pts:
    p = pc[k]
    fr = [(v - lo) / (hi - lo) for v, lo, hi in ((hp, p["hp"], p["hp_lv99"]), (s, p["str"], p["str_lv99"]), (a, p["agi"], p["agi_lv99"]), (e, p["eth"], p["eth_lv99"]))]
    byL[lv].append((k, [round(f, 4) for f in fr]))
for lv in sorted(byL): print(lv, byL[lv])
for k in range(1, 8): print(k, {c: pc[k][c] for c in ("hp","hp_lv99","str","str_lv99","agi","agi_lv99","eth","eth_lv99")})
