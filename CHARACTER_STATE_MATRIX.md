# Character state matrix (3D-rc1, updated for 3E-rc1 and 3F-rc1)

Every character record of the three games, what it means, and what the converter does with it. Evidence tags as in
the earlier reports: **[game]** = written or shown by a real game (Monado / Dolphin / Azahar run, or a genuine save),
**[code]** = read from the game's code, **[table]** = the game's own data tables, **[static]** = converter analysis only.
Sections 1-5 are the 3D text (3E/3F changes are marked there); section 0 is the current state. The 3E copy:
`phase3f/docs/previous_3E/CHARACTER_STATE_MATRIX.md`.

## 0. Current support (3F-rc1)

| Character state | DE → Wii/3DS | Wii/3DS → DE | Wii ↔ 3DS | Played by a game after conversion |
|---|---|---|---|---|
| Main characters 1, 2, 4-7 in the party | ✓ | ✓ | ✓ (lossless) | ✓ (2E-3E) |
| Fiora's first form (3), scenario < 275 | ✓ | ✓ | ✓ | ✓ |
| Fiora's later form (8), scenario ≥ 275, in the party | ✓ (3D) | ✓ | ✓ | load/save Wii, 3DS, DE (3D); reunion party 3DS (3F) |
| 3 in a party at ≥ 275, 8 at < 275, guests 9-13 in a party | refused | refused | carried (same game) | — |
| Away in a story split with stored gear: 1, 2, 4, 5, 6, 7 | ✓ (3E) + reunion room (3F, F1) | ✓ | ✓ | Alcamoth reunions Wii/3DS/DE (3E); Fallen Arm 288 → 291 on the 3DS and DE (3F: Shulk, Reyn, Sharla) |
| **Away with stored gear: Fiora's later form (8), scenario 288** | **✓ (3F)** + reunion room | **✓ (3F)** | ✓ | **DE (native) and 3DS (converted): her gear and both gems returned exactly**; Wii not played (locked workstation) |
| Fiora-8 stored while the join mask lacks bit 8 (never seen) | refused (3F guard: the game would re-initialise her) | refused | carried | — |
| In the party but the game skipped the return (references still staged; full pocket at the reunion) | n/a | **refused, names given (3F, F1)** | carried | reproduced on the 3DS with a 3E export (x2) |
| Retired record 3 after 275, stale stash entries of record 3 | kept from base/sidecar | kept | carried | — |

Fiora-8 at the 288 split [data, 3F]: record 8 complete and unchanged by the departure (level 53, arts, palette, skill
trees, links); equipment references `(0, 0)` (DE) / gear id + box index 0xFFFF (Wii/3DS); gear in DE 0x3BB50 entries
of character 8 / Wii staging slot 158 + her staged gems 56-57; join mask bit 8 set. Details:
`FIORA_REUNION_ANALYSIS.md`.

## 1. Record layout

| Game | Records | Size | Where |
|---|---|---|---|
| Wii (`monado01`) | 14 (0 unused, 1–13) | 0x2AC | `wii_save.CHAR_BASE` |
| New 3DS | same records as the Wii (QuickLZ-packed little-endian copy of the Wii layout) | | `xc3d` |
| DE (v10) | 16 main records (1–16) + Future Connected / Nopon records up to 27 | 0x138 | `de_save.layout()["chars"]` |

## 2. Character IDs

| ID | Character | Wii / 3DS | DE | Converted? |
|---|---|---|---|---|
| 1 | Shulk | main | main | yes |
| 2 | Reyn | main | main | yes |
| 3 | Fiora (first form) | main **until scenario 274**; frozen afterwards | same | yes before scenario 275; afterwards only its frozen record travels with the sidecar/record |
| 4 | Dunban | main | main | yes |
| 5 | Sharla | main | main | yes |
| 6 | Riki | main | main | yes |
| 7 | Melia | main | main | yes |
| 8 | Fiora (later form) | dormant record before 275, **main from 275** | same | **yes from scenario 275 (new in 3D)**; refused in a party before 275 |
| 9 | Dickson (guest) | guest=1 [table] | guest | refused in a party, record kept |
| 10 | Mumkhar (guest) | guest | guest | refused in a party, record kept |
| 11 | Alvis (guest) | guest | guest | refused in a party, record kept |
| 12, 13 | Dunban (prologue guest records) | guest | guest | refused in a party, record kept |
| 14, 15 | Kino, Nene (Future Connected) | — | DE only | DE-only, never on the Wii/3DS; kept from the DE save / sidecar |
| 16–27 | Nopon (Future Connected guests) | — | DE only | DE-only, kept |

