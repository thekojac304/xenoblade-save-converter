# Three-platform regression (Phase 3E, 3E-rc1)

All runs on this PC (Windows 11, Python 3.14, PySide6), 2026-11-08/09. Logs in `phase3e/logs/` (copied to
`release_candidate_3E/validation/logs/`). The 3D version of this file: `phase3e/docs/previous_3D/`.

## 1. Stored equipment in every direction

| Path | Data | Result | Evidence |
|---|---|---|---|
| DE → Wii, DE → 3DS, → back unplayed | 7 genuine split saves (154, 156, 158, 269, 276, 283; Alcamoth and Fallen Arm) | Wii/3DS stored gear = DE's; returns byte-identical | `test_all_directions_on_genuine_split_saves` |
| Wii → DE first-time | the same exports | DE stored gear = original | same |
| 3DS → Wii (same game) | the same | identical | same |
| DE → Wii → 3DS → DE, 3 rounds | 156 | stable | `test_repeated_three_platform_conversions_are_stable` |
| **Played reunions** | Wii 156→158→160, 3DS 156→158→160, DE 158→160 from a Wii-built stash | returning gear and gems = native DE result; inventory changes identical; save, cold reload; returns to DE = native 160 | `REUNION_VALIDATION.md`, `TestGameWrittenReunions` |
| Fiora's later form away (288) | genuine | refused with her name, nothing written | `test_fiora_away_is_refused`, package test |
| Damaged stored data (missing / orphan / duplicate gems, > 8 gems, staging id mismatch, away but equipped) | synthetic edits of genuine saves | refused, nothing written | `TestAdversarial` |
| Stored item modified on the DE before conversion | synthetic | the modified item arrives | `test_equipment_changed_before_reunion_follows_the_save` |
| Returns of pre-3E files (3C/3D exports of splits, no stored gear in the file) | 3C fixtures (154/156 Wii and 3DS), 3D fixtures (276/283/288) | the DE's own stored gear kept byte-equal | 3C story tests, 3D game-written tests |

## 2. Sync Hub (unchanged 3B code, 3E engine)

| Scenario | Result |
|---|---|
| Genuine 154 → 156 → 158 → 160 as DE generations (two departures, two reunions) | each recognised as new progress (3D took a split for an older-sync branch: stored items now count as owned); Wii and 3DS outputs carry the DE's stored gear |
| Wii session on the 160 generation (Melia away) | complete; her stored gear back unchanged |
| Rollback to the split generation | DE file byte-identical |
| DE save with Fiora away (288) | blocked with her name; nothing committed |
| 3B/3C/3D hub suites | pass |

## 3. Automated suites

| Suite | Command | Result |
|---|---|---|
| 2H engine/service | `python -m unittest discover -s tests` | **136 OK** (1 skipped, as before) |
| 3A | `python -m unittest discover -s phase3a/tests` | **41 OK** |
| 3B Sync Hub | `python -m unittest discover -s phase3b/tests` | **65 OK** |
| 3C | `python -m unittest discover -s phase3c/tests` | **22 OK** |
| 3D | `python -m unittest discover -s phase3d/tests` | **21 OK** |
| **3E new** | `python -m unittest discover -s phase3e/tests -v` | **24 OK** (decode 5, translation 4, game-written reunions 6, adversarial 7, Sync Hub 2) |
| GUI Sync Hub tab on the 3E GUI | `python -m pytest phase3e/tests_gui` | **18 passed** |
| GUI converter tab (2H + 3A) on the 3E GUI | `python -m pytest phase3e/tests_gui_3a` | **39 passed** |
| Output parity vs the 3D release engine | `python phase3e/scripts/parity_3d.py` | 14 of 18 byte-identical (all saves outside split windows); story 160 differs in 21 bytes = Melia's stored gear (references + staging records + checksums, she is away there); 156/269/283 now convert (3D refused); 288 refused in both (now naming Fiora) |

## 4. Packaged application (`phase3e/dist/XCSaveConverter`, clean folder, no Python)

| Package test | Result |
|---|---|
| 3E (`phase3e/scripts/package_test_3e.py`): version, B2, B3, character 8, Fiora refusal, stored equipment round trip (269), 3DS reunion save → DE | **13/13** |
| 3B (unchanged) | **19/19** |
| 3A (unchanged) | **32/32** |

## 5. Emulator runs and safety

27 runs in 3E (Dolphin 11, Monado 2, Azahar 14), each on an isolated copy; the 2,935-file protected manifest
(including release_candidate_3D) and each live save folder unchanged after every run and at the end.

## 6. Failures found and their resolution

| # | What happened | Resolution |
|---|---|---|
| F1 | 3DS reunion returned the gear but not the 6 gems | defect D3 (link table byte order) fixed in `xc3d`; rerun returned all gems |
| F2 | 2F `test_temporarily_unavailable_and_rejoin`: "unresolved mappings: char:equipment_ref" | its synthetic rejoin edited only the party list; with the gear now stored (references keep the id) that is not a reachable state - the synthetic session is money only, real rejoins are game-written 3E tests |
| F3 | 3C returns of 3C-era Wii/3DS files refused ("staging record does not hold gear 652") | re-import keeps the DE's entries for characters whose stored-gear bytes did not change since the export (before reading them); read-back accepts them |
| F4 | 3E decode test assumed the user's story-8 3DS save had no stored character | it has one (Reyn away with his starting gear); test corrected and the case added |
| F5 | 3E D3 test used a transcode round trip (not byte-exact by design) | direct byte-order check |
| F6 | 3E package test "inputs unchanged" | the test copied two inputs after its snapshot; copies moved before it |
| F7 | Dolphin / Azahar automation (hidden window, quest window, wrapping menu, one Azahar start without its control port) | reruns from the same game-written saves; no failed run's output used |
