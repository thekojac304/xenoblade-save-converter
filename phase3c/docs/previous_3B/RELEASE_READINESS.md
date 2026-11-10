# Release readiness — XC Save Converter 3B-rc1 (Xenoblade Sync Hub)

The per-direction conversion verdicts of 3A still apply unchanged (same engine):
`phase3b\docs\previous_3A\RELEASE_READINESS.md` (also `release_candidate_3B\docs_3A\`).

## Verdict

**Ready for regular use on this PC's emulators (Dolphin, Monado, Azahar) with the Sync Hub, with the manual copy
steps described in the user guide.** The completion standards of the Phase 3B brief are met on the evidence below.
**Not yet validated on real devices** (New 3DS + Checkpoint, Android Dolphin on the phone and Odin 2 Mini, GPD Win
Mini): use those after the one-time checks in part C, with backups.

## A. Completion standards

| Standard | Status | Evidence |
|---|---|---|
| Startup scanning is read-only | **met** | hub + incoming folders hashed before/after (unit test, packaged window test) |
| New gameplay distinguished from unchanged or generated saves | **met** | game-written saves: Monado walk, 3DS battle, Dolphin walk = new progress; Monado re-save, 3DS re-saves (3A a1, a5), generated files returned = in sync |
| Divergent histories cannot be silently merged | **met** | two-device progress, old-copy play (more play time), abandoned generations -> conflict, explicit choice only, other branch snapshotted; no merge code exists |
| All requested outputs independently validated | **met** | per-generation validation list (structure, checksums, references, same state, item multiset); failure injection proves a wrong output is refused |
| Incomplete generations cannot become authoritative | **met** | failure injection at 8 points + process kill at 8 points: pointer unchanged before commit; publication repair after |
| Previous generations remain recoverable | **met** | immutable folders, rollback as a new generation, snapshots of every candidate |
| Platform-specific metadata survives supported round trips | **met, with B3** | DE-only character data (Expert Mode, cosmetics, link unlocks) and flags survive Wii/3DS hops; DE-only per-item favourite marks can be partly lost when the Wii/3DS game rewrote items (engine behaviour, unchanged from 3A) |
| Existing manual conversions remain correct | **met** | 2H 136 + 3A 41 unit tests, 3A/2H GUI tests on the 3B GUI, 3A package test on the 3B build, byte parity |
| Protected original and live saves unchanged | **met** | 1,226-file manifest unchanged after every run and at the end; release_candidate_3A unchanged |
| Packaged GUI works independently of the development environment | **met** | package test from a clean folder, Python removed from PATH, scales 1/1.5/2 |

## B. Remaining risks

1. Real New 3DS / Checkpoint restore untested (as in 3A).
2. Android Dolphin's app-private storage needs manual file copies (no Syncthing access); untested on the devices.
3. B1 (Wii heap junk) is handled by the hub only; the manual converter tab still refuses such a Wii -> 3DS
   conversion (3A behaviour).
4. Story progression after a conversion was not played (battles, travel, menus, saving were).
5. Hub on a network share / two PCs writing the same hub: not supported (lock is advisory across PCs).

## C. One-time checks before relying on real devices

1. **Backups**: copy each device's current Xenoblade save somewhere safe.
2. **New 3DS**: copy `ready\new-3ds\Checkpoint\XenobladeSync-genNNNNNN` to
   `sdmc:/3ds/Checkpoint/saves/<the Xenoblade folder>/`, restore it with Checkpoint, load the slot, check party and
   location, save, back the save up with Checkpoint, put it in the 3DS incoming folder, Scan: "New progress found on
   New Nintendo 3DS."
3. **Android Dolphin**: find Dolphin's user folder (Config > User Data), copy `monado01` in and out as the guide
   describes, then the same load / save / scan check.
4. **Desktop / Win Mini**: copy `bfsgameNN.sav` (+ `.tmb`) from the ready folder into Monado's `save\save_0` after a
   backup; load; save; scan.
