"""Phase 3F GUI: plain-language text for the F1 refusal and for the reunion-room capacity refusal."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gui"))
from xcgui import messages  # noqa: E402


def test_skipped_return_is_explained():
    f = messages.explain(Exception("Shulk, Reyn: back in the party, but the game has not given back the equipment it "
                                   "kept during the story separation (...)"))
    assert f.title == "Equipment not given back by the game" and "Nothing was written" in f.text


def test_reunion_room_refusal_offers_the_overflow_option():
    f = messages.explain(Exception("weapon: 140 items exceed the Wii capacity of this save (140) less the 4 slots the "
                                   "game needs free to give the stored equipment back at the party's reunion; rerun"))
    assert f.title == "Inventory too large for the Wii save"
