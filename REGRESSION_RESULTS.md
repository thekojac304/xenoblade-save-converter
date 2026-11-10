# Regression results (Phase 3C, 3C-rc1)

All runs on this PC (Windows 11, Python 3.14, PySide6), 2026-11-08. Logs in `phase3c/logs/` (copied to
`release_candidate_3C/validation/logs/`).

## 1. Automated suites

| Suite | Command | Result | Notes |
|---|---|---|---|
| 2H engine/service (retained) | `python -m unittest discover -s tests` | **136 OK** (1 skipped, as in 3B) | `test_version` now expects the 3C engine stamp `3C-rc1` (was `2G-rc1` from 2G to 3B, when the engine did not change) |
| 3A three-platform (retained) | `python -m unittest discover -s phase3a/tests` | **41 OK** | |
| 3B Sync Hub (retained) | `python -m unittest discover -s phase3b/tests` | **65 OK** | two tests pinned 3B behaviour that 3C corrects: `test_b2_unplayed_return_is_never_converted` asserted the engine *refuses* the unplayed return (B2) — now asserts the hub still treats it as in sync **and** the manual return is byte-identical; `test_game_written_chain_reproduces_the_emulator_cycle` pinned generation 4 to the 3B bytes — now asserts the only difference is the E1 Expert word (= the EXP the 3DS battle gave, 7 bytes) and uses Monado's real re-save of the 3C generation 4 for the in-sync step |
| **3C new** | `python -m unittest discover -s phase3c/tests -v` | **22 OK** | metadata 12, Wii-only bytes / unplayed returns 3, Sync Hub multi-generation 1, game-written story saves 6 (below) |
| 3B GUI, Sync Hub tab, on the 3C GUI | `python -m pytest phase3c/tests_gui` | **18 passed** | generated from `phase3b/tests_gui` (paths only) |
| 2H + 3A GUI, converter tab, on the 3C GUI | `python -m pytest phase3c/tests_gui_3a` | **39 passed** | run on the real display; version assertion `3C-rc1` |
| Engine parity vs the frozen 3B engine | `python phase3c/scripts/e_parity_3b.py` | 18 cases: 10 byte-identical, 4 differ **only in DE item records**, 1 (E1) only in six highest-level-EXP words, all with identical gameplay state; 3 that 3B refused now succeed | `phase3c/work/e_parity_3b.json`; differences explained in `DE_METADATA_FIDELITY.md` |

### New tests (each tied to a verified defect or guarantee)

| Test | Guards |
|---|---|
| `test_b3_real_3ds_session_keeps_every_de_only_record` | B3 on the 3DS game's own save (a5): 176/176 crystal entries, 0 records differ; 3B engine = 90; gameplay state identical to 3B |
| `test_compacted_deferred_and_same_slot_favourites_return` | marks on compacted, overflow and same-slot items |
| `test_three_platform_cycle` | DE → Wii → 3DS → Wii → DE: marks, Expert Mode/appearance/link unlocks, DE-only flags, FC counters; W progress arrives |
| `test_unchanged_wii_is_byte_identical` | B2 (Wii): unplayed return with compaction = original bytes; 3B refused |
| `test_sold_item_not_revived_and_mark_not_moved` | disposal: no revival, no mark moved |
| `test_identical_replacement_in_same_slot_gets_no_mark` | **3B mis-association defect** (old record given to an identical replacement) |
| `test_newest_survivor_of_a_changed_box_is_unresolved` | the documented ambiguity is reported, not guessed |
| `test_stack_used_partly_keeps_mark_stack_added_to_does_not` | Wii re-ages a stack on add (0x80159024..) |
| `test_duplicate_items_mark_stays_with_its_own_instance` | duplicates never swap metadata |
| `test_equipment_swap_and_gem_change_keep_mark` | equipment changes keep the item's mark |
| `test_metadata_restoration_never_changes_shared_state` | 3C result's gameplay state = 3B result's |
| `test_unresolvable_export_map_restores_nothing` | a map that does not validate restores nothing |
| `test_same_item_keeps_wii_only_bits` / `test_identical_replacement_gets_fresh_record` | Wii-only item bits follow the DE serial (3B kept stale bits) |
| `test_de_3ds_de_unplayed_with_compaction_is_byte_identical` | B2 (3DS) |
| `test_wii_event_changes_the_same_state_as_the_de_event` / `test_3ds_event_and_return` | game-written: the Wii and 3DS games' 154 → 156 events change the same flags as the DE game's |
| `test_cold_reload_keeps_state` | Dolphin cold reload (game-written) |
| `test_return_to_de_reproduces_the_de_games_state_incl_expert_pair` | **E1** (Expert word) on game-written saves |
| `test_after_wii_and_back_the_de_story_continues_to_the_same_state` | DE → Wii (story) → DE → Monado (story) = pure-DE result |
| `test_wii_only_high_flags_are_set_by_normal_wii_play` | Part D finding on the game-written travel save |
| `test_alternating_generations_keep_marks_and_never_revive_disposed_items` | Sync Hub: 5 generations (DE → 3DS with a disposed marked crystal → Wii → DE → 3DS), unchanged re-save in sync, rollback exact; the disposed crystal never returns although the generation-1 anchor sidecar still holds it |

