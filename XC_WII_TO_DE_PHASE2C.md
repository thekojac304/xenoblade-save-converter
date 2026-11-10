# Xenoblade Chronicles Wii → Definitive Edition
## Phase 2C: Characters, Arts, Skills, Equipment and Inventory

Date: 2026-11-05. Read-only static analysis of copies of your own executables, game data and saves.

What was not done:
- No save was created, edited, injected or loaded. Dolphin and Monado were not run.
- No differential saves were made. All results come from code, game tables and the existing saves.
- Nothing in the Monado install, the Dolphin NAND, the disc image or `work/originals` was modified. After the
  work, `work/originals/SHA256SUMS.txt` still verifies, and the live `monado01` and `save_0/bfsgame00.sav` hashes
  match their snapshots.

Evidence labels (as in Phase 2B):
- **[C] Code.** Read from disassembly, with an address. Wii addresses are `main.dol` SX4E01; DE addresses are the
  NSO `7E1DF8E0…`.
- **[D] Data.** Reproduced by a script against real saves or game tables.
- **[CD]** Both.
- **[H] Hypothesis.**
- **[3P] Third party.** hashcade/xbde-save-editor or hanyu1774, re-checked here against real saves.

---

## 1. Executive findings

1. **The Wii character and inventory formats are now decoded, and the decoding is backed by code.**
   - Sources: the GAME and ITEM serialisers `0x8023E414` and `0x8023EA80` (the ITEM part starts at `0x8023EC2C`),
     their loaders, and the item-box accessor `0x80158490`.
   - Every byte of the 14 character records and of the 0x12120-byte ITEM payload is either a named field or an
     explicitly labelled raw span.
   - Decoding then re-encoding is byte-identical for both Wii saves (13/13 tests pass) [CD].
2. **IDs transfer by identity. No translation table is needed, only the verification tables delivered here** [D].
   These spaces exist unchanged in DE:
   - all 3,765 Wii global item IDs (same type and same row in each type table)
   - 152 art IDs, 200 skill IDs, 40 skill-link rows and 64 skill-link shape rows
   - 97 gem effects and 600 crystal definitions

   DE only appends new IDs, and changes icons and some English text. There are two minor balance edits:
   Summon Aqua's `st_itv`, and one Rapid Healing skill parameter.
3. **Equipment uses the same model in both games: a character points at a slot in a per-type inventory box.**
   - All 35 equipped references of your six party members resolve to the right item instance [CD].
   - DE boxes have 500 slots and Wii uses at most 150, so each Wii slot number can be kept as the DE slot number.
4. **Arts use DE's exact on-disk encoding** of (level, manual-flag) byte pairs [CD]. The Wii stores them per
   character, indexed by `pc_arts.idx`; DE stores one global table indexed by art ID. All 118 art records of
   characters 1–7 pass the `get_lv` consistency check (event and talent arts exempt). Art owner and index are
   identical in DE for all 152 arts.
5. **Your actual progression, decoded:**

   | | Shulk | Reyn | Dunban | Sharla | Riki | Melia |
   |---|---|---|---|---|---|---|
   | Level | 52 | 52 | 51 | 52 | 51 | 51 |
   | EXP into level | 12,295 | 9,150 | 21,224 | 1,110 | 29,548 | 33,318 |
   | AP | 2,832 | 6,987 | 7,579 | 10,845 | 8,721 | 14,984 |
   | Affinity Coins | 78 | 78 | 77 | 78 | 77 | 77 |
   | Tree-1 skills learned | 4 | 4 | 3 | 3 | 2 | 3 |
   | SP on tree 1 | 1,860 | 1,803 | 1,057 | 1,952 | 169 | 219 |

   The save genuinely contains:
   - Skill progress only on each character's first tree, and that tree is still selected for everyone.
   - No skill links assigned.
   - No art manuals used: art levels are at most 4 and every manual flag is 0.
   - No art manuals in the inventory.

   A faithful conversion reproduces exactly this. It is not a decoding gap.
