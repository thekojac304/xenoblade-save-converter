# Stored equipment mapping (Phase 3E)

How the three games keep the equipment of party members who are away during a story event, and how the converter
translates it. Code: `tools/stored_gear.py` (readers, writers, policy), used by `tools/de_to_wii.py` (DE → Wii/3DS),
`tools/convert.py` (Wii/3DS → DE) and `tools/canon.py` (canonical `stored_gear`). Evidence tags: **[code]** read from
the Wii executable, **[game]** written or replayed by a real game in an isolated emulator, **[data]** genuine saves.

## 1. When it applies

A character's gear is stored when the story removes him/her from the party and given back when the story returns
him/her. The converter treats as "stored characters": main characters of the current era (Fiora = 3 before scenario 275,
8 from 275) who are **absent from the party**, **have joined already** (first scenario in the party journal
`JNL_PCrelatelist`: Shulk/Reyn 1, Sharla 70, Dunban 100, Melia 128, Riki 137, Fiora-8 275), other than Fiora's retired
record 3. Before a character's first join the slot holds scripted prologue gear (e.g. Dunban's prologue Monado at
stories 6–23 on the Wii and the DE); that case keeps the 3D rule (the Wii base provides it).

Genuine windows seen [data]: Alcamoth 154–158 (Melia alone → Shulk alone; 2E/3C Monado saves), 158 → 160 (four
friends return), Fallen Arm 269–288 and the reunion at 291 (public DE playthrough). Departures may also happen with
default gear (Melia leaves at 158 wearing her table defaults; still stored) [data].

## 2. Definitive Edition

| Item | Layout |
|---|---|
| Table | `0x3BB50` (v7 and v10), 7 entries × `0xB4` per character `k` (`k` = 1…35), entry `j` = slot head, body, arm, legs, feet, weapon, 7th unused |
| Entry `+0x00..0x2F` | the equipment record exactly as it was in its box: `+0` old box slot, `+2` type, `+4` gear id, `+6` type, `+8` qty, `+0xC` serial, `+0x10` present, `+0x14` armour class, `+0x15` socket count, sockets `+0x18 + 8s`: normal = `3<<16 | gem slot`, fixed = `1<<16 | gem id` |
| Entry `+0x30 + 0x2C·g` (g = 0…2) | verbatim copies of the gem records the sockets referenced; matched by their own `+0` slot field; `+0x10` present (a record with present = 0 may keep stale bytes - ignored) |
| Character record | equipment references `(0, 0)` while away |
| Return [game: 156→158, 158→160, 288→291] | each item and gem re-added in free slots with new serials, socket references rewritten, entry cleared to zeros |
| Present characters | entries all zero (or prologue defaults never cleared) |

## 3. Wii and New 3DS (same layout; the 3DS file is the Wii layout re-encoded)

Routine `0x8007F368(character, join)` [code]:

| Leave (join = 0), per slot head…weapon | Join (join = 1), per slot |
|---|---|
| copy the equipped 0x34-byte inventory record to the staging record of that box at slot `150 + k` (`k` = 1…11; getter `0x80158308`) | create a NEW item from the character reference's gear id (empty weapon → default weapon, `0x8003B148`) and equip it |
| for every socketed gem: copy the 16-byte gem record to the character's staged-gem table entry `i` (item `+0x11AB8 + 16·(8(k-1)+i)`, getter `0x80158308` type 3), write the link `(slot+1, socket)` as two bytes at item `+0x12038 + 2·(8(k-1)+i)` (getter `0x80158414`), delete the gem | socket count = the staging record's (max 4) |
| delete the inventory item; the reference keeps the gear id, row 0, box index `0xFFFF` | for each link of this slot: re-add the staged gem to the gem box, socket it, clear the link and the staged gem |
| after the loop: clear unused staged-gem entries | staging records are NOT cleared (stale ones remain in every save) |

Script command `0x8004A24C` writes scripted gear the same way (prologue Dunban) [code]. Limits: 8 staged gems per
character, 4 sockets.

**3DS byte order (defect D3, fixed):** the link table is two bytes per entry (`lbz +0`, `lbz +1`). The 3A transcoder
treated it as u16 words and swapped the bytes; the 3DS game then found no gem for Shulk's sockets [game: run
x1c_s156_audience - gear back, 6 gems missing]. `xc3d` now copies it as bytes; with the fix the 3DS game returned all
6 gems [game: x2_s156_audience]. No earlier save had a non-zero table, so no earlier output changes.

## 4. Canonical form and translation