No genuine save of the 359 public DE saves, the user's Wii/3DS saves, or any run in this project has a guest (9–13) in
the saved party [game]: guests exist only inside scripted battles. A save with one is refused, never re-mapped.

## 3. Fiora: records 3 and 8

### Era boundary (scenario 275)

Both games' party journal table `JNL_PCrelatelist` shows character 3 for scenarios 11–274 and character 8 from 275
[table]. The public playthrough (2025-09-11 saves 260–291) agrees [game]: story 269 party `[1]` (Fiora absent), 276
`[8,1]` (reunited at Fallen Arm, event vs12080150), 283 `[8,2,1,5]`, 288 `[4,6,7]` (temporary split without Fiora),
291 `[8,6,5,7,2,1,4]`. `canon.FIORA_ERA = 275`; `canon.fiora(story)` and `canon.main_chars(story)` decide which record
is "Fiora" for every reader and writer.

### What each record holds

| Field | Record 3 after 275 | Record 8 before 275 | Record 8 after 275 |
|---|---|---|---|
| level / EXP | DE: frozen (lv 9 in the public playthrough) [game]. Wii: frozen | DE: lv 40, EXP 0 (table default) [game]. **Wii: accrues EXP while absent** (870 at story 18, 10 436 at 150) [game] | live; at the rejoin the DE sets lv 53 [game] |
| AP, affinity coins | frozen (DE: coins of record 3 still move after the rejoin [game]) | default | live; seeded from record 3 at the rejoin |
| skill trees | Wii: **mirror of the active record** (code 0x800A3644–0x800A3690 copies the skill object +0x1F4..+0x29F 3→8 and 8→3 after every skill update) [code]; DE: frozen | Wii: mirror of record 3 (Fiora-3 skill ids 51+) [game] | own skill ids 176–200 (learn routine 0x800A34C8; "Mechonis Equipment" 176, "Battle Stance" 181) [code][table]; DE: SP/learned counts seeded from record 3 (`[100,155,13]/[1,1,1]` → `[100,193,13]/[1,1,1]`) [game] |
| skill links | other characters' link slot 3 keeps Fiora-3's links | — | **separate DE slot 8** (e.g. Shulk's slot 8 = `[0,0,181,0,0]` at story 291) [game]; unlock levels mirrored slot 3 = slot 8 [game]; the Wii has one Fiora row per character (row of the active record) |
| equipment | frozen references | Wii: staging gear ids 667–671 + weapon 65 (box index 0xFFFF) [game] | DE: rejoin gear added to the inventory and equipped [game] |
| arts / palette | frozen | Fiora-8 arts (25, pc 8) at defaults | live; DE palette slot 8 = art 134 at 276 [game] |
| appearance (DE) | DE-only cosmetic fields kept by the sidecar | | DE-only cosmetic fields kept by the sidecar |

Records 3 and 8 are **not** linked or swapped by the games; record 8 is seeded once from record 3 at the rejoin and is a
separate character from then on (DE) — on the Wii only the skill object is kept identical by the mirror.

### What the converter does (3D-rc1)

| Situation | Behaviour |
|---|---|
| story < 275, any direction | exactly the 3C behaviour (fingerprints of all pre-275 fixtures identical to 3B/3C, `fp_check.py`); record 8 = template/base record |
| story ≥ 275, DE → Wii/3DS | record 8 written from the DE (level, EXP, AP, coins, SP, learned nodes with ids 176+, selected tree, arts, palette, equipment); record 3's skill object = copy of record 8's (Wii mirror); link rows of the other six characters use record 8's DE slot 8; unlock levels stay mirrored |
| story ≥ 275, Wii/3DS → DE | record 8 read as Fiora; DE link slot 8 written from the Wii Fiora row and slot 3 unlock mirrored; record 3 (frozen) kept from the template / sidecar |
| character 3 in a party at ≥ 275, or 8 at < 275 | **refused** (`unsupported_party`), nothing written; 3 is never substituted for 8 or back |
| record 8 at ≥ 275 holding foreign (Fiora-3) skill ids | **refused** (read-back: non-own skill id); `phase2c.SKILL_ID_ALT` stays empty until a genuine Wii/3DS save shows such ids |
| guest in the party | refused (all directions involving the DE); Wii ↔ 3DS carries the party unchanged (same game) |
| main characters away in a story split, holding real gear in the stored-equipment table (DE 0x3BB50 / Wii staging slot 150+id) | 3D: **refused (D2)** unless the destination stores the same gear or itself has them away (return to the playthrough's own save); see section 5. **3E: translated (1, 2, 4-7); 3F: also Fiora-8, with the reunion room (section 0)** |

## 5. Stored equipment of members who are away (D2)

| | DE | Wii / 3DS |
|---|---|---|
| Where | 0x3BB50: per character 7 × 0xB4 = equipment record (verbatim, incl. its old slot and gem refs) + copies of its 3 gem records | box slot 150 + id (ids 1–11) of each equipment box, gem descriptors inside the record; per-character gem records in the item tail (routine 0x80158308) |
| When written | a member leaves in a story event (283 → 288: Shulk, Reyn, Fiora, Sharla) [game] | the same routine family; prologue Dunban's slot holds the scripted prologue gear (Monado, id 37) on the user's story 6/8/18 saves [game] |
| At the reunion | gear re-added to the inventory in new slots, new serials, gems restored; entry cleared to id 0 [game, 288 → 291] | not observed (event not reached); the Wii does not clear its staging records (stale values on the user's story-150 save) |
| Converter | not translated → refusal rule `tools/stored_gear.py` (joined members only: journal scenario Shulk/Reyn 1, Sharla 70, Dunban 100, Melia 128, Riki 137, Fiora 8 275; Fiora's record 3 excluded; table defaults ignored) | same rule, other direction |

Known, accepted: on a *foreign* Wii base (DE-native playthrough) record 3 keeps the base's values after 275 — the games
never show record 3 again (journal), and the DE's own record 3 comes back from the sidecar.

## 4. Validation

| Check | Evidence | Result |
|---|---|---|
| Wii game loads the converted 276/283/288/291 saves, saves again | Dolphin `wd_s276_save`, `wd_s283_save`, `wd_s288_save`, `wd_s291_save` | loads; canonical diff of the game's re-save = clock, play time, position only [game] |
| Wii keeps record 8's own skill ids and the mirror | `wdiff.py` on the re-save | ids 176/181/186 kept; only node/link state bytes normalised (all characters; limitation 14) [game] |
| Wii re-save → DE with sidecar | `r_w2d_s276..291` + `itemset.py` | shared state = original + clock/time/position; compacted equipped items keep their Wii slot (limitation 6), every item and every equipped item's content identical |
| unchanged returns | `test_de_to_wii_and_back_unchanged_is_byte_identical`, `..._3ds_...` | byte-identical (4 saves × 2 families) |
| 3DS game | Azahar x5_s291_save: Party screen (Fiora lv 53 leading), Change Equipment (Mechonis Swords + gems, Ether Goggles, Ether Frame), Skill Trees (Daring / Courage / Zeal), in-game save | shared state kept; the game raised 9 link unlocks (limitation 5); back to DE with the record → Monado cold load + save: clock/time only |
| Wii/3DS saves of 276/283/288 | made before D2 was found (their exports are now refused) | still evidence that the games load and save character 8 and the split party; their returns to the original DE save are allowed and keep the DE's stored gear byte-equal |
| equipment / skill initialisation | `test_wii_records_after_the_rejoin` | level, EXP, AP, coins, SP, learned, selected tree, arts of record 8 round-trip exactly |
