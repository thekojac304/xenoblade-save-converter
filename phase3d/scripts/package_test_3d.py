"""Phase 3D clean-directory checks of the packaged application (in addition to the 3B and 3A package tests, which are
run against the same build): the packaged xcconv.exe gives the 3D engine results, without Python.

  python phase3d\\scripts\\package_test_3d.py <portable folder> <clean test root> <result json>

  * version stamp 3D-rc1 in xcconv.exe output and in its records;
  * character 8 (story 291, Fiora's later form, full party): DE -> 3DS -> DE unplayed = byte-identical; the 3DS game's
    own save of it (Azahar x5) returns to DE with the party and every item;
  * D2: a DE save from the story split (288) is refused with the names, nothing written;
  * B2: unplayed DE s232 -> 3DS -> DE return (compaction + overflow) is byte-identical (3B: refused);
  * B3: DE s232 -> 3DS -> the 3DS game's own save (Azahar a5) + synthetic flags -> DE keeps all 176 DE-only crystal
    entries and every DE record's bytes (3B: 90); output identical to the same steps from source;
  * the window starts and reports 3D-rc1.
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P3D = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3D)
P3C = os.path.join(ROOT, "phase3c")
FX = os.path.join(P3D, "fixtures")
sys.path.insert(0, os.path.join(P3C, "tests"))
sys.path.insert(0, os.path.join(ROOT, "phase3b", "scripts"))
import package_test_3b as P  # noqa: E402  (clean_env, tree, sha)
import p3cfix as F  # noqa: E402
from p3cfix import H, T, rd  # noqa: E402
import canon  # noqa: E402
import xc3dservice as s3  # noqa: E402


def main(portable, root, result_path):
    t0 = time.time()
    portable, root, result_path = (os.path.abspath(p) for p in (portable, root, result_path))
    if os.path.exists(root):
        shutil.rmtree(root)
    app = os.path.join(root, "app", "XCSaveConverter")
    shutil.copytree(portable, app)
    inp = os.path.join(root, "inputs")
    os.makedirs(os.path.join(inp, "x3"))
    shutil.copyfile(H.DE_S232, os.path.join(inp, "s232.sav"))
    for n in ("monado01", "monado02", "monado03"):
        shutil.copyfile(os.path.join(os.path.dirname(H.X3_USER), n), os.path.join(inp, "x3", n))
    os.makedirs(os.path.join(inp, "a5"))
    with open(os.path.join(inp, "a5", "monado01"), "wb") as f:
        f.write(H.x3_a5_played())
    for n in ("de_s288_v10_monado.sav", "de_s291_v10_monado.sav", "x3_s291_azahar_x5_game_save",
              "x3_s291_export_3d.de_to_3ds.record.json"):
        shutil.copyfile(os.path.join(FX, n), os.path.join(inp, n))
    inputs_before = P.tree(inp)
    data = os.path.join(root, "mydata")
    os.makedirs(data)
    for n in ("bdat_wii.json", "bdat_de.json"):
        shutil.copyfile(os.path.join(ROOT, "data", n), os.path.join(data, n))
    app_before = P.tree(app)
    exe = os.path.join(app, "xcconv.exe")
    res = {"portable": portable, "clean_root": root, "checks": []}

    def check(name, ok, **detail):
        res["checks"].append({"name": name, "ok": bool(ok), **detail})
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    def run(*args):
        return subprocess.run([exe, *args], cwd=root, env=P.clean_env(data), capture_output=True, text=True,
                              timeout=900)

    s232, x3t = os.path.join(inp, "s232.sav"), os.path.join(inp, "x3", "monado01")
    o1 = os.path.join(root, "o1")
    r1 = run("de-to-3ds", "--de", s232, "--template", x3t, "--out", o1, "--overflow", "sidecar")
    check("xcconv.exe de-to-3ds (s232, overflow kept in the record)", r1.returncode == 0, out=r1.stdout[-400:],
          err=r1.stderr[-400:])
    check("version stamp 3D-rc1 (console and record)", "3D-rc1" in r1.stdout and
          json.load(open(os.path.join(o1, "de_to_3ds.record.json")))["converter_version"] == "3D-rc1")
    rec = os.path.join(o1, "de_to_3ds.record.json")
    o2 = os.path.join(root, "o2")
    r2 = run("3ds-to-de", "--3ds", os.path.join(o1, "3ds", "monado01"), "--record", rec, "--current-de", s232,
             "--out", o2)
    out2 = os.path.join(o2, "save_0", "bfsgame00.sav")
    check("B2: unplayed DE -> 3DS -> DE return is byte-identical (3B refused it)",
          r2.returncode == 0 and os.path.exists(out2) and rd(out2) == rd(s232), err=r2.stderr[-400:])
    o3 = os.path.join(root, "o3")
    r3 = run("3ds-to-de", "--3ds", os.path.join(inp, "a5", "monado01"), "--record", rec, "--current-de", s232,
             "--out", o3)
    out3 = os.path.join(o3, "save_0", "bfsgame00.sav")
    ok3 = r3.returncode == 0 and os.path.exists(out3)
    n_cr = len(canon.from_de(rd(out3), T)["de_only"]["items"].get("crystal", {})) if ok3 else None
    diffs = sum(F.de_only_bytes_equal(rd(s232), rd(out3), b)[1] for b in F.DBOX) if ok3 else None
    check("B3: 3DS game save -> DE keeps every DE-only item record (176 crystal entries, 0 records differ)",
          ok3 and n_cr == 176 and diffs == 0, crystal_entries=n_cr, records_differing=diffs, err=r3.stderr[-400:])
    src = os.path.join(root, "src_run")
    s1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=s232, out=os.path.join(src, "a"), template=x3t,
                                       overflow="sidecar"))
    s2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=os.path.join(inp, "a5", "monado01"),
                                       out=os.path.join(src, "b"), record=s1.sidecar_path, current=s232))
    check("packaged output identical to the source engine (3DS export and DE return)",
          ok3 and rd(s1.main_output) == rd(os.path.join(o1, "3ds", "monado01")) and rd(s2.main_output) == rd(out3))
    # Phase 3D: character 8 and D2
    s291 = os.path.join(inp, "de_s291_v10_monado.sav")
    o4 = os.path.join(root, "o4")
    r4 = run("de-to-3ds", "--de", s291, "--template", x3t, "--out", o4, "--overflow", "sidecar")
    o5 = os.path.join(root, "o5")
    r5 = run("3ds-to-de", "--3ds", os.path.join(o4, "3ds", "monado01"), "--record",
             os.path.join(o4, "de_to_3ds.record.json"), "--current-de", s291, "--out", o5)
    out5 = os.path.join(o5, "save_0", "bfsgame00.sav")
    check("character 8 (story 291): DE -> 3DS -> DE unplayed is byte-identical",
          r4.returncode == 0 and r5.returncode == 0 and os.path.exists(out5) and rd(out5) == rd(s291),
          err=(r4.stderr + r5.stderr)[-400:])
    o6 = os.path.join(root, "o6")
    r6 = run("3ds-to-de", "--3ds", os.path.join(inp, "x3_s291_azahar_x5_game_save"), "--record",
             os.path.join(inp, "x3_s291_export_3d.de_to_3ds.record.json"), "--current-de", s291, "--out", o6)
    out6 = os.path.join(o6, "save_0", "bfsgame00.sav")
    ok6 = r6.returncode == 0 and os.path.exists(out6)
    a, b = (canon.from_de(rd(p), T)["shared"] for p in (s291, out6)) if ok6 else ({}, {})
    check("3DS game's save with character 8 returns to DE (party, items)",
          ok6 and a["party"] == b["party"] == [8, 6, 5, 7, 2, 1, 4] and
          {x: sorted(map(str, map(canon.strip_order, v.values()))) for x, v in a["inventory"].items()} ==
          {x: sorted(map(str, map(canon.strip_order, v.values()))) for x, v in b["inventory"].items()},
          err=r6.stderr[-400:])
    o7 = os.path.join(root, "o7")
    r7 = run("de-to-3ds", "--de", os.path.join(inp, "de_s288_v10_monado.sav"), "--template", x3t, "--out", o7,
             "--overflow", "sidecar")
    check("D2: story-split DE save (288) refused with the names, nothing written",
          r7.returncode == 2 and "Shulk, Reyn, Sharla left the party" in (r7.stdout + r7.stderr) and
          not os.path.exists(o7), out=(r7.stdout + r7.stderr)[-400:])
    smoke = os.path.join(root, "smoke.json")
    r = subprocess.run([os.path.join(app, "XCSaveConverter.exe"), "--smoke", smoke], cwd=root, env=P.clean_env(),
                       capture_output=True, text=True, timeout=300)
    si = json.load(open(smoke)) if os.path.exists(smoke) else {}
    pv = subprocess.run(["powershell", "-NoProfile", "-Command",
                         f"(Get-Item '{os.path.join(app, 'XCSaveConverter.exe')}').VersionInfo.ProductVersion"],
                        capture_output=True, text=True).stdout.strip()
    check("window starts without Python (frozen); program version 3D-rc1",
          r.returncode == 0 and si.get("frozen") and si.get("visible") and pv == "3D-rc1", smoke=si, version=pv)
    check("inputs unchanged", P.tree(inp) == inputs_before)
    check("portable folder unchanged by running it", P.tree(app) == app_before)
    res["passed"] = sum(c["ok"] for c in res["checks"])
    res["total"] = len(res["checks"])
    res["seconds"] = round(time.time() - t0)
    json.dump(res, open(result_path, "w"), indent=1)
    print(f"{res['passed']}/{res['total']} passed in {res['seconds']} s")
    return 0 if res["passed"] == res["total"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
