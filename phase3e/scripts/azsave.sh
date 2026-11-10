# In-game save on the 3DS (session already open, field shown): menu -> System -> Save -> slot 1 -> Yes; then finish.
# usage: bash azsave.sh <run name>
cd /c/Dev/XC_Wii_to_DE_Research
A="python phase3e/scripts/az3e.py"
$A press B 200; sleep 3
$A press X 200; sleep 4
for i in 1 2 3; do $A press RIGHT 200; sleep 2; done   # fresh session: cursor on Party; the bar wraps (7 icons)
$A shot s_menu > /dev/null
$A press A 200; sleep 3; $A press A 200; sleep 4; $A press A 200; sleep 3; $A press UP 200; sleep 2
$A shot s_confirm --bottom > /dev/null
$A press A 200; sleep 9; $A press A 200; sleep 2; $A press B 200; sleep 2; $A press B 200; sleep 2
$A finish "$1" | tail -1
