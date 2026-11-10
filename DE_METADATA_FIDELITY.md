# DE-only metadata fidelity (Phase 3C)

Scope: data the Definitive Edition save holds and the Wii / 3DS save cannot, and what happens to it on
DE → Wii/3DS → DE trips (including several Wii/3DS generations through the Sync Hub). Gameplay-state fidelity (story,
flags, items, levels, quests…) is reported separately in `GAMEPLAY_COMPATIBILITY_MATRIX.md`; it was already exact
and is unchanged by 3C (verified: identical canonical shared state to the 3B engine in every case below).

Evidence labels: **[code]** read from the DE (`exe/de/main.bin`, build 7E1DF8E0…) or Wii (`main.dol`) executable ·
**[data]** measured on real game-written saves · **[test]** automated test on real saves with synthetic edits ·
**[game]** observed in an emulator run.

## 1. The fields

### 1.1 Per item (the 3B finding "B3")

DE item records are 0x30 (equipment), 0x2C (crystals, gems) or 0x14 (stacks) bytes; the Wii/3DS records are a
different, smaller layout. Bytes of the DE record that the Wii/3DS cannot carry:

| Offset | Field | Purpose | Gameplay? | Evidence |
|---|---|---|---|---|
| `+0x11` | **Favourite mark** | user-set mark on an item | Presentation / inventory management. The only reads found copy it into the item-list UI entry (`0x3FA2F4`, `0x3FA404` → list builder `0x4C2EB0`); the item-add routine clears it (`0xBF480`, halfword store over +0x10/+0x11). No read in stat, battle, shop-price or quest code was found by the scans run (byte loads at +0x11 next to the record's presence byte). Not proven absent everywhere. | [code] |
| crystal `+0x18` for **list crystals** (fixed-id crystals) | "named" byte, 1 or 2 | For drop crystals the converter derives it from the source enemy (`named` table) as before; for list crystals the Wii has no source for it. 58 of 713 list crystals in 10 real DE saves hold 2. Effect in game unidentified — treated as possibly meaningful and preserved. | [data] |
| `+0x0A..0x0B`, equipment `+0x12..0x13`, crystal `+0x1B`, unused crystal effect slots, `+0x23`, `+0x2B` | **not initialised by the game** | The item-add routine copies a whole record from a caller-built stack buffer (`0xBF454..0xBF46C`) and then sets only index, serial, quantity and presence. These bytes are stack leftovers: identical multi-byte patterns recur on unrelated items and saves (e.g. `3A 81` / `40 29` / `70 83 10` / `6C` on 960 crystals). 4,669 of 9,697 real records have non-zero `+0x0A`. No read found. | [code] [data] |

DE also has an acquisition **serial** per item (`+0x0C`, from a per-type counter that only grows,
`0x9AB70..0x9AB88`). The Wii keeps only an age (order); 2F already maps it exactly (order preserved, items that existed
keep their DE serial).

### 1.2 Per character, flags, other DE-only state (unchanged since 2F; re-verified in 3C)

| Data | Preserved how | Status |
|---|---|---|
| Expert Mode: highest level, its EXP, reserve EXP | DE character record restored when the shared content is unchanged; otherwise highest = max(original, new), reserve untouched; **3C (E1):** while a character is at its highest level and the pair tracks its EXP, the highest-level EXP follows the EXP earned on the Wii/3DS, as the DE game does | exact [test, real Expert saves s206–s269]; **E1 fixed [game]**: after the 154 → 156 event played on the Wii, the return equals the DE game's own 156 save in every DE-only character field |
| Appearance: costume (cosmetic) slots, second palette, Shulk's second talent byte | character record / 3-way merge | exact [test] |
| Skill-link unlock indexes | character record | exact; games may raise unlocks on load (documented) |
| DE-only flags (incl. DE-only achievement/award state, Time Attack, options, Noponstones…) | template = the DE save the trip started from | exact [test] |
| Future Connected quest bytes/counters, header, location words | template / deferred | exact [test] |
| DE-only items (no Wii id) and inventory overflow (more items than the Wii box) | held in the sidecar (`deferred`), put back at their own slot when free | exact; never revived after a later DE change (staleness rules) [test] |

### 1.3 Expert Mode bookkeeping after play on the Wii/3DS (found in 3C, "E1")

The DE keeps, per character, the highest level reached and an EXP value for it (`+0xEC`, `+0xF0`). Monado's own story
saves show the rule while no EXP is banked: at the highest level `+0xF0` moves with every EXP gain (+858 for five
characters across 154 → 156, +661 across 156 → 158); on a level-up it restarts (Melia 51 → 52: 0). Up to 3B a return
from the Wii kept the pre-export value whenever the level did not rise, so after EXP earned on the Wii the pair lagged
the DE's own behaviour by that EXP (found by comparing the Wii-played 156 save, converted back, with Monado's own 156
save). 3C mirrors the DE rule when the pair was tracking at export (level = highest level and `+0xF0` = EXP) and the
level is unchanged; otherwise (Expert saves with banked EXP, where `+0xF0` ≠ EXP) the 2F rule stays. Test:
`test_return_to_de_reproduces_the_de_games_state_incl_expert_pair` (game-written saves).

