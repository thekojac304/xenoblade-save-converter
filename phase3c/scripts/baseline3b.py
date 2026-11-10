"""Run one conversion with the FROZEN 3B engine (phase3c/baseline_3B, a copy of release_candidate_3B/source) for
comparison with the 3C engine. Separate process: the two engines share module names.

  python baseline3b.py wii_to_de <wii> <sidecar> <current_de> <out_dir>
  python baseline3b.py de_to_wii <de> <base|-> <sidecar|-> <current_wii|-> <out_dir>
  python baseline3b.py convert3 <json ThreeDSRequest kwargs>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.normpath(os.path.join(HERE, "..", "baseline_3B"))
for p in (os.path.join(B, "phase3b", "src"), os.path.join(B, "phase3a", "src"), os.path.join(B, "tools")):
    sys.path.insert(0, p)
os.environ.setdefault("XCCONV_DATA", os.path.normpath(os.path.join(HERE, "..", "..", "data")))
import xcservice as xs  # noqa: E402

a = sys.argv[1:]
if a[0] == "wii_to_de":
    r = xs.wii_to_de(xs.WiiToDeRequest(wii=a[1], out=a[4], sidecar=a[2], current_de=a[3]))
elif a[0] == "wii_to_de_first":                     # <wii> <template> <out_dir>
    r = xs.wii_to_de(xs.WiiToDeRequest(wii=a[1], out=a[3], template=a[2]))
elif a[0] == "de_to_wii":
    opt = lambda v: None if v == "-" else v  # noqa: E731
    r = xs.de_to_wii_convert(xs.DeToWiiRequest(de=a[1], out=a[5], base=opt(a[2]), sidecar=opt(a[3]),
                                               current_wii=opt(a[4]), overflow="sidecar"))
elif a[0] == "convert3":
    import xc3dservice as s3
    r = s3.convert3(s3.ThreeDSRequest(**json.loads(a[1])))
print(json.dumps({"main_output": r.main_output, "sidecar": r.sidecar_path, "engine": xs.__file__}))
