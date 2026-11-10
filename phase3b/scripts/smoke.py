import os, sys, shutil, time, json
HERE = os.path.dirname(os.path.abspath(__file__)); P3B = os.path.dirname(HERE); ROOT = os.path.dirname(P3B)
sys.path.insert(0, os.path.join(P3B, "src"))
from xcsync import store, scan, sync
W = os.path.join(P3B, "work", "smoke")
if os.path.exists(W): shutil.rmtree(W)
FIX = os.path.join(ROOT, "phase3a", "fixtures")
def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst); t=time.time()-60; os.utime(dst,(t,t))
h = store.Hub.create(os.path.join(W, "hub"))
d_pc = h.add_device("Windows desktop", "de"); d_odin = h.add_device("Odin 2 Mini", "wii"); d_3ds = h.add_device("New 3DS", "3ds")
t0=time.time(); h.add_template("de", os.path.join(ROOT,"work","template","bfsgame00.sav"))
h.add_template("3ds", os.path.join(ROOT,"phase3a","originals","azahar_live","00000001","monado01")); print("templates", round(time.time()-t0,1))
cp(os.path.join(FIX,"wii_user_s150.bin"), os.path.join(d_odin["incoming"],"monado01"))
t0=time.time(); r = scan.scan(h, delay=0.05); print("scan", round(time.time()-t0,1), r.decision)
for ds in r.devices: print(" ", ds.device["name"], ds.status, ds.text, [(o.name,o.state,o.status,o.detail) for o in ds.saves])
t0=time.time(); res = sync.sync(h, r, delay=0.05); print("sync", round(time.time()-t0,1), res)
r = scan.scan(h, delay=0.05); print(r.decision); [print(" ", ds.device["name"], ds.status, ds.ready_state) for ds in r.devices]
# --- cycle 2: the 3DS game re-saved the converted s150 save (3A run a1) -> new progress on the 3DS
A1 = os.path.join(ROOT,"phase3a","runs","azahar","a2_s150_gameplay","save_after","00000001","monado02")
cp(A1, os.path.join(d_3ds["incoming"],"monado01"))
r = scan.scan(h, delay=0.05); print("scan2", r.decision.kind, r.decision.message)
for ds in r.devices: print(" ", ds.device["name"], ds.status, [(o.name,o.status,o.detail) for o in ds.saves])
if r.decision.source:
    res = sync.sync(h, r, delay=0.05); print("sync2", res.generation, res.message, res.notes)
    g = h.load_generation(res.generation); print(json.dumps(g["conversions"]), [v["check"] for v in g["validation"]])
# --- cycle 3: Wii played on from s150 (old copy!) while the 3DS progressed -> divergent / conflict expected
LATER = os.path.join(ROOT,"work","phase2e","dolphin","d6_travel","user","Wii","title","00010000","53583445","data","monado01")
cp(LATER, os.path.join(d_odin["incoming"],"monado02"))
r = scan.scan(h, delay=0.05); print("scan3", r.decision.kind, r.decision.message)
for ds in r.devices: print(" ", ds.device["name"], ds.status, [(o.name,o.status,o.detail) for o in ds.saves])
