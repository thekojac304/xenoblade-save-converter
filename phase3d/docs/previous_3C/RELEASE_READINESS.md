# Release readiness — XC Save Converter 3C-rc1 (Sync Hub + converter)

3B's readiness record (Sync Hub standards) still applies to the unchanged hub code: `phase3c\docs\previous_3B\
RELEASE_READINESS.md` (also `release_candidate_3C\docs_3B\`). This file covers what 3C changed and verified.

## Verdict

**Ready for regular use on this PC's emulators (Dolphin, Monado, Azahar), with or without the Sync Hub.** 3C is a
strict improvement over 3B: identical results wherever 3B was right (byte parity on first conversions and DE → Wii
returns), DE-only data kept where 3B lost or misplaced it, and three refusals of valid unplayed returns removed.
**Real devices remain untested** (New 3DS + Checkpoint, Android Dolphin, GPD Win Mini) — keep backups and do the one-time
checks in 3B's part C.

## Success criteria of the 3C brief

| Criterion | Status | Evidence |
|---|---|---|
| Verified DE-only fields survive supported round trips without restoring discarded or consumed items | **met** (with limit L-A) | `DE_METADATA_FIDELITY.md` §4; 16 metadata tests on game-written saves; real 3DS game session 176/176; 5-generation hub test with a disposed item |
| Story validation by the game's own event system, save reloads, progression remains available | **met for the transitions played** | DE 156 → 158 → 160 (+ reload, normal save, cold reload), 232 → 233; Wii 154 → 156 (+ cold reload, back to DE and on to 158); 3DS 154 → 156 (+ cold reload, back to DE) |
| No counter/flag/quest/party/event state edited; teleport only to legitimate sites, never into a scene | **met** | only `XCDE_WARP`/tour `warp` to EVT_sev sites or beside NPCs; one disclosed case where the tour's 60 s limit left a repeatable NPC conversation (not a story scene) |
| Sync Hub compatibility, lineage and transactional guarantees | **met** | 3B suite 65 OK (two tests updated to the corrected behaviour, see `REGRESSION_RESULTS.md`); 3B package test on the 3C build; parity explained |
| Test safety | **met** | 1,679-file protected manifest unchanged before/after every run; isolated save folders; no live install; release_candidate_3B unchanged (checksums verified) |
| Existing release preserved; GUI unchanged except version | **met** | `phase3c\gui` = 3B GUI with version 3C-rc1; GUI tests 18 + 39 |

## Remaining risks (details in KNOWN_LIMITATIONS.md)

1. Fiora's rejoin (character 8) still refused for DE — late-game players cannot convert from that point on.
2. Story beyond the played sample (Eryth Sea after 160, Mechonis, endgame, Future Connected) not exercised.
3. Real hardware untested.
4. Ambiguous items (newest survivor of a changed pocket; stacks added to) lose DE-only bytes — by design.
