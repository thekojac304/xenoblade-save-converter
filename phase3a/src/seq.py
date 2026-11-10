"""Run a sequence of harness steps: 'A:200' press, 'w:3' wait seconds, 's:name' screenshot, 'c:x,y,ms' circle pad."""
import sys, time
import azahar_harness as h
h.wait_rpc(120)
for step in sys.argv[1:]:
    k, v = step.split(":", 1)
    if k == "w":
        time.sleep(float(v))
    elif k == "s":
        h.shot(v)
    elif k == "c":
        x, y, ms = v.split(",")
        h.press("-", int(ms), circle=(int(float(x) * 0x9A), int(float(y) * 0x9A)))
    else:
        h.press(k, int(v))
        time.sleep(0.4)
