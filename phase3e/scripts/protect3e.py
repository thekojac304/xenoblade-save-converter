"""Phase 3E protected-input manifest = 3D set + release_candidate_3D. Read-only.   python protect3e.py start | check [name]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for d in ("phase3d", "phase3c", "phase3b", "phase3a", "phase2f"):
    sys.path.insert(0, os.path.join(ROOT, d, "scripts"))
import protect3d  # noqa: E402,F401
import protect_manifest as pm  # noqa: E402

pm.DIRS["release_candidate_3D"] = os.path.join(ROOT, "release_candidate_3D")
pm.MAN = os.path.join(ROOT, "phase3e", "manifests")

if __name__ == "__main__":
    sys.exit(pm.main(sys.argv))
