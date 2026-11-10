#!/bin/bash
cd /c/Dev/XC_Wii_to_DE_Research
until grep -q '"protected_unchanged"' phase3c/runs/monado/c11_s160_entrance/run_manifest.json 2>/dev/null; do sleep 10; done
sleep 5
python phase3c/scripts/erun3c.py monado m2_3c_gen4_load_save phase3c/inputs/hub_gen4_3c phase3c/routes/m2_3c_gen4_load_save.txt --timeout 300 > phase3c/logs/m2_3c_gen4_load_save.txt 2>&1
echo "m2 exit $?"
