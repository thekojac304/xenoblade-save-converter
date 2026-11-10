"""Phase 3C wrapper of the 3A Azahar harness (phase3a/src/azahar_harness.py): identical isolation (private portable
copy, RPC input, 149 live Azahar/Citra files hashed before/after), run folders under phase3c/runs/azahar, and the
3C protected-file manifest (protect3c.py) checked by `finish`.

  python az3b.py setup <name> --slot 1=<3ds save> | press <btns|-> <ms> | stick <x> <y> <ms> | shot <label> [--bottom]
  python az3b.py finish <name>
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P3C = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3C)
sys.path.insert(0, os.path.join(ROOT, "phase3a", "src"))
import azahar_harness as ah  # noqa: E402

ah.RUNS = os.path.join(P3C, "runs", "azahar")
ah.STATE = os.path.join(ah.RUNS, "_current.json")
os.makedirs(ah.RUNS, exist_ok=True)

if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == "setup":
        slots = {int(s.split("=", 1)[0]): s.split("=", 1)[1] for s in a[a.index("--slot") + 1::2] if "=" in s}
        ah.setup(a[1], slots)
    elif cmd == "press":
        ah.press(a[1], int(a[2]))
    elif cmd == "stick":
        ah.press("-", int(a[3]), circle=(int(float(a[1]) * 0x9A), int(float(a[2]) * 0x9A)))
    elif cmd == "shot":
        ah.shot(a[1], "--bottom" in a)
    elif cmd == "finish":
        ah.finish(a[1])
        r = subprocess.run([sys.executable, os.path.join(HERE, "protect3c.py"), "check", f"after_{a[1]}"],
                           capture_output=True, text=True)
        print("3C protected manifest unchanged:", r.returncode == 0)
        if r.returncode:
            print(r.stdout[-3000:])
            sys.exit(3)
