#!/bin/bash
cd /c/Dev/XC_Wii_to_DE_Research
until grep -q '"protected_unchanged"' phase3c/runs/monado/c5_de156_from_wii/run_manifest.json 2>/dev/null; do sleep 15; done
sleep 5
python phase3c/scripts/erun3c.py monado c6_s158_reyn phase3c/inputs/s158 phase3c/routes/c6_reyn.txt --timeout 400 > phase3c/logs/c6_s158_reyn.txt 2>&1
echo "c6 exit $?"
