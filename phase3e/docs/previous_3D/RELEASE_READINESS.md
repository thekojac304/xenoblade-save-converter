# Release readiness — XC Save Converter 3D-rc1 (Sync Hub + converter)

3C's readiness record still applies to everything 3D did not change: `phase3d\docs\previous_3C\RELEASE_READINESS.md`
(also `release_candidate_3D\docs_3C\`). This file covers what 3D changed and verified.

## Verdict

**Ready for regular use on this PC's emulators (Dolphin, Monado, Azahar), with or without the Sync Hub — including the
late game after Fiora's return.** 3D is a strict improvement over 3C: identical results wherever 3C was right (byte
parity on 8 of 12 reference conversions; the other differences are the intended D1 byte and the new D2 refusal),
character 8 now supported, one crash fixed, and one silent equipment loss turned into a clear refusal.
**Real devices remain untested** — keep backups and do the one-time checks in 3B's part C.

## Completion criteria of the 3D brief

| Criterion | Status | Evidence |
|---|---|---|
| Character 8 converts without invariant violations | **met** | read-back clean in every direction; adversarial tests; `CHARACTER_STATE_MATRIX.md` |
| Loads in the games | **met** | Dolphin wd_s276/283/288/291_save; Azahar x5_s291_save; Monado m_r_x2d_s291, m_r_w2d_s283 |
| Displays the correct character and equipment | **met** (3DS screens) | Party screen: Fiora lv 53 leading; Change Equipment: Mechonis Swords + 2 gems, Ether Goggles, Ether Frame; Skill Trees: Daring / Courage / Zeal |
| Survives save and reload | **met** | game re-saves on Wii and 3DS; Monado cold load + save of both returns: clock/time only |
| Compatible with subsequent progression | **partly** | post-event states play and save on all three games; the rejoin/reunion events themselves were not reached on Wii/3DS (L-F) |
| "Do not silently substitute 3 for 8" | **met** | era rule; 3 refused from 275, 8 refused before 275 |
| Story splits with stored equipment | **refused (D2)** with exact reason | `tools/stored_gear.py`; tests; package test |
| Never weaken a test | **met** | 4 earlier tests now assert the D2 refusal for the affected saves and keep all other assertions (`THREE_PLATFORM_REGRESSION.md` §5) |
| Test safety | **met** | 2,323-file protected manifest unchanged before/after every one of 33 runs and at the end; isolated save folders; nothing installed into a live profile |
| Earlier releases preserved | **met** | release_candidate_2E … 3C in the protected manifest, unchanged |
| Packaged without Python, no game data or saves | **met** | package tests 3D 11/11, 3B 19/19 (incl. "no game data, saves or keys"), 3A 32/32; 3D has no `user_data` folder |

## Remaining risks (details in KNOWN_LIMITATIONS.md)

1. Saves from story splits (Alcamoth ~154–158, Fallen Arm → reunion 269–288) are refused until everyone is back (L-E).
2. The rejoin/reunion events were not played on the Wii/3DS (L-F); a genuine Wii save written at the rejoin is
   still missing (L-H, refused rather than guessed).
3. Story beyond the sample (Mechonis, endgame, Future Connected) not exercised after conversion.
4. Real hardware untested.
