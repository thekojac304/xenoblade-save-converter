# Release readiness — XC Save Converter 3F-rc1 (Sync Hub + converter)

3E's readiness record still applies to everything 3F did not change: `phase3f\docs\previous_3E\RELEASE_READINESS.md`
(also `release_candidate_3F\docs_3E\`). This file covers what 3F changed and verified.

## Verdict

**Ready for regular use on this PC's emulators, now also for saves made while Fiora's later form is away (scenario
288)**, with one disclosed gap: the 288 → 291 reunion was played by the DE and the 3DS games but not by the Wii game
(the workstation was locked for the whole session, which stops Dolphin). 3F also fixes F1, which made 3E's
conversions of the Fallen Arm splits unsafe to play through on the Wii/3DS. Outside the split windows 3F is
byte-identical to 3E. `release_candidate_3E` is untouched and stays the fallback. **Real devices remain untested** —
keep backups.

## Completion criteria of the 3F brief

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | A genuine converted 288 save loads | **met** (3DS); Wii: not loaded this phase | Azahar x2/x3 |
| 2 | Fiora's stored equipment and gems preserved | **met** (all directions, byte-identical unchanged returns) | `TestTranslation`, package test |
| 3 | The game naturally restores her during the reunion | **met** on DE (native) and 3DS (converted); **not played on the Wii** (L-N) | m1b, x3 |
| 4 | Arts, skills, links, progression correct | **met** | `test_3ds_reunion_on_converted_save_equals_native`, link round trip |
| 5 | In-game save and cold reload | **met** (3DS x3/x4, Monado m1b/m2) | gameplay doc |
| 6 | Converts back without loss or duplication | **met** (3DS → DE with the record = native content; skipped returns refused) | x4 → DE, package test |
| 7 | Same behaviour on all three, or gaps disclosed | **met with a disclosed gap** (Wii, L-N; code path read, 3DS executed the same layout) | `FIORA_REUNION_ANALYSIS.md` A2 |
| — | No story/party/equipment flag edited to simulate success | **met** | debug positioning only, game event table sites |
| — | Refusal removed only on evidence; narrow guards kept | **met** | `VALIDATED` + first-join guard + skipped-return refusal; stored-gear safety gate unchanged otherwise |
| — | Unaffected saves byte-identical to 3E | **met** (23/23 incl. Alcamoth splits); deliberate F1 changes documented (6 Fallen Arm split exports) | `parity_3e.json` |
| — | All earlier suites, GUI, Sync Hub rerun; tests not weakened | **met** | 2H 136, 3A 41, 3B 65, 3C 22, 3D 21, 3E 24, 3F 34, GUI 20 + 39; 4 tests moved from "288 refused" to "288 translated/syncs" (originals in `phase3f/docs/previous_tests_3E`) |
| — | Packaged GUI/CLI in a clean directory, no game data | **met** | package tests 16/16, 19/19 (incl. no game data), 32/32 |
| — | Originals, live saves, emulators, earlier releases untouched | **met** | 3,648-file manifest unchanged at every check |

## Remaining risks (details in KNOWN_LIMITATIONS.md)

1. Wii reunion 288 → 291 not played (L-N) — runbook in `FIORA_REUNION_GAMEPLAY_TESTS.md`.
2. 3E-converted Fallen Arm saves already on a Wii/3DS (L-O): free pocket space before the reunion or re-convert.
3. Fallen Arm reunions 269 → 276 and 276 → 283 not played; story beyond the sample; real hardware: untested.
