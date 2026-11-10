# Workday summary: Phase 2F (2026-11-06)

**Bottom line:** I tried hard to break the converter and did, 25 times; every defect is fixed, with a regression
test. Four of them would have hurt normal play. Your Wii → DE save is ready to try, with a backup, using the
checklist in `RELEASE_READINESS.md`. Your original saves and live folders are untouched (106 hashes verified).
Nothing was installed into your games.

## Status

| | Status |
|---|---|
| Wii → DE | **VALIDATED** (your save; the new file loaded and saved in Monado today) |
| DE → Wii | **PARTIALLY VALIDATED** (loads, saves and comes back exactly; Wii story progression after an export still not played) |
| Bidirectional | **VALIDATED for the tested chains**, now including a late-game Expert Mode save through both games |
| Fiora's second form / guests in the party | refused (not supported yet) |

## The four defects that mattered most

1. **Item pickups on the Wii would have blocked the return to DE.** The Wii stores an item's *age*: every pickup
   ages all items (found in the game code). The old safety check compared those numbers, so any pickup made it
   refuse the re-import. DE's "newest" sort order was also reversed.
2. **Fiora's skill progress made in DE was undone by the Wii game.** The Wii keeps a hidden copy of her skills in
   another record and restores from it on load. Caught in Dolphin, fixed, then re-tested in Dolphin.
3. **Late-game DE saves could not go to the Wii at all**, because DE-crafted crystal cylinders had no Wii encoding.
4. **An old sidecar could bring back an item you had sold in DE.** Re-imports now need your current save of the
   other game and refuse old sidecars, even with `--branch`.

Also fixed:
- a first export no longer inherits the template's reserve EXP, fashion or Noponstones;
- unlocked skill-link slots move both ways;
- output folders are all-or-nothing, and the live-folder guard now resolves junctions;
- damaged or impossible inputs are refused cleanly (no tracebacks, nothing written).

## New evidence

- **Real Expert Mode saves.** Monado converted six public late-game saves (story 20–269, Expert Mode) to v10. These
  game-written files round-trip through the converter exactly.
- **A full trip through both games.** A story-232 save went DE → Wii (the Wii game loaded and saved it) → DE (Monado
  loaded and saved it). Only clock, play time and position changed; all 1,256 items and the Expert data were kept.
- **The mysterious Wii flag block.** It is mostly Heart-to-Heart flags (found in code; placement confirmed on real
  DE saves). The 420 flags above it remain unexplained and stay on the Wii side, as before.

## What you should do

1. Read `RELEASE_READINESS.md` → **Manual acceptance checklist** (≈ 15 minutes in Monado).
2. Your file: `release_candidate_2F\user_saves\wii_to_de_monado01\save_0\bfsgame01.sav`
   (SHA-256 `1028f718…73b2`). Keep the sidecar next to it.
3. New in the commands: give your current save of the other game when you convert back (`--current-de` /
   `--current-wii`), and pick a **new** output folder each time.

## Not done / still open

- A Wii story event after DE → Wii, a quest completed on the Wii after an export, and a real Wii item pickup
  followed by re-import were not played.
- Fiora rejoined (character 8): no test save exists; the converter refuses.
- The optional GUI was not started; correctness came first.

## Where things are

- Reports:
  - `XC_WII_TO_DE_PHASE2F.md` (technical);
  - `TEST_COVERAGE_MATRIX.md`;
  - `EDGE_CASE_RESULTS.md`;
  - `KNOWN_LIMITATIONS.md`;
  - `README_CONVERTER.md`;
  - `RELEASE_READINESS.md`.
- Release: `release_candidate_2F\` (the Phase 2E release in `release_candidate\` is unchanged).
- Work log and evidence: `phase2f\` (`CHECKPOINT.md`, `runs\`, `fixtures\`, `results\`, `manifests\`).
