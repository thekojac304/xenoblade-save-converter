# Xenoblade Chronicles Wii ⇄ Definitive Edition
## Phase 2F: release hardening, adversarial testing and generalization

Date: 2026-11-06 (autonomous workday run). Converter **2F-rc1** (canonical schema `xc1-canon/2`, sidecar
`xc1-sidecar/1`, unchanged format). Release: `release_candidate_2F/`. The Phase 2E release (`release_candidate/`) is
unchanged (its 74 checksums verify).

Evidence labels: **[C]** executable code (Wii `main.dol` SX4E01 / DE `main`) · **[D]** real save or table data ·
**[G]** observed in an isolated Monado or Dolphin run · **[S]** synthetic fixture (a real save with game-plausible
edits; tests logic, not game behaviour) · **[H]** hypothesis.

---

## 1. Results at a glance

| Direction | Status | Basis |
|---|---|---|
| **Wii → DE** | **VALIDATED** for your playthrough | 2E: load, combat, travel, story 150 → 156 [G]. 2F: the 2F file (differs from 2E only in item serials) loaded and saved in Monado [G]; checkpoint matrix and 109 tests [S/D] |
| **DE → Wii** | **PARTIALLY VALIDATED** | 2E: load, party, combat, travel, save [G]. 2F: a game-written late-game DE save (story 232, Expert Mode, 1,256 items, 46 deferred) loaded and saved in Dolphin and came back to DE exactly apart from play [G]. **Not played: a Wii story event after an export.** |
| **Re-import (Wii → DE with sidecar)** | **VALIDATED for the tested chains** | 2E chain [G]; 2F cycle DE (game) → Wii (game) → DE (game) at story 232 [G]; 4-generation alternation, stale/divergent/corrupt sidecars [S] |
| Fiora's second form, guests in the party | **UNSUPPORTED** (refused) | no validated mapping |
| DE format v7 | **UNSUPPORTED** for export (refused) | re-save once in DE 2.0; Monado's own upgrade verified lossless on 6 saves [G] |

**25 defects found and fixed** (4 marked "normal use" in §3 would have hit regular play). **109 automated tests pass**
(1 skipped: symlinks need Developer Mode). **10 isolated game runs** (8 Monado, 2 Dolphin), 0 isolation problems;
**all 106 protected files unchanged**.

---

## 2. Safety record

- **Snapshot first.** The 2E source, tests, specs, docs and release were frozen in `phase2f/snapshot_2E/`
  (129 files hashed). `release_candidate/` was never modified.
- **Protected inputs** (`phase2f/manifests/protected_start.json`, 106 files):
  - Wii saves in the Filen folder, the Proton Drive NAND and the portable Dolphin `User\Wii`;
  - live Monado `save_0`;
  - research originals and template;
  - the 2E release;
  - `xcde.exe`, `xcde.ini`, `Dolphin.exe` and the `.rvz` disc image.
- **Re-checks.** After every game run, and at the end (`protected_end.json`): unchanged.
- **Monado runs.** Own `save_0` via `LARECOMP_SAVE_DIR`. The game was killed if it mounted anything else. The live
  `save_0` was hashed before and after.
- **Dolphin runs.** Own `-u` user dir, plus an explicit `NANDRootPath` inside the run folder (checked before
  launch), plus a watchdog that re-hashed the protected Wii folders every 2 s and would have killed the run's Dolphin
  process.
- Nothing was deployed, downloaded or published.

---

## 3. Defects found and fixed

Each fix has a regression test. "Normal use" marks defects that would have hit regular play.