6. **Gems are fully decoded** [CD]:
   - 68 loose gems; 16 socketed references to loose gems; 37 built-in gems on equipment.
   - The descriptor packer `0x80156380` gives effect, rank, strength and chance.
   - For every loose gem, chance equals the table `percent` for its rank and strength is inside the rank's range.
7. **Remaining gaps, in order of severity** (§9):
   - **Crystals.** 159 records. Header decoded; identity and payload not yet.
   - **Collectopaedia.** The Wii storage was not located.
   - Smaller items:
     - meaning of the Wii EXP-earned counter `+0x2A0` against DE `+0xF0/+0xF4`
     - palette slot layout, to confirm in game
     - the per-character staging slots
     - DE stack field `+0x0A`
8. **With Phase 2B, a high-fidelity conversion now looks achievable.** Story, quests, flags, characters, arts,
   skills, equipment, gems, money and the stackable inventory all have complete, checked rules. Crystals and the
   Collectopaedia are the only categories that cannot yet be converted.

---

## 2. Wii character record (0x304 bytes, 14 records)

**Location** [C]. GAME payload starts at `0xB260`.
- It begins with a 0x41F0-byte memcpy of the game-state object.
- Then come 14 records of 0x304 bytes from **`0xF450`**. Record *k* is character ID *k*: 1 Shulk … 7 Melia,
  8 Mechon Fiora, 9 Dickson, 10 Mumkhar, 11 Alvis, 12–13 Dunban variants. Record 0 is unused.
- Earlier phases' "Shulk at 0xF8D0" is record 1 + 0x17C (the level field).
- Serialiser `0x8023E414`, loader `0x8023F5B8`. Runtime character objects have a stride of 0x3DD4. Runtime offsets
  below 0x17A are copied 1:1.

| Offset | Size | Field | Source | Class |
|---|---|---|---|---|
| 0x000 | 2 | character ID | runtime +0 | direct |
| 0x002 | 12 | equipped global item ID ×6 (head, body, arm, legs, feet, weapon) | copy | direct [CD] |
| 0x00E | 12 | equipped item row in its type table ×6 | copy | direct (redundant) [D] |
| 0x01C | 12 | equipped **box index** ×6 (0xFFFF = none) | copy | direct [CD] |
| 0x028 | 0xA0 | per-armour-slot stat cache (class, defence values) | copy | **derived** [D] |
| 0x0C8 | 0x20 | weapon stat cache (speed floats, damage low/high) | copy | **derived** [D] |
| 0x0E8 | 0x30 | **art levels**: 24 × (u8 level, u8 manual flags) at `2·pc_arts.idx` | `0x800A2000` | direct [CD] |
| 0x118 | 1 | palette flag (1) | | unknown, low |
| 0x119 | 8 | art palette (8 art IDs, u8) | `0x800A2060` | direct [CD] |
| 0x121 | 8 | Monado palette (Shulk) | | direct [CD] |
| 0x129 | 7 | talent-art list (`[0]` = active talent; Dunban 41–44, Sharla 61–62, Melia 96–102) | `stb 0x41(r23)` | direct [CD] |
| 0x130 | 0x48 | u16 flags and a palette-like byte list | | unknown, low |
| 0x17C | 4 | **level** | runtime +0x17CC | direct [C] |
| 0x180 | 0x74 | HP, strength/agility/ether and other stat floats | runtime +0x17D0… | **derived**; recomputed after load (`0x8023F78C`, `0x8009F974`) [C] |
| 0x1F4 | 0x8F | **skill object**: 11 rows × 13 bytes (below) | `0x80260D58` / `0x80260E30` | direct [C] |
| 0x284 | 4 | **Affinity Coins** | clamped to 0–999 at `0x802639C8` | direct [C] |
| 0x288 | 20 | **SP per tree** ×5 | runtime skill +0x888 | direct [C] |
| 0x29C | 4 | **selected tree** | runtime skill +0x89C | direct [C] |
| 0x2A0 | 4 | EXP-earned counter (= cumulative level cost for Shulk and Reyn) | runtime +0x177C | direct; DE target unknown [CD] |
| 0x2A4 | 4 | **EXP into current level** | runtime +0x1780 | direct [CD] |
| 0x2A8 | 4 | **AP** | runtime +0x1784 | direct [CD] |
| 0x2AC | 0x14 | misc (u16 100, u32 0x32C832, floats) | runtime +0x34D4 | unknown, low |
| 0x2C0 | 1 | flag | | unknown, low |
| 0x2C1 | 0x43 | zero-filled on save (memset 0x40) | | none |

