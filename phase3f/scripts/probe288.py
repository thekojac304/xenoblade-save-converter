"""Probe: with Fiora-8 allowed (in-process only), does DE 288 translate exactly in every direction?"""
import os, sys, shutil, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3e", "tests"))
os.chdir(os.path.join(ROOT, "phase3e", "tests"))
import test_phase3e_stored_gear as t  # noqa
import stored_gear as sg
sg.VALIDATED = sg.VALIDATED | {8}
xs, s3, H, rd = t.xs, t.s3, t.H, t.rd
p = os.path.join(t.F3D, "de_s288_v10_monado.sav")
src = t.stored(p)
print("stored chars", sorted(src), "fiora gems", len(src["8"]["gems"]))
d = os.path.join(ROOT, "phase3f", "work", "probe288")
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
w = xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=os.path.join(d, "w"), base=H.W150, overflow="sidecar"))
print("wii eq", t.stored(w.main_output) == src)
b = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "b"), sidecar=w.sidecar_path, current_de=p))
print("return byte-identical", rd(b.main_output) == rd(p))
f = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "f"), template=H.DE_TPL))
print("first-time eq", t.stored(f.main_output) == src)
x = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=p, out=os.path.join(d, "x"), template=H.X3_USER, overflow="sidecar"))
print("3ds eq", t.stored(x.main_output) == src)
x2 = s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=x.main_output, out=os.path.join(d, "x2")))
print("3ds->wii eq", t.stored(x2.main_output) == src)
print(json.dumps(src["8"], indent=None)[:1500])
