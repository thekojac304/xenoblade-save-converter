# Xenoblade Chronicles save converter — Phase 3E report

**Stored equipment, temporary party separation and reunion validation** · 2026-11-08/09 · 3E-rc1

Companion documents: `STORED_EQUIPMENT_MAPPING.md` (structures and translation rules), `REUNION_VALIDATION.md`
(played reunions), `THREE_PLATFORM_REGRESSION.md` (all suites, parity, packages), `KNOWN_LIMITATIONS.md`,
`RELEASE_READINESS.md`, `PHASE3E_SUMMARY.md`. Progress log: `phase3e/CHECKPOINT.md`.

## 1. Outcome

| Priority | Result |
|---|---|
| 1 — decode | DE table at 0x3BB50 fully decoded (record + gem copies, references, return behaviour); the Wii/3DS leave/join routine 0x8007F368 read from the executable (staging records, staged-gem table, 2-byte links, reference rules); script command 0x8004A24C for scripted gear. Exact translation rules: `STORED_EQUIPMENT_MAPPING.md`. |
| 2 — implementation | `tools/stored_gear.py`; canonical `stored_gear` (present only in split saves — every other save's canonical state and output unchanged); DE → Wii/3DS and Wii/3DS → DE writers; 3-way re-import; unreadable or unvalidated data refused, never guessed. |
| 3 — real reunions | Played by the games on converted saves: Wii 156→158 and 158→160 (five characters return), 3DS 156→158 (and 158→160, §REUNION_VALIDATION), DE 158→160 from a Wii-built stash. Returning characters' gear and gems identical to the DE game's native result; inventory changes identical; saved, cold-reloaded, converted back. |
| 4 — adversarial | Missing / orphan / duplicate stored gems, > 8 gems, staging id mismatch, away-but-equipped, modified stored items, repeated three-platform conversions, sidecar returns of pre-3E files, Fiora's later form, Sync Hub — tests in `phase3e/tests`. |
| 5 — regression and release | All suites green; 3D parity byte-identical outside split windows; `release_candidate_3E`. |

## 2. Defects

| # | Defect | Found by | Fix | Test |
|---|---|---|---|---|
| D2 (3D) | stored equipment not translated (3D refused split saves) | 3D Sync Hub check | translated (this phase) | `TestTranslation`, game-written reunion tests |
| **D3** | 3DS transcoder swapped the bytes of the staged-gem link table (treated as u16; the game reads two bytes) → the 3DS game skipped the gems of returning characters | Azahar run x1c: Shulk returned without his 6 gems | `xc3d` copies the table as bytes; no earlier save had a non-zero table, so no earlier output changes | `test_d3_link_table_is_bytes_on_the_3ds`, run x2 (gems back) |
| E1 | a 3-way rule was needed: returning a 3C/3D-era Wii/3DS file of a split to its DE save would have overwritten (or, where the file's references name base/template gear without a staging record, refused) the DE's real stored gear | analysis + the 3C/3D return tests | `reimport`: characters whose stored-gear bytes did not change since the export keep the DE's entries (byte signature, before any reading); a character who rejoined on the Wii/3DS has his entries cleared (as the DE does); the service read-back accepts the kept entries | 3C story returns, 3D game-written returns (stash byte-equal), `test_wii_cold_reload_and_return_to_de` |

## 3. Policy

* Stored characters: away, already joined (party journal), current era, not Fiora's retired record 3.
* Translated for Shulk, Reyn, Dunban, Sharla, Riki, Melia (returns played for 1, 2, 4, 5, 6; Melia's stored state
  written by the Wii and 3DS games themselves and read back equal to the DE's).
* Still refused: Fiora's later form away (288) — no reunion with her stored gear was reachable; > 8 socketed gems for
  one character on the Wii/3DS; any inconsistent stored data.

## 4. Changes to earlier tests

| Test | 3D | 3E | Why |
|---|---|---|---|
| 2E `test_monado_progressed_saves`, 2F `test_temporarily_unavailable_and_rejoin`, `test_matrix`, `test_export_keeps_copy_in_step` | asserted the D2 refusal for the split saves | **restored to their original 2E/2F assertions** (exports succeed) | stored gear translated |
| 3D `test_d2_members_away_with_stored_gear` | refused 269/276/283/288 | 269/276/283 translate exactly; 288 refused naming Fiora | policy |
| 3D `test_first_time_import_of_the_split_is_faithful` | refused | the pre-D2 Wii files hold no stored gear; imported faithfully | translation |
| 3D hub `test_split_blocks_reunion_syncs` | message named Shulk, Reyn, Sharla | names Fiora | policy |
| 3D `test_first_time_import_of_the_split_is_faithful` (288) | refused (D2) | refused (Fiora's leftover base references - no staging record) | no guessing |
| 2F `test_temporarily_unavailable_and_rejoin` | synthetic rejoin = party list edited | the export of s269 now stores the gear (references keep the id), so a party-list edit is no longer a state the game can reach; the synthetic Wii session is money only and the stored gear must come back unchanged; real rejoins are the game-written 3E tests | translation |
| 3C `test_wii_event_changes_the_same_state_as_the_de_event` | allowed differences: achievements, characters, clock, play time | + `stored_gear` | the 3C export carried none (D2) |
| 2H `test_version` | 3D-rc1 | 3E-rc1 | version |

## 5. Safety

Isolated emulator copies only; the 2,935-file protected manifest (originals, live saves, NAND, emulators, ROM/disc
images, all earlier releases incl. 3D, Syncthing config) checked after every run and at the end — unchanged. The only
edit ever made to a save beyond conversion was the player position (debug positioning), recorded per run.