| # | Defect (2E-rc1) | Root cause | Fix | Regression test | Evidence |
|---|---|---|---|---|---|
| 1 | **Re-import refused after any Wii item pickup** (normal use) | The Wii header serial is an *age*: a pickup ages every item (`0x80159080`), `0x80159488` renumbers boxes. The descent check matched items by (id, serial). | Canonical acquisition `order`; multiset item identity; encoders per direction | `A-06`, `B-11`, properties | [C][S] |
| 2 | DE "newest" sort order reversed for converted items | 2D/2E copied Wii ages into DE acquisition numbers | DE serial = acquisition rank; Wii age = N+1−rank | `B-11` | [C][D] |
| 3 | **Fiora's DE skill progress reverted by the Wii game** (normal use before she leaves the party) | Record 8 keeps a copy of record 3's skill object; the Wii restores record 3 from it on load | DE → Wii writes both copies | `G-01..03` | [G] Dolphin d1 (bug) → d2 (fixed) |
| 4 | **Every late-game DE save refused for DE → Wii** (s241+) | DE-crafted cylinders use source 0; only source 1 had a Wii encoding | Canonical source 1 for gid-0 cylinders with source 0 | `G-04`, checkpoint matrix | [D][G] |
| 5 | Unlocked link slots not sent to the Wii; first export inherited the template's unlocks | Treated as DE-only; `max(template, Wii)` | Shared canonical field, both directions | `C-08`, `C-09` | [D][G] |
| 6 | **A stale sidecar (no `--current-de`) brought back a sold DE-only item and dropped newer DE progress** (normal use) | Re-import never looked at the current DE save unless given | Current save required (or explicit `--no-current-…`); stale-evidence refusal even with `--branch` | `E-07`, `E-04` | [S] |
| 7 | **First export inherited the template's Expert reserve EXP, fashion and Noponstones** (EXP from another playthrough) | Template bytes kept | Reset on first export | `H10` probe → tests | [S] |
| 8 | DE v7 saves exportable but never re-importable | Re-import needs a v10 template | v7 refused with guidance | `F-03` | [G] upgrade verified |
| 9 | Fiora's second form / guests accepted and half-converted | Characters 8–13 not modelled; party check allowed ≤ 13 | Refused both ways | `C-05` | [S] |
| 10 | A newer DE-only change (current DE differs only in DE-exclusive fields) was reverted | The re-import always used the export-time DE save as template | Such a current DE save becomes the template | `E-11` | [S] |
| 11 | Expert "highest-level EXP" overwritten on re-import | Rewritten whenever the record changed | Kept unless the level passes the highest | checkpoint matrix | [D] |
| 12 | Moved (compacted) items lost their DE serial; deferred items could duplicate serials | Slot-based matching | Identity pairing in acquisition order; parked slots excluded | `G-04` | [S] on real data |
| 13 | `--slot 00/../../x` wrote outside `save_0` | Slot spliced into the file name | Strict slot names | `F-13` | [S] |
| 14 | Absolute Wii `--slot` wrote anywhere | `os.path.join` with an absolute name | Strict slot names | `F-13` | [S] |
| 15 | Partial output on refusal (save written, sidecar refused) | One file at a time | Staging folder + one directory rename | `F-05..07` | [S] |
| 16 | Live-folder guard bypassed by a junction | No path resolution, markers only | realpath + marker files + case | `F-09..11` | [S] |
| 17 | Tracebacks on truncated / malformed input and corrupt sidecar JSON | Unvalidated parsing | Validated loaders; exit codes 0/1/2/3 | `F-01..04`, `E-02` | [S] fuzz 60 |
| 18 | `--dry-run` wrote `--report` | Report written regardless | Nothing written in a dry run | `F-08` | [S] |
| 19 | Forged / inconsistent sidecars accepted; damaged snapshot found only when used | Integrity hash only | Consistency checks, eager snapshot decoding | `E-03` | [S] |
| 20 | Damaged section headers accepted | CRCs cover payloads only | Container header check | `F-01` | [D] |
| 21 | DE states the Wii → DE mapping rejects could be exported (one-way trip) | Asymmetric validation | Closure check on every Wii output | `B-07` | [S] |
| 22 | Dangling DE gem reference crashed (KeyError) | No reference check | Explicit refusal | `F-03` | [S] |
| 23 | Invalid DE values silently normalized (quest bytes, EXP ≥ next level, coins, field widths) | Clamping / masking | Refused | `C-04`, `F-03` | [S] |
| 24 | Map check too loose (`area ≤ 24`) | Range test | Exact Wii `FLD_maplist` (28 maps) | `D-05` | [D] |
| 25 | Wii gem strength > 255 crashed Wii → DE; unclosed files; a JSON spec read as cp1252 | Unchecked byte fields; I/O hygiene | Explicit refusal; `with`/UTF-8 | `B-07` | [S] |

Test-harness errors found along the way (fixtures, not converter defects) are listed in `EDGE_CASE_RESULTS.md` §6.

---

## 4. New mappings and evidence

| Topic | Finding | Evidence |
|---|---|---|
| Wii item serial | An age: pickup ages all items in boxes 2–13 (`0x80159080..0x80159100`), new item 0; `0x80159488` sorts a box by age and renumbers 1..N | [C] |
| DE item serial | Per-type acquisition number; counter at `0x46900` equals the newest serial in game saves | [D] |
| Wii capacities | Re-read `0x80158490`: types 2, 4–8, 11 = 10·bits(1..11) + 60 + min(bonus, 30) (clamp written back); 3, 9, 10 = 300; 12 = 200; 13 = 240; others 0 | [C] |
| Heart-to-Heart flags | Wii `0x3440 + row` set by `CMenuKizunaTalk` (`0x801BE4FC`); list `0x80274D08` reads it with `0x24B0 + row` (viewed) and the story requirement. DE block at `0x3634` (= +500) fits six game-generated saves; no other base comes close | [C][D] |
| Other high Wii flags | `0x3508` switch; `0x3509 + i` skill-category unlocks; `0x352C–0x36CF` unaddressed by code, scripts or dumped tables (meaning open) | [C][D] |
| Fiora | Record 8 = copy of record 3 `+0x1F4..+0x29F`; the Wii restores 3 from 8 on load | [D][G] |
| Crafted cylinders | DE source 0 ⇔ Wii kind 3 (source 1); DE keeps leftover effect bytes | [D][G] |
| Link slots | Same concept in both games; DE recomputes from pair affinity on load (one value raised) | [D][G] |
| Expert Mode | Reserve EXP is one party-wide pool stored in every record; highest-level EXP ≠ current EXP at the same level | [D] (6 game-generated saves) |
| v7 → v10 | Monado's own upgrade keeps every canonical field and all DE-only character data | [G] 6 runs |
| Wii stat caches | Not used at run time (Party screen recomputed HP), not rewritten by the game | [G] |

