# Fiora reunion gameplay tests (Phase 3F)

Every reunion below was played by the game's own event system in an isolated emulator copy. The only aid was **debug
positioning** to the event site the game's own table gives for scenario 288 (`EVT_cs` 1108 `vs12210100`, ma1601,
(-614.068, 11.272, 338.309), facing 251°): Monado `XCDE_WARP` at frame 5400 after the load; Wii-layout files
`phase3e/scripts/wpos.py` (position and facing only, checksums recomputed). No story counter, flag, party,
character-availability or equipment field was edited by anything but the games. Inputs: A presses through the scenes
(the post-event "Quest Complete" window needs A), then System → Save. Protected manifest (3,648 files) checked before
and after every run: unchanged every time.

## Results

| Run | Platform | Start | Story | Party after | Returning gear vs stored | vs native DE | Save / reload | Back to DE |
|---|---|---|---|---|---|---|---|---|
| m1 `m1_s288_native` | DE (Monado) | genuine DE 288 | 288 → (scenes) | — | — | — | no save (route ended at 24 captures; Monado wrote no autosave for this event) | — |
| **m1b** `m1b_s288_native_save` | **DE** (Monado) | genuine DE 288 | **288 → 291** | `[4,6,7,1,2,5,8]` | **identical** for Shulk, Reyn, Sharla, Fiora-8 | (this is the native reference) | in-game save ✓ | — |
| x1 `x1_s288_reunion` | 3DS (Azahar) | DE 288 → 3DS (pre-F1 engine) | 288 → 291 (scenes, Organise Party, Quest Complete) | — | — | — | save sequence ended on the Quest Complete window (no save) | — |
| **x2** `x2_s288_reunion` | **3DS** | same file | **288 → 291** | `[4,6,7,1,2,5,8]` | Sharla, Fiora-8 identical; **Shulk and Reyn: nothing returned** | **defect F1** | in-game save ✓ | refused (names), nothing written |
| **x3** `x3_s288_reunion` | **3DS** | DE 288 → 3DS (**3F engine**, room kept) | **288 → 291** | `[4,6,7,1,2,5,8]` | **identical** (all four) | **identical** (all 7 characters' gear; inventory change +24 items, +13 gems = native) | in-game save ✓; Party screen and Fiora's Change Equipment screen inspected | ✓ (below) |
| **x4** `x4_s291_reload` | **3DS** | x3's save | 291 | same | — | — | cold reload + save: **clock and play time only** | with x3's record: 12/12 boxes and 42/42 equipped items = native; nothing stored; DE stash cleared |
| **m2** `m2_x4back_reload` | **DE** (Monado) | x4 → DE | 291 | same | — | — | cold load + save: clock/time + Shulk's palette slot 0 2 → 1 (Monado normalises it on load) | — |
| d1, d1b, d0…d0g | Wii (Dolphin) | DE 288 → Wii | — | — | — | — | **not reached**: the workstation was locked for the whole session (Windows lock screen); Dolphin booted but ran throttled (~0.4 core), its render window stayed hidden and no save was ever written, even for a load-and-save control on the same file. Null video backend does not boot this game. | — |

Screens and captures: `phase3f/runs/monado/*/shots`, `phase3f/runs/azahar/*/shots` (x3: `t2_scene_*`, `t3_field`,
`p1` Party, `e1` Change Equipment: **Mechonis Swords + Strength Up IV + Agility Up IV, Ether Goggles (Debuff Resist
III), Ether Frame (Attack Plus IV)** - exactly her stored gear), contact sheets `phase3f/work/*_sheet.png`.

## What the events changed (identical on DE and 3DS)

Story 288 → 291; flags 12798, 8117, 8118, 8119, 8718 set, 13118 cleared, 1345 111 → 254; quest counter 801 closed;
position (-658.68, 5.604, 360.1); every character AP +108 and +38 SP on the selected skill tree. EXP: the 3DS gives +915 to each
character (Riki +1098); the DE save is in Expert Mode, which banks the same +915 in the reserve pool (Shulk 456,176 →
457,091) - same event, different storage. Fiora-8's level, arts, palette, skill trees, learned nodes, link slot and
affinity: unchanged on both.

## Criteria (brief, "fully validated only when")

| # | Criterion | DE | 3DS | Wii |
|---|---|---|---|---|
| 1 | genuine converted 288 save loads | (native) | ✓ x2, x3 | ✓ structurally; game load of a 288 split shown in 3D (`wd_s288_save`, pre-3E export without stored gear); this file not loaded (lock) |
| 2 | Fiora's stored gear and gems preserved | ✓ | ✓ (staging slot 158 read back = DE) | ✓ static (same reader/writer; `TestTranslation`) |
| 3 | game naturally restores her | ✓ m1b | ✓ x3 | **not played** (environment) |
| 4 | arts, skills, links, progression correct | ✓ | ✓ | static ✓ |
| 5 | in-game save and cold reload | ✓ m1b, m2 | ✓ x3, x4 | — |
| 6 | converts back without loss or duplication | — | ✓ x4 → DE = native; overflow items return from the record | static ✓ (unchanged returns byte-identical) |
| 7 | same behaviour on all three | ✓ | ✓ | **gap disclosed**: the Wii game code was read (no Fiora-specific path; F1 and the first-join gate apply equally to the Wii), the 3DS game - the same code base and the same save layout - executed the character-8 return from staging slot 158 |

## How to finish the Wii leg (needs an unlocked desktop)

```
python phase3e/scripts/wpos.py phase3f/fixtures/wii_s288_export_3f phase3f/inputs/d2_s288/monado01 -614.068 11.272 338.309 251
python phase3e/scripts/mkdroute.py phase3f/routes/d2_reunion.dsl --scene-s 210 --shot-every 20000 --save
python phase3f/scripts/erun3f.py dolphin d2_s288_reunion phase3f/inputs/d2_s288/monado01 phase3f/routes/d2_reunion.dsl --timeout 420 --diag 15
```
Then `python phase3e/scripts/gearcmp.py <run>/user/Wii/title/00010000/53583445/data/monado01 phase3f/fixtures/de_s291_monado_m1b_native_reunion.sav 1,2,4,5,6,7,8`.
Keep Dolphin's window uncovered (3E note: hidden windows fail the same way).

## Automation notes

* Monado writes at most ~24 captures per run and exits after the last one; routes now use ≤ 23 shots.
* The 3DS post-reunion sequence: scenes → "Organise Party" (B closes) → "Quest Complete" (A) → field; then
  X, RIGHT ×3 (System), A, A, A, UP, A.
* The Dolphin failures were environmental (locked session) and are kept in `phase3f/runs/dolphin` with their
  manifests; no output of a failed run was used.
