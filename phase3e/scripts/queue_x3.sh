cd /c/Dev/XC_Wii_to_DE_Research
prev=phase3e/runs/azahar/x2_s156_audience/save_after/00000001/monado01
for step in "x3b_riki 114.03 154.622 473.59 33 40 -" "x4b_sharla 116.18 154.622 475.61 34 40 -" "x5b_reyn 127.72 154.622 472.28 55 40 500" "x6_dunban 113.265 154.622 446.407 180 300 -"; do
  set -- $step
  python phase3e/scripts/wpos.py $prev phase3e/inputs/$1/monado01 $2 $3 $4 $5 >/dev/null
  W=""; [ "$7" != "-" ] && W="--walk $7"
  python phase3e/scripts/azplay.py $1 phase3e/inputs/$1/monado01 $6 --shots 2 --no-save --keep $W > phase3e/logs/$1.txt 2>&1
  [ "$1" = "x6_dunban" ] && sleep 20
  bash phase3e/scripts/azsave.sh $1 >> phase3e/logs/$1.txt 2>&1
  out=phase3e/runs/azahar/$1/save_after/00000001/monado01
  echo "== $1 $(tail -1 phase3e/logs/$1.txt)"
  python phase3e/scripts/ccmp.py phase3e/inputs/$1/monado01 $out --max 30 | grep "flags\|story"
  prev=$out
done
