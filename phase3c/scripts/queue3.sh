#!/bin/bash
cd /c/Dev/XC_Wii_to_DE_Research
until grep -q '"protected_unchanged"' phase3c/runs/monado/l1_s232_valak/run_manifest.json 2>/dev/null; do sleep 15; done
sleep 5
python phase3c/scripts/erun3c.py dolphin d2_s156_reload phase3c/inputs/c1_wii156/monado01 phase3c/routes/d2_s156_reload.dsl --timeout 400 > phase3c/logs/d2_s156_reload.txt 2>&1
echo "d2 exit $?"
python phase3c/scripts/erun3c.py monado c5_de156_from_wii phase3c/inputs/c1_de156 phase3c/routes/c1_s156.txt --warp 4600:11:1:629.652:715.068:0.005:0 --timeout 900 > phase3c/logs/c5_de156_from_wii.txt 2>&1
echo "c5 exit $?"
