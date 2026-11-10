# Sync Hub test results (Phase 3B, 3B-rc1)

## 1. Summary

| Suite | Command (from the research root) | Result | Log |
|---|---|---|---|
| Sync Hub unit/integration tests | `python -m unittest discover -s phase3b/tests -p "test_*.py"` | **65 / 65 OK** | `phase3b\logs\final_unittest_3b.txt` |
| Sync Hub GUI tests (pytest-qt) | `python -m pytest phase3b/tests_gui` | **18 / 18 passed** | `phase3b\logs\final_gui_3b.txt` |
| 2H + 3A GUI tests on the 3B GUI | `python -m pytest phase3b/tests_gui_3a` | **39 / 39 passed** (one expectation changed: version string 3B-rc1) | `phase3b\logs\final_gui_3a_on_3b.txt` |
| 3A unit tests (engine unchanged) | `python -m unittest discover -s phase3a/tests` | **41 / 41 OK** | `phase3b\logs\final_unittest_3a.txt` |
| 2H unit tests (engine unchanged) | `python -m unittest discover -s tests` | **136 OK (1 skipped, as in 3A)** | `phase3b\logs\final_unittest_2h.txt` |
| Packaged app, Sync Hub (clean folder, no Python) | `python phase3b\scripts\package_test_3b.py <dist> <clean> <json>` | **19 / 19** | `phase3b\logs\package_test_3b.json` |
| Packaged app, unchanged 3A package test | `python phase3a\scripts\package_test_3a.py <dist> <clean> <json>` | **32 / 32** | `phase3b\logs\package_test_3a_on_3b.json` |
| Emulator acceptance cycle | `phase3b\scripts\acceptance.py`, `erun3b.py`, `az3b.py` | **4 generations, 5 emulator sessions, all checks met** | §4 |
| Protected files | `python phase3b\scripts\protect3b.py check final` | **1,226 files unchanged** | `phase3b\manifests` |

## 2. Coverage matrix (brief §11 -> tests)

`test_synchub.py` = U, `test_phase3b_gui.py` = G, package test = P, emulator acceptance = E.