## 2. Where the per-item data disappeared (3B) — root cause

1. **Export (DE → Wii/3DS)**: a DE item in a slot beyond the Wii box (e.g. crystal slot 340 of 500; the Wii box has
   300) is moved to a free Wii slot ("compaction"). Equipment and gem references follow. Overflow items wait in the
   sidecar.
2. **Wii/3DS play**: the games never move an item between slots (verified on every game-written pair: Dolphin d2,
   Azahar a5 and 3B a1 — 0 items moved).
3. **Return (Wii/3DS → DE)**: the converted item lands at its *Wii* slot. 3B restored the original DE record only
   "at the same DE slot with the same content". A compacted item is never at the same slot, so it was rebuilt from
   the empty-slot pattern: favourite, list-crystal "named" byte and the residue bytes were lost. On the s232 Expert save
   through a real 3DS session: crystal DE-only entries 176 → 90 (the B3 measurement), 104 records changed.
4. **Mis-association hazard (found in 3C)**: the same 3B rule gave the original record — favourite included — to a
   *different* item that happened to sit in the same slot with the same content: an identical item bought or found
   on the Wii after the original was sold. Demonstrated with the frozen 3B engine
   (`test_identical_replacement_in_same_slot_gets_no_mark`).

## 3. Item correspondence (3C) — `tools/itemcorr.py`

Slot numbers alone are never trusted; identity is followed in two steps:

**a) DE slot → exported Wii slot (export map).** Reconstructed from the sidecar's two snapshots with the exporter's
own rule (same slot when it fits, otherwise the free Wii slots in ascending order), then **validated item by item**:
same content (equipment sockets compared through the gem map) and the same acquisition order. A box that does not
validate is *unresolved*: nothing is restored for it (old sidecars are handled the same way; no format change).

**b) exported Wii slot → current Wii slot (survivors).** A candidate is the same slot holding the same item (same id;
for crystals/gems the full identity). Two identical items are never assumed to be one:

* the Wii makes every added item the **newest**, including a stack that was added to (`0x80159024..0x80159100`: all
  records age by one, the new or stacked-up record gets age 0); the DE does not re-age stacks (`0xBF564..0xBF5B4`);
* so a candidate is accepted only if it lies on **every** longest chain that keeps the exported acquisition order: a
  replacement obtained later, or a stack that was added to, falls off the chain;
* the **newest** chain member of a box that changed at all is indistinguishable from an identical replacement that
  took its place before anything else changed — it stays *unresolved* (reported, not restored).

**c) restore.** Each certain survivor gets its original record's DE-only bytes; the fields the Wii/3DS owns come from
the converted record (slot index, quantity, serial, and for equipment armour class, socket count and sockets — gems
may have been changed on the Wii). The canonical shared state must be identical before and after; a box that would
change it is left as converted and reported (never happened in any test).

Never done: adding an item, reviving a sold/consumed item, moving a mark to another copy, restoring a quantity.

