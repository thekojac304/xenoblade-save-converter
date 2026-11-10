# Test coverage matrix (Phase 2F, converter 2F-rc1)

Full suite: **109 tests, OK (skipped=1)** in 223 s
(`python -m unittest discover -s tests -v`, log `validation/full_suite_final.log`). The 40 Phase 2C–2E tests are
included. The table below lists the 68 Phase 2F checks with their actual result from that log.

Data kinds: **game-generated** (written by Monado or the Wii game in an isolated run), **real save data** (your saves
or the public archive, unmodified), **code (static)** (executable or tables), **synthetic** (a real save with
game-plausible edits; tests logic, not game behaviour).

## Feature summary

| Feature | Proven by static checks | Proven in a game | Synthetic only | Unverified | Refused / incompatible |
|---|---|---|---|---|---|
| Wii → DE conversion (your save) | read-back, byte round trip | 2E: load, combat, travel, story 150→156; 2F: load + save of the 2F file | — | story beyond 156 | — |
| DE → Wii conversion | read-back + closure check, 6 game-generated checkpoints | 2E: load, combat, travel, save; 2F: story-232 DE save loads, saves, returns | — | Wii story events after export | Fiora (8), guests, DE-only maps, v7 |
| Re-import (3-way, sidecar) | properties, 4 generations | 2E chain; 2F story-232 cycle through both games | Wii pickups (aging rule from code) | real Wii pickup + re-import | stale / divergent without branch |
| Item acquisition order | code (aging, renumbering) | 2F file loads and saves | random pickups | DE "newest" sort viewed on screen | — |
| Inventory capacity / overflow | code formula, all boxes × 6 sizes | story-232: 46 deferred items came back after a Wii save | — | full 150-item Wii box | — |
| Equipment, gems, crystals | references, compaction, sockets, cylinders | story-232 equipment on the Wii Party screen | extreme gem values | gem craft completed in a game | invalid gem/crystal values |
| Characters, levels, EXP | boundaries | 2E: level-ups from combat | — | level 99 in a game | EXP ≥ next level, levels 0 / 100 |
| Expert Mode | real data from 6 game-generated saves round trip | story-232 cycle kept reserve / highest | level-down state | Expert menu used after conversion | — |
| Arts, skills, links, unlocks | random states | Monado recomputed one unlock (expected) | — | link costs paid after conversion | — |
| Fiora skill copy (record 8) | real saves hold the copy | Dolphin d1 (bug) → d2 (fixed) | — | — | — |
| Quests | every quest × objective × value; 90 / 221 / 287 | 2E: Quest Log coherent | partial kill progress | quest completed on the Wii after export | invalid quest bytes |
| Story / world flags | flags × 2 cycles; Heart-to-Heart block (+500) checked on real DE data | 2E story events | — | Wii story events | — |
| Wii flags 0x352C–0x36CF | kept Wii-side (lineage) | set by Dolphin in 2E | — | meaning | no DE slot |
| Clock, maps, minimap | boundaries, all 28 Wii maps | 2E: clock / minimap shown | — | — | DE-only maps |
| Sidecar safety | corrupt / forged / stale / divergent / other playthrough | — | all | — | — |
| Filesystem safety | failure injection, junction, markers, case, traversal | — | all | symlinks (need Developer Mode) | live folders |
| Packaging / CLI | clean-directory test 10/10, help, exit codes | — | — | GUI (not built) | — |

## Phase 2F checks (actual results)

