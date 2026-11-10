"""Drive the 3A GUI (offscreen) through every direction with --automate jobs; print outcomes."""
import json, os, subprocess, sys, shutil
P3 = r"C:\Dev\XC_Wii_to_DE_Research\phase3a"
ROOT = os.path.dirname(P3)
W = os.path.join(P3, "work", "gui_auto")
X3 = os.path.join(P3, "originals", "azahar_live", "00000001", "monado01")
X3G = os.path.join(P3, "runs", "azahar", "a2_s150_gameplay", "save_after", "00000001", "monado02")
W150 = os.path.join(P3, "fixtures", "wii_user_s150.bin")
DE = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
jobs = {
 "j1_wii_to_3ds": {"source": W150, "dest": X3},
 "j2_3ds_to_wii_nodest": {"source": X3G, "target": "wii"},
 "j3_3ds_to_de": {"source": X3, "dest": DE},
 "j4_de_to_3ds": {"source": DE, "dest": X3},
 "j5_wii_to_de_2h": {"source": W150, "dest": DE},
}
sel = sys.argv[1:] or list(jobs)
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
for name in sel:
    j = dict(jobs[name])
    d = os.path.join(W, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    j.update(output_parent=os.path.join(d, "out"), result=os.path.join(d, "result.json"), settings=os.path.join(d, "s.ini"),
             data_dir=os.path.join(ROOT, "data"))
    jp = os.path.join(d, "job.json")
    json.dump(j, open(jp, "w"), indent=1)
    r = subprocess.run([sys.executable, os.path.join(P3, "gui", "xcconv_gui.py"), "--automate", jp], env=env,
                       capture_output=True, text=True, timeout=900)
    res = json.load(open(j["result"])) if os.path.exists(j["result"]) else {"stderr": r.stderr[-2000:]}
    print(name, "rc", r.returncode, {k: res.get(k) for k in ("ok", "direction", "plan", "missing", "page", "result_title", "result_detail", "main_output", "exception")})
