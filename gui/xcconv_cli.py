"""Console entry point of the packaged command-line converter (xcconv.exe); same engine as the GUI."""
import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import xcconv  # noqa: E402

if __name__ == "__main__":
    sys.exit(xcconv.main())
