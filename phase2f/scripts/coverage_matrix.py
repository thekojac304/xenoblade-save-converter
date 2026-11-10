"""Build TEST_COVERAGE_MATRIX data: curated metadata per Phase 2F test joined with the ACTUAL result of a verbose
unittest run (phase2f/results/<log>). Game runs come from phase2f/runs/*/run_manifest.json.

  python coverage_matrix.py <verbose log> <out.json> <out.md>
"""
import json
import os
import re
import sys

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REV = "2F-rc1"
S, G, C, D = "synthetic", "game-generated", "code (static)", "real save data"
# id: (test, workstream feature, fixture provenance, kind, expected, caveat)
M = [
    ("A-01", "Determinism.test_same_inputs_same_bytes", "A2 determinism", "monado01, template", D,
     "same inputs -> same bytes (DE, Wii, sidecar)", ""),
    ("A-02", "RoundTrips.test_wii_de_wii_byte_identical_for_random_wii_states", "A1 Wii->DE->Wii",
     "monado01, monado03 + 12 seeded Wii progressions", S, "byte-identical, read-back clean", "progressions synthetic"),
    ("A-03", "RoundTrips.test_de_wii_de_foreign_path_canonical", "A1 DE->Wii->DE (no sidecar)",
     "DE conversion of monado01 + 12 seeded DE progressions", S, "shared state equal", "lossy award projection excluded"),
    ("A-04", "RoundTrips.test_repeated_conversion_is_a_fixpoint", "A1 repeated conversions", "monado01", D,
     "no growth; fixpoint after 1 cycle", ""),
    ("A-05", "DeltaReimport.test_random_wii_progress_reimports_exactly", "A1 DE->Wii->Wii play->DE",
     "12 seeded Wii progressions (minimised on failure)", S, "result = Wii state; DE-only unchanged; serials unique",
     ""),
    ("A-06", "DeltaReimport.test_pickups_age_every_wii_item_and_still_reimport", "B3 Wii item aging",
     "monado01-derived; pickups aged per code 0x80159080", S, "descent passes; old DE serials kept; new ones newest",
     "aging rule from code, not observed in-game"),
    ("A-07", "Alternation.test_four_generations_alternating_with_progress", "A1/E1 alternating 4 generations",
     "monado01 + seeded progress both sides", S, "lineage id stable, generation +1, money/levels follow", ""),
    ("A-08", "Locality.test_single_changes_wii_to_de", "A2 metamorphic Wii->DE", "monado01 single mutations", S,
     "only the mutated canonical fields change", ""),
    ("A-09", "Locality.test_single_changes_de_to_wii", "A2 metamorphic DE->Wii", "DE conversion single mutations", S,
     "only the mutated canonical fields change", ""),
    ("A-10", "Locality.test_invalid_reference_rejected_before_any_output", "A2 invalid reference", "synthetic", S,
     "refused before any output", ""),
    ("B-01", "Capacity.test_capacity_formula_matches_code", "B1 Wii capacities", "code 0x80158490 (re-read)", C,
     "10*bits+60+min(bonus,30); fixed boxes 300/200/240; equipment <=150", ""),
    ("B-02", "Capacity.test_boundaries_every_category", "B1 0/1/cap-1/cap/cap+1/cap+50 x 8 boxes",
     "synthetic inventories on the user's DE conversion", S, "fit / refuse / defer+restore", ""),
    ("B-03", "Capacity.test_compaction_remaps_equipment_and_gem_references", "B1/B2 compaction + references",
     "equipped weapon DE slot 300, gem slot 450", S, "references follow the moved instances", ""),
    ("B-04", "Capacity.test_equipped_items_beyond_capacity_are_never_deferred", "B1 overflow policy", "synthetic", S,
     "equipped items stay in the Wii file", ""),
    ("B-05", "EquipmentAndGems.test_sockets_fixed_and_removable_gems", "B2 sockets/gems",
     "3 sockets, 0 sockets, fixed gem, loose gem at rank-S max", S, "round trip equal", ""),
    ("B-06", "EquipmentAndGems.test_empty_equipment_slots_and_absent_characters", "B2 empty slots, inactive chars",
     "user's DE conversion", S, "empty slot stays empty; absent chars hold none", ""),
    ("B-07", "EquipmentAndGems.test_gem_values_beyond_field_widths_refused", "B2 gem limits", "synthetic", S,
     "refused both directions", ""),
    ("B-08", "EquipmentAndGems.test_crystals_round_trip_all_kinds", "B2 crystals", "user's 159 crystals", D,
     "byte-identical; unmatched drop crystal refused", ""),
    ("B-09", "Identity.test_de_only_ids_deferred_or_refused", "B3 DE-only ids", "synthetic", S,
     "unequipped deferred, equipped refused", ""),
    ("B-10", "Identity.test_invalid_ids_and_quantities", "B3 invalid ids/qty, max stack", "synthetic", S,
     "qty 0/100 and unknown id refused, 99 kept", ""),
    ("B-11", "Identity.test_acquisition_order_both_directions", "B3 acquisition order", "user's saves", D,
     "order preserved both ways; serials unique; counter above", ""),
    ("C-01", "CheckpointMatrix.test_matrix", "D1/C3 checkpoint matrix (story 20-269)",
     "6 public DE saves re-saved by Monado (fixtures/real)", G,
     "exact without play; with Wii play equal to Wii state; Expert/DE-only data intact", "Wii play synthetic"),
    ("C-02", "CheckpointMatrix.test_expert_level_down_state", "C3 Expert level-down", "s232 (game-generated) edited",
     S, "highest/reserve untouched; repeated exports identical", "level-down synthetic"),
    ("C-03", "CharacterBoundaries.test_level_exp_ap_coin_boundaries_round_trip", "C2 boundaries", "synthetic", S,
     "level 1/2/50/99, EXP edges, AP/coins min/max survive", ""),
    ("C-04", "CharacterBoundaries.test_exp_at_threshold_refused_both_ways", "C2 invalid EXP", "synthetic", S,
     "refused both directions", ""),
    ("C-05", "CharacterBoundaries.test_unsupported_party_members_refused_both_ways", "C1 Fiora(8)/guests",
     "synthetic", S, "refused both directions", "no real post-rejoin save available"),
    ("C-06", "CharacterBoundaries.test_temporarily_unavailable_and_rejoin", "C1 split party / rejoin",
     "s269 (game-generated, Shulk alone)", G, "absent members keep progression; rejoin imports", "rejoin synthetic"),
    ("C-07", "ArtsSkillsLinks.test_random_valid_progression_states", "C4 arts/skills/links", "8 seeded states", S,
     "round trip equal; talent pairs equal", ""),
    ("C-08", "ArtsSkillsLinks.test_unlocked_empty_link_slots_reach_the_wii", "C4 unlocked link slots", "synthetic",
     S, "unlocked slots set on the Wii", ""),
    ("C-09", "ArtsSkillsLinks.test_first_export_does_not_inherit_template_link_unlocks", "C4 template leak",
     "template edited", S, "no unlock inherited", ""),
    ("D-01", "Quests.test_counter_encodings_round_trip_every_quest", "D2 every quest x objective x value",
     "JNL_quest tables", C, "all valid encodings survive", "sub-quest objectives (type 4) skipped"),
    ("D-02", "Quests.test_regression_quests_90_221_287", "D2 quests 90/221/287", "monado01", D,
     "exact counters both ways; partial kill progress", ""),
    ("D-03", "Quests.test_quest_states_completed_stay_completed", "D2 quest states", "monado01 + accept", D,
     "states verbatim; completed not reopened; accepted not done", ""),
    ("D-04", "WorldState.test_clock_and_day_boundaries", "D3 clock/day", "synthetic", S, "0:00, 23:59, day 1/65535", ""),
    ("D-05", "WorldState.test_every_wii_map_round_trips", "D3 maps", "Wii FLD_maplist (28 maps)", C,
     "all Wii maps round trip; DE-only maps refused", ""),
    ("D-06", "WorldState.test_world_flags_survive_two_cycles", "D3 world flags x2 cycles", "synthetic", S,
     "landmarks, collectopaedia, affinity flags survive", ""),
    ("E-01", "NormalUse.test_six_step_cycle_through_cli", "E1 export/play/re-import x2 via CLI",
     "monado01 + synthetic sessions", S, "DE-only item parked 2 sessions per cycle, never duplicated", ""),
    ("E-02", "BadSidecars.test_missing_corrupted_and_unsupported", "E2 missing/corrupt/schema", "synthetic", S,
     "refused, nothing written", ""),
    ("E-03", "BadSidecars.test_internally_inconsistent_sidecars", "E2 forged/inconsistent", "synthetic", S,
     "refused at load", ""),
    ("E-04", "BadSidecars.test_wrong_direction_and_missing_current", "E2 wrong direction / no current save",
     "synthetic", S, "refused with explanation", ""),
    ("E-05", "BadSidecars.test_other_slot_and_other_playthrough", "E2 other slot / playthrough", "user saves", D,
     "refused", ""),
    ("E-06", "BadSidecars.test_altered_wii_save", "E2 altered Wii save", "synthetic", S, "checksum refusal", ""),
    ("E-07", "StaleSidecar.test_old_sidecar_is_refused_even_with_branch", "E2 stale sidecar (2E defect)",
     "synthetic chain", S, "refused with/without branch; sold item stays sold", ""),
    ("E-08", "Divergence.test_refused_without_branch", "E3 divergence", "synthetic", S, "refused", ""),
    ("E-09", "Divergence.test_branch_wii_keeps_wii_state_without_contamination", "E3 branch wii", "synthetic", S,
     "Wii state only, no DE-branch flags/money/deletions", ""),
    ("E-10", "Divergence.test_branch_de_keeps_de_state_without_contamination", "E3 branch de (CLI)", "synthetic", S,
     "DE state only", ""),
    ("E-11", "Divergence.test_only_de_exclusive_change_is_kept", "E4 newer DE-only state", "synthetic", S,
     "kept", ""),
    ("E-12", "Restoration.test_de_exclusive_state_survives_and_wii_progress_wins", "E4 restoration", "synthetic", S,
     "Expert, cosmetics, Noponstones, DE-only item/flag, FC byte kept; Wii progress wins", ""),
    ("F-01", "CorruptInput.test_wii_corruptions", "F1 Wii container", "monado01 damaged", S,
     "refused, no output, no traceback", ""),
    ("F-02", "CorruptInput.test_wii_out_of_range_values_with_valid_crc", "F1 Wii impossible values", "synthetic", S,
     "refused", ""),
    ("F-03", "CorruptInput.test_de_corruptions_and_invalid_states", "F1 DE invalid states", "synthetic + public v7",
     S, "refused", ""),
    ("F-04", "CorruptInput.test_random_bit_flips", "F1 fuzz 60 bit-flip cases", "seed 2026", S,
     "clean success or clean refusal only", ""),
    ("F-05", "Transactional.test_failure_injection_every_stage", "F2 failure injection", "6 stages", S,
     "no output, no staging left", ""),
    ("F-06", "Transactional.test_manifest_matches_written_bytes_and_no_overwrite", "F2 manifest / no overwrite",
     "monado01", D, "hashes match; second run refused", ""),
    ("F-07", "Transactional.test_interrupted_run_recovery", "F2 interrupted run", "synthetic staging", S,
     "next run unaffected; cleanup-staging", ""),
    ("F-08", "Transactional.test_dry_run_and_report", "H1 dry run", "monado01", D, "nothing written", ""),
    ("F-09", "PathSafety.test_live_markers_traversal_and_case", "F3 markers/traversal/case", "fake trees", S,
     "refused", ""),
    ("F-10", "PathSafety.test_junction_and_symlink_into_live_tree", "F3 junction/symlink", "fake trees", S,
     "refused", "symlink part skipped without Developer Mode"),
    ("F-11", "PathSafety.test_output_folder_itself_a_junction", "F3 junction output", "fake tree", S, "refused", ""),
    ("F-12", "PathSafety.test_unexpected_working_directory", "F3/H2 other cwd", "monado01", D, "works", ""),
    ("F-13", "PathSafety.test_slot_names", "F3 slot names", "synthetic", S, "refused", ""),
    ("H-01", "CommandLine.test_help_lists_every_command", "H1 help", "-", C, "complete help", ""),
    ("H-02", "CommandLine.test_clear_messages", "H1 messages", "monado01", D, "clear messages, sidecar notice", ""),
    ("G-01", "FioraSkillCopy.test_real_saves_hold_the_copy", "C1 Fiora record 8 copy", "monado01, monado03", D,
     "records 3/8 skill object identical", ""),
    ("G-02", "FioraSkillCopy.test_game_reverts_record3_from_record8", "C1 Fiora revert (evidence)",
     "Dolphin run d1 (game-written)", G, "game restored record 3 from record 8", ""),
    ("G-03", "FioraSkillCopy.test_export_keeps_copy_in_step", "C1 Fiora fix", "s020 game-generated + edit", S,
     "copy synced; all checkpoints", ""),
    ("G-04", "CraftedCylinders.test_de_crafted_cylinder_round_trip", "B2 DE crafted cylinder",
     "s241 (game-generated)", G, "exported as kind 3, restored exactly", ""),
    ("G-05", "GameWrittenWiiFile.test_wii_resave_reimports_exactly_apart_from_play", "Cross-game acceptance",
     "Dolphin run d2 (game-written Wii file)", G, "only clock/time/position differ; 1256 items; Expert intact", ""),
]


