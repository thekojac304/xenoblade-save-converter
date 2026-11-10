"""Byte parity of conversions: 3C engine (release_candidate_3C/source) vs 3D engine (research tree), same inputs.
  python parity_3c.py            -> phase3d/work/parity_3c.json
Each engine runs in its own process (its own sys.path); outputs go to phase3d/work/parity/<engine>/<case>."""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
WORK = os.path.join(ROOT, "phase3d", "work", "parity")
F2 = os.path.join(ROOT, "phase2f", "fixtures", "real")
W150 = os.path.join(ROOT, "phase3a", "fixtures", "wii_user_s150.bin")
W018 = os.path.join(ROOT, "phase3a", "fixtures", "wii_user_s018.bin")
X3 = os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado01")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
CASES = [("de_to_wii", f"s{s}", os.path.join(F2, f"s{s}_v10_monado.sav"), W150) for s in ("020", "206", "232", "241", "258", "269")] + \
        [("de_to_3ds", f"s{s}", os.path.join(F2, f"s{s}_v10_monado.sav"), X3) for s in ("020", "232", "258")] + \
        [("wii_to_de", "w150", W150, TPL), ("wii_to_de", "w018", W018, TPL), ("wii_to_3ds", "w150", W150, X3)]

CHILD = r'''
import json, os, sys
src, work, cases = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
sys.path[:0] = [os.path.join(src, "tools"), os.path.join(src, "phase3a", "src")]
os.environ.setdefault("XCCONV_DATA", os.path.join(r"%s", "data"))
import xcservice as xs, xc3dservice as s3
res = {}
for d, name, a, b in cases:
    out = os.path.join(work, d + "_" + name)
    try:
        if d == "de_to_wii":
            r = xs.de_to_wii_convert(xs.DeToWiiRequest(de=a, out=out, base=b, overflow="sidecar"))
        elif d == "wii_to_de":
            r = xs.wii_to_de(xs.WiiToDeRequest(wii=a, out=out, template=b))
        else:
            r = s3.convert3(s3.ThreeDSRequest(d, source=a, out=out, template=b, overflow="sidecar"))
        res[d + "_" + name] = {"ok": True, "main": open(r.main_output, "rb").read().hex()}
    except Exception as e:
        res[d + "_" + name] = {"ok": False, "error": type(e).__name__ + ": " + str(e)[:200]}
print(json.dumps(res))
''' % ROOT


def run(src, tag):
    import shutil
    w = os.path.join(WORK, tag)
    if os.path.isdir(w):
        shutil.rmtree(w)
    os.makedirs(w)
    r = subprocess.run([sys.executable, "-c", CHILD, src, w, json.dumps(CASES)], capture_output=True, text=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    a = run(os.path.join(ROOT, "release_candidate_3C", "source"), "3c")
    b = run(ROOT, "3d")
    out = {}
    for k in a:
        x, y = a[k], b[k]
        if x["ok"] and y["ok"]:
            bx, by = bytes.fromhex(x["main"]), bytes.fromhex(y["main"])
            nd = sum(1 for i in range(min(len(bx), len(by))) if bx[i] != by[i]) + abs(len(bx) - len(by))
            out[k] = {"3c": "ok", "3d": "ok", "identical": bx == by, "bytes_differing": nd,
                      "sha_3c": hashlib.sha256(bx).hexdigest()[:16], "sha_3d": hashlib.sha256(by).hexdigest()[:16]}
        else:
            out[k] = {"3c": "ok" if x["ok"] else x["error"], "3d": "ok" if y["ok"] else y["error"]}
    json.dump(out, open(os.path.join(ROOT, "phase3d", "work", "parity_3c.json"), "w"), indent=1)
    for k, v in out.items():
        print(k, {kk: (vv[:90] if isinstance(vv, str) else vv) for kk, vv in v.items() if not kk.startswith("sha")})
