"""Static checks of the stored-gear translation on genuine DE saves: DE -> Wii (user's story-150 base) and DE -> 3DS
(user's story-8 template): stored gear read back from the Wii layout equals the DE's; then Wii -> DE first-time (DE
template) and with the sidecar: equal again; unchanged returns byte-identical.  python sg_roundtrip.py [files]"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "phase3a", "src")]
import canon  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402

W150 = os.path.join(ROOT, "phase3a", "fixtures", "wii_user_s150.bin")
X3 = os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado01")
TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
WORK = os.path.join(ROOT, "phase3e", "work", "sg_rt")


def sg_of(p):
    b = open(p, "rb").read()
    if b[:4] == b"!qzb":
        b = xc3d.transcode(xc3d.unpack(b), "wii")
    c = canon.from_wii(b, T) if b[:4] == b"USRD" else canon.from_de(b, T)
    return canon.jsonable(c["shared"].get("stored_gear")), c


T = xs.tables()
files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "phase3c", "fixtures", "de_s15*.sav")) +
                               glob.glob(os.path.join(ROOT, "phase3d", "fixtures", "de_s2*.sav")))
import shutil  # noqa: E402
if os.path.isdir(WORK):
    shutil.rmtree(WORK)
for p in files:
    n = os.path.basename(p)[:30]
    src, cs = sg_of(p)
    d = os.path.join(WORK, n)
    try:
        w = xs.de_to_wii_convert(xs.DeToWiiRequest(de=p, out=os.path.join(d, "w"), base=W150, overflow="sidecar"))
        ws, _ = sg_of(w.main_output)
        back = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "b"), sidecar=w.sidecar_path,
                                              current_de=p))
        same_back = open(back.main_output, "rb").read() == open(p, "rb").read()
        f = xs.wii_to_de(xs.WiiToDeRequest(wii=w.main_output, out=os.path.join(d, "f"), template=TPL))
        fs, _ = sg_of(f.main_output)
        x = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=p, out=os.path.join(d, "x"), template=X3,
                                          overflow="sidecar"))
        xs3, _ = sg_of(x.main_output)
        xb = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=x.main_output, out=os.path.join(d, "xb"),
                                           record=x.sidecar_path, current=p))
        print(n, cs["shared"]["story"], "wii==de", ws == src, "| unchanged return identical", same_back,
              "| wii->de first-time==de", fs == src, "| 3ds==de", xs3 == src,
              "| 3ds return identical", open(xb.main_output, "rb").read() == open(p, "rb").read(),
              "| written", w.report.get("stored_gear_written") if isinstance(w.report, dict) else "")
    except Exception as e:
        print(n, "ERROR", type(e).__name__, str(e)[:300])