def results(log):
    txt = open(log, encoding="utf-8", errors="replace").read()
    out, cur = {}, None
    for ln in txt.splitlines():
        m = re.match(r"^(test_\w+) \(([\w.]+)\)", ln)
        if m:
            cur = f"{m.group(2).split('.')[-2]}.{m.group(1)}"
        if cur:
            s = re.search(r"\.\.\. (ok|FAIL|ERROR|skipped)", ln) or re.match(r"^(ok|FAIL|ERROR|skipped)\b", ln)
            if s:
                out[cur] = s.group(1)
                cur = None
    tail = re.search(r"Ran (\d+) tests in ([\d.]+)s\s+(\S+.*)", txt)
    return out, (tail.groups() if tail else None)


def main(log, out_json, out_md):
    res, summary = results(log)
    rows = []
    for tid, test, feat, prov, kind, exp, cav in M:
        r = res.get(test, "not run")
        rows.append({"id": tid, "test": test, "feature": feat, "fixture": prov, "kind": kind, "expected": exp,
                     "actual": "as expected" if r == "ok" else r, "result": {"ok": "PASS"}.get(r, r.upper()),
                     "evidence": "tests/ + phase2f/results/" + os.path.basename(log), "revision": REV, "caveats": cav})
    runs = []
    for kind_dir in ("monado", "dolphin"):
        d = os.path.join(P2F, "runs", kind_dir)
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            p = os.path.join(d, n, "run_manifest.json")
            if os.path.exists(p):
                m = json.load(open(p))
                runs.append({"emulator": kind_dir, "run": n, "status": m.get("status"),
                             "isolated": (m.get("live_unchanged", True) and m.get("protected_unchanged", True) and
                                          m.get("protected_all_unchanged", True) and not m.get("watchdog_violation")),
                             "save_written_by_game": m.get("save_changed"), "evidence": f"phase2f/runs/{kind_dir}/{n}"})
    json.dump({"revision": REV, "suite": summary, "tests": rows, "game_runs": runs,
               "all_tests_in_log": res}, open(out_json, "w"), indent=1)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("| ID | Feature | Fixture provenance | Data | Expected | Actual | Result | Evidence | Rev | Caveats |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['id']} | {r['feature']} | {r['fixture']} | {r['kind']} | {r['expected']} | {r['actual']} | "
                    f"{r['result']} | `{r['test']}` | {r['revision']} | {r['caveats']} |\n")
    print(json.dumps({"suite": summary, "matrix_rows": len(rows), "pass": sum(r["result"] == "PASS" for r in rows),
                      "not_pass": [r["id"] + ":" + r["result"] for r in rows if r["result"] != "PASS"],
                      "game_runs": len(runs), "runs_not_isolated": [r["run"] for r in runs if not r["isolated"]]}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
