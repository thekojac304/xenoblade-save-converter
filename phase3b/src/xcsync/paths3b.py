"""Import paths for the 3B modules: the 2H engine (tools/) and the 3A modules (phase3a/src), from the research
folder or from a release candidate's source/ folder (same relative layout), or frozen (PyInstaller bundles them)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))           # .../phase3b/src/xcsync
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
for p in (os.path.join(ROOT, "phase3a", "src"), os.path.join(ROOT, "tools"), os.path.dirname(HERE)):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
