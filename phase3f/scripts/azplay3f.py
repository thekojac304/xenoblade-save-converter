"""Azahar story helper (Phase 3F (3 RIGHT to System, azsave.sh rule)): setup a run with a 3DS save in slot 1, load it from the title menu, press A for N
seconds (dialogue / scenes), optional B presses, then System -> Save -> slot 1 -> Yes, and finish (protected check).
  python azplay.py <name> <3ds save> <a_seconds> [--no-save] [--shots N]"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AZ = [sys.executable, os.path.join(HERE, "az3f.py")]


def az(*a):
    r = subprocess.run(AZ + [str(x) for x in a], capture_output=True, text=True)
    return r.stdout.strip()


def press(k, wait, ms=200):
    az("press", k, ms)
    time.sleep(wait)


def main():
    name, save, a_s = sys.argv[1], sys.argv[2], int(sys.argv[3])
    shots = int(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else 6
    az("setup", name, "--slot", f"1={save}")
    time.sleep(25)
    for k, w in (("A", 4), ("A", 4), ("A", 3), ("UP", 1), ("A", 30), ("A", 35)):
        press(k, w, 150)
    az("shot", "t1_field")
    if "--walk" in sys.argv:
        az("stick", "0", "1", sys.argv[sys.argv.index("--walk") + 1])
        time.sleep(1)
    t0, n = time.time(), 0
    every = max(a_s // shots, 1)
    while time.time() - t0 < a_s:
        press("A", 1.3)
        if time.time() - t0 > (n + 1) * every:
            n += 1
            az("shot", f"t2_scene_{n:02d}")
    for _ in range(4):
        press("B", 1.5)
    time.sleep(10)
    az("shot", "t3_field")
    az("shot", "t3_field", "--bottom")
    if "--no-save" not in sys.argv:
        time.sleep(15)
        for attempt in range(1):
            press("B", 3)
            press("X", 5)
            az("shot", f"t4_menuopen_{attempt}")
            for _ in range(3):
                press("RIGHT", 2.5, 250)
            az("shot", f"t4_menu_{attempt}")
            press("A", 3)          # System
            press("A", 4)          # Save
            press("A", 3)          # slot 1
            press("UP", 2)
            az("shot", f"t5_confirm_{attempt}", "--bottom")
            press("A", 8)          # Yes
            az("shot", f"t6_saved_{attempt}", "--bottom")
            press("A", 3)
            press("B", 2)
            press("B", 2)
    if "--keep" not in sys.argv:
        print(az("finish", name))


if __name__ == "__main__":
    main()
