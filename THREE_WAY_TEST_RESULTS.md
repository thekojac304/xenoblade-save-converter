# Three-way test results (Phase 3A, 2026-11-07)

Evidence levels used below: **byte-exact** static round trip · **field-level** static comparison (canonical state) ·
**emulator load** · **in-game save/reload** · **gameplay** (menus, combat, travel) · **hardware** (none in 3A).

## 1. Automated tests

| Suite | Command (research root) | Result |
|---|---|---|
| 2H regression (2C–2F engine, 2G/2H service), after all 3A work | `python -m unittest discover -s tests` | **136 OK** (1 skipped, as since 2F) — logs `phase3a\logs\final_unittest_2H.txt` |
| Phase 3A | `python -m unittest discover -s phase3a\tests` | **41 OK** — `phase3a\logs\final_unittest_3a.txt` |
| GUI: the 30 Phase 2H GUI tests run against the 3A window + 9 new 3A GUI tests | `cd phase3a && python -m pytest tests_gui` | **39 passed** on the real display (4 2H display tests fail only under `QT_QPA_PLATFORM=offscreen`, also for the unchanged 2H GUI) |
| Packaged app from a clean folder, no Python on PATH | `python phase3a\scripts\package_test_3a.py <dist> <clean dir> <json>` | **32 / 32** (all 18 2H checks + 14 3DS checks) — `phase3a\logs\package_test_3a.json` |

Phase 3A unit tests cover: QuickLZ (byte-identical recompression of every game-written file, synthetic and stored
blocks, damaged blocks); container (empty slot, wrong magic, truncation, padding, wrong size, checksum damage);
schema (full coverage, 3DS → Wii → 3DS and Wii → 3DS → Wii byte-exact, item/gem bitfields against native data, play
time, chest layout from the game's own re-save, wrong-source refusal); stats (no-op on game-written saves, level-up
formula, Monado scaling, stale-block rebuild, u16 weapon-flag regression); all four 3DS directions and their byte-
exact return trips; the Wii → DE → 3DS → Wii → DE chain (DE file byte-identical, shared state identical, generation 3,
DE state carried); deterministic output; inventory overflow refused / kept; templates required; lineage (current
save required, different playthrough refused, divergence refused unless explicitly kept, normal return, tampered
record refused); safety (3DS live paths, Azahar sdmc, Checkpoint folder, junction into a live folder, existing output
folder, injected failure leaves nothing, inputs unchanged); CLI (refusal exit code, CLI = service, 2H commands pass
through, 3DS inspect/validate). GUI tests cover 3DS preview, the "Convert to" choice, destination-decides-target,
empty/damaged 3DS saves, 3DS → Wii without destination, Wii → 3DS with Checkpoint folder and automatic return, DE → 3DS
→ DE automatic return byte-identical, divergence with the "keep this save's progress" action, drag and drop, live 3DS
output folder refused.

Parity: GUI and CLI write byte-identical files (2H and 3A directions); the 3A app's Wii → DE output is byte-identical
to the 2H CLI (and the validated 2F user save `1028f718…`).

## 2. Static round trips on real saves

| Trip | Result |
|---|---|
| your 3DS save → payload → recompressed | byte-identical file |
| 3DS → Wii → 3DS (your save) | byte-identical |
| Wii → 3DS → Wii (your story-150 and story-6 saves) | byte-identical (story-18 save: only junk bytes outside every section differ) |
| DE → 3DS → DE (your DE template) | DE file byte-identical |
| 3DS → DE → 3DS (your 3DS save) | 3DS file byte-identical |
| Wii → DE (2H) → 3DS → Wii → DE | DE file byte-identical; Wii canonical state identical |
| 3DS game's own re-save of a converted save → back to Wii | canonical state identical to the original Wii save except clock/play time |

## 3. Emulator runs (all isolated; inputs are copies)

| Run | Platform | Input | What was done | Result |
|---|---|---|---|---|
| a0 | Azahar (portable copy) | your own 3DS save | title → Continue → load | loads in Colony 9; isolation proven; save untouched |
| a1 | Azahar | your 22 h Wii save (story 150) → 3DS | load menu, load, party, equipment/gems, in-game save to slot 3 | loads (Eryth Sea, Lv 52, 22:01, 375,150 G, 6-member party, gems shown); **3DS game's save: canonical state identical** except clock/play time. Found the TBOX enum-size defect (A1) |
| a2 | Azahar | same, TBOX fixed | combat to victory (arts used), Area List, Colony 9 map with landmarks/minimap, **skip travel** to Gem Man's Stall, in-game save, skill trees (Affinity Coins 78/78) | all worked; game save differs only by battle EXP/AP/SP, kill counters, location flags, map/position/time |
| a3 | Azahar | the save the 3DS game wrote in a2 | **cold reload** from title, party, quest log, inventory | loads (22:06, 375,150 G); quest log and inventory present |
| a4 | Azahar | DE story-232 save (Expert Mode) → 3DS, before the stats fix | load, party, equipment | loads, but **stale HP/defence** (defect A2) |
| a5 | Azahar | same, stats rebuilt | load, party (Lv 43 HP 3831–8075), Dunban: Str 371, Def 266/264, in-game save | correct; then 3DS → DE return: every item (multiset), equipped item, flag, quest, achievement, character and DE-only value identical |
| a6 | Azahar | final build (packaged xcconv.exe) Wii story 150 → 3DS | load, party, Shulk's equipment screen, combat, in-game save | correct; game save = battle progress only; the game's own blocks equal the converter's stat model |
| w1 | Dolphin | the save played on the 3DS in a2 → Wii | load menu, load, party, in-game save | loads (Colony 9, 22:05, Lv 52 party, 375,150 G); **Wii game's save: canonical state identical** except clock/play time |
| w2 | Dolphin | the save the Wii game wrote in w1 | cold reload | loads at the Gem Man's Stall |
| m1 | Monado | the save played on the 3DS in a2 → DE | load, menu, in-game save | loads (Colony 9 Commercial District); saved: Lv 52, 22:06, Chapter Eight; DE re-save changes only clock/time and two link unlocks DE recomputes |
| m2 | Monado | DE s232 → 3DS (a5, played and saved on the 3DS) → DE | load, in-game save | loads (Frontier Village); saved: Lv 43 Riki, 54:40, Chapter Ten |

Screens: `phase3a\runs\azahar\*\shots\` (94 captures), `phase2f\runs\dolphin\p3a_*\user\ScreenShots`,
`phase2f\runs\monado\p3a_*\shots`; GUI screenshots `phase3a\screenshots\` (light/dark).

## 4. Protected data

* Azahar runs: 149 live files (Azahar install and AppData, Citra sdmc) hashed before/after every run: **0 changed,
  0 added** in all 7 runs.
* Session manifest (`phase3a\scripts\protect3a.py`, 904 files: your Wii/3DS/DE saves and their originals, live
  Dolphin/Monado/Azahar/Citra save folders and configs, emulator executables, the 3DS ROM, the Wii disc image, every
  earlier release candidate): **unchanged** after w1, m1, m2, w2 and at the end of the phase (`protected_final`).
* The 2F wrapper scripts report Monado live-save files as changed against their 2026-11-06 baseline; those files were
  modified 2026-11-06 21:09–22:14 (before this session, by your own play) and are unchanged since this session began.

## 5. Hardware

**No physical New 3DS test was performed.** Checkpoint compatibility is expected (complete archive folder) but
unconfirmed. See the checklist in `RELEASE_READINESS.md`.
