import sys, hashlib
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\phase3a\src")
import xc3d
f3 = open(r"C:\Dev\XC_Wii_to_DE_Research\phase3a\originals\azahar_live\00000001\monado01","rb").read()
raw = xc3d.unpack(f3)
print("container", xc3d.check_container(raw), "pads not E3:", [(hex(a),hex(b)) for a,b in xc3d.pad_report(raw)])
w = xc3d.transcode(raw, "wii")
back = xc3d.transcode(w, "3ds", template=raw)
diff = [i for i in range(len(raw)) if raw[i] != back[i]]
print("3DS->Wii->3DS diffs:", len(diff), [hex(x) for x in diff[:20]])
print("repacked identical file:", xc3d.pack(back) == f3)
for p in ["fixtures/wii_d7_s006.bin", "fixtures/wii_user_s018.bin", "fixtures/wii_user_s150.bin"]:
    wd = open(r"C:\Dev\XC_Wii_to_DE_Research\phase3a\\" + p, "rb").read()
    t = xc3d.transcode(wd, "3ds", template=raw)
    wb = xc3d.transcode(t, "wii")
    diff = [i for i in range(len(wd)) if wd[i] != wb[i]]
    print(p, "Wii->3DS->Wii diffs:", len(diff), [hex(x) for x in diff[:10]], "3ds container", xc3d.check_container(t))