**Skill object** [C]. The learn routine is `0x800A34C8`: the node cost is `BTL_PSVskill.point_PP × 100`, and the
skill row is `(id−1)·25 + 5·tree + node + 1`.
- **Rows 0–4 are the five trees.** Each row has 6 entries of (u8, u8). Entry 0 is a header; entries 1–5 are nodes
  holding the learned skill ID (0 = not learned) and a state byte.
- **Rows 5–10 are skill-link rows.** Row 5+j belongs to the j-th other main character in ID order. A node holds
  the linked skill ID and a state byte (1 = slot unlocked).
- This row ↔ source order was verified against pair affinity from the flag bank:
  - Unlocked slots equal `1 + ⌊affinity/1000⌋` for 13 of 14 non-zero pairs.
  - The exception is Shulk–Dunban: 1,240 affinity but 1 slot. DE re-derives this anyway (§4).
- The link-menu code at `0x80268AB0` confirms 6 rows and the coin budget.

**Equipment** [CD]. The character record holds item ID, row and box index for each slot. The box record repeats
the item ID, so references can be checked: **35/35 resolve**. Reyn's head slot is empty.

---

## 3. DE v10 character record (0x138 bytes, base `0x152728`, index = ID − 1)

Layout from [3P], with the +0x3C0 v10 shift from Phase 2A. It was re-verified on your v10 save (scenario 6) and the
public v7 scenario-206 save:
- Equipment references resolve in both.
- Template levels match: Dunban 27, Fiora (Mechon) 40.
- The art table sits at `0x153AA8`.

| Offset | Field | Wii source |
|---|---|---|
| 0x00 / 0x04 / 0x08 / 0x0C | level / EXP / AP / Affinity Coins (≤ 999) | 0x17C / 0x2A4 / 0x2A8 / 0x284 |
| 0x14–0x2B | 6 × (u16 box index, u16 type) | 0x01C + box type |
| 0x30 | cosmetic ×6 (DE only) | keep template (0) |
| 0x48 / 0x5A | palette (talent + 8) / second palette | `[0x129] + 0x119`; Shulk `[1] + 0x121` |
| 0x78 / 0x7C / 0x90 | selected tree / SP ×5 / learned count ×5 | 0x29C / 0x288 / count of non-zero nodes, rows 0–4 |
| 0xA4 | link unlock index ×8, by source ID | (unlocked slots − 1), rows 5–10 |
| 0xC4 | links u8[8][5], by source ID | node values, rows 5–10 |
| 0xEC / 0xF0 / 0xF4 | highest level / its EXP accumulator / reserve EXP | level / template / template |
| 0x10, 0x2C, 0x6C, 0xF8–0x137 | unknown | keep template |

Arts: 188 × (level, flags) at `0x153AA8`, indexed by art ID − 1 [3P/D]. Manual flags 1, 3 and 7 raise the cap to 7,
10 and 12 (DE `0x1926D0`).

---

## 4. Arts and skills mapping

