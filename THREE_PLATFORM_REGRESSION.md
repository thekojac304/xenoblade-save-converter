# Three-platform regression (Phase 3F, 3F-rc1)

All runs on this PC (Windows 11, Python 3.14, PySide6), 2026-11-09. Logs in `phase3f/logs/` (copied to
`release_candidate_3F/validation/logs/`). The 3E version of this file: `phase3f/docs/previous_3E/`.

## 1. Fiora's later form away (288) and stored equipment in every direction

| Path | Data | Result | Evidence |
|---|---|---|---|
| DE 288 → Wii → DE (unchanged) | genuine 288 | Wii stored gear = DE's (staging slot 158 for Fiora); return **byte-identical** | `test_de288_to_wii_and_back_unchanged_is_byte_identical` |
| DE 288 → 3DS → DE (unchanged) | genuine 288 | return **byte-identical** | `test_de288_to_3ds_and_back_unchanged_is_byte_identical`, package test |
| Wii 288 → 3DS → Wii | the Wii export | canonical state identical (stored gear, party, characters) | `test_wii288_to_3ds_to_wii` |
| Wii 288 → DE → 3DS → Wii | first-time import | stored gear, party, Fiora-8 level/EXP/AP/coins/SP/arts/palette identical at every step | `test_wii288_to_de_to_3ds_to_wii` |
| Fiora-8 link slot (DE slot 8) and unlock levels of the six others | DE → Wii → DE | identical | `test_fiora_link_slot_round_trips` |
| DE → Wii → 3DS → DE, 3 rounds | 288 | stable | `test_repeated_generations_are_stable` |
| **Played** (gameplay-progressed) | DE 288 → 3DS → **3DS game's reunion** → cold reload → DE (record) → **Monado cold load + save** | 3DS: returning gear = stored = native DE; inventory change = native; → DE: 12/12 boxes and 42/42 equipped items = native content; Monado: palette normalisation + clock/time | `TestGameWrittenReunion`, `FIORA_REUNION_GAMEPLAY_TESTS.md` |
| Same 3DS save → Wii format → DE first-time | x4 | equipped gear of all 7 = native; without the record the 571 overflow items it holds are absent - exactly those, nothing else | ad-hoc check (`phase3f/work/tests/x4_wii_de`); documented first-time behaviour |
| Expected differences after play | | slot numbers (each game places items in its own free slots; compacted items keep their Wii slot, limitation 6), Shulk's palette slot 0 (platform event/normalisation, L-D), EXP vs Expert reserve EXP (same 915), clock/time/position | |
| Wii game played the reunion | — | **not done** (locked workstation; see the gameplay doc) | — |

## 2. Defect F1 (reunion room) - reproduction and fix

| Step | Result |
|---|---|
| 3E engine: DE 288 → 3DS on the user's story-8 template (capacity 60) | every gear box filled to 60 (overflow to the record) |
| 3DS game plays the reunion | Shulk and Reyn back in the party **without** their gear (references still staged); Sharla and Fiora fine (their join raises the capacity first) [game: x2] |
| 3E engine on Fallen Arm splits | Wii weapon box 140/140 for 269/276/283; 3DS gear boxes 60/60 for 269/283 (`parity_3e.py` + room check) - those reunions would have hit F1 on the Wii/3DS |
| 3F engine | keeps `reunion_room()` slots free (288: 4 per gear box, 13 gems); played: all four returned [game: x3] |
| Return of a skipped-return save | refused with the names, nothing written (`test_skipped_return_is_refused_never_lost`, package test) |

## 3. Byte parity with the 3E release (`phase3f/scripts/parity_3e.py` → `phase3f/work/parity_3e.json`)

| Group | Cases | Result |
|---|---|---|
| Not affected by 3F (DE → Wii 020/206/232/241/258/291/160/233, DE → 3DS 020/232/258/291/160, Wii → DE w150/w018 and the game-written Wii saves a1_s158/a6_s160/wd_s291, Wii → 3DS w150) | 19 | **byte-identical** |
| Alcamoth splits (DE → Wii 154/156/158, DE → 3DS 156) | 4 | **byte-identical** (their boxes had room) |
| Fallen Arm splits 269/276/283 (Wii) and 269/283 (3DS) | 6 | **deliberately different**: F1 room (extra unequipped items wait in the sidecar/record; stored gear unchanged) |
| 288 | 2 | 3E refused; 3F converts |

## 4. Automated suites

| Suite | Command | Result |
|---|---|---|
| 2H engine/service | `python -m unittest discover -s tests` | **136 OK** (1 skipped, as before; version test 3F-rc1) |
| 3A | `python -m unittest discover -s phase3a/tests` | **41 OK** |
| 3B Sync Hub | `python -m unittest discover -s phase3b/tests` | **65 OK** |
| 3C | `python -m unittest discover -s phase3c/tests` | **22 OK** |
| 3D | `python -m unittest discover -s phase3d/tests` | **21 OK** (2 tests moved from "288 refused" to "288 translated / syncs") |
| 3E | `python -m unittest discover -s phase3e/tests` | **24 OK** (2 tests moved likewise) |
| **3F new** | `python -m unittest discover -s phase3f/tests -v` | **34 OK** (state 3, translation 6, reunion room 6, game-written 6, adversarial 8, Sync Hub 5) |
| GUI Sync Hub tab on the 3F GUI | `python -m pytest phase3f/tests_gui` | **20 passed** (18 + 2 new message tests) |
| GUI converter tab (2H + 3A) on the 3F GUI | `python -m pytest phase3f/tests_gui_3a` | **39 passed** (run natively) |

The 3E originals of the changed tests are in `phase3f/docs/previous_tests_3E`; the change script is
`phase3f/scripts/patch_tests_for_3f.py`.

## 5. Packaged application (clean directory, no Python on PATH)

| Package test | Result |
|---|---|
| `phase3f/scripts/package_test_3f.py` | **16/16** (version; B2/B3; character 8; 288 → 3DS → DE byte-identical; F1 room; 3DS reunion → DE = native; skipped return refused; 269; Alcamoth; frozen window 3F-rc1; inputs and folder unchanged) |
| `phase3b/scripts/package_test_3b.py` (Sync Hub, incl. "no game data in the portable folder") | **19/19** |
| `phase3a/scripts/package_test_3a.py` | **32/32** |

## 6. Safety

Protected manifest (3,648 files: originals, live Dolphin/Monado/Azahar saves, NAND, emulators, ROM/disc images,
Syncthing configuration, every earlier release incl. `release_candidate_3E`) recorded at the start, checked after
every emulator run and at the end: unchanged. Monado's own shader cache (`cache\variants.bin` in its installation)
is updated by every Monado run, as in all earlier phases (not game or save data).
