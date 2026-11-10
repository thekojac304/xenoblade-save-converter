"""Phase 3B protected-input manifest (extends 3A/2F): every original and live save folder, emulator executables,
game images, every earlier release candidate (now including release_candidate_3A) and Syncthing's configuration
(when present). Read-only.

  python protect3b.py start | check [name]      (manifests in phase3b/manifests)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "phase3a", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "phase2f", "scripts"))
import protect3a  # noqa: E402,F401  (fills pm.DIRS / pm.FILES)
import protect_manifest as pm  # noqa: E402

LOCAL = os.environ.get("LOCALAPPDATA", r"C:\Users\lawma\AppData\Local")
pm.DIRS.update({
    "release_candidate_3A": os.path.join(ROOT, "release_candidate_3A"),
    "phase3a_originals": os.path.join(ROOT, "phase3a", "originals"),
})
# Syncthing: only its configuration file (its database and log change on their own while it runs)
pm.FILES["syncthing_config_xml"] = os.path.join(LOCAL, "Syncthing", "config.xml")
pm.MAN = os.path.join(ROOT, "phase3b", "manifests")

if __name__ == "__main__":
    sys.exit(pm.main(sys.argv))