| Item | Wii | DE | Rule | Evidence |
|---|---|---|---|---|
| Art IDs | `pc_arts` 1–152 | 1–235 (153+ Future Connected) | identity; same owner `pc` and `idx` 152/152 | [D] `tables/idmap_arts.tsv` |
| Art level and manual flags | char +0xE8 + 2·idx | `0x153AA8 + 2·(id−1)` | copy both bytes | [CD] |
| Talent pair (Shulk arts 1/2 share idx 16) | one byte | two records | write the value to both | [D] DE saves hold both at level 1 |
| Melia discharges 97–102 | own idx 17–22 | DE derives them from summons (`0x47D6A0`) | copy; DE re-syncs | [3P] |
| Art manuals (`ITM_artslist`) | 0 in inventory; all flags 0 | 240 → 376 IDs | identity | [D] |
| Skill IDs | `BTL_PSVskill` 1–200 | same 200 | identity (199/200 identical; one internal parameter) | [D] |
| Tree progress | node IDs in rows 0–4 | learned count | count of non-zero nodes (contiguous 35/35) | [CD] |
| SP / selected tree | 0x288 / 0x29C | 0x7C / 0x78 | copy | [C] |
| Hidden 4th/5th trees | Wii flags 0x3508/0x3509 | DE 0x36FC/0x36FD | Phase 2B +500 rule | [CD] |
| Skill-link slots | rows 5–10 | 0xA4 / 0xC4 | row → source ID mapping above; DE re-derives unlocks from affinity, monotonic (`0xBC240`) | [CD] |
| Link shapes (`MNU_PSset`) | 64 rows | 64 rows | identical | [D] |
| Affinity Coins | 0x284 | 0x0C | copy (both capped at 999) | [C] |

---

## 5. Equipment and inventory structure

The ITEM payload (`0x11F60`, 0x12120 bytes) is a memcpy of the item object. The getter `0x80158490` returns base,
count and record size for each type [C].

| Box | Type | File offset | Record size | Slots | Your records | DE box | DE record size |
|---|---|---|---|---|---|---|---|
| head / body / arm / legs / feet | 4–8 | 0x11F60 / 0x1407C / 0x16198 / 0x182B4 / 0x1A3D0 | 0x34 | 163 | 28 / 26 / 24 / 35 / 29 | 0x98D0 … 0x20FD0 | 0x30 |
| weapon | 2 | 0x1C4EC | 0x34 | 163 | 49 | 0x3B10 | 0x30 |
| crystal | 9 | 0x1E608 | 0x1C | 300 | 159 | 0x26D90 | 0x2C |
| gem | 3 | 0x206D8 | 0x10 | 300 | 68 | 0x2C380 | 0x2C |
| art manual | 13 | 0x21998 | 0x08 | 240 | 0 | 0x38EA0 | 0x14 |
| collectable | 10 | 0x22118 | 0x08 | 300 | 116 (538 items) | 0x31970 | 0x14 |
| material | 11 | 0x22A78 | 0x08 | 300 | 126 (499 items) | 0x34080 | 0x14 |
| key item | 12 | 0x233D8 | 0x08 | 200 | 13 | 0x36790 | 0x14 |
| tail | — | 0x23A18 | | | 88×16 per-character records (all 0), u16[88], **money `0x24048`** (375,150), capacity masks | money 0x151B40 | |

**Common 8-byte header** [C] (`0x80158BE4`):
- word0 = `gid<<20 | type<<16 | row<<5`
- `+4` u16 acquisition serial
- `+6` quantity (stacks are capped at 99, `0x801588D8`)
- `+7` flags

**Equipment record** (`+8`):
- 4 gem descriptors
- `+0x28` 4 × u16 gem-box index (0xFFFF means a built-in gem)
- `+0x30` socket count (`jwl_slot`)
- `+0x31` kind (1–5 armour part, 6 weapon)

**Equipment slots 0–149 are the inventory.** Slots 150 + character ID (151–161) are per-character staging records
(`0x80158308`). They hold default gear for characters who are not joined: Fiora's weapon and the guests' gear.
They are not inventory and are not converted.

**DE equivalence** [3P/D]:
- Stack record: index, type, item ID, type, quantity, `+0x0A`, serial, present, favourite.
- Equipment record: armour class `+0x14`, sockets `+0x15`, normal gem refs `+0x18/0x20/0x28`, fixed gems
  `+0x1C/0x24/0x2C`.
