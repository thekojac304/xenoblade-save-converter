# Xenoblade Chronicles save converter — Phase 3D report

**Late-game compatibility, character-state hardening and three-platform regression** · 2026-11-08 · 3D-rc1

Companion documents: `CHARACTER_STATE_MATRIX.md` (every character record), `STORY_TRANSITION_RESULTS.md` (late-game
transitions and emulator evidence), `THREE_PLATFORM_REGRESSION.md` (all directions, multi-hop, Sync Hub, suites),
`KNOWN_LIMITATIONS.md`, `RELEASE_READINESS.md`, `PHASE3D_SUMMARY.md`. Progress log: `phase3d/CHECKPOINT.md`.

## 1. Outcome

| Goal | Result |
|---|---|
| Character 8 (Fiora's later form) | **Supported from scenario 275** in every direction. Validated on game-written data: the Wii game (Dolphin) loaded and re-saved converted 276/283/288/291 saves; the 3DS game (Azahar) loaded 291, showed Fiora-8's party slot, equipment and own skill trees, and saved; both returns to DE were cold-loaded and re-saved by Monado with only clock/play time changing. |
| "Do not treat 8 as an ordinary member" | Era rule from the party journal (3 until 274, 8 from 275); 3 is never substituted for 8 or back; record 3's skill object stays the Wii mirror of record 8; DE link slot 8 separate from slot 3; foreign skill ids in record 8 refused. |
| Characters 9–13 | Guests (BTL_pclist guest=1: Dickson, Mumkhar, Alvis, prologue Dunban ×2), never in any saved party → refused in a party, records kept. DE 14–27: Future Connected (DE-only, kept). |
| Defects found | **D1** (fixed): Shulk's Wii-only arts flag from an early base → 3DS crash / Wii hang at Fallen Arm. **D2** (refused): stored equipment of members away in a story split is not translated → such saves refused with the names. |
| Story transitions | Post-event states validated on all three games; the rejoin/reunion events themselves were not reached on the Wii/3DS within bounded navigation effort (see §4). |
| Regression | All earlier suites pass (2H 136, 3A 41, 3B 65, 3C 22; 4 earlier tests updated for D2, documented); 3D tests 21; GUI 18 + 39; package tests 11 + 19 + 32 = 62/62; parity with 3C byte-identical except the intended D1 byte. |
| Release | `release_candidate_3D/` (no Python needed; no game data or saves inside). All earlier releases untouched. |

## 2. Workstream A — character state

Findings (details and evidence tags in `CHARACTER_STATE_MATRIX.md`):

* **Representations.** Wii/3DS record 8 is dormant before the rejoin but *accrues EXP* (870 at story 18, 10 436 at 150)
  and holds a mirror of record 3's skill object (code 0x800A3644–0x800A3690 copies +0x1F4..+0x29F both ways after
  every skill update). DE record 8 is lv 40 / EXP 0 until the rejoin, when the DE seeds it from record 3 (SP,
  learned counts, coins), sets lv 53 and adds Fiora-8's gear to the inventory. Afterwards they are separate
  characters; DE link slots 3 and 8 are separate (Shulk's slot 8 = `[0,0,181,0,0]` = Fiora-8's "Battle Stance").
* **Ground truth for the open question** (own ids 176+ vs mirrored 51+): the Wii game kept the converter's own ids
  (176/181/186) and the mirror on re-save, and the 3DS showed Fiora-8's own trees. A genuine Wii save written *at*
  the rejoin was not available, so a record 8 with Fiora-3 ids is refused rather than guessed (`SKILL_ID_ALT` empty).
* **Equipment/skill initialisation verified**: level, EXP, AP, coins, SP, learned nodes, selected tree, arts and
  palette of record 8 round-trip exactly; equipment content identical after every return (`itemset.py`).
* **Engine** (`canon.FIORA_ERA`, `main_chars`, `fiora`, `unsupported_party`; era-aware phase2c, convert, de_to_wii,
  xc3dservice, xcservice). Pre-275 canonical fingerprints identical to 3C on 12 saves; conversions byte-identical.

