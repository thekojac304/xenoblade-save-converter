# Xenoblade Chronicles save converter — Phase 3F report

**Fiora's scenario-288 reunion, stored equipment and final compatibility validation** · 2026-11-09 · 3F-rc1

Companion documents: `FIORA_REUNION_ANALYSIS.md` (state and code, Part A), `FIORA_REUNION_GAMEPLAY_TESTS.md`
(played reunions, Part B), `CHARACTER_STATE_MATRIX.md` (section 0), `STORED_EQUIPMENT_MAPPING.md` (section 6),
`THREE_PLATFORM_REGRESSION.md`, `SYNC_HUB_REGRESSION.md`, `KNOWN_LIMITATIONS.md`, `RELEASE_READINESS.md`,
`PHASE3F_SUMMARY.md`. Progress log: `phase3f/CHECKPOINT.md`.

## 1. Outcome

| Part | Result |
|---|---|
| A - state | The 288 split decoded field by field (283 / 288 / native 291): Fiora-8's record is untouched, her gear (667-671 + Mechonis Swords with two socketed gems) is in the DE table / Wii-3DS staging slot 158; the 3E data mapping holds her exactly. Wii code read: the join routine has no character-specific path; the one Fiora-specific step (re-seeding record 8 from record 3) runs only on her **first** join, gated by join-mask bit 8, which the converter carries. |
| B - gameplay | Reunion trigger found in the game's own tables (`EVT_cs` 1108 `vs12210100`, then 289 events, → 291). Played: **DE** (Monado, genuine 288) and **3DS** (Azahar, converted 288): Fiora, Shulk, Reyn and Sharla got exactly their stored gear and gems, identical to the native DE result; saved, cold-reloaded, converted back to DE = native content, Monado cold load. **Wii not played**: the workstation stayed locked, which stops Dolphin (disclosed, runbook provided). |
| Defect **F1** (found in B) | A full equipment pocket makes the Wii/3DS skip a returning character's gear (played: Shulk and Reyn came back empty-handed). 3E's exports of the Fallen Arm splits were full. Fixed: the converter keeps room for the returning gear; a save where the game already skipped a return is refused with names. |
| C - implementation | `stored_gear.VALIDATED` includes 8; first-join guard; `reunion_room` / `unfinished_returns`; GUI plain-language rule; versions 3F-rc1. |
| D - adversarial | 34 new tests (empty slot, orphan gem, > 8 gems, duplicate items, EXP on the Wii while she is away, DE-only metadata, three generations, first-join bit, skipped return, interrupted sync, divergence). |
| E - round trips | DE 288 → Wii → DE and → 3DS → DE byte-identical; Wii 288 → 3DS → Wii and Wii → DE → 3DS → Wii canonical-identical; played 3DS reunion → DE = native. |
| F - Sync Hub | split and reunion are ordinary progress; the 3DS game's own reunion comes back through the hub with no duplicate or lost item; divergence = conflict; interrupted sync commits nothing. |
| G - release | All suites green; 3E parity byte-identical outside the F1 cases; package tests 16/16, 19/19, 32/32; `release_candidate_3F`. |

## 2. Defects

| # | Defect | Found by | Root cause | Fix | Tests |
|---|---|---|---|---|---|
| **F1** | Returning characters can come back without their gear on the Wii/3DS | Azahar x2: 3DS reunion of a 3E-style export - Shulk and Reyn in the party, references still staged; Sharla and Fiora fine | 0x8007F368 creates each item through 0x80158EEC and **returns at the first failed add**; capacity = 60 + 10 × bits(item +0x12108) + bonus, and only characters 3/5/6/7/8/11 raise it when they join; the converter filled pockets to capacity (overflow to the sidecar). Also present in 3E for Fallen Arm splits 269/276/283 (Wii weapons 140/140; 3DS 60/60) - those reunions were never played in 3E | `stored_gear.reunion_room` reserved in `de_to_wii.build` while characters are stored; `unfinished_returns` → clear refusal on Wii/3DS → DE; GUI message | `TestReunionRoom` (6), Azahar x3 (all returned), package test |
| (guard) | Fiora-8 stored with join-mask bit 8 clear would be re-initialised by the Wii/3DS | code reading (0x8007FB98 / 0x80082D28) | one-time character-8 initialisation | refused in both directions (`first_join_problems`); no genuine save affected | `test_first_join_bit_clear_is_refused`, `test_join_mask_records_fioras_first_join` |

Minimal reproductions kept: `phase3f/fixtures/x3_s288_export_3e_engine` (+ record) and the game's save
`x3_s291_azahar_x2_reunion_save`.

## 3. Policy (3F)

* Stored characters 1, 2, 4, 5, 6, 7 and **8** are translated (DE ↔ Wii ↔ 3DS).
* While anyone is stored, the Wii/3DS output keeps `reunion_room()` free per pocket; with `--overflow refuse` a save
  that does not fit is refused with that reason.
* Refused: Fiora-8 stored with bit 8 clear; an in-party character whose references still name staged gear; every 3E
  refusal of inconsistent stored data (unchanged).
* Unchanged: the 3E safety gate for unreadable or inconsistent stored data, sidecar/record 3-way rules, Sync Hub.

## 4. Changes to earlier tests

| Test | 3E | 3F | Why |
|---|---|---|---|
| 3D `test_d2_members_away_with_stored_gear` | 288 refused naming Fiora | 288 translated (Wii and 3DS) | policy |
| 3D hub `test_split_blocks_reunion_syncs` | 288 blocked, 291 = generation 1 | 288 syncs (generation 1), 291 follows; rollback target generation 2; all other steps unchanged | policy |
| 3E `test_fiora_away_is_refused` | refused | `test_fiora_away_is_translated` | policy |
| 3E `test_all_directions_on_genuine_split_saves` | 288 excluded | 288 included | policy |
| 3E hub `test_fiora_away_blocks_with_her_name` | blocked | `test_fiora_away_syncs` | policy |
| 2H `test_version` | 3E-rc1 | 3F-rc1 | version |

Originals: `phase3f/docs/previous_tests_3E`; script: `phase3f/scripts/patch_tests_for_3f.py`.

## 5. Source references

| What | Where |
|---|---|
| Fiora-8 policy, first-join guard, reunion room, skipped returns | `tools/stored_gear.py` (`VALIDATED`, `FIRST_JOIN_GUARDED`, `first_join_problems`, `reunion_room`, `unfinished_returns`, `unfinished_message`) |
| Room reserved in DE → Wii/3DS | `tools/de_to_wii.py` `build()` inventory section (`room`, `lim`) |
| Refusals in Wii/3DS → DE | `tools/convert.py` `build()` (after the stored-gear read) |
| GUI | `phase3f/gui/xcgui/messages.py` (rule "Equipment not given back by the game"), version stamps |
| Tests | `phase3f/tests/test_phase3f_fiora.py`, `phase3f/tests_gui/test_phase3f_messages.py` |
| Harness additions | `phase3f/scripts/erun3f.py` (`--gfx`, `--log`, `--novsync` for the isolated Dolphin profile), `az3f.py`, `azplay3f.py`, `mkroute*.py`, `conv_research.py`, `parity_3e.py`, `wintitles.py` |

## 6. Safety

Isolated emulator copies only; 3,648-file protected manifest (originals, live saves, NAND, emulators, ROM/disc
images, Syncthing configuration, every earlier release incl. `release_candidate_3E`) checked after every run and at
the end - unchanged. The only edit to any save before play was debug positioning at the game's own event site. No
experimental save was installed in a live profile; nothing was published.