- Gem record: rank `+0x16`, attribute `+0x17`, effect `+0x1C`, strength and chance `+0x1E/0x1F`.
- **Inventory ordering:** DE slot = Wii slot, DE serial = Wii serial, DE per-type counter at `0x46900` =
  max(template, max serial + 1).

---

## 6. Item-ID compatibility results

From `tools/id_compare.py`; full tables are `tables/idmap_*.tsv`.

| Space | Wii IDs | Identical in DE | Text-only change | Balance change | DE-only additions |
|---|---|---|---|---|---|
| Global items (`ITM_itemlist`) | 3,765 | 3,739 | 26 (e.g. "First Attack Plus" → "First Atk Plus"; placeholder rows 3748–3765) | 0 | 892 |
| Weapons | 636 | 636 | 0 | 0 | 22 |
| Armour (`ITM_equiplist`) | 615 | 610 | 0 | 5 (Colony set gains a `pc10` model) | 369 |
| Gem effects | 97 | 96 | 1 | 0 | 0 |
| Crystals | 600 | 600 | 0 | 0 | 0 |
| Collectables | 318 | 300 | 18 (placeholders 301–318) | 0 | 28 |
| Materials | 512 | 511 | 1 | 0 | 0 |
| Key items | 200 | 200 | 0 | 0 | 40 |
| Art manuals | 240 | 240 | 0 | 0 | 136 |
| Arts | 152 | 151 | 0 | 1 (Summon Aqua `st_itv` 0 → 40) | 83 |
| Skills | 200 | 199 | 0 | 1 (Rapid Healing internal skill 93 → 157) | 0 |

`icon` changes are uniform menu-icon renumbering and are treated as cosmetic. **Every item record in your save (495 equipment, collectable, material and key-item records) has the same type
and row in DE** (test `test_item_ids_identical_in_de`). Gems are checked separately (§7).

---

## 7. Gems and equipment-reference validation

**Gem descriptor** [CD] (`0x80156380`):
- `[gid−2048:11][strength:11][rank:3, 1 = E … 6 = S][chance:7]`
- then `[effect:12][category:3][flag:1]` and u16 0

**Checks:**
- 68/68 loose gems: header row = effect; chance = `BTL_skilllist.percent_<rank>`; strength in range.
- 49 gems are crafted (Wii placeholder item 3747, which becomes DE item 0). 19 are named gem items.

**Sockets:**
- 37 built-in gems map to DE fixed sockets (item ID, presence).
- 16 socketed gems map to DE normal references (gem index, type 3). The descriptor copied on the equipment matches
  the gem-box record in every case.
- 19 equipped items carry gems.
- No item uses a fourth socket (DE has three).

**Equipment references:**
- 35/35 active references resolve. Reyn's head is empty.
- All 6 medium/heavy armour pieces are covered by a learned equipment skill. This matters because DE enforces the
  rule.
- Not converted: Mechon Fiora (record 8) and Fiora's staging weapon. Keep the DE template for them.

**Wii equipment with no DE equivalent:** none. All 191 inventory equipment records exist identically in DE.

---

## 8. Collectopaedia and miscellaneous state

| State | Status |
|---|---|
| Collectopaedia | **Not located on the Wii side.** DE storage is known (bit `0x19E9+id` from `0x148D6C`). Two candidates were tested and rejected: flag block `0x20C8`, and bit scans of GAME/FLAG constrained to the areas you have visited |
| Skill-tree unlock flags | Phase 2B flag rule (+500) |
| Equipment presets and cosmetics | Wii has none. DE cosmetics: keep template (0) |
| Affinity Coins | mapped (§4) |
| Character and region affinity, achievements, unique-monster counters, landmarks, Colony 6 | Phase 2B flag rules |
| Time played | Wii `0x11EB0` is packed `h<<12 \| m<<6 \| s` (THUM serialiser `0x8023E98C`) = 22:01:57, which becomes **79,317 s** at DE header `+0x04` [C] |
| Money | 375,150, both games cap at 999,999,999 [C] |
| HP and derived stats | rebuilt on load in both games; not written |
| Wii inventory capacity masks (`0x12108`, `0x12110`) | Wii only. DE boxes are a fixed 500 slots |

