# Sync Hub regression - Fiora leaving and rejoining (Phase 3F)

Hub code: unchanged 3B code (`phase3b/src/xcsync`), 3F engine. Every test uses an isolated hub with simulated
Syncthing device folders (`hubfix.HubFx`: "Windows desktop" = DE, "Odin 2 Mini" = Wii, "New 3DS" = 3DS) and genuine
or game-written saves. Tests: `phase3f/tests/test_phase3f_fiora.py::TestSyncHub` (5) plus the moved 3D/3E hub tests.

| Scenario | Data | Expected | Result |
|---|---|---|---|
| Story progress through the split: 283 → 288 → 291 as DE generations | genuine 283, 288; Monado's native 288 → 291 | each "new progress" (never "unrelated" or a branch); Wii/3DS outputs carry exactly the stored gear of each generation (Fiora's at 288), none after the reunion; party `[4,6,7,1,2,5,8]` after | **pass** (`test_283_288_291_sequence_is_one_playthrough`) |
| Rollback to the split generation | same hub | DE file byte-identical to the 288 save | **pass** |
| Wii session while Fiora is away | 288 generation → synthetic Wii play (flags, money) | complete; the DE's stored-equipment table returns byte-equal - no stored gear treated as sold or lost, none restored from an outdated sidecar, no duplicate | **pass** (`test_wii_session_during_the_split_keeps_the_stored_gear`) |
| **The 3DS game's own reunion** comes back | 288 generation; Azahar x4 save (the 3DS game played the reunion on exactly the hub's 3DS output) | "new progress" from the New 3DS; DE output = native reunion's items (no duplicate gem or item), nothing stored, DE stash cleared; Wii output has no stored gear | **pass** (`test_3ds_game_reunion_comes_back_through_the_hub`) |
| Party composition changes are not a reason to reject a descendant | 283 `[8,2,1,5]` → 288 `[4,6,7]` → 291 `[4,6,7,1,2,5,8]`; 3DS x4 | accepted as progress | **pass** (both tests above) |
| Divergent histories | DE plays the reunion (291) while the Wii plays on from the same 288 generation | "conflict" requiring a choice; nothing committed without it | **pass** (`test_divergent_reunions_are_not_merged`) |
| Interrupted synchronisation | fault injected in the DE → Wii conversion of the 288 sync | nothing committed; the next sync completes with the stored gear | **pass** (`test_interrupted_sync_of_the_split_commits_nothing`) |
| 3D hub test (288 then 291, Wii and 3DS sessions, rollback) | genuine 288/291 | 3D/3E: 288 blocked. 3F: 288 syncs (generation 1), 291 follows as progress, the rest of the test unchanged (rollback target moves to generation 2) | **pass** |
| 3E hub test (Alcamoth 154 → 160, Wii session, rollback) | genuine | unchanged | **pass** |
| 3E hub test for 288 | genuine 288 | 3E: blocked with her name. 3F: syncs; Wii output carries her stored gear | **pass** |
| 3B hub suite (65 tests: conflicts, rollback, crash at each stage, publication failures, Syncthing conflict files) | | unchanged | **65 OK** |

Not covered: real Syncthing transfers between devices (the hub reads ordinary folders; tested since 3B with simulated
folders only) and real Android/3DS devices.