| Case | Where |
|---|---|
| No devices / one / several | U `test_no_devices`, `test_one_device_valid_save_is_start`, many multi-device tests |
| Missing or inaccessible folder; empty folder | U `test_empty_and_missing_folders`; G `test_missing_device_folder_is_shown_not_fatal` |
| Valid / corrupt / truncated saves | U `test_corrupt_and_truncated_saves_are_ignored` (bad CRC Wii, truncated Wii/DE, damaged 3DS) |
| Partial transfers (Syncthing temp files) | U `test_syncthing_temp_file_means_waiting`, `test_new_file_still_arriving_via_temp_only`; G `test_waiting_disables_sync` |
| Files changing during scan; just modified | U `test_file_changing_during_scan_is_pending`, `test_recently_modified_file_is_pending` |
| Same save on several devices (incl. as 3DS) | U `test_same_save_on_several_devices_counts_once` |
| Generated output returned unchanged | U `test_generated_output_returned_unchanged_is_in_sync`; E step s3/s4 device states |
| Save with only new timestamp / re-save | U `test_resave_without_play_does_not_trigger`, `test_game_resave_from_3a_run_a1_is_not_progress`, `..._a5_...`, replay (Monado re-save); E step s5 |
| New gameplay on one / two devices | U `test_new_gameplay_on_one_device` (3DS game save), `test_new_gameplay_on_two_devices_is_a_conflict`; E s2–s4 |
| Another playthrough | U `test_save_from_another_playthrough` |
| Stale / missing / wrong sidecar | U `test_incorrect_sidecar_association_is_refused` (edited anchor sidecar -> refused) |
| Unavailable destination template | U `test_missing_template_blocks` |
| Scan is read-only | U `test_scan_is_read_only`; P "window scan is read-only" |
| Wii / DE / 3DS source -> all three | U `test_wii_source_to_all_three`, `test_de_source_to_all_three_with_overflow`, `test_3ds_source_to_all_three`; E gens 1–4 |
| Parity with the 3A engine | U `test_outputs_match_the_3a_engine_for_identical_inputs`, DE parity in `test_de_source...`, 3DS -> DE return parity in `test_alternating...`; P packaged = source |
| Repeated Sync without new gameplay | U `test_repeated_sync_without_new_gameplay` |
| Alternating platforms, DE-only data across Wii/3DS hops | U `test_alternating_platforms_keep_de_only_state` (5 generations, Expert Mode s232); E (Monado changes kept through 3DS and Wii generations) |
| Items added/removed, EXP, quests | U `test_items_exp_quests_follow_the_source` (synthetic edits); E (3DS battle EXP +44 carried to DE) |
| Inventory overflow | U `test_de_source_to_all_three_with_overflow` (269 items kept for DE, exact count check) |
| Unsupported party (Fiora 8 / guests) | U `test_unsupported_party_blocks_and_changes_nothing`; G `test_blocked_platform_offers_partial_update` |
| Explicit partial sync | U `test_explicit_partial_sync_is_labelled_partial`; G same |
| Incomplete conversion failure | U `test_engine_refusal_during_conversion`, `test_validation_catches_a_wrong_output`, failure at 8 points |
| Interrupted publication | U `test_interrupted_publication_is_reported_and_finished`, `test_publication_failure_after_some_files`; G `test_interrupted_publication_offers_finish_publishing` |
| Application crash | U `test_application_killed_at_each_stage` (real process kill at 8 points) |
| Rollback | U `test_rollback_to_previous_generation`, `test_rollback_then_continue_and_anchor_follows`; G `test_history_dialog_and_rollback`; P rollback |
| Two devices independently; story branch; inventory/quest differences | U `TestConflicts` (synthetic branches with story +1, items, flags), replay `test_two_wii_family_branches...` (game-written) |
| Old save returning after a newer sync | U `test_old_save_returning_after_newer_sync`, `test_played_on_an_older_copy_is_divergent_even_with_more_play_time` |
| Malformed lineage / history | U `test_damaged_history_is_reported_not_guessed`, `test_malformed_pointer`; G `test_damaged_history_shows_error_and_blocks` |
| Divergent branch only by explicit choice; other branch recoverable | U `test_choice_keeps_the_other_branch_recoverable`, `test_divergent_save_can_only_be_continued_explicitly`; G `test_conflict_requires_explicit_choice`; P conflict steps |
| Lock / duplicate submissions / cancel | U `test_second_window_cannot_sync_at_the_same_time`, `test_stale_lock...`, `test_cancel_before_commit`; G `test_duplicate_submissions_are_ignored`, `test_cancel_before_commit` |
| Initial setup, settings persistence | G `test_welcome_and_first_run_setup`, `test_settings_persist_and_startup_scan_runs`; U `TestSetup` |
| Automatic startup scan, Scan Again, keyboard | G `test_settings_persist...`, `test_scan_again_picks_up_new_files`, `test_keyboard_mnemonics_and_f5`, Ctrl+Enter in `test_successful_sync...` |
| Light/dark, DPI | G `test_light_and_dark`; P scales 1.5 and 2; screenshots light/dark × 1/1.5 (`phase3b\screenshots`) |
| B1 Wii heap junk | U `test_b1_wii_save_with_heap_junk_converts_to_3ds` |
| B2 unplayed return | U `test_b2_unplayed_return_is_never_converted` |

