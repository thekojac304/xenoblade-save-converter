"""Phase 2F protected-input manifest: SHA-256 of every original / live save, game executable, disc image and the
Phase 2E release candidate. Read-only.

  python protect_manifest.py start            -> phase2f/manifests/protected_start.json
  python protect_manifest.py check [name]     -> compares against protected_start.json, writes protected_<name>.json
Exit code 1 if anything changed or went missing.
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P2F = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.normpath(os.path.join(P2F, ".."))
MAN = os.path.join(P2F, "manifests")

DIRS = {  # label -> folder (every file inside, recursively)
    "wii_filen_data": r"C:\Filen\Video Game Stuff\Game Saves & Memory Cards\Wii\title\00010000\53583445\data",
    "wii_proton_nand_data": r"C:\Users\lawma\Proton Drive\lawmat304\My files\Video Game Stuff\Game Saves & Memory "
                            r"Cards\Wii\title\00010000\53583445\data",
    "dolphin_portable_data": r"E:\Launchbox\Emulators\Dolphin\User\Wii\title\00010000\53583445\data",
    "monado_live_save_0": r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save\save_0",
    "research_originals": os.path.join(ROOT, "work", "originals"),
    "research_template": os.path.join(ROOT, "work", "template"),
    "release_candidate_2E": os.path.join(ROOT, "release_candidate"),
}
FILES = {
    "monado_exe": r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\build\xcde.exe",
    "monado_ini": r"C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\xcde.ini",
    "dolphin_exe": r"E:\Launchbox\Emulators\Dolphin\Dolphin.exe",
    "wii_disc_image": r"E:\Launchbox\Games\ROMs\Wii\Xenoblade Chronicles [NTSC-U].rvz",
}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def entry(p):
    st = os.stat(p)
    return {"path": p, "sha256": sha_file(p), "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))}


def collect():
    out = {}
    for label, d in DIRS.items():
        if not os.path.isdir(d):
            out[label + "/<missing>"] = {"path": d, "missing": True}
            continue
        for dp, _, fs in os.walk(d):
            for f in sorted(fs):
                p = os.path.join(dp, f)
                out[label + "/" + os.path.relpath(p, d).replace("\\", "/")] = entry(p)
    for label, p in FILES.items():
        out[label] = entry(p) if os.path.isfile(p) else {"path": p, "missing": True}
    return out


def main(argv):
    os.makedirs(MAN, exist_ok=True)
    mode = argv[1] if len(argv) > 1 else "check"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    cur = collect()
    if mode == "start":
        path = os.path.join(MAN, "protected_start.json")
        if os.path.exists(path):
            raise SystemExit(f"{path} exists; refusing to replace the start manifest")
        json.dump({"taken_at": now, "files": cur}, open(path, "w"), indent=1)
        print(f"{len(cur)} protected files recorded -> {path}")
        return 0
    start = json.load(open(os.path.join(MAN, "protected_start.json")))["files"]
    changed = [k for k in start if start[k].get("sha256") != cur.get(k, {}).get("sha256")]
    added = [k for k in cur if k not in start]
    name = argv[2] if len(argv) > 2 else "check"
    res = {"checked_at": now, "start_files": len(start), "changed_or_missing": changed, "added": added,
           "unchanged": not changed and not added, "files": cur}
    json.dump(res, open(os.path.join(MAN, f"protected_{name}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1))
    return 0 if res["unchanged"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