| ID | Feature | Fixture provenance | Data | Expected | Actual | Result | Evidence | Rev | Caveats |
|---|---|---|---|---|---|---|---|---|---|
| A-01 | A2 determinism | monado01, template | real save data | same inputs -> same bytes (DE, Wii, sidecar) | as expected | PASS | `Determinism.test_same_inputs_same_bytes` | 2F-rc1 |  |
| A-02 | A1 Wii->DE->Wii | monado01, monado03 + 12 seeded Wii progressions | synthetic | byte-identical, read-back clean | as expected | PASS | `RoundTrips.test_wii_de_wii_byte_identical_for_random_wii_states` | 2F-rc1 | progressions synthetic |
| A-03 | A1 DE->Wii->DE (no sidecar) | DE conversion of monado01 + 12 seeded DE progressions | synthetic | shared state equal | as expected | PASS | `RoundTrips.test_de_wii_de_foreign_path_canonical` | 2F-rc1 | lossy award projection excluded |
| A-04 | A1 repeated conversions | monado01 | real save data | no growth; fixpoint after 1 cycle | as expected | PASS | `RoundTrips.test_repeated_conversion_is_a_fixpoint` | 2F-rc1 |  |
| A-05 | A1 DE->Wii->Wii play->DE | 12 seeded Wii progressions (minimised on failure) | synthetic | result = Wii state; DE-only unchanged; serials unique | as expected | PASS | `DeltaReimport.test_random_wii_progress_reimports_exactly` | 2F-rc1 |  |
| A-06 | B3 Wii item aging | monado01-derived; pickups aged per code 0x80159080 | synthetic | descent passes; old DE serials kept; new ones newest | as expected | PASS | `DeltaReimport.test_pickups_age_every_wii_item_and_still_reimport` | 2F-rc1 | aging rule from code, not observed in-game |
| A-07 | A1/E1 alternating 4 generations | monado01 + seeded progress both sides | synthetic | lineage id stable, generation +1, money/levels follow | as expected | PASS | `Alternation.test_four_generations_alternating_with_progress` | 2F-rc1 |  |
| A-08 | A2 metamorphic Wii->DE | monado01 single mutations | synthetic | only the mutated canonical fields change | as expected | PASS | `Locality.test_single_changes_wii_to_de` | 2F-rc1 |  |
| A-09 | A2 metamorphic DE->Wii | DE conversion single mutations | synthetic | only the mutated canonical fields change | as expected | PASS | `Locality.test_single_changes_de_to_wii` | 2F-rc1 |  |
| A-10 | A2 invalid reference | synthetic | synthetic | refused before any output | as expected | PASS | `Locality.test_invalid_reference_rejected_before_any_output` | 2F-rc1 |  |
| B-01 | B1 Wii capacities | code 0x80158490 (re-read) | code (static) | 10*bits+60+min(bonus,30); fixed boxes 300/200/240; equipment <=150 | as expected | PASS | `Capacity.test_capacity_formula_matches_code` | 2F-rc1 |  |
| B-02 | B1 0/1/cap-1/cap/cap+1/cap+50 x 8 boxes | synthetic inventories on the user's DE conversion | synthetic | fit / refuse / defer+restore | as expected | PASS | `Capacity.test_boundaries_every_category` | 2F-rc1 |  |
| B-03 | B1/B2 compaction + references | equipped weapon DE slot 300, gem slot 450 | synthetic | references follow the moved instances | as expected | PASS | `Capacity.test_compaction_remaps_equipment_and_gem_references` | 2F-rc1 |  |
| B-04 | B1 overflow policy | synthetic | synthetic | equipped items stay in the Wii file | as expected | PASS | `Capacity.test_equipped_items_beyond_capacity_are_never_deferred` | 2F-rc1 |  |
| B-05 | B2 sockets/gems | 3 sockets, 0 sockets, fixed gem, loose gem at rank-S max | synthetic | round trip equal | as expected | PASS | `EquipmentAndGems.test_sockets_fixed_and_removable_gems` | 2F-rc1 |  |
| B-06 | B2 empty slots, inactive chars | user's DE conversion | synthetic | empty slot stays empty; absent chars hold none | as expected | PASS | `EquipmentAndGems.test_empty_equipment_slots_and_absent_characters` | 2F-rc1 |  |
| B-07 | B2 gem limits | synthetic | synthetic | refused both directions | as expected | PASS | `EquipmentAndGems.test_gem_values_beyond_field_widths_refused` | 2F-rc1 |  |
| B-08 | B2 crystals | user's 159 crystals | real save data | byte-identical; unmatched drop crystal refused | as expected | PASS | `EquipmentAndGems.test_crystals_round_trip_all_kinds` | 2F-rc1 |  |
| B-09 | B3 DE-only ids | synthetic | synthetic | unequipped deferred, equipped refused | as expected | PASS | `Identity.test_de_only_ids_deferred_or_refused` | 2F-rc1 |  |
| B-10 | B3 invalid ids/qty, max stack | synthetic | synthetic | qty 0/100 and unknown id refused, 99 kept | as expected | PASS | `Identity.test_invalid_ids_and_quantities` | 2F-rc1 |  |
| B-11 | B3 acquisition order | user's saves | real save data | order preserved both ways; serials unique; counter above | as expected | PASS | `Identity.test_acquisition_order_both_directions` | 2F-rc1 |  |
| C-01 | D1/C3 checkpoint matrix (story 20-269) | 6 public DE saves re-saved by Monado (fixtures/real) | game-generated | exact without play; with Wii play equal to Wii state; Expert/DE-only data intact | as expected | PASS | `CheckpointMatrix.test_matrix` | 2F-rc1 | Wii play synthetic |
| C-02 | C3 Expert level-down | s232 (game-generated) edited | synthetic | highest/reserve untouched; repeated exports identical | as expected | PASS | `CheckpointMatrix.test_expert_level_down_state` | 2F-rc1 | level-down synthetic |
| C-03 | C2 boundaries | synthetic | synthetic | level 1/2/50/99, EXP edges, AP/coins min/max survive | as expected | PASS | `CharacterBoundaries.test_level_exp_ap_coin_boundaries_round_trip` | 2F-rc1 |  |
| C-04 | C2 invalid EXP | synthetic | synthetic | refused both directions | as expected | PASS | `CharacterBoundaries.test_exp_at_threshold_refused_both_ways` | 2F-rc1 |  |
| C-05 | C1 Fiora(8)/guests | synthetic | synthetic | refused both directions | as expected | PASS | `CharacterBoundaries.test_unsupported_party_members_refused_both_ways` | 2F-rc1 | no real post-rejoin save available |
| C-06 | C1 split party / rejoin | s269 (game-generated, Shulk alone) | game-generated | absent members keep progression; rejoin imports | as expected | PASS | `CharacterBoundaries.test_temporarily_unavailable_and_rejoin` | 2F-rc1 | rejoin synthetic |
| C-07 | C4 arts/skills/links | 8 seeded states | synthetic | round trip equal; talent pairs equal | as expected | PASS | `ArtsSkillsLinks.test_random_valid_progression_states` | 2F-rc1 |  |
| C-08 | C4 unlocked link slots | synthetic | synthetic | unlocked slots set on the Wii | as expected | PASS | `ArtsSkillsLinks.test_unlocked_empty_link_slots_reach_the_wii` | 2F-rc1 |  |
| C-09 | C4 template leak | template edited | synthetic | no unlock inherited | as expected | PASS | `ArtsSkillsLinks.test_first_export_does_not_inherit_template_link_unlocks` | 2F-rc1 |  |
| D-01 | D2 every quest x objective x value | JNL_quest tables | code (static) | all valid encodings survive | as expected | PASS | `Quests.test_counter_encodings_round_trip_every_quest` | 2F-rc1 | sub-quest objectives (type 4) skipped |
| D-02 | D2 quests 90/221/287 | monado01 | real save data | exact counters both ways; partial kill progress | as expected | PASS | `Quests.test_regression_quests_90_221_287` | 2F-rc1 |  |
| D-03 | D2 quest states | monado01 + accept | real save data | states verbatim; completed not reopened; accepted not done | as expected | PASS | `Quests.test_quest_states_completed_stay_completed` | 2F-rc1 |  |
| D-04 | D3 clock/day | synthetic | synthetic | 0:00, 23:59, day 1/65535 | as expected | PASS | `WorldState.test_clock_and_day_boundaries` | 2F-rc1 |  |
| D-05 | D3 maps | Wii FLD_maplist (28 maps) | code (static) | all Wii maps round trip; DE-only maps refused | as expected | PASS | `WorldState.test_every_wii_map_round_trips` | 2F-rc1 |  |
| D-06 | D3 world flags x2 cycles | synthetic | synthetic | landmarks, collectopaedia, affinity flags survive | as expected | PASS | `WorldState.test_world_flags_survive_two_cycles` | 2F-rc1 |  |
| E-01 | E1 export/play/re-import x2 via CLI | monado01 + synthetic sessions | synthetic | DE-only item parked 2 sessions per cycle, never duplicated | as expected | PASS | `NormalUse.test_six_step_cycle_through_cli` | 2F-rc1 |  |
| E-02 | E2 missing/corrupt/schema | synthetic | synthetic | refused, nothing written | as expected | PASS | `BadSidecars.test_missing_corrupted_and_unsupported` | 2F-rc1 |  |
| E-03 | E2 forged/inconsistent | synthetic | synthetic | refused at load | as expected | PASS | `BadSidecars.test_internally_inconsistent_sidecars` | 2F-rc1 |  |
| E-04 | E2 wrong direction / no current save | synthetic | synthetic | refused with explanation | as expected | PASS | `BadSidecars.test_wrong_direction_and_missing_current` | 2F-rc1 |  |
| E-05 | E2 other slot / playthrough | user saves | real save data | refused | as expected | PASS | `BadSidecars.test_other_slot_and_other_playthrough` | 2F-rc1 |  |
| E-06 | E2 altered Wii save | synthetic | synthetic | checksum refusal | as expected | PASS | `BadSidecars.test_altered_wii_save` | 2F-rc1 |  |
| E-07 | E2 stale sidecar (2E defect) | synthetic chain | synthetic | refused with/without branch; sold item stays sold | as expected | PASS | `StaleSidecar.test_old_sidecar_is_refused_even_with_branch` | 2F-rc1 |  |
| E-08 | E3 divergence | synthetic | synthetic | refused | as expected | PASS | `Divergence.test_refused_without_branch` | 2F-rc1 |  |
| E-09 | E3 branch wii | synthetic | synthetic | Wii state only, no DE-branch flags/money/deletions | as expected | PASS | `Divergence.test_branch_wii_keeps_wii_state_without_contamination` | 2F-rc1 |  |
| E-10 | E3 branch de (CLI) | synthetic | synthetic | DE state only | as expected | PASS | `Divergence.test_branch_de_keeps_de_state_without_contamination` | 2F-rc1 |  |
| E-11 | E4 newer DE-only state | synthetic | synthetic | kept | as expected | PASS | `Divergence.test_only_de_exclusive_change_is_kept` | 2F-rc1 |  |
| E-12 | E4 restoration | synthetic | synthetic | Expert, cosmetics, Noponstones, DE-only item/flag, FC byte kept; Wii progress wins | as expected | PASS | `Restoration.test_de_exclusive_state_survives_and_wii_progress_wins` | 2F-rc1 |  |
| F-01 | F1 Wii container | monado01 damaged | synthetic | refused, no output, no traceback | as expected | PASS | `CorruptInput.test_wii_corruptions` | 2F-rc1 |  |
| F-02 | F1 Wii impossible values | synthetic | synthetic | refused | as expected | PASS | `CorruptInput.test_wii_out_of_range_values_with_valid_crc` | 2F-rc1 |  |
| F-03 | F1 DE invalid states | synthetic + public v7 | synthetic | refused | as expected | PASS | `CorruptInput.test_de_corruptions_and_invalid_states` | 2F-rc1 |  |
| F-04 | F1 fuzz 60 bit-flip cases | seed 2026 | synthetic | clean success or clean refusal only | as expected | PASS | `CorruptInput.test_random_bit_flips` | 2F-rc1 |  |
| F-05 | F2 failure injection | 6 stages | synthetic | no output, no staging left | as expected | PASS | `Transactional.test_failure_injection_every_stage` | 2F-rc1 |  |
| F-06 | F2 manifest / no overwrite | monado01 | real save data | hashes match; second run refused | as expected | PASS | `Transactional.test_manifest_matches_written_bytes_and_no_overwrite` | 2F-rc1 |  |
| F-07 | F2 interrupted run | synthetic staging | synthetic | next run unaffected; cleanup-staging | as expected | PASS | `Transactional.test_interrupted_run_recovery` | 2F-rc1 |  |
| F-08 | H1 dry run | monado01 | real save data | nothing written | as expected | PASS | `Transactional.test_dry_run_and_report` | 2F-rc1 |  |
| F-09 | F3 markers/traversal/case | fake trees | synthetic | refused | as expected | PASS | `PathSafety.test_live_markers_traversal_and_case` | 2F-rc1 |  |
| F-10 | F3 junction/symlink | fake trees | synthetic | refused | skipped | SKIPPED | `PathSafety.test_junction_and_symlink_into_live_tree` | 2F-rc1 | symlink part skipped without Developer Mode |
| F-11 | F3 junction output | fake tree | synthetic | refused | as expected | PASS | `PathSafety.test_output_folder_itself_a_junction` | 2F-rc1 |  |
| F-12 | F3/H2 other cwd | monado01 | real save data | works | as expected | PASS | `PathSafety.test_unexpected_working_directory` | 2F-rc1 |  |
| F-13 | F3 slot names | synthetic | synthetic | refused | as expected | PASS | `PathSafety.test_slot_names` | 2F-rc1 |  |
| H-01 | H1 help | - | code (static) | complete help | as expected | PASS | `CommandLine.test_help_lists_every_command` | 2F-rc1 |  |
| H-02 | H1 messages | monado01 | real save data | clear messages, sidecar notice | as expected | PASS | `CommandLine.test_clear_messages` | 2F-rc1 |  |
| G-01 | C1 Fiora record 8 copy | monado01, monado03 | real save data | records 3/8 skill object identical | as expected | PASS | `FioraSkillCopy.test_real_saves_hold_the_copy` | 2F-rc1 |  |
| G-02 | C1 Fiora revert (evidence) | Dolphin run d1 (game-written) | game-generated | game restored record 3 from record 8 | as expected | PASS | `FioraSkillCopy.test_game_reverts_record3_from_record8` | 2F-rc1 |  |
| G-03 | C1 Fiora fix | s020 game-generated + edit | synthetic | copy synced; all checkpoints | as expected | PASS | `FioraSkillCopy.test_export_keeps_copy_in_step` | 2F-rc1 |  |
| G-04 | B2 DE crafted cylinder | s241 (game-generated) | game-generated | exported as kind 3, restored exactly | as expected | PASS | `CraftedCylinders.test_de_crafted_cylinder_round_trip` | 2F-rc1 |  |
| G-05 | Cross-game acceptance | Dolphin run d2 (game-written Wii file) | game-generated | only clock/time/position differ; 1256 items; Expert intact | as expected | PASS | `GameWrittenWiiFile.test_wii_resave_reimports_exactly_apart_from_play` | 2F-rc1 |  |