Synthetic fixtures (flag/money/EXP/item/story edits with checksums recomputed, `hubfix.play_wii` / `play_de`) are
used where no game-written continuation exists and are marked as such in the tests; every decision that matters for
real use was also exercised with game-written saves (3A runs a1, a2, a5; 3B runs m1, a1, w1, m2; the user's saves).

## 3. Failure injection and crash results

* Exception at `read`, `convert`, `sidecar`, `stage`, `validate`, `manifest`, `commit`, `pointer`: generation 1
  stays current; hub tree unchanged except staging (and, for `pointer`, a prepared folder that the next Sync sets
  aside); next Sync = generation 2, complete.
* Process killed (`os._exit`) at convert, stage, validate, commit, pointer, after-commit, publish, publish-ready:
  before the pointer -> generation 1 current, interruption reported, next Sync recovers; after -> generation 2
  current, ready folders reported outdated, Finish publishing completes them.

## 4. Emulator acceptance (2026-11-08)

Hub `phase3b\runs\acceptance\Xenoblade Sync`, devices Windows desktop (DE), Odin 2 Mini (Wii), New 3DS (3DS) with
simulated Syncthing folders; DE and 3DS templates. Every Sync Hub step through the real window
(`--sync-automate`; results and window captures in `phase3b\runs\acceptance\steps\`).

| Step | Emulator / Sync Hub | Result |
|---|---|---|
| s1 | user's Wii save (story 150, 22:01:57) on Odin -> Sync All | gen 1, all three platforms, 5.8 s; DE output = the 2F-validated `1028f718…` |
| m1 | **Monado** (isolated, run `m1_gen1_walk_save`): load gen-1 DE | Eryth Sea, Chapter Eight, 22:02, party Shulk 52 / Dunban 51 / Riki 51 / Sharla 52 / Reyn 52 / Melia 51; walked ~50 units; saved |
| s2 | Monado's save -> Windows desktop incoming; restart, scan | "New progress found on Windows desktop." -> gen 2 (DE -> Wii return onto gen 1, 3DS) |
| a1 | **Azahar** (run `a1_gen2_3ds`): load gen-2 3DS | load list Eryth Sea Lv 52 22:02; field: Shulk 52 HP 4484, Dunban 51, Riki 51; **battle won** (Lv 32 Perna Eluca: +44 EXP, 15 AP, 1 SP each); saved (22:05) |
| s3 | 3DS save -> New 3DS incoming; scan | "New progress found on New 3DS." -> gen 3: DE = return onto **gen 2's Monado save** (Shulk EXP 12,295 -> 12,339; Monado's link unlocks kept; DE-only unchanged); Wii = the 3DS state exactly |
| w1 | **Dolphin** (run `w1_gen3_walk_save`): load gen-3 Wii | party menu: same HP as 3DS, 375,150 G, 22:06; walked; saved |
| s4 | Dolphin save -> Odin incoming; scan | "New progress found on Odin 2 Mini." -> gen 4 (DE return onto gen 2 again; 3DS with gen 3's picture) |
| m2 | **Monado** (run `m2_gen4_load_save`): load gen-4 DE (no .tmb provided) | loads; Chapter Eight, 22:07, full party; saved |
| a2 | **Azahar** (run `a2_gen4_3ds_load`): load gen-4 3DS | load list shows Dolphin's save time; field and party menu: same party/HP, 375,150 G |
| s5 | Monado's no-play re-save -> desktop incoming; scan | first: "New progress" (defect B6: height +0.001) -> fixed -> "All available saves match the last sync.", Sync disabled |

Isolation: every run on copies (Monado `LARECOMP_SAVE_DIR` + mount check, Dolphin own user dir + NANDRootPath +
watchdog, Azahar portable copy); live Monado save folder and 149 Azahar/Citra files unchanged; the 1,226-file 3B
manifest unchanged after each run. Monado wrote only to its own `cache\` and `crash\stall_1.txt` inside its
installation (run manifests list them), as in earlier phases.

The whole cycle is replayed from the game-written saves in `TestAcceptanceReplay` (generation 4's DE save is
reproduced byte for byte).

## 5. Safety verification

* `phase3b\manifests\protected_start.json` (1,226 files) vs final check: **unchanged**.
* `release_candidate_3A\SHA256SUMS.txt`: 312/312 OK at the start and at the end.
* Syncthing `config.xml`: unchanged (in the manifest); no Syncthing folder or share was created or modified.
* All writes inside `C:\Dev\XC_Wii_to_DE_Research` (hubs, runs, clean package folders).
