"""Start the XC Save Converter desktop application (python gui\\xcconv_gui.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xcgui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
