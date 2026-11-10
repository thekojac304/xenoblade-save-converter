"""Plain-language explanations for converter refusals and errors (GUI only; the engine messages stay unchanged).

explain(exc) -> Friendly(title, text, detail, kind). The technical message is always kept in `detail` (shown under
"Technical details" and in the diagnostic report); `text` never contains a traceback or a command-line option.
"""
import re
from dataclasses import dataclass


@dataclass
class Friendly:
    title: str
    text: str
    detail: str = ""
    kind: str = "refused"      # refused (nothing written, expected) | internal (unexpected; nothing written)


# (pattern on the engine message, title, plain-language text); first match wins
RULES = [
    (r"party member\(s\) \[[^\]]*\b(8|9|1[0-3])\b|character 8 is Fiora",
     "Temporary character form in the party",
     "This save contains a temporary character form (Fiora's second form) or a guest character in the party. The "
     "converter cannot safely transfer these characters yet, so it stopped. Nothing was written."),
    (r"back in the party, but the game has not given back",
     "Equipment not given back by the game",
     "In this save a character is back in the party, but the game has not given back the equipment it kept while "
     "the character was away (the Wii/3DS game skips that when an equipment pocket is full at the reunion). "
     "Converting it would lose that equipment, so the converter stopped. Nothing was written."),
    (r"party \[[^\]]*\] cannot exist on the Wii",
     "Party not possible on the Wii",
     "The party in this save is a combination the Wii version cannot have. Change the party in the game, save, and "
     "convert that save."),
    (r"Wii base is not a valid used XC1 save",
     "Starting Wii save not usable",
     "The starting Wii save is empty or damaged. Choose another Wii save of yours."),
    (r"format-v7|format v7|not format v10|different format version|template is not a v10 save",
     "Older Definitive Edition save",
     "This Definitive Edition save uses the older format (v7, from game version 1.x). Load it once in DE 2.0 or "
     "Monado and save it again; that upgrades it to format v10, which the converter needs."),
    (r"is not a Wii map|DE-only or Future Connected|Future Connected",
     "Area not available on the Wii",
     "Your party is in an area that only exists in the Definitive Edition (or in Future Connected). Travel to an "
     "area that exists in both games, save, and convert that save."),
    (r"story scenario \d+ is not a Wii scenario",
     "Story progress not available on the Wii",
     "This save's story progress belongs to content that only exists in the Definitive Edition, so it cannot become "
     "a Wii save."),
    (r"sidecar looks older",       # not "older than your latest": the divergence message also says that (2H fix)
     "Older conversion record selected",
     "The selected conversion record is older than your latest conversion: your other save already contains newer "
     "progress. Conversion has been stopped to protect your progress. Choose the conversion record written by your "
     "most recent conversion."),
    (r"does not continue the exported one",     # "not the one this sidecar exported" is the divergence message
     "Conversion record from a different save history",
     "The selected conversion record belongs to a different save history. Conversion has been stopped to protect "
     "your progress. Choose the conversion record that was written when this save was last converted."),
    (r"save also progressed|No automatic merge",
     "Both games have new progress",
     "Both games have progress made after the last conversion. The converter never merges two different progress "
     "histories. Decide which progress you want to keep: either continue in the game you played most recently, or "
     "use \"Keep only the progress from this save\" under Advanced options (the other game's newer progress is "
     "then discarded in the converted file; your original files are never changed)."),
    (r"has no progress since the export but",
     "Nothing new to convert",
     "The save you selected has no progress since the last conversion, but your save in the other game does. Your "
     "other save is already the newer one, so there is nothing to convert."),
    (r"with --sidecar, give your current|current DE save of this playthrough is required",
     "Current save of the other game needed",
     "To bring a save back safely, the converter needs to see your current save in the other game (it is only "
     "read). Select it, or confirm that you have not played the other game since the last conversion."),
    (r"exceed the Wii capacity|do not fit the Wii box|over the Wii capacity",
     "Inventory too large for the Wii save",
     "Your Definitive Edition inventory holds more items than this Wii save can store. Turn on \"Keep extra items in "
     "the conversion record\" under Advanced options: unequipped extra items then wait in the conversion record and "
     "come back when you return to the Definitive Edition."),
    (r"DE-only item \d+ is equipped",
     "Definitive Edition item equipped",
     "A character is wearing an item that only exists in the Definitive Edition. Unequip it in the game, save, and "
     "convert that save."),
    (r"output folder already exists|refusing to overwrite",
     "Output folder already used",
     "The output folder already contains files. Existing files are never overwritten; choose a new folder."),
    (r"live game/save location|game or emulator installation",
     "Output inside a game or save folder",
     "The chosen output location is inside a game, emulator or live save folder. To protect your saves the converter "
     "only writes to a separate folder (for example in Documents). Copy the result into the game yourself after "
     "making a backup."),
    (r"link/junction",
     "Output folder is a link",
     "The chosen output folder is a link or junction to another location. Choose a plain new folder."),
    (r"empty Wii save slot",
     "Empty Wii save slot",
     "This Wii save slot is empty: it does not contain a game. Choose a slot you have saved to."),
    (r"damaged or edited|cannot be decoded|header version \d+, which does not match|integrity hash mismatch|"
     r"container damaged|not a used XC1 save slot|corrupted|snapshot does not match",
     "File damaged or edited",
     "This file appears damaged or edited (its internal checks do not match). It is not repaired or converted."),
    (r"is not a text sidecar|not a JSON object|unsupported sidecar schema|missing required fields|sidecar .*inconsistent|"
     r"names itself|session id does not match|sidecar games do not match|lineage generation is invalid|"
     r"deferred data is malformed|hash does not match its snapshot|unknown sidecar direction|missing from the sidecar",
     "Not a valid conversion record",
     "The selected file is not a valid conversion record from this converter, or it was changed by hand."),
    (r"was written by a .* conversion; this command needs|was not written by a DE -> Wii export",
     "Conversion record for the other direction",
     "This conversion record was written by a conversion in the other direction. Choose the one written when this "
     "save was last converted to the game you are leaving."),
    (r"is not a Xenoblade Chronicles (Wii|DE|Wii or DE) save|not an XC1 Wii or DE save|not a DE v7/v10 save",
     "Not a Xenoblade Chronicles save",
     "The selected file is not a Xenoblade Chronicles save for the expected game."),
    (r"game tables not found",
     "Game data not set up",
     "The converter needs data tables made from your own copies of the games. Open the \"Game data\" tab to choose "
     "or create them."),
    (r"EXP \d+ is not below|affinity coins|above the game limits|above the Wii limit|is not a valid DE value|"
     r"references empty|references DE slot \d+ with no item|level \d+$|quantity .* outside",
     "Values the game cannot produce",
     "The save contains values the games cannot produce (for example after editing with a save editor). It is not "
     "repaired or converted."),
    (r"read-back|does not read back|does not match what was written|would not convert back",
     "Verification failed",
     "The converted save did not pass the independent verification, so nothing was written. Please keep the "
     "diagnostic report (Advanced tools) if you report this."),
    (r"no Wii drop-crystal row|does not exist on the Wii|do(es)? not fit the Wii|unresolved mappings|4th socket|"
     r"is not a gem item|index \d+ >= 500|flag rule violations|exceed the DE|no empty slot|no free DE",
     "Something in this save has no equivalent",
     "Part of this save (an item, crystal or gem) has no exact equivalent in the other game, so the conversion "
     "would lose it. The converter stopped. Nothing was written."),
    (r"file not found",
     "File not found",
     "A selected file no longer exists. Choose it again."),
    (r"too large to be a save",
     "File too large",
     "The selected file is too large to be a save or conversion record."),
]


REFUSAL_TYPES = ("Refused", "SidecarError", "DivergenceError", "IncompatibleError", "ConvertError")


def _rule(text):
    for pat, title, plain in RULES:
        if re.search(pat, text, re.I):
            return title, plain
    return None


def explain(exc):
    """exc: an exception from the service layer (or any exception from a worker)."""
    name = type(exc).__name__
    detail = f"{name}: {exc}"
    internal = name not in REFUSAL_TYPES
    hit = _rule(str(exc))
    if hit:
        return Friendly(hit[0], hit[1], detail, "internal" if internal else "refused")
    if internal:
        return Friendly("Unexpected problem",
                        "An unexpected problem stopped the converter. Nothing was written and your original files "
                        "are unchanged. The technical details below (and the diagnostic report in Advanced tools) "
                        "help to find the cause.", detail, "internal")
    return Friendly("Conversion stopped",
                    "The converter stopped to protect your progress. Nothing was written. The technical details "
                    "below explain why.", detail, "refused")


# plain-language warnings for compatibility pre-check problems (DE -> Wii and Wii -> DE)
def explain_problem(p):
    hit = _rule(p)
    return hit[1] if hit else p
