# Gameplay compatibility matrix (3C-rc1)

How well converted saves keep *playing* — story checkpoints, party states and conversion directions — with the
evidence for each cell. Metadata fidelity (DE-only per-item data) is reported separately in
`DE_METADATA_FIDELITY.md`.

Evidence: **[story]** a real story transition played by the game's own event system after conversion, saved by the
game and checked (this phase unless noted) · **[play]** load, menus, combat/travel, save, reload (earlier phases) ·
**[load]** loads and saves only · **[static]** byte/canonical round trip on a real save · **—** not exercised.

## 1. Story checkpoints × platforms

| Checkpoint (scenario) | Party state | DE (Monado) | Wii (Dolphin) | 3DS (Azahar) |
|---|---|---|---|---|
| 6–8 (Colony 9, early) | Shulk, Reyn | [static] | [play] 3A (user's 3DS save, story 8) | [play] 3A |
| 18 | Shulk, Reyn, Fiora | [static] | [play] user's save | [static] |
| 20 (Cylinder Hangar) | Fiora, Shulk, Reyn | [static] s020 round trip | [static] | [static] |
| 150 (Eryth Sea, first visit) | 6 members | **[story]** 2E: 150 → 154 (Melia alone) | [play] 2E–3B (combat, travel, saves) | [play] 3A/3B (combat, travel, save) |
| 154 (Alcamoth, **Melia alone**) | [Melia] | **[story]** 2E: 154 → 156 | **[story] 3C W1: 154 → 156 on a DE → Wii converted save; same 6 flags as the DE game; cold reload W2** | **[story] 3C X1: 154 → 156 on a DE → 3DS converted save; same 6 flags; in-game save; cold reload X2** |
| 156 (Audience Chamber) | [Melia] | **[story] 3C M1: 156 → 157 → 158 (party change Melia → Shulk alone)**; also on the save that played 154 → 156 on the Wii (c5) | [load] (W1/W2) | [load] (X1/X2) |
| 158 (guest room: "talk to his friends") | [Shulk] | **[story] 3C M3: 158 → 160** — talks with Riki, Sharla, Reyn and Dunban; Alvis's scene; **party re-forms Shulk alone → Shulk, Reyn, Dunban, Sharla, Riki** | [static] | [static] |
| 160 (allowed to move freely) | five members | autosave + normal save + two cold reloads (c10, c11); next event (Eryth Sea) not reached | [static] 160 → Wii → DE byte-identical; Wii output carries the five-member party | [static] 160 → 3DS → DE byte-identical |
| 206 (Prison Island, Expert) | 6 members | [static] | [static] | [static] |
| 232 (Satorl → Valak, Expert) | 6 members | **[story] 3C L1: 232 → 233** on a save that went DE → Wii → *the Wii game* → DE | [play] 2F d2 (load, Party, save) | [load] 3A a5 (load, save) |
| 241 (Valak, Fiora alive) | 6 members (no Fiora) | [static] | [static] | [static] |
| 258 (Galahad Fortress) | 6 members | [static] | [static] | [static] |
| 269 (Fallen Arm, **Shulk alone**) | [Shulk] | [static] | [static] | [static] |
| Fiora rejoined (character 8) / guests | — | refused by design (no validated mapping) | carried Wii ⇄ 3DS (lossless) | carried Wii ⇄ 3DS |

## 2. Conversion directions

| Direction | Status | Story evidence after conversion |
|---|---|---|
| Wii → DE | VALIDATED | 2E 150 → 156; 3C 156 → 158 (same playthrough, Monado autosaves), 3C L1 232 → 233 (return trip) |
| DE → Wii | **VALIDATED for story** (was PARTIALLY) | 3C W1: 154 → 156 played by the Wii game; W2 cold reload; back to DE = the DE game's own 156 state except palette[0]/clock/time |
| Wii → 3DS | VALIDATED (3A) | (the 3DS event in §3 used a DE source; the Wii → 3DS transcode is lossless, 3A) |
| 3DS → Wii | VALIDATED (3A) | — |
| DE → 3DS | **VALIDATED for story** (was PARTIALLY) | 3C X1: 154 → 156 played by the 3DS game; X2 cold reload; back to DE = the DE game's own 156 state except palette[0]/clock/time |
| 3DS → DE | VALIDATED (3A) | — |

## 3. Azahar (3DS)

See `STORY_PROGRESSION_TESTS.md` (X1, X2): the converted DE 154 save loads (Alcamoth, Lv 51 Melia), the 3DS game plays
the 154 → 156 event, saves, reloads; back in DE it equals the DE game's own 156 save.

## 4. Transitions not exercised (remaining risk)

| Transition type | Why not | Risk assessment |
|---|---|---|
| Fiora's rejoin and later Fiora state (char 8) | refused by the converter for DE (no validated mapping) | **High for late game** — conversion stops with an explanation; nothing silently lost |
| Endgame (Mechonis, Agniratha, final areas) | no game-written save at those points | Medium — canonical round trips of 6 real late DE saves are exact; no event played |
| Future Connected | DE-only content (refused while in progress) | n/a |
| Quest-gated story steps (e.g. 233: fetch the Magma Rock) | needs quest play (item pickup in a specific cave) | Low–medium: quests and quest counters round-trip exactly [static]; no quest completed after conversion |
| Party-join at a new character (Sharla, Riki, Melia joins) | earlier than the user's save; no fixtures before story 150 except 6/8/18/20 | Medium |
