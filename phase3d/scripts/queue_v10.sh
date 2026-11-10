#!/bin/bash
cd /c/Dev/XC_Wii_to_DE_Research
for s in 269 276 283 288 291; do
  python phase3d/scripts/erun3d.py monado g_s${s}_v7load phase3d/inputs/s${s}_v7 phase3d/scripts/route_load_save.txt --timeout 300 > phase3d/logs/g_s${s}_v7load.txt 2>&1
  echo "s$s exit $?"
done
