# Phase 3F checkpoint log (newest last)

## Setup
- Workspace phase3f/; protect3f.py = 3E set + release_candidate_3E (3,648 files), start recorded, unchanged.
- Wrappers: erun3f.py (monado/dolphin; + --gfx/--log/--novsync for the isolated Dolphin profile), az3f.py,
  azplay3f.py (3 RIGHT to System), mkroute.py/mkroute2.py (Monado A-tap routes, <= 24 shots - Monado writes at most
  ~24 captures per run, then exits), conv_research.py (research engine + Fiora-8 allowed in-process only), sheet.py.

## A - scenario-288 state (genuine DE 283/288/291)
- 288 party [4,6,7]; stored 1,2,5,8 (Fiora-8: 667-671 defaults with fixed gems, weapon 65 with 2 socketed gems
  Strength Up IV / Agility Up IV). Fiora-3 stash = stale table entries (excluded, as in 3E).
- In-process probe (VALIDATED|{8}): 288 -> Wii, -> 3DS, 3DS -> Wii, first-time -> DE all equal; unchanged return
  byte-identical.
- Event site: EVT_cs 1108 vs12210100 (scenario 288) at (-614.068, 11.272, 338.309) ma1601; chain vs12220050/60 -> 291.

## A2 - code
- 0x8007F368 join/leave: character checks only 1..11 range; no Fiora branch.
- Party update 0x8007FB98: leave loop, then per new member 0x80157CD8 (capacity mask bit for ids 3,5,6,7,8,11,
  table 0x8052F6B8, item +0x12108) + join. Character-8 block (seed from record 3, level) gated by 0x80082D28 =
  first-join bit in flag 0x108 (canonical flag_bitmask_0; DE 32-bit flag 0). Converted 288 has bit 8 set.

## B - played
- Monado m1/m1b (native DE 288): reunion 288 -> 291, party [4,6,7,1,2,5,8]; returning gear = stored gear (all 4);
  +24 items +13 gems; event: AP +108, SP +38 all, Expert reserve EXP +915.
- Dolphin d1..d0e: desktop locked (LogonUI) -> Dolphin throttled (~0.4 core), never reached the save; Null backend
  does not boot. Wii leg pending (needs an unlocked desktop).
- Azahar x1/x2 (3E engine output): reunion played; Shulk and Reyn NOT given their gear -> **F1**.
- F1: Wii/3DS box capacity 60 + 10*bits(item+0x12108) + bonus; converter filled boxes to capacity (3DS template
  mask 0 -> 60); join adds fail -> 0x8007F368 returns early -> character in party with staged refs. Sharla/Fiora
  succeeded because their join raises capacity first. Fix: de_to_wii keeps stored_gear.reunion_room() free; Wii/3DS
  -> DE refuses unfinished returns with a clear message (stored_gear.unfinished_returns).
- Azahar x3 (fixed): reunion, all 4 returning = stored = native DE; inventory delta = native; Fiora equipment screen
  shows Mechonis Swords + Strength Up IV + Agility Up IV, Ether Goggles, Ether Frame. x4 cold reload: clock/time.
- 3DS -> DE (record): 12/12 boxes, 42/42 equipped = native; Monado m2 cold load + save: palette slot0 2->1 + clock.

## C - implementation
- stored_gear: VALIDATED |= {8}; FIRST_JOIN_GUARDED/first_join_problems (both directions); reunion_room (de_to_wii
  build reserves it per box; refuse-mode message names the reunion); unfinished_returns/unfinished_message (convert
  build refuses). Versions 3F-rc1 (sidecar, xc3dservice, xcsync, GUI). GUI phase3f/gui (+1 message rule).
- Tests: patch_tests_for_3f.py moved 4 tests (3D d2 + hub, 3E fiora + hub) from "refused" to "translated/syncs";
  originals in docs/previous_tests_3E. New phase3f/tests 34 OK; GUI 20 + 39.
- Parity vs release_candidate_3E/source (parity_3e.py): 23 identical; Fallen Arm 269/276/283 differ (F1: 3E outputs
  had full Wii weapon / 3DS pockets); 288 3E refused.
- Package tests (phase3f/dist): 3F 16/16, 3B 19/19, 3A 32/32. 3DS hub output of 288 == the x3 played export.
- x4 via Wii format -> DE first-time: gear = native; missing exactly the 571 overflow items held in the record.

## Dolphin
- Locked session all phase: D3D/Vulkan boot, ~0.4 core, render window hidden, no save even for load+save control;
  VSync off no help; Null backend does not boot. Wii leg = disclosed gap L-N with runbook.