**Reverse direction (Wii-only per-item bytes, DE → Wii).** The Wii equipment header has 5 low bits (values 0/1/2 in
real saves) and crystals a byte `+0x16`; their meaning is unidentified. They are kept from the Wii base only for the
**same DE item instance**: same slot, same id and same DE acquisition serial as in the DE save the sidecar exported
(the DE never re-issues a serial). 3B kept them for any same-content item in the slot.

## 4. Verified behaviour (all on real game-written saves; marks and inventory edits synthetic)

| Scenario | 3B | 3C | Test |
|---|---|---|---|
| s232 Expert → 3DS → the **3DS game's own save** (Azahar a5) + flags → DE | crystals 176 → 90 DE-only entries; 104 records changed | every record byte-identical (index/serial aside); 176 → 176 | `test_b3_real_3ds_session_keeps_every_de_only_record` |
| 17 marks (compacted crystals 305/340/499, overflow weapons 150/162 and material 166 in the sidecar, same-slot items) → Wii played → DE | compacted marks lost | all 17 back; 0 records differ | `test_compacted_deferred_and_same_slot_favourites_return` |
| DE → Wii → 3DS → Wii → DE (each W hop played) | lost for compacted items | all back | `test_three_platform_cycle` |
| marked crystal used up on the Wii | not revived | not revived; mark count −1, no mark moved | `test_sold_item_not_revived_and_mark_not_moved` |
| identical weapon re-bought into the same slot | **old record + mark applied to the new weapon** | new weapon unmarked | `test_identical_replacement_in_same_slot_gets_no_mark` |
| duplicates: two identical weapons, older marked; newer sold / older sold | — | mark stays with the older / disappears; never moves to the other copy | `test_duplicate_items_mark_stays_with_its_own_instance` |
| stack partly used (order unchanged) / stack added to (re-aged) | — | mark kept / **unresolved** (could be a used-up-and-found-again stack) | `test_stack_used_partly_keeps_mark_stack_added_to_does_not` |
| newest surviving item of a changed box | — | unresolved, reported | `test_newest_survivor_of_a_changed_box_is_unresolved` |
| equipment worn/changed on the Wii | — | mark kept | `test_equipment_swap_and_gem_change_keep_mark` |
| unplayed return DE → Wii → DE with compaction/overflow (3B finding **B2**) | **refused** (slot-by-slot read-back) | byte-identical to the original DE save | `test_unchanged_wii_is_byte_identical`, `test_de_3ds_de_unplayed_with_compaction_is_byte_identical` |
| Wii-only bits, DE item replaced by an identical one | stale Wii bits kept | fresh record | `test_identical_replacement_gets_fresh_record` |
| Sync Hub, 5 generations (DE → 3DS(sold crystal) → Wii → DE → 3DS) + unchanged re-save + rollback | — | marks follow the items; the disposed crystal never returns although generation 1's anchor sidecar still holds it; re-save in sync; rollback exact | `test_alternating_generations_keep_marks_and_never_revive_disposed_items` |

Engine parity with the frozen 3B engine (`phase3c/scripts/e_parity_3b.py`, `phase3c/work/e_parity_3b.json`): first
conversions in both directions on 8 real saves, a 3DS export and a DE → Wii return are **byte-identical**; the
Wii/3DS → DE returns differ **only inside DE item records** (826, 830, 459 and 2 bytes) with identical canonical
shared state; the three unplayed returns 3B refused now return the source byte for byte.

## 5. Remaining limits

* The **newest surviving item of every box that changed** and **stacks that were added to** on the Wii/3DS lose their
  mark/named byte/residue (conservative; reported in the conversion log as `uncertain`). Everything else returns.
* Items **acquired on the Wii/3DS** have no DE-only data (the games have none to give).
* A favourite mark set in DE **after** the export while the Wii/3DS was played too is a DE-only change on a diverged
  branch: the divergence rules apply (one branch is kept, never merged).
* Purpose of the list-crystal "named" byte and of the Wii equipment header bits is not identified; both are preserved
  for the same item and never invented for another.
