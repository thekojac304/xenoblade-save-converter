# Fiora's later form at the scenario-288 split — analysis (Phase 3F)

Evidence tags: **[data]** genuine saves (public DE playthrough 283/288/291 in `phase3d/fixtures`), **[code]** read from
the Wii executable `exe/wii/main.dol` (disassembly in `phase3f/work/f_8007fd.txt`, `phase3e/work/f_8007f4.txt`),
**[table]** the game's own data tables, **[game]** written or shown by a game in an isolated emulator run
(`FIORA_REUNION_GAMEPLAY_TESTS.md`), **[hypothesis]** not proven.

## A1. The scenario-288 state

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Why is Fiora absent at 288? | Story split on the Fallen Arm: Shulk, Reyn, Sharla and Fiora are separated from Dunban, Melia and Riki; scenario 288 = "Dunban, Melia and Riki find themselves together ... set out to look for them" (`MNU_scenario` 288 → help 134) | [table] `gb:MNU_scenario_ms` 134; [data] party 288 = `[4, 6, 7]` |
| 2 | Active / inactive flags | Party list `[4, 6, 7]`; Fiora-8's journal entry stays (first join 275); join mask (DE 32-bit flag 0 = Wii flag 0x108) keeps bit 8 set (`0b111111111110` from 276 on); no other per-character "available" flag changed for her between 283 and 288 | [data] `canon` `flag_bitmask_0` on 269/276/283/288/291 |
| 3 | Which records stay populated | Record 8 stays complete (level 53, EXP, AP, coins, skill trees, arts, palette, links) - only its equipment references become `(0, 0)` on the DE (Wii/3DS: gear id, row 0, box index 0xFFFF); record 3 (Fiora's first form) stays frozen | [data] `ccmp` 283 → 288 |
| 4 | Where her equipment and gems are | DE table 0x3BB50, entries of character 8 (7 × 0xB4): head 667, body 668, arm 669, legs 670, feet 671 (her default "Mechonis" armour, each with its fixed gem except the feet), weapon 65 Mechonis Swords with two **socketed** gems (Strength Up IV rank 4 / 35; Agility Up IV rank 4 / 20). Wii/3DS: staging slot 158 (= 150 + 8) of each box, staged gems 0-1 of character 8 (item +0x11AB8 + 16·(56 + i)), links (6, 0) and (6, 1) at item +0x12038 + 2·(56 + i) | [data] `phase3e/scripts/dump_store.py`; [code] 0x8007F368 |
| 5 | Inventory references during the separation | Her six items and two gems are **removed from the inventory**; they exist only in the stored-equipment table. 283 → 288 is a swap: the four leaving take −4 items per gear box and 12 socketed gems out, while Dunban, Riki and Melia (stored at 283) come back with +3 per box and 13 gems | [data] `invdelta.py` 283 → 288 |
| 6 | Art palette and skill trees | Preserved unchanged (record 8 is not touched by the departure). Between 283 and 288 the player learned one Courage node (SP 692 → 106, learned `[1,1,1] → [1,2,1]`) - normal play, unrelated to the split | [data] |
| 7 | Skill links and affinity | Other characters' Fiora-8 link slot (DE slot 8) and unlock levels unchanged; affinity unchanged by the departure | [data] `test_fiora_link_slot_round_trips` |
| 8 | Stored gear on Wii / 3DS / DE | Same content in all three; layouts differ (above). The converter's canonical `stored_gear[8]` reads identically from the DE table, from a converted Wii file and from a converted 3DS file | [data] probe + `TestTranslation` |
| 9 | Which event restores her | `EVT_cs` 1108 `vs12210100` (scenario_flag 288, ma1601, site (-614.068, 11.272, 338.309)) - Dunban's group reaches the Hidden Machina Village area and finds the others; chained `EVT_sev` 180 `vs12220050` / `EVT_cs` 1109 `vs12220060` (289, same site) - the Machina appear, Linada; the story becomes 291 and the party `[4, 6, 7, 1, 2, 5, 8]` | [table] `EVT_cs`, `EVT_sev`; [game] Monado m1/m1b, Azahar x1-x3 |
| 10 | Is the public 291 a completed reunion? | Yes: party `[8,6,5,7,2,1,4]`, nothing stored, every returning item present - but saved later and elsewhere (map index 5, party re-ordered by the player), so the **native reference used in 3F is Monado's own reunion of the genuine 288** (`de_s291_monado_m1b_native_reunion.sav`), not the public 291 | [data] + [game] |

### Field-level differences

| Field | 283 (before) | 288 (split) | 291 native (after) |
|---|---|---|---|
| party | `[8, 2, 1, 5]` | `[4, 6, 7]` | `[4, 6, 7, 1, 2, 5, 8]` |
| Fiora-8 equipment refs | inventory slots | `(0, 0)` (DE) / gid + 0xFFFF (Wii) | new inventory slots (new serials) |
| DE table 0x3BB50, char 8 | zero | 6 records + 2 gem copies | zero (cleared) |
| Fiora-8 level / EXP / arts / palette / skill trees / links | — | unchanged by the split | unchanged except event AP +108 and SP +38 (every character gets the same) |
| join mask bit 8 | 1 | 1 | 1 |
| story flags | | | 288 → 291; flags 12798, 8117-8119, 8718 set, 13118 cleared, 1345 111 → 254, quest counter 801 closed |
| Expert Mode (DE only) | | | reserve EXP +915 (the 3DS gives the same 915 EXP to the characters) |

### Is the 3E mapping sufficient?

**Yes for the data; no for the policy.** The same table, routine and canonical form hold character 8 exactly (static
probe and every round trip). Two Fiora-specific facts needed a rule (A2): her first-join initialisation, and - found in
the gameplay test, not Fiora-specific - the room the games need to give stored gear back (F1).

## A2. The restoration path

### Verified rules [code]

| Step | Wii routine | What happens for character 8 |
|---|---|---|
| Party change | **0x8007FB98** (party update): for each old member not in the new party → `0x8007F368(id, 0)` (leave) and remove; for each new member not in the old party → `0x80157CD8(id, 1)` then `0x8007F368(id, 1)` (join) | Fiora-8 is an ordinary member here |
| Capacity mask | `0x80157CD8(id, 1)`: if `id` is one of the table at 0x8052F6B8 = **(3, 5, 6, 7, 8, 11)**, set bit `id` in item +0x12108; the Wii box getter 0x80158490 gives equipment/material boxes **60 + 10 × (bits set) + min(item +0x12110, 30)** slots | Fiora-8 raises capacity by 10 at her first join (bit 8); Shulk, Reyn, Dunban never do |
| Join | `0x8007F368(id, 1)`: character checks only `1 ≤ id ≤ 11` (`cmplwi r18, 1` / `0xb`); per slot head…weapon: NEW item from the reference's gear id (`0x80158EEC` add; empty weapon → default weapon 0x8003B148), socket count from staging slot 150 + id, staged gems re-added by their links. **If the add fails (box full) the routine returns 0 at once** (`8007F488 cmpwi r3,0 / li r3,0 / b exit`) | no character-specific branch; the two `cmpwi …, 8` are the 8-staged-gem loop limits |
| First-join initialisation | after the joins, per new member: `0x80082D28(id, 1)` reads flag 0x108, returns 1 only if bit `id` was **clear**, and sets it. Only then: level = party average (0x800A1238), re-init (0x8009F974, 0x800A2BD0), and **for id 8: copy from record 3** (+0x3534 / +0x17C virtual 0x200 → 0x1F8) | Fiora-8 joined at 275 → bit 8 already set → **not re-initialised at the 288 → 291 reunion** |
| Skill object mirror | 0x800A3644-0x800A3690 copies the skill object 3 ↔ 8 after skill updates (3D finding) | unchanged by the reunion |

### Platform comparison

| | Wii | New 3DS | DE |
|---|---|---|---|
| Storage | staging slot 158, staged gems/links of character 8 | same layout (3DS file = Wii layout, LE) | table 0x3BB50 entries of character 8 |
| Join for Fiora-8 | 0x8007F368 [code] | same logic [game: x3 - her gear and both gems returned exactly] | [game: m1b - returned exactly] |
| Full box at the join | character's return skipped [code] | **observed** [game: x2 - Shulk, Reyn skipped] | DE boxes are large; not observed |
| First-join gate | flag 0x108 bit 8 [code] | same flag (Wii layout) - bit set, Fiora not reset [game: x3 level/skills unchanged] | DE 32-bit flag 0 bit 8 set in all genuine post-275 saves [data] |

### Hypotheses (not needed by the converter, not proven)

* The bonus term item +0x12110 (min 30) is probably an inventory-expansion reward; its source was not traced. The
  converter keeps the base's value (as since 2F) and reserves room against the capacity it actually yields.
* The DE uses the same party-update logic (its returns at 156→158, 158→160 and 288→291 behave identically); not read
  from the DE executable.

## Consequences for the converter (Part C)

1. **Fiora-8's stored gear is translated** like the other characters' (`stored_gear.VALIDATED` now includes 8).
2. **Guard:** a stored Fiora-8 with join-mask bit 8 clear is refused in every direction (`first_join_problems`) - the
   Wii/3DS would reset her at the return. No genuine save has that state.
3. **F1 (all stored characters):** while characters are stored, DE → Wii/3DS keeps
   `stored_gear.reunion_room()` slots free per box (one per stored item incl. the default weapon, one per staged gem);
   extra unequipped items wait in the sidecar/record as before. Wii/3DS → DE refuses a save in which the game skipped
   a return (`unfinished_returns`), naming the characters - converting it would drop their gear.
