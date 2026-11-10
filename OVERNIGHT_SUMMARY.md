# Overnight summary: Phase 2E (2026-11-06)

**Bottom line:** your playthrough now moves both ways. The Wii save → Definitive Edition → played in Monado →
back to the Wii → played in Dolphin → back to Definitive Edition, and every step loaded, played, saved and
reloaded. The state matched at every handoff. Your original saves and live profiles are unchanged (all 21 hashes
verified). Nothing was installed into your games.

## Status

| | Status |
|---|---|
| Wii → DE | **VALIDATED** for your scenario-150 save (story verified to 156) |
| DE → Wii | **PARTIALLY VALIDATED** (no Wii story progression test) |
| Bidirectional | **VALIDATED** for the tested chain |

## What was done

### Implemented

- Phase 2E converter steps:
  - quest objective counters (fixes a real Phase 2D defect: 2 completed objectives would have reverted);
  - minimap exploration;
  - time of day (yours is 13:13, day 30, not 6:36);
  - exact award counters (11 Phase 2D values corrected);
  - all seven characters' progression.
- DE → Wii converter, with Wii inventory-capacity rules and compaction.
- Canonical state model.
- Sidecar format with lineage, snapshots and deferred DE-only data.
- 3-way re-import with Expert Mode and divergence protection.
- The `xcconv` command-line tool.
- Isolated Monado and Dolphin test harnesses.
- Release candidate.

### Statically tested (40/40 automated tests)

- Wii → DE → Wii is **byte-identical** for `monado01` and `monado03`.
- DE → Wii → DE is byte-identical when the Wii side is unchanged.
- An independent decoder confirms every conversion field by field.
- Late-game public DE saves either convert or are refused clearly (inventory too large for the Wii).
- Synthetic DE-only data (Expert Mode, cosmetics, DE-only items, Future Connected bytes) survives a trip to the Wii.

### Tested in Monado (isolated, 16 runs)

- Load in Eryth Sea.
- All menu screens: equipment and gems for six characters, Skill Trees, Skill Links, Arts, Gem Crafting crystals,
  Items, Collectopaedia, Affinity Chart, Quest Log.
- Battle won with arts.
- Two fast travels.
- Converted clock and minimap visible.
- In-game save and reload.
- **Story advanced 150 → 154 → 156** through the game's own events. Teleport was used only to reach the trigger.
- Saves coming back from the Wii load, save and reload.

### Tested in Dolphin (isolated, 10 runs)

- Converted Wii saves load (play time 22:04 on the load list), at the right location.
- Party and inventory are correct; Quest Log is coherent.
- Battle won with arts.
- Two skip travels.
- The Wii game saves, and its own saves reload.
- Your DE-native scenario-6 save, exported to the Wii, loads and saves.

### Untested or unsupported

- Story beyond 156 (the scenario-157 trigger in Alcamoth was not found).
- Story progression on the Wii.
- Changing the active party.
- Completing a gem craft.
- Real Expert Mode or cosmetics data (synthetic fixture only).
- Changing equipment in DE and then playing on the Wii.
- Future Connected (refused by design).

**Found and handled:** the Wii sets flags in a block (`0x3440+i`, NPC registration) that DE has no slot for. They
now stay on the Wii side instead of blocking the import. See `KNOWN_LIMITATIONS.md`.

## Your files

- `release_candidate\user_saves\wii_to_de_monado01\save_0\bfsgame01.sav`: your converted DE save (the exact file
  tested in Monado), plus `wii_to_de.sidecar.json`. Keep the sidecar.
- `release_candidate\converter\`: the converter (code and docs only, no game data).
- Reports: `XC_WII_TO_DE_PHASE2E.md`, `BIDIRECTIONAL_DESIGN.md`, `README_CONVERTER.md`, `KNOWN_LIMITATIONS.md`.

## Commands to try (from `C:\Users\lawma\Documents\XC_Wii_to_DE_Research\release_candidate\converter`)

```
python tools\xcconv.py inspect ..\user_saves\wii_to_de_monado01\save_0\bfsgame01.sav
python tools\xcconv.py roundtrip-check --wii ..\..\work\originals\monado01 --template ..\..\work\template\bfsgame00.sav
python tools\xcconv.py wii-to-de --wii ..\..\work\originals\monado01 --template ..\..\work\template\bfsgame00.sav --out C:\Users\lawma\Documents\xc_test\w2d --slot 01
python tools\xcconv.py de-to-wii --de C:\Users\lawma\Documents\xc_test\w2d\save_0\bfsgame01.sav --sidecar C:\Users\lawma\Documents\xc_test\w2d\wii_to_de.sidecar.json --out C:\Users\lawma\Documents\xc_test\d2w
```

Full regression suite (from the research folder): `python -m unittest discover -s tests -v`

To play the converted save, copy `bfsgame01.sav` (and `.tmb`) into Monado's `save\save_0`. Back that folder up
first. Slot 01 is used so your slot 00 is never replaced. This step was **not** done for you.
