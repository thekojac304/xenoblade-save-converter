#!/bin/bash
cd /c/Dev/XC_Wii_to_DE_Research
until grep -q '"protected_unchanged"' phase3c/runs/monado/m2_3c_gen4_load_save/run_manifest.json 2>/dev/null; do sleep 10; done
sleep 5
python phase3c/scripts/erun3c.py monado c12_s160_approach phase3c/inputs/s160_manual phase3c/routes/c12_s160_approach.txt --warp 4600:11:1:-35.0:-0.544:-10.0:0 --timeout 600 > phase3c/logs/c12_s160_approach.txt 2>&1
echo "c12 exit $?"
