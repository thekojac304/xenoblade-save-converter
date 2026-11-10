# Three-platform regression (Phase 3D, 3D-rc1)

All runs on this PC (Windows 11, Python 3.14, PySide6), 2026-11-08. Logs in `phase3d/logs/` (copied to
`release_candidate_3D/validation/logs/`).

## 1. Directions and multi-hop paths with character 8 (story 291, Fiora's later form, full party)

| Path | Data | Result | Evidence |
|---|---|---|---|
| DE → Wii | genuine DE 291 | ✓ record 8 = DE record 8; record 3 = mirror of its skill object | `test_wii_records_after_the_rejoin` |
| DE → Wii → DE (unplayed) | 276*, 283*, 288*, 291 | byte-identical | `test_de_to_wii_and_back_unchanged_is_byte_identical` (*made before D2; 291 in the suite) |
| DE → 3DS → DE (unplayed) | 291 | byte-identical | `test_de_to_3ds_and_back_unchanged_is_byte_identical`, package test |
| DE → Wii → **Wii game** → DE → **Monado** | 276, 283, 288, 291 | Wii re-save = clock/time/position; DE return = same + limitation 6 slots; Monado cold load + save = clock/time | wd_s*_save, m_r_w2d_s283, `test_return_to_de` |
| DE → 3DS → **3DS game** (screens + save) → DE → **Monado** | 291 | 3DS save = clock/time/position + 9 raised link unlocks; DE return identical items/equipment; Monado cold load + save = clock/time | x5_s291_save, m_r_x2d_s291, `Test3dsGameSession` |
| Wii → DE → 3DS → Wii | 291 lineage | shared state equal (outside documented lossy fields), equipment content equal | `test_multi_hop_paths` |
| DE → Wii → 3DS → DE | 291 | equal | `test_multi_hop_paths` |
| 3DS → DE → Wii → 3DS | 291 lineage | equal | `test_multi_hop_paths` |
| Wii ↔ 3DS with guests / out-of-era party | synthetic | carried unchanged (same game) | `test_wii_parties_outside_the_era_rule_are_refused` |
| Any direction involving DE with a guest, 8 before 275, 3 from 275 | synthetic | refused, nothing written | adversarial tests |
| Any direction from a story split (D2) | genuine DE 269/276/283/288; 2E/3C saves 154–158 | refused with names, nothing written; returns to the own save allowed | `test_d2_*`, package test |

"Gameplay between hops" in the game-written rows = the real game loading, opening menus and saving; synthetic play
(hubfix rules: flags, EXP, items, money, time) is used inside the Sync Hub and multi-generation tests.

## 2. Sync Hub (unchanged 3B code, 3D engine)

| Scenario | Result |
|---|---|
| DE save from the split (288) | the whole sync is blocked with the D2 text; nothing committed (all-or-nothing) |
| DE 291 → Wii + 3DS outputs; Wii play (character 8 +100 EXP) → DE; 3DS play → DE | complete; party kept; character 8's EXP and the DE Expert word move together (E1); DE-only character data kept |
| Unchanged 3DS re-save | in sync |
| Rollback to generation 1 | DE save byte-identical to the original |
| 3C/3B hub suites (multi-generation, interrupted sync, conflicts, anchors) | pass unchanged (3B 65, 3C 22) |

Legitimate party changes: a party change that is not a departure with stored gear (e.g. Fiora leaving at the
3-era, reorderings, 288 → 291 reunion on DE) is never mistaken for corruption. A departure with stored gear is now
refused rather than synced.

## 3. Automated suites

| Suite | Command | Result |
|---|---|---|
| 2H engine/service | `python -m unittest discover -s tests` | **136 OK** (1 skipped, as before); 4 tests updated for D2 + version (see §5) |
| 3A three-platform | `python -m unittest discover -s phase3a/tests` | **41 OK** |
| 3B Sync Hub | `python -m unittest discover -s phase3b/tests` | **65 OK** |
| 3C | `python -m unittest discover -s phase3c/tests` | **22 OK** |
| **3D new** | `python -m unittest discover -s phase3d/tests -v` | **21 OK** (characters/era/adversarial/D1/D2 14, game-written 6, Sync Hub 1) |
| GUI: Sync Hub tab on the 3D GUI | `python -m pytest phase3d/tests_gui` | **18 passed** |
| GUI: converter tab (2H + 3A) on the 3D GUI | `python -m pytest phase3d/tests_gui_3a` | **39 passed** |
| Canonical reading parity vs 3C (12 pre-275 saves) | `fp_check.py` | **12/12 identical** |
| Output parity vs 3C engine (12 conversions) | `parity_3c.py` | 8 byte-identical; 3 DE→3DS differ only in the D1 byte + its section checksum; s269 → Wii now refused (D2) |

## 4. Packaged application (`phase3d/dist/XCSaveConverter`, clean folder, no Python on PATH)

| Package test | Result |
|---|---|
| 3D (`phase3d/scripts/package_test_3d.py`): version, B2, B3, character 8 round trip, 3DS game save → DE, D2 refusal, window | **11/11** |
| 3B (`phase3b/scripts/package_test_3b.py`, unchanged) | **19/19** |
| 3A (`phase3a/scripts/package_test_3a.py`, unchanged) | **32/32** |

## 5. Test changes and failures found

| # | What happened | Resolution |
|---|---|---|
| F1 | 2H: 4 tests errored after D2 (`test_monado_progressed_saves`, `test_temporarily_unavailable_and_rejoin`, `test_matrix`, `test_export_keeps_copy_in_step`) - they export the 2E story-154 save (Melia alone) or s269 (Shulk alone) | expected: those saves are D2 states. Each test now asserts the refusal (with the names) for that save and keeps every assertion for the others; the absent-member checks moved to the story-20 save (`phase3d/scripts/patch_tests_d2.py`, `XC_PHASE3D_REPORT.md` §5) |
| F2 | 2H `test_version` | 3C-rc1 → 3D-rc1 |
| F3 | first 3D multi-hop test compared slot positions | the first-time DE hop compacts and drops overflow by design (limitations 2, 6, 8); the test now compares everything else exactly and equipment by content |
| F4 | 3D hub test: DE-only character data differed by 100 | E1 (3C): the Expert highest-level word follows the 100 EXP earned on the Wii; expectation states it |
| F5 | first D2 build flagged every absent character | `stored_gear.de_stored` read the record type (+2) instead of the id (+4); fixed before any test relied on it |
| F6 | first D2 rule refused returns to the playthrough's own DE save | the destination's own stored gear is authoritative when it has the member away too; rule refined, returns kept |

Final logs: `phase3d/logs/suite_2h.txt`, `suite_3a.txt`, `suite_3b.txt`, `suite_3c.txt`, `suite_3d.txt`,
`gui_synchub_3d.txt`, `gui_converter_3d.txt`; package results `phase3d/work/package_test_3{a,b,d}.json`.
