"""Phase 3C protected-input manifest = the 3B manifest (originals, live saves of Dolphin/Monado/Azahar/Citra, emulator
executables and configs, Wii disc image and 3DS ROM, every earlier release candidate, Syncthing config.xml) plus
release_candidate_3B. Read-only.

  python protect3c.py start | check [name]      (manifests in phase3c/manifests)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3b", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "phase3a", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "phase2f", "scripts"))
import protect3b  # noqa: E402,F401  (fills pm.DIRS / pm.FILES with the 3B set)
import protect_manifest as pm  # noqa: E402

pm.DIRS["release_candidate_3B"] = os.path.join(ROOT, "release_candidate_3B")
pm.MAN = os.path.join(ROOT, "phase3c", "manifests")

if __name__ == "__main__":
    sys.exit(pm.main(sys.argv))
