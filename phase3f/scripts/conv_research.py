"""RESEARCH-ONLY conversions for the Phase 3F reunion runs: the research engine with Fiora's later form (8) allowed in
the stored-gear policy for this process only (stored_gear.VALIDATED | {8}); nothing else differs from the engine.
   python conv_research.py de_to_wii|de_to_3ds|wii_to_de|3ds_to_de|wii_to_3ds|3ds_to_wii <src> <out dir> [--sidecar S] [--current C] [--template T]"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "phase3a", "src")]
import stored_gear as sg  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402

sg.VALIDATED = sg.VALIDATED | {8}
W150 = os.path.join(ROOT, "phase3a", "fixtures", "wii_user_s150.bin")
X3 = os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado01")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--sidecar")
ap.add_argument("--current")
ap.add_argument("--template")
a = ap.parse_args()
if a.dir == "de_to_wii":
    r = xs.de_to_wii_convert(xs.DeToWiiRequest(de=a.src, out=a.out, base=a.template or W150, overflow="sidecar"))
elif a.dir == "wii_to_de":
    kw = dict(sidecar=a.sidecar, current_de=a.current) if a.sidecar else dict(template=a.template or TPL)
    r = xs.wii_to_de(xs.WiiToDeRequest(wii=a.src, out=a.out, **kw))
else:
    kw = {"template": a.template or (X3 if a.dir.endswith("3ds") else TPL)} if a.dir in ("de_to_3ds", "wii_to_3ds") \
        else {}
    if a.dir == "3ds_to_de":
        kw = dict(record=a.sidecar, current=a.current) if a.sidecar else {"template": a.template or TPL}
    if a.dir == "de_to_3ds":
        kw["overflow"] = "sidecar"
    r = s3.convert3(s3.ThreeDSRequest(a.dir, source=a.src, out=a.out, **kw))
print("main:", r.main_output)
print("side:", getattr(r, "sidecar_path", None) or getattr(r, "record_path", None))