Details: `phase2f/results/d4_flag_blocks.md`; scripts in `phase2f/scripts/` (`scan_flag_blocks.py`,
`scan_de_desc.py`, etc.).

---

## 5. Game runs (all isolated)

| Run | Emulator | What | Result |
|---|---|---|---|
| g1_s020, g1_s206, g1_s232, g1_s241, g1_s258, g1_s269 | Monado | Public v7 saves (story 20–269) loaded, saved in-game | Game wrote v10. Canonical state identical except clock minute and play time; Expert data identical. Fixtures in `phase2f/fixtures/real/` |
| d1_s232_load_save | Dolphin | 2F (pre-fix) export of the s232 v10 save on base monado01: load, field, Party, save | Loads in Frontier Village, party and levels correct. **Found defect #3** (Fiora reverted) |
| d2_s232_fiora_fix | Dolphin | Same after the fix | Wii save differs from the export only in clock, play time, position |
| m3_s232_back_from_wii | Monado | Re-import of the Dolphin-written file: load, save | Only clock minute and play time changed; Expert data and serials identical |
| m2_user_2f | Monado | **Your save**, 2F conversion (= release file `bfsgame01.sav`, SHA-256 `1028f718…`): load, menu, save | Eryth Sea 13:29, Lv 52 Shulk, Chapter Eight; saved. Monado raised one link unlock (affinity recomputation) |

---

## 6. Workstream coverage

| Workstream | Done | Gaps |
|---|---|---|
| A round trips / properties | 10 tests, 12 seeds each, minimisation on failure | — |
| B inventory / equipment | capacity formula [C], boundaries ×8 boxes, compaction, gems, crystals, identity, order | Full 150-item Wii equipment box only synthetic |
| C characters / EXP | boundaries, unsupported party, split party (real s269), Expert (real data + synthetic level-down), arts/skills/links | Fiora rejoined: no fixture (refused) |
| D story / quests / world | 6-checkpoint matrix (game-generated); every quest × objective × value; quests 90/221/287; maps; flags ×2 cycles; D4 flag blocks | No real Wii save beyond scenario 150; Wii story progression not played |
| E sidecar | normal 6-step CLI cycle; missing / corrupt / forged / stale / other playthrough; divergence both branches; restoration | — |
| F corruption / transactions / paths | container, impossible values, 60-case fuzz, failure injection at 6 stages, interrupted runs, junctions, case, traversal, other cwd | Symlinks need Developer Mode (junction case covered) |
| G game acceptance | 10 runs (§5) | No new combat / travel / quest / story run in 2F (2E evidence stands) |
| H CLI / packaging | help, messages, dry run, exit codes; clean-directory package test 10/10 | No GUI (optional, not started) |

---

## 7. Remaining issues

See `KNOWN_LIMITATIONS.md`. The most important:
1. Wii story progression after a DE → Wii export has never been played.
2. Fiora's second form and guests are refused; late-game conversion stops at Fiora's rejoin.
3. Wii flags `0x352C–0x36CF` have no DE slot; their meaning is open.
4. The Wii item-aging rule is code-backed; a real Wii pickup followed by a re-import was not played.

---

## 8. Files added or changed in Phase 2F

| File | Purpose |
|---|---|
| `tools/safeio.py` (new) | Path guards, all-or-nothing commit, staging cleanup, bounded inputs |
| `tools/xcconv.py`, `canon.py`, `convert.py`, `de_to_wii.py`, `sidecar.py`, `reimport.py`, `wii_save.py` | Fixes in §3 |
| `tools/build_rc_2f.py` (new) | Release builder |
| `tests/p2f_util.py`, `tests/test_phase2f_*.py` (new, 69 tests) | Property, sidecar, inventory, progression, safety, regression suites |
| `tests/test_phase2e.py` | API updates only (explicit `no_newer_de` / `--no-current-wii`; RealChain W1 now asserts the order inversion) |
| `phase2f/` | Manifests, snapshot, scripts, fixtures (real + synthetic), runs, results, checkpoint log |
