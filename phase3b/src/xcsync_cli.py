"""Entry point: python phase3b/src/xcsync_cli.py ...  (packaged as xcsync.exe)."""
import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xcsync.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
