#!/bin/bash
# sequential emulator queue (one emulator at a time), started after c2 finished
cd /c/Dev/XC_Wii_to_DE_Research
until grep -q '"protected_unchanged"' phase3c/runs/monado/c2_s158_warp/run_manifest.json 2>/dev/null; do sleep 15; done
sleep 5
python phase3c/scripts/erun3c.py monado c3_s158_scan phase3c/inputs/s158 phase3c/routes/c3_scan.txt --warp 4600:11:1:113.265:154.622:446.407:0 --env XCDE_ENT_SCAN=5400 --env XCDE_PARTY_PROBE=5400 --timeout 400 > phase3c/logs/c3_s158_scan.txt 2>&1
echo "c3 exit $?"
python phase3c/scripts/erun3c.py dolphin d1_s154_story phase3c/work/cw_d2w_s154/monado01 phase3c/routes/d1_s154_story.dsl --timeout 600 > phase3c/logs/d1_s154_story.txt 2>&1
echo "d1 exit $?"
python phase3c/scripts/erun3c.py dolphin dD_w150_travel phase3a/fixtures/wii_user_s150.bin phase3c/routes/d_w150_travel.txt --timeout 600 > phase3c/logs/dD_w150_travel.txt 2>&1
echo "dD exit $?"
