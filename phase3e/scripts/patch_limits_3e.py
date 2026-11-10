"""Turn the root KNOWN_LIMITATIONS.md (3D) into the 3E version. The 3D copy is kept in phase3e/docs/previous_3D."""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
p = os.path.join(ROOT, "KNOWN_LIMITATIONS.md")
s = open(p, encoding="utf-8").read()
head_end = s.index("## What 3D changed in this list")
HEAD = """# Known limitations (XC Save Converter 3E-rc1), ranked by impact

3E keeps the 3D application and Sync Hub and adds the translation of **stored equipment** - the gear (and socketed
gems) the games keep for party members who are away in a story event - between the Wii, the New 3DS and the DE,
validated in reunions played by the Wii, 3DS and DE games (`REUNION_VALIDATION.md`). It also fixes a 3DS transcoding
defect (D3). The 3D copy of this file is in `phase3e\\docs\\previous_3D`. Mapping: `STORED_EQUIPMENT_MAPPING.md`.

## What 3E changed in this list

| Item | 3D | 3E |
|---|---|---|
| Saves made while party members are away in a story event (Alcamoth 154-158, Fallen Arm 269-288) | refused (L-E) | **converted**, stored gear and gems included; the Wii, 3DS and DE games gave the returning characters exactly their own gear in played reunions |
| Fiora's later form away (story 288) | refused | still refused (no reunion with her stored gear could be played) - L-J |
| 3DS staged-gem links | byte-swapped by the 3A transcoder (no effect before 3E: no save had any) | fixed (D3) |
| Returning a file exported by 3C/3D during a split | kept the DE's stored gear | same (3-way: the DE's entries are kept when the Wii/3DS session did not change the stored gear) |

## New in 3E

| # | Limit | Detail | Severity |
|---|---|---|---|
| L-J | **Fiora's later form away (288) is refused** | Same table and routine, but no reunion with her stored gear was reachable in the emulators. Convert after the reunion (291) or play the split on one platform. | Medium (one chapter) |
| L-K | **Stored items carry no Wii-only header bits** | The age byte and low header bits of a staging record are written as 0; the games rebuild the item at the return and do not use them (verified by the reunions). | Cosmetic |
| L-L | **More than 8 socketed gems stored for one character cannot go to the Wii/3DS** | The Wii keeps 8 per absent character; such a DE save is refused (never seen in real saves: maximum 6). | Low |
| L-M | **Fallen Arm reunions not played** | 269-291 translate exactly in every direction (static, all genuine saves), but those reunions themselves were only played for Alcamoth (156 -> 158 -> 160). | Low |

"""
s = HEAD + s[head_end:].replace("## What 3D changed in this list", "## What 3D changed in this list (L-E superseded by 3E)", 1)
s = s.replace("| L-E | **Story splits cannot be converted (D2)** |", "| L-E | **(3D; superseded in 3E)** Story splits cannot be converted (D2) |")
open(p, "w", encoding="utf-8").write(s)
print("ok")