`shared["stored_gear"] = {k: {"slots": {slot: record | None}, "gems": [gem, …]}}`, present only when the save has a
stored character (every other save's canonical state is unchanged). Records are the inventory's canonical equipment
records; a socketed gem is `["gem", i]` into `gems` (slot order, then socket - the Wii's link order).

| | DE → Wii/3DS (`write_wii`) | Wii/3DS → DE (`write_de`) |
|---|---|---|
| references | gear id, row 0, index `0xFFFF` | `(0, 0)` |
| item | staging record = the encoder's inventory record (header, fixed and socketed gem descriptors, socket count, kind); gem-box references `0xFFFF` | DE record built like an inventory item: old-slot = a free slot of that box, serial from the DE counter, armour class from the table |
| gems | staged-gem record + link `(slot+1, socket)`, in slot/socket order; > 8 → refused | DE gem record copy (old-slot = a free gem slot, new serial) after the item |
| identical destination | its bytes are kept (unchanged returns stay byte-identical) | same |
| return with sidecar/record | — | per character: if every byte that defines the stored gear (references, six staging records, staged gems and links) is unchanged since the export, the DE's own entries are kept - also for files made before 3E that carried no stored gear, or whose references name base/template gear no staging record holds; a character who rejoined during the session gets his DE entries cleared, as the DE does |
| refused (nothing written) | DE entry inconsistent (socket naming a gem that is not stored, two stored gems with one slot, a stored gem no socket uses); > 8 socketed gems | reference id ≠ staging record id (except on an unchanged return, above); away character still equipped from the inventory; socketed gem without staged copy; 4th socket; two links for one socket; orphan staged gem |

Wii-only bytes not represented on the DE: the item's age (+5) and low header bits (+3) of a staging record (game
copies them; the converter writes 0 - the game rebuilds the item at the join and does not use them), stale staging
records of present characters (left as in the base).

## 5. Validation (details: `REUNION_VALIDATION.md`)

| Check | Result |
|---|---|
| Encoder vs game-written staging records (Dunban prologue, user's Wii 18/6; Reyn/Sharla stale, Wii 150) | identical except the age byte and low header bits (above) |
| Reader on game-written leaves (Melia stored by the Wii game at 156→158; by the 3DS game) | equal to the DE game's own stored gear for the same event |
| Static: 9 genuine DE saves with stored characters → Wii and → 3DS, back | Wii/3DS reading = DE; unchanged returns byte-identical; first-time Wii → DE = DE |
| Reunions played by the target game | Wii 156→158 (Shulk) and 158→160 (Reyn, Dunban, Sharla, Riki); 3DS 156→158; DE 158→160 from a Wii-converted stash: every returning character got exactly his own gear and gems, identical to the DE game's native result; inventory changes identical; no duplication |

## 6. Phase 3F additions

**Fiora's later form (character 8).** Same table and routine: DE entries of character 8, Wii/3DS staging slot 158 and
staged gems 56-63 (8·(8-1) + i). The join routine has no character-specific path [code]; her return was played on the
DE (native) and on the 3DS from a converted save: gear and both gems identical [game]. `VALIDATED` now includes 8.
Guard: the party update's one-time character-8 initialisation (level, seed from record 3) runs only when bit 8 of the
join mask (Wii flag 0x108 / DE 32-bit flag 0 / canonical `flag_bitmask_0`) is clear - a stored Fiora-8 with the bit
clear is refused (`first_join_problems`); no genuine save has that state.

**Reunion room (defect F1, all stored characters).** The join creates each returning item through 0x80158EEC; when a
box is full the add fails and 0x8007F368 returns at once, skipping the rest of that character's return [code; game:
Azahar x2]. Wii/3DS capacity of the equipment boxes = 60 + 10 × bits of item +0x12108 + min(item +0x12110, 30); the
bits are set only when characters 3, 5, 6, 7, 8 or 11 join (0x80157CD8, table 0x8052F6B8). Rule:

| | |
|---|---|
| DE → Wii/3DS with stored characters | keep `reunion_room()` free per box: one slot per stored item (an empty weapon slot counts: the game creates the default weapon) and one gem slot per staged gem; extra unequipped items go to the sidecar/record (`--overflow sidecar`) or the conversion is refused with the reason |
| Wii/3DS → DE | a main character in the party whose references still name staged gear (gear id, box index 0xFFFF) = a skipped return → refused with the names (`unfinished_returns`), never converted (the gear would be lost) |
| Saves without stored characters | unaffected (byte-identical to 3E) |
