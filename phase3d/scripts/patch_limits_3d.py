"""Turn the root KNOWN_LIMITATIONS.md (3C) into the 3D version: new header and 3D sections, updated character-8 rows.
The 3C copy is kept in phase3d/docs/previous_3C."""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
p = os.path.join(ROOT, "KNOWN_LIMITATIONS.md")
s = open(p, encoding="utf-8").read()

HEAD_OLD = s[:s.index("## What 3C changed in this list")]
HEAD_NEW = """# Known limitations (XC Save Converter 3D-rc1), ranked by impact

3D keeps the 3C application and Sync Hub and changes the engine for the late game: Fiora's later form (character 8)
is supported from scenario 275, defect D1 (Shulk's Wii-only arts flag from an early base) is fixed, and saves from
story splits whose departed members' stored equipment cannot be translated (D2) are refused. The 3C copy of this file
is in `phase3d\\docs\\previous_3C`. Sync Hub limits: `SYNC_KNOWN_LIMITATIONS.md`. Character details:
`CHARACTER_STATE_MATRIX.md`.

## What 3D changed in this list

| Item | 3C | 3D |
|---|---|---|
| Fiora's later form (character 8) in the party | refused in every direction involving the DE | **converted** from scenario 275 (era rule from the party journal); loaded, viewed and saved by the Wii (Dolphin) and 3DS (Azahar) games, returned to DE and cold-loaded by Monado |
| Character 3 in a party from 275, or 8 before 275 | (8 refused) | refused - 3 is never substituted for 8 or back |
| DE save from a story split (members away, gear stored by the game) | converted; their stored gear silently replaced by the destination's | **refused** with their names (D2) unless the destination stores the same gear or is the playthrough's own save |
| Early 3DS/Wii base below story 20 used for a later save | Shulk could keep arts flag 0 -> 3DS crash / Wii hang at Fallen Arm | fixed (D1) |

## New in 3D

| # | Limit | Detail | Severity |
|---|---|---|---|
| L-E | **Story splits cannot be converted (D2)** | While main characters who have joined are away in a story event (public saves: Alcamoth 154-158 - Melia or Shulk alone; Fallen Arm to the reunion 269-288), both games keep their equipment in a stored-equipment table (DE 0x3BB50; Wii/3DS staging slots 150+id) and give it back at the reunion. The converter does not translate that table, so such saves are refused (the DE scan of 359 public saves: only 269-288 in that archive; the 3C story fixtures 154-158 too). Convert before the split or after the reunion, or play through it on one platform. A return to the playthrough's own save is allowed (its stored gear is kept). | **High** for players in those chapters (temporary) |
| L-F | **Reunion events not played on the Wii/3DS** | Fiora's rejoin (269 -> 276) and the 288 -> 291 reunion were not reached on the Wii/3DS (navigation); the post-event states were validated instead. | Medium |
| L-G | **Record 3 after 275 on a foreign Wii base** | For a DE-native playthrough exported after scenario 275, Fiora's retired record 3 keeps the base's values on the Wii; the games never show it again and the DE's own record 3 returns from the sidecar. | Cosmetic |
| L-H | **Wii skill ids of a game-written post-rejoin record 8 unknown** | The Wii keeps the converter's own-skill ids (176+) for record 8 and mirrors them into record 3; a genuine Wii save written at the rejoin was not available. A record 8 holding Fiora-3 ids (51-75) is refused, not guessed. | Low |
| L-I | **The 3DS raises skill-link unlocks on viewing the skill screens** | After opening Fiora-8's Skill Trees, nine unlock levels went up (including Fiora-8 slots); they return to DE as raised (limitation 5). | Cosmetic |

"""
s = s.replace(HEAD_OLD, HEAD_NEW, 1)
s = s.replace("## What 3C changed in this list", "## What 3C changed in this list (unchanged in 3D)", 1)
s = s.replace("## New in 3C\n", "## New in 3C (unchanged in 3D)\n", 1)
old_row = ("| Fiora's second form (character 8) or a guest (9–13) in the party | No real save with Fiora rejoined was available; "
           "her record and skill-link rows have no validated mapping. Converting would silently drop her progress. | "
           "**High** for late-game players: from Fiora's rejoin on, conversion is not possible yet |")
new_row = ("| A guest (9–13) in the party; character 8 before scenario 275 or character 3 from 275 | Guests exist only in "
           "scripted battles (never in a saved party in any real save); the Fiora records follow the era rule "
           "(`CHARACTER_STATE_MATRIX.md`). | Low |\n"
           "| Main characters away with stored gear (story split, D2) | See L-E. | **High** (temporary) |")
assert old_row in s
s = s.replace(old_row, new_row)
s = s.replace("| Fiora's second form / guests | Carried between Wii and 3DS (lossless), still refused towards DE (2H rule). | as 2H |",
              "| Fiora's second form / guests | Carried between Wii and 3DS (lossless). Towards DE: character 8 converted from 275 (3D); guests refused. | Low |")
s = s.replace("- Fiora rejoined (character 8), guest party members (refused).",
              "- The rejoin and reunion events themselves on the Wii/3DS (L-F); guest party members (refused).")
s = s.replace("| L-C | **Story coverage is a sample** | Played after conversion: DE 156 → 158 → 160 and 232 → 233; Wii 154 → 156; 3DS 154 → 156. Not played: Eryth Sea after 160, Fiora's return, the Mechonis and endgame chapters, Future Connected, quest-gated steps (e.g. 233's Magma Rock). | Medium |",
              "| L-C | **Story coverage is a sample** | Played after conversion: DE 156 → 158 → 160 and 232 → 233; Wii 154 → 156; 3DS 154 → 156. 3D: post-rejoin states 276-291 loaded, saved and returned on all three games. Not played: Eryth Sea after 160, the rejoin/reunion events on Wii/3DS, the Mechonis and endgame chapters, Future Connected, quest-gated steps. | Medium |")
open(p, "w", encoding="utf-8").write(s)
print("ok")
