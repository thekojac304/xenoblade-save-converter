"""Phase 3F protected-input manifest = 3E set + release_candidate_3E. Read-only.   python protect3f.py start | check [name]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for d in ("phase3e", "phase3d", "phase3c", "phase3b", "phase3a", "phase2f"):
    sys.path.insert(0, os.path.join(ROOT, d, "scripts"))
import protect3e  # noqa: E402,F401
import protect_manifest as pm  # noqa: E402

pm.DIRS["release_candidate_3E"] = os.path.join(ROOT, "release_candidate_3E")
pm.MAN = os.path.join(ROOT, "phase3f", "manifests")

if __name__ == "__main__":
    sys.exit(pm.main(sys.argv))
