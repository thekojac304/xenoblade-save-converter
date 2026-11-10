#!/bin/bash
cd /c/Dev/XC_Wii_to_DE_Research
until grep -q '"protected_unchanged"' phase3c/runs/dolphin/dD_w150_travel/run_manifest.json 2>/dev/null; do sleep 15; done
sleep 5
python phase3c/scripts/erun3c.py monado c4_s158_talk phase3c/inputs/s158 phase3c/routes/c4_s158_talk.txt --warp 4600:11:1:113.265:154.622:446.407:180 --env XCDE_ENT_SCAN=4700,5000,5400,6000,9000,15000,21000 --timeout 700 > phase3c/logs/c4_s158_talk.txt 2>&1
echo "c4 exit $?"
python phase3c/scripts/erun3c.py monado l1_s232_valak phase3c/inputs/l1_s232 phase3c/routes/l1_s232.txt --warp 4600:13:1:-1939.0:-1233.4:-843.0:0 --timeout 700 > phase3c/logs/l1_s232_valak.txt 2>&1
echo "l1 exit $?"
