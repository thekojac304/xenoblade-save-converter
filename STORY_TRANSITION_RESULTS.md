# Story transition results (Phase 3D)

Late-game transitions involving Fiora (records 3 and 8), party separation and restoration, and scripted equipment.
Every run used an isolated emulator copy and copied saves; the 2,323-file protected manifest (originals, live saves,
NAND, executables, ROM, earlier releases, Syncthing config) and each emulator's live save folder were hashed before
and after every run (33 runs: Monado 8, Dolphin 6, Azahar 19; **none changed a protected or live file**).

## 1. What the genuine saves show (public DE playthrough, 2025-09-11, re-saved by Monado)

| Story | Party | Event between saves | What the DE game wrote |
|---|---|---|---|
| 269 | `[1]` | Shulk alone at Fallen Arm (others captured/away) | stored-equipment table: real gear of 2, 4, 5, 6, 7 |
| 276 | `[8, 1]` | Fiora reunited (event vs12080150) | record 8: lv 40 → 53, AP, coins, skill progress seeded from record 3; her gear added to the inventory and equipped; stash entry 8 cleared |
| 283 | `[8, 2, 1, 5]` | Reyn and Sharla return | their gear restored from the stash into **new** inventory slots, with their gems |
| 288 | `[4, 6, 7]` | split: Shulk, Reyn, Fiora, Sharla away | their equipment references zeroed; gear (+ gems) moved into the stash; inventory no longer lists it |
| 291 | `[8, 6, 5, 7, 2, 1, 4]` | everyone reunited | all gear restored from the stash (new slots, new serials); stash entries of party members cleared (id 0) |

## 2. Procedure results (the brief's 10 steps, per transition)

| Transition | Genuine save | Convert | Load (target game) | Legit trigger reached | Game event | Party verified | In-game save | Cold reload | Compare | Convert again |
|---|---|---|---|---|---|---|---|---|---|---|
| **Fiora rejoins (269 → 276)** on the 3DS | DE 269 | ✓ (after D1 fix) | ✓ Azahar (crashed before D1) | ✗ — navigation to the red-light column not found in bounded effort (3DS marker route, Monado warp probe m1_s269_lock) | not played | — | — | — | — | — |
| **Fiora rejoined, character 8 in party** (276/283/291) on the Wii | DE 276, 283, 291 | ✓ | ✓ Dolphin | n/a (state after the event) | — | ✓ `[8,1]`, `[8,2,1,5]`, `[8,6,5,7,2,1,4]` | ✓ wd_s*_save | ✓ (game re-save is the reload of the converted save) | ✓ clock/time/position only | ✓ → DE with sidecar, then **Monado cold load + save** (m_r_w2d_s283): clock/time only |
| **Character 8 on the 3DS** (291) | DE 291 | ✓ | ✓ Azahar x5: Party screen (Fiora lv 53 leading), Change Equipment (Mechonis Swords + 2 gems, Ether Goggles, Ether Frame), Skill Trees (Fiora‑8's Daring / Courage / Zeal) | n/a | — | ✓ | ✓ System → Save → overwrite | ✓ | ✓ + 9 skill-link unlocks raised by the game (limitation 5) | ✓ → DE with record, then **Monado cold load + save** (m_r_x2d_s291): clock/time only |
| **Temporary split (288)** on the Wii | DE 288 | ✓ in the early 3D build; **now refused (D2)** | ✓ Dolphin wd_s288_save | n/a | — | ✓ `[4,6,7]` | ✓ | ✓ | ✓ | return with sidecar ✓ (DE's own stash kept, byte-equal) |
| **Party restoration (288 → 291)** | DE 288 / 291 | — | — | not played on Wii/3DS (DE-only evidence, section 1) | — | — | — | — | — | — |

The rejoin event itself was not reached on the Wii/3DS. Per the brief, effort on that one navigation was bounded and
the work moved to validating the post-event states in every game, which is what a user's converted save needs.

## 3. Findings

### D1 — Shulk's Wii-only arts flag (fixed)
The first 3DS load of the converted 269 save crashed (stack overflow at PC 0x2CA438, Fallen Arm, Shulk leading) and
the Wii hung on the loading screen. Bisection with hybrid saves (bisect3ds.py, runs bs0–bs13) isolated one byte:
Shulk's record +0x118, 0 in the user's story-8 3DS template, 1 in every game-written save after he has battle arts.
`de_to_wii` now sets it from story 20 when the base has 0. Verified: bs13_fixed loads; test
`test_d1_shulk_arts_flag`.

### D2 — stored equipment of members who left (refused; not translated)
Found while checking the Sync Hub on the 283 → 288 → 291 sequence (the hub took the split for an older-sync branch
because the departing members' gear vanished from the inventory). Both games keep that gear in a table outside the
inventory (DE 0x3BB50, 7 × 0xB4 per character = equipment record + its 3 gem records; Wii/3DS staging records in box
slot 150 + id, routine 0x80158308) and restore it at the reunion. The converter does not translate that table, so a
converted split save played through the reunion would equip the destination's stale gear and lose the real gear and
its gems. Rule (`tools/stored_gear.py`): a main character who has joined (party journal), is away, is not Fiora's
retired record 3 and has non-default stored gear makes the conversion **refused**, unless the destination stores the
same gear or itself has that character away (a return to the playthrough's own save — its stash is kept). Public
archive scan (359 saves): affected = stories 269–288 only; the prologue Dunban slot (stories 6–23, scripted Monado)
is not affected. Tests: `test_d2_*`, `test_first_time_import_during_the_split_is_refused`, hub `test_split_blocks_reunion_syncs`.

### Platform differences observed (not defects)
* The 3DS game raised nine skill-link unlock levels (incl. Fiora‑8 slots) after the Skill Trees screen was opened;
  the DE return carries the higher values (limitation 5: unlocks only go up, derived from affinity).
* The Wii and 3DS normalise skill node / link state bytes on save for every character (limitation 14).
* Compacted equipped items keep their Wii slot on return (limitation 6); every item and every equipped item's content
  verified identical (`itemset.py`).