## 3. Workstream E — defects

### D1 — Shulk's Wii-only arts flag (fixed)
* Reproducer: DE 269 → 3DS on the user's story-8 3DS save → Azahar stack overflow (PC 0x2CA438) at Fallen Arm with
  Shulk leading; the Wii (Dolphin) hangs on the loading screen.
* Root cause (bisected over 14 hybrid saves): character +0x118 is 1 for every character with arts in every
  game-written save, but Shulk's is 0 until he has battle arts; the story-8 base still had 0.
* Fix: `de_to_wii` sets it to 1 from story 20 when the base has 0 (3 output bytes differ from 3C: the flag and the
  section checksum). Regression: `test_d1_shulk_arts_flag`; emulator: bs13_fixed loads.

### D2 — stored equipment of members who are away (refused)
* Reproducer: the Sync Hub flagged genuine DE progress 283 → 288 as an older-sync branch; cause: Reyn's and
  Sharla's gear left the inventory. The DE moves departing members' gear (with gem copies) to a table at 0x3BB50
  and restores it at the reunion (288 → 291, new slots and serials); the Wii/3DS use staging slots 150+id
  (routine 0x80158308). The converter carried neither, so a converted split save played through the reunion would
  equip the destination's stale gear (the user's own story-150 Wii base: Shulk's Colony 9 clothes) or nothing (the
  story-8 3DS base) and lose the real gear and gems.
* Affected: public archive 269–288; the 3C story fixtures 154–158 (Alcamoth). Not affected: not-yet-joined members
  (prologue Dunban), Fiora's retired record 3, table defaults.
* Smallest safe fix: refusal with names (`tools/stored_gear.py`), except when the destination stores the same gear or
  is the playthrough's own save that has the member away (its table is kept — returns stay possible). A translator
  was not written because the reunion could not be reproduced in any game to validate it.
* Regression: `test_d2_*`, `test_first_time_import_during_the_split_is_refused`, hub `test_split_blocks_reunion_syncs`,
  package test; four 2E/2F tests updated (§5).

## 4. Workstream B — story transitions (bounded)

The Fiora rejoin (269 → 270 → 276) needs the party to reach the "column of red light" at Fallen Arm. Two 3DS attempts
(marker navigation: Shulk ended in the sea, distance oscillating) and one Monado warp probe did not trigger it. As the
brief directs, effort moved to the states after the event, which were validated on all three games; and to the
genuine DE before/after saves, which define what the event does (`STORY_TRANSITION_RESULTS.md` §1). No scenario,
party or event flag was ever set by hand.

## 5. Changes to earlier tests (none weakened)

| Test | Before | Now | Why |
|---|---|---|---|
| `test_phase2e.DEToWii.test_monado_progressed_saves` | exported the 2E story-154 save (Melia alone) | asserts the D2 refusal for it (names); the other save unchanged | D2 |
| `test_phase2f_progression.test_temporarily_unavailable_and_rejoin` | exported s269 | asserts the s269 refusal; the absent-member checks run on the story-20 save (members not joined yet) | D2 |
| `test_phase2f_progression.CheckpointMatrix.test_matrix` | s269 row round-tripped | s269 row asserts refusal; all other rows unchanged | D2 |
| `test_phase2f_regressions.test_export_keeps_copy_in_step` | all real saves exported | s269 asserts refusal; others unchanged | D2 |
| `test_phase2g_service.test_version` | 3C-rc1 | 3D-rc1 | version |

## 6. Safety

* 33 emulator runs (Monado 8, Dolphin 6, Azahar 19) on isolated copies; the 2,323-file protected manifest and each
  live save folder hashed before/after every run: **no change**. Monado wrote only its shader cache in its install
  folder, as in every earlier phase.
* No original save, live profile, NAND, ROM, executable, Syncthing configuration or earlier release candidate was
  modified; nothing was published; game tables are not in the release (3C put them in `user_data`; 3D does not).
* Final protected-manifest check: see `RELEASE_READINESS.md`.