---

## 9. Remaining unknowns, by severity

| Severity | Item | Impact on your save | Next concrete step |
|---|---|---|---|
| **Medium** | **Crystals.** Header decoded, but its row field goes up to 790 against a 600-row table, so identity is unclear. The 20-byte payload and the DE 0x2C crystal record are not decoded | 159 crystals (crafting inputs only; no character capability) | Static: Wii crystal initialisers `0x80158DCC` and `0x80157400` (they read `ITM_crystallist` columns) against the DE gem/crystal packet builder `0xEBD60`. Differential alternative: pick up one crystal in an isolated Dolphin copy |
| **Medium** | **Collectopaedia location (Wii)** | Registration bits; rewards were already granted into inventory | Isolated Dolphin copy: register one collectable, save, diff GAME `0xB260–0xF450` |
| Low–medium | Wii `+0x2A0` EXP-earned counter against DE `+0xF0` (highest-level EXP) and `+0xF4` (reserve EXP) | Expert Mode reserve only; level and EXP are exact | DE `0xA6DD0` writer and `0xBA2A0` level routine: semantics of runtime `+0x1C/+0x20` |
| Low | Palette layout: Wii Monado palette slot 0 is empty; non-Shulk second palette uses template defaults | Cosmetic; can be reordered in the menu | In-game check after the first load |
| Low | DE stack-record `+0x0A` (0x0B70 / 0x3FFF in real saves) | Every new stack record | Copy the template slot's value; confirm at the DE allocator `0x9A480` |
| Low | Wii char `+0x118`, `+0x130–0x177`, `+0x2AC–0x2C0`, node state byte (0/1/2) | None known (UI or new-markers) | Leave unconverted |
| Low | Staging slots 151–161 and 88 per-character type-3 records (all zero) | None in this save | None |
| Low | One link-slot count (Shulk–Dunban) that does not follow the 1,000 rule | DE re-derives it from affinity | None |

---

## 10. Completion criteria and estimated fidelity

Counts are from `tables/phase2c_completion.tsv`. "Mapped" means a DE target value was computed and passed every
check.

| Category | In save | Decoded | Mapped to DE | Unresolved | Evidence | Fidelity |
|---|---|---|---|---|---|---|
| Character core (level, EXP, AP, coins), 7 characters | 28 fields | 28 | 28 | 0 | [CD] | **~100 %** |
| EXP-earned counter | 7 | 7 | 0 | 7 | [CD] | n/a (no DE target) |
| Equipment slots, characters 1–7 (35 equipped + 6 empty) | 41 | 41 | 41 | 0 | [CD] | **100 %** |
| Skill trees (7 × 5) | 35 | 35 | 35 | 0 | [CD] | **100 %** |
| Skill-link rows | 42 | 42 | 42 | 0 | [CD] | 100 % (none assigned) |
| Arts (level and manual flags) | 118 | 118 | 118 | 0 | [CD] | **100 %** |
| Palettes | 8 | 8 | 8 | 0 | [D] | ~90 % (layout to confirm) |
| Weapons and armour (inventory) | 191 | 191 | 191 | 0 | [CD] | **100 %** |
| Gems, loose and socketed | 68 + 53 sockets | all | all | 0 | [CD] | **100 %** |
| Collectables / materials / key items / art manuals | 116 / 126 / 13 / 0 | all | all | 0 | [CD] | **100 %** |
| Crystals | 159 | 159 (header) | 0 | 159 | [C] | **0 %** for now |
| Staging slots, guests, Mechon Fiora | 49 / 5 / 1 | all | template | — | [C] | n/a (keep template) |
| Money, play time, party | 3 | 3 | 3 | 0 | [C] | 100 % |
| Collectopaedia | 1 table | 0 | 0 | 1 | — | **0 %** |
| Story, quests, flags (Phase 2B) | — | — | rule complete | — | [CD] | ~96 % flags, 100 % quests |

