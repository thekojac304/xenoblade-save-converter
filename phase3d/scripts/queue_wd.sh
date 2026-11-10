cd /c/Dev/XC_Wii_to_DE_Research
for s in 283 288 291; do
  python phase3d/scripts/erun3d.py dolphin wd_s${s}_save phase3d/work/w_d2w_s$s/monado01 phase3d/runs/droutes/d_load_save.dsl --timeout 300 > phase3d/logs/wd_s${s}_save.txt 2>&1
  W=phase3d/runs/dolphin/wd_s${s}_save/user/Wii/title/00010000/53583445/data/monado01
  echo "== $s"; grep -o '"save_changed": [a-z]*' phase3d/logs/wd_s${s}_save.txt | tail -1
  python phase3d/scripts/ccmp.py phase3d/work/w_d2w_s$s/monado01 $W --max 8
  python phase3a/src/xcconv3.py wii-to-de --wii $W --sidecar phase3d/work/w_d2w_s$s/de_to_wii.sidecar.json --current-de phase3d/inputs/s${s}_v10/bfsgame00.sav --out phase3d/work/r_w2d_s$s 2>&1 | tail -1
  python phase3d/scripts/ccmp.py phase3d/inputs/s${s}_v10/bfsgame00.sav phase3d/work/r_w2d_s$s/save_0/bfsgame00.sav --max 8
done
