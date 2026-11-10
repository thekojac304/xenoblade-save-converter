# Release readiness — XC Save Converter 3E-rc1 (Sync Hub + converter)

3D's readiness record still applies to everything 3E did not change: `phase3e\docs\previous_3D\RELEASE_READINESS.md`
(also `release_candidate_3E\docs_3D\`). This file covers what 3E changed and verified.

## Verdict

**Ready for regular use on this PC's emulators (Dolphin, Monado, Azahar), with or without the Sync Hub — now also
for saves made while party members are away in a story event.** 3E is byte-identical to 3D outside those windows; inside
them it converts what 3D refused, with gameplay proof on all three games. One configuration stays refused (Fiora's later
form away, scenario 288). **Real devices remain untested** — keep backups.

## Completion criteria of the 3E brief

| Criterion | Status | Evidence |
|---|---|---|
| Stored-equipment structures decoded (DE table, Wii/3DS staging, gems, identity, references, restoration) | **met** | `STORED_EQUIPMENT_MAPPING.md`; Wii routine 0x8007F368 read from the executable; encoder vs game bytes |
| Canonical model separate from inventory and equipped items; both directions on all three versions | **met** | `canon` `stored_gear`; `tools/stored_gear.py`; translation tests |
| Translated records survive the target game's save/reload | **met** | Wii a6, 3DS x7, Monado m2 cold reloads (clock/time only) |
| Returning characters receive the correct original equipment and gems in a legitimate reunion | **met** for Alcamoth (156→158, 158→160) on Wii, 3DS and DE | `REUNION_VALIDATION.md` R1–R6; identical to the DE game's native result |
| No story counter / equipment flag / party flag edited to manufacture success | **met** | debug positioning only (`wpos.py`), recorded per run |
| Where gameplay validation is blocked, conservative refusal kept | **met** | Fiora's later form away (288) refused; Fallen Arm translations structural (L-M) |
| Ambiguities rejected, not guessed | **met** | `TestAdversarial`; unreadable stored data refused |
| Saves outside split windows byte-identical to 3D | **met** | `parity_3d.py`: 14/14 identical |
| Existing suites, GUI, Sync Hub rerun; tests not weakened | **met** | 2H 136, 3A 41, 3B 65, 3C 22, 3D 21, 3E 24, GUI 18 + 39; test changes listed in `XC_PHASE3E_REPORT.md` §4 (2E/2F tests restored to their original assertions) |
| release_candidate_3D unchanged; safety | **met** | in the 2,935-file protected manifest, unchanged at the end |
| Packaged without Python, no game data or saves | **met** | package tests 13/13, 19/19 (incl. "no game data"), 32/32; no `user_data` folder |

## Remaining risks (details in KNOWN_LIMITATIONS.md)

1. Fiora's later form away (288): refused (L-J).
2. Fallen Arm reunions not played (L-M); the translation is the same and exact in every direction on all genuine saves.
3. Story beyond the sample, real hardware: untested.