**Overall gameplay-state fidelity, on current evidence, is about 97 %.**
- Excluding crystals and the Collectopaedia, every capability-affecting field is mapped.
- No differential save has been needed so far. In-game acceptance is still unverified.

---

## 11. Proposed Phase 2D: integrated conversion and validation (not started; needs your authorisation)

1. **Close the two medium gaps first**, or decide to accept them.
   - Crystals: run the static trace in §9. If unresolved, offer the option of leaving crystals out.
   - Collectopaedia: one isolated Dolphin differential save (needs authorisation). Fallback: keep the template's
     Collectopaedia, which loses the entries but not their rewards.
2. **Converter**, a single script in the research folder. It reads `monado01` and a *copy* of your v10 save, and
   writes `work/poc/save_0/bfsgame00.sav` only:
   - a. Phase 2B flag transplant (story, quests, affinity, landmarks, Colony 6, achievements), plus map and position.
   - b. Party [1,4,6,5,2,7].
   - c. Inventory boxes, written per §5 and `specs/wii_to_de_rules.json`:
     - Slot = Wii slot, serial = Wii serial; then advance the serial counters.
     - Unknown fields and empty-slot bytes come from the template.
   - d. Character records 1–7: level, EXP, AP, coins, equipment references, SP, learned counts, selected tree,
     links and unlock indices, palettes. Highest level = level. Everything else stays as the template.
   - e. The art table.
   - f. Money and play time.
3. **Self-checks before any game run:**
   - Re-decode the output with `de_save.py`.
   - Every planned value reads back.
   - Every equipment and gem reference resolves.
   - Bytes outside the written fields are identical to the template.
   - The IR→DE value tables equal `data/phase2c_ir.json`.
4. **Isolated Monado run**, as specified in Phase 2B §8. Check:
   - title slot, field load in Eryth Sea
   - status, arts, skills and link screens for all six characters
   - equipment and gems
   - inventory tabs and money
   - one battle
   - save and reload, then a byte diff
   - progression 150→160
5. **Stop rules:**
   - Stop on any crash.
   - Stop on a wrong level or EXP, or a missing art or skill.
   - Stop on an invalid equipment reference shown in the menu.
   - Stop if the menu rejects any item.

Estimated effort:

| Work | Hours |
|---|---|
| Gap closure | 6–15 |
| Converter and self-checks | 10–20 |
| Validation | 10–20 |
| **Total** | **26–55** |

---

## Files produced in this phase

| File | Purpose |
|---|---|
| `tools/bdat.py`, `tools/dump_bdat.py` | Legacy BDAT reader for Wii (big-endian, scrambled) and DE; dumps to `data/bdat_{wii,de}.json` |
| `tools/id_compare.py` | Wii/DE ID comparison; writes `tables/idmap_*.tsv` |
| `tools/ppc.py` | Robust PPC disassembly, cross-references, displacement and string-reference search |
| `tools/wii_save.py` | **Wii decoder** (container, character records, ITEM) to a lossless IR, plus re-encoders |
| `tools/de_save.py` | DE v7/v10 reader (characters, arts, boxes, serials) |
| `tools/phase2c.py` | IR → DE dry-run mapping; writes `data/phase2c_ir.json`, `tables/phase2c_completion.tsv`, `tables/phase2c_entries.tsv` (one row per entry, with the planned DE value) |
| `tools/write_specs.py` | Writes `specs/wii_layout.json`, `specs/de_v10_layout.json`, `specs/wii_to_de_rules.json` |
| `tests/test_phase2c.py` | 13 tests: CRCs, field-table coverage, byte-exact round trip, references, IDs, gems, arts, skills, DE v7/v10 |

`data/bdat_*.json` and `exe/` are derived from your own game files. Do not share them.

Rerun from the research folder:

```
python tools/dump_bdat.py <Wii DATA/files> <Monado targets/romfs>
python tools/phase2c.py work/originals/monado01 work/originals/user_v10_bfsgame00.sav
python -m unittest discover -s tests -v
```
