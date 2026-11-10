"""Phase 3D protected-input manifest = 3C set (originals, live saves, emulators, images, every release candidate up to
3B, Syncthing config) + release_candidate_3C. Read-only.   python protect3d.py start | check [name]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for d in ("phase3c", "phase3b", "phase3a", "phase2f"):
    sys.path.insert(0, os.path.join(ROOT, d, "scripts"))
import protect3c  # noqa: E402,F401
import protect_manifest as pm  # noqa: E402

pm.DIRS["release_candidate_3C"] = os.path.join(ROOT, "release_candidate_3C")
pm.MAN = os.path.join(ROOT, "phase3d", "manifests")

if __name__ == "__main__":
    sys.exit(pm.main(sys.argv))
