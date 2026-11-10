# Reunion validation (Phase 3E)

Every reunion below was triggered by the game's own event system in an isolated emulator. The only aid was **debug
positioning**: the player position (and facing) in the save file was set in front of the event site or the person to
talk to, exactly the warp positions the 3C Monado runs used (`phase3e/scripts/wpos.py`; nothing else in the file
changes; checksums recomputed). No story counter, party, flag or equipment field was edited. The native reference is
the DE game's own result for the same events (3C Monado autosaves 156 → 158 → 160 from the same playthrough).

Criteria per reunion (brief steps 1–8): genuine pre-reunion save converted · absent characters' gear stored correctly ·
reunion triggered by the game · returning characters' equipment and gems inspected · in-game save and cold reload ·
compared with the native DE result · converted back · no loss, duplication or wrong assignment.

## 1. Results

| # | Platform | Reunion | Start | Returning | Gear and gems vs native DE | Inventory change vs native | Save / reload | Back to source |
|---|---|---|---|---|---|---|---|---|
| R1 | **Wii** (Dolphin a1) | Emperor's audience 156 → 158 | DE 156 → Wii (stored gear translated) | Shulk (6 items, 6 socketed gems) | **identical** | identical (Shulk +6 items +6 gems, Melia −6 stored) | in-game save ✓ | chain continues (R2) |
| R2 | **Wii** (Dolphin a2–a5c) | friends 158 → 160 | R1's Wii save | Reyn (empty head), Dunban, Sharla, Riki | **identical** (all four + Shulk) | identical (+23 items, +7 gems) | in-game save ✓, cold reload a6 ✓ (clock/time only) | → DE with the 156 export's sidecar: = native 160 except slot numbers of two identical items, 2 platform event differences, clock/time; 12/12 boxes same items, 30/30 equipped same |
| R3 | **3DS** (Azahar x1c → x2) | audience 156 → 158 | DE 156 → 3DS | Shulk | first run: items back, **6 gems missing** → defect **D3** found and fixed; rerun: **identical** | identical | in-game save ✓ | chain continues (R5) |
| R4 | **DE** (Monado m1) | friends 158 → 160 | R1's Wii save → DE **first-time** (no sidecar; DE stored gear built from the Wii staging) | Reyn, Dunban, Sharla, Riki | **identical** | identical | autosave ✓ | — |
| R5 | **3DS** (Azahar x3b–x6c) | friends 158 → 160 | R3's 3DS save | Reyn, Dunban, Sharla, Riki | **identical** (all five) | identical (+23 items, +7 gems) | in-game save ✓, cold reload x7 ✓ (clock/time only) | → DE with the 3DS record: = native 160 like R2; 12/12 boxes, 30/30 equipped |
| R6 | **DE** (Monado m2) | — | R4's 160 autosave | — | — | — | cold reload + normal save ✓ (clock/time only) | — |

Stored gear of characters still away after each reunion (e.g. Melia, whom the Wii and 3DS games stored themselves at
156 → 158) equals the DE game's own stored gear for the same event.

## 2. Platform differences seen (not converter effects)

* Shulk's palette slot 0: DE event 2, Wii event 1 (known since 3C).
* Melia's art 99: the Wii event sets level 1, the DE event leaves 0.
* Item slot numbers: each game places returning items in its own free slots.

## 3. Run notes

* Every talk changed the same flag the DE game sets for it (Riki 1198, Sharla 1197, Reyn 1195, Dunban 1196) and the
  reunion the same seven flags (story 32 → 160, 1069, 12839, 13118, 7972, 7973) on the Wii, the 3DS and the DE.
* Automation issues, all in the harness, none in the save: Dolphin hidden behind other windows (a4c, a5 — no save
  written); the post-reunion "New Quest" window needs A, not B (a5b, x6); the 3DS menu bar wraps (x3, x4: the save
  sequence ended on Party); one Azahar start never answered its control port (x6b). Each was rerun from the same
  game-written save; no failed run's output was used.
* The user's own story-8 3DS save holds a genuine stored state too (Reyn away with his starting gear) — read and
  translated like the others.

## 4. Not played

* The Fallen Arm reunions (269 → 276 Fiora, 276 → 283 Reyn/Sharla, 288 → 291 everyone): event sites not reachable
  within bounded navigation (3D); covered structurally (all 7 genuine saves translate both ways; the same table and
  routine as the reunions above).
* A departure played on the Wii/3DS with socketed gems (the games' own leave writing staged gems): Melia left wearing
  gem-less defaults; the leave of gems is covered by the code reading and by the join side above.
