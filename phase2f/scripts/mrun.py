"""Phase 2F isolated Monado run: compile a route, run tools/monado_harness.run with RUNS = phase2f/runs/monado, then
re-check every protected file (phase2f/manifests). The harness kills the game if it mounts anything but the run's
own save_0 and hashes the live save_0 before/after.

  python mrun.py <name> <save dir with bfsgame00.sav [+ .tmb, bfssystem.sav]> <route script.txt> [--timeout S]
"""
import json
import os
import subprocess
import sys

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import monado_harness as mh  # noqa: E402
import route  # noqa: E402

mh.RUNS = os.path.join(P2F, "runs", "monado")


def main(name, save, script, timeout=900):
    os.makedirs(mh.RUNS, exist_ok=True)
    rdir = os.path.join(P2F, "runs", "routes")
    os.makedirs(rdir, exist_ok=True)
    rt = os.path.join(rdir, name + ".route")
    ev, shots = route.compile_script(open(script, encoding="utf-8").read().splitlines())
    with open(rt, "w", newline="\n") as fo:
        fo.write("# xcde input v1\n# compiled from %s\n" % os.path.basename(script))
        for e in ev:
            fo.write("%d %x %d %d %d %d\n" % e)
    json.dump({"shots": shots}, open(rt + ".shots.json", "w"), indent=1)
    m = mh.run(name, save, rt, [s[0] for s in shots], None, (), timeout, True)
    chk = subprocess.run([sys.executable, os.path.join(P2F, "scripts", "protect_manifest.py"), "check", f"after_{name}"],
                         capture_output=True, text=True)
    m["protected_unchanged"] = chk.returncode == 0
    m["shot_labels"] = {f"f{s[0]}.png": s[1] for s in shots}
    json.dump(m, open(os.path.join(mh.RUNS, name, "run_manifest.json"), "w"), indent=1)
    print(json.dumps({"protected_unchanged": m["protected_unchanged"], "status": m["status"]}))
    if not m["protected_unchanged"]:
        print("!!! PROTECTED FILES CHANGED !!!\n" + chk.stdout, file=sys.stderr)
        return 3
    return 0 if m["live_unchanged"] and not m["status"].startswith(("ISOLATION", "killed: no mount")) else 2


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    t = int(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 900
    sys.exit(main(*args[:3], timeout=t))
