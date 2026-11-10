"""Console entry point of the packaged command-line converter (xcconv.exe); same engine as the GUI (3A: Wii, DE, 3DS)."""
import os
import sys

if not getattr(sys, "frozen", False):
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:0] = [os.path.join(here, "..", "src"), os.path.join(here, "..", "..", "tools")]
import xcconv3  # noqa: E402

if __name__ == "__main__":
    sys.exit(xcconv3.main())