## Game runs (Phase 2F)

| Run | Emulator | Isolated | Game wrote a save | Evidence |
|---|---|---|---|---|
| g1_s020_v7load | monado | yes | yes (new slot) | `phase2f/runs/monado/g1_s020_v7load` |
| g1_s206_v7load | monado | yes | yes (new slot) | `phase2f/runs/monado/g1_s206_v7load` |
| g1_s232_v7load | monado | yes | yes | `phase2f/runs/monado/g1_s232_v7load` |
| g1_s241_v7load | monado | yes | yes | `phase2f/runs/monado/g1_s241_v7load` |
| g1_s258_v7load | monado | yes | yes | `phase2f/runs/monado/g1_s258_v7load` |
| g1_s269_v7load | monado | yes | yes | `phase2f/runs/monado/g1_s269_v7load` |
| m2_user_2f | monado | yes | yes | `phase2f/runs/monado/m2_user_2f` |
| m3_s232_back_from_wii | monado | yes | yes | `phase2f/runs/monado/m3_s232_back_from_wii` |
| d1_s232_load_save | dolphin | yes | yes | `phase2f/runs/dolphin/d1_s232_load_save` |
| d2_s232_fiora_fix | dolphin | yes | yes | `phase2f/runs/dolphin/d2_s232_fiora_fix` |

The g1_s020 and g1_s206 runs saved into a new slot (bfsgame02 / bfsgame01), so the harness's slot-00 check shows no
change. The files were collected from those slots (`phase2f/fixtures/real/PROVENANCE.md`).

## Remaining gaps

- Wii story progression after a DE → Wii export; a quest completed on the Wii after an export.
- A real Wii item pickup followed by a re-import (the aging rule is from code; the logic is tested synthetically).
- Fiora's second form and guests (refused; no fixture).
- No in-game check of DE's "newest" sort order on screen.
- Symlink output paths (junctions tested).