## 2. Packaged application (`phase3c/dist/XCSaveConverter`, PyInstaller, clean folder, no Python on PATH)

| Package test | Result |
|---|---|
| 3C (`phase3c/scripts/package_test_3c.py`): version stamp, B2, B3 on the a5 game save, packaged = source output, window starts | **8/8** |
| 3B (`phase3b/scripts/package_test_3b.py`, unchanged): Sync Hub window automation, xcsync.exe, packaged = source generations, rollback, no game data in the package | **19/19** |
| 3A (`phase3a/scripts/package_test_3a.py`, unchanged): converter window and xcconv.exe, all directions | **32/32** |

## 3. Real game runs (isolated emulators)

See `STORY_PROGRESSION_TESTS.md` for the evidence of each run and `phase3c/scripts/runs_summary.py` for the safety
record (every run: isolated save folder, live saves hashed before/after, the 1,679-file protected manifest checked
before and after). **19 runs** — Monado 14 (c1–c12, L1, m2_3c), Dolphin 3 (d1, d2, dD), Azahar 2 (x1, x2) — none
changed a protected file or a live save (Azahar: its 149 live/Citra files hashed too). Monado wrote only its own cache
(`cacheariants.bin`, once `crash\stall_1.txt`, a frame-stall note) inside its installation folder, as in 2F–3B.
Summary: `phase3c/logs/emulator_runs_3c.json`.

## 4. Failures found and their resolution

| # | Failure | Resolution |
|---|---|---|
| F1 | 3B suite `test_b2_unplayed_return_is_never_converted` failed after the B2 fix | expected: the test pinned the defect; updated to the fixed behaviour (hub decision unchanged) |
| F2 | first metadata test run: the unplayed return was refused by the read-back (B2) | fixed in `xcservice.unchanged_return_diffs` |
| F3 | sidecar `deferred` slot keys are strings after JSON; `de_to_wii.verify` ignored them | keys normalised in the new read-back |
| F4 | Dolphin run d1 produced no captures | Dolphin ignores the screenshot hotkey without window focus; the 3C wrapper sets `HotkeysRequireFocus = False` in the run's own config |
| F5 | Monado tour helper started its warp before the save had loaded (frame 2400) | later runs use `XCDE_WARP` with an explicit frame after the load |
| F6 | `XCDE_ENT_SCAN=5400` printed nothing | the switch takes a frame list and prints positions only for playable characters; NPC positions read with `XCDE_DUMP_MEM` + `memscan.py` |
| F7 | after the E1 fix the 3B replay test failed (generation 4 differs from the 3B bytes) | verified: exactly the 7 Expert-word bytes, equal to the battle EXP; test updated; Monado re-save of the 3C generation 4 recorded as a new game-written fixture |
| F8 | first Wii/DE comparison after the Wii story event showed Shulk's palette[0] 1 vs 2 | not a converter defect: the DE event sets it, the Wii event does not (both game-written) |
