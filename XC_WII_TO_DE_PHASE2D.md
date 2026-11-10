# Xenoblade Chronicles Wii → Definitive Edition
## Phase 2D: Crystals, Collectopaedia, Integrated Converter and Isolated In-Game Validation

Date: 2026-11-06. Input: `monado01`, scenario 150, Eryth Sea, 22:01:57. Template: your DE v10 save, scenario 6.

**Safety record.**
- All game runs used the isolated folders `work/run1` to `work/run8`, with `LARECOMP_SAVE_DIR` set, the journal
  off and backups off.
- Runs 2–8 show `mounted host directory …\work\runN/save_0` in their own stderr logs. Run 1 is also confirmed
  isolated: its load list showed a single "Eryth Sea" slot, which only the converted save has.
- After every run:
  - your live `save_0` files still match their SHA-256 snapshots;
  - the live Wii `monado01` still matches its snapshot (`78f67f19…`);
  - no journal or backup folder was created.
- Nothing was deployed to your normal Monado profile.
- One false alarm during run 1: I first read the stale `build/last_game.log` (written at 22:06 on Nov 5, during
  your own earlier session) as "live folder mounted". That was wrong. From run 2 onward each run's log is
  captured separately.

Evidence labels: [C] code (address), [D] data (script against real saves and tables), [G] observed in the game
under Monado (isolated), [H] hypothesis.

---

## 1. Executive summary

1. **Crystals are solved** [CD]. All 159 records are decoded, checked against tables and mapped.
   - 42 crystal-list crystals.
   - 93 enemy-drop crystals. Each one's effects match `ITM_dropcrystallist` skill1/skill2, and its stored source
     enemy is known.
   - 24 crafting cylinders.
   - The DE crystal record is code-backed: generator `0xC19D0`, deposit-crystal writer `0xBF15C`, naming routine
     `0xC2DBC`.
2. **Collectopaedia is solved** [C].
   - Wii: a 320-bit array at game object `+0x3866` (file `0xEAC6`). Setter `0x8009F5F0` is called by the
     registration action at `0x802561CC`. The bit index is the `ITM_collectlist` row, which is the same ID DE uses
     at bit `0x19E9+id`.
   - **Your Wii save has 0 registrations**, consistent with carrying 116 collectable stacks, so nothing is lost.
3. **Smaller uncertainties are resolved:**
   - Expert-mode reserve and `+0xF0` [C].
   - Palette order (positional) [C].
   - DE stack field `+0x0A`: padding, never written by the allocator [C].
   - Achievement-counter grouping [D].
   - DE location word `0x149C04`: DE recomputes it [G].
4. **The integrated converter is built** (`tools/convert.py`). It is deterministic (two runs produce identical
   bytes), refuses any output outside `work/`, validates every mapping before writing, and then reads the output
   back with a separate decoder:
   - 26,479 bytes written in 1,907 logged ranges;
   - 0 read-back failures;
   - 0 bytes changed outside the logged ranges.
5. **In-game, isolated** [G]:
   - The converted save appears as "Eryth Sea" and loads into Eryth Sea field with Shulk, Dunban and Riki.
   - The main menu shows 375,150 G, 22:03 play time, and levels 52/51/51/52/52/51.
   - Shulk's and Riki's equipment screens show the exact Wii gear and gems (names, ranks and values).
   - The quest log matches Wii states (completed quests flagged; "Mementos of a Lost Son" active with Tatty Armour
     1/1).
   - An in-game save worked, and reloading that save worked.
6. **Save/reload normalization** [G].
   - DE's own re-save differs from the converter output in only 209 bytes:
     - the header: play time, timestamp, and u32 `0x4C` set to 1;
     - the derived location word;
     - 197 bytes of a newly revealed minimap patch.
   - **Flags, characters, arts, skills, links, equipment, gems, crystals, inventory, party and money came back
     byte-identical.**
   - This means more than "it loads". DE rebuilds the character records and inventory boxes from its runtime
     objects when saving (`0xA6DD0`), so these values passed through the game's own data structures unchanged.
7. **Not 100 %.** Gameplay-critical dependencies are still unverified (§7): story progression 150→160, combat,
   and fast travel were not exercised. There are also two known content losses:
   - minimap exploration, a player-visible unmapped category;
   - the in-progress kill counter of one accepted quest.

---

## 2. Crystals (Priority 1)

### 2.1 Wii crystal record (0x1C bytes)

Field accessors are in type-9 handler vtables `0x8052FA48` (normal) and `0x8052F8D8` (`flags&3 == 3`) [C].

| Field | Location | Evidence |
|---|---|---|
| kind | header flags `& 3`: 1 crystal-list crystal, 2 enemy drop, 3 crafting cylinder | [CD] all 159 consistent with their tables |
| attribute | header flags `>> 2` = `atr_type` | [D] 159/159 |
| rank | word0 `(w0 >> 2) & 7` | setter `0x8015678C` [C] |
| identity | header gid: list = global crystal item (1252–1851); drop = `ITM_dropcrystallist` row (≤ 820; this table was found by the init `0x80157400` reading `r13-0x5780`); cylinder = effect ID | [CD] |
| effects | u16[4] at `+8`, effect = `>> 4` | `0x8015C6A0` [C] |
| values | u8[4] at `+0x12` | `0x8015C610` [C] |
| source | u16 `+0x18`: low 15 bits = global enemy ID; bit 15 = cylinder | `0x8015C5DC`/`0x8015C5B0` [C]; the IDs name the right enemies |
| `+0x10` | u16 = source mod 100 (redundant) | `0x8015C5A8` [C] |

Checks against the tables, 159/159 [D]:
- **Drop crystals:** rank, attribute, cylinder flag and the effect list all equal the `ITM_dropcrystallist` row.
- **List crystals:** attribute and rank fall within `ITM_crystallist`'s ranges, and effect count ≤ `skill_max`.
- **Cylinders:** each has exactly one effect, and `BTL_skilllist.atr_type` matches.

### 2.2 DE crystal record (0x2C bytes) and mapping

| DE | From Wii | Evidence |
|---|---|---|
| `+0x04` gid | list: Wii gid; drop and cylinder: 0 | `0xC1C74` writes `0x90000` (gid 0, type 9) for drops; deposit writer `0xBF164` writes the item [C] |
| `+0x14` source | Wii `+0x18 & 0x7FFF` | `0xC1C80` [C] |
| `+0x16` rank, `+0x17` attribute | Wii rank, `flags >> 2` | `0xC1CC0` / `0xC1CF8` [C] |
| `+0x18` named | drop: 2 if DE `BTL_enelist*.named` is non-zero, else 1; list and cylinder: 1 | `0xC1AB0` [C]. **93/93 drop crystals: named ⇔ value ≥ 80**, which is DE's own 80–100 band [D] |
| `+0x19` cylinder, `+0x1A` count | Wii bit 15, number of effects | `0xC1D04`, `0xC1B64`/`0xC1BC0` [C] |
| `+0x1C + 4i` | (u16 effect, u8 value, u8 0) | `0xC1BA8`, `0xC1C54`, `0xBF13C` [C] |

- **How DE names a crystal** (`0xC2DBC`):
  - `source == 0` gives an attribute name (for example "Fire Crystal");
  - `source != 0` with the cylinder flag gives `BTL_skilllist.cylinder_name`;
  - otherwise the name comes from the enemy.
- **How the Wii stores crafted cylinders:** source `0x8001`, i.e. cylinder bit plus source 1. The mapping therefore
  makes them display as cylinders [C].
- **In game:** crystals were not opened in the menu. All 159 crystal records survived DE's re-save byte-identical
  [G].

---

## 3. Collectopaedia (Priority 2)

- **Wii storage:** game object (`r13-0x59F8`) `+0x3866`, 40 bytes, bit `id & 7` of byte `id >> 3`.
  - Bounds check: `id < 0x140` (`0x8009F5F0` sets, `0x8009F644` gets).
  - The menu (`0x802566D8`) shows state 3 = registered and state 2 = owned.
  - The ID comes from `ITM_itemlist.itemID` (`0x80139D1C`), i.e. the `ITM_collectlist` row [C].
- **DE storage:** bit `0x19E9 + id` from `0x148D6C` (setter `0x81310`), the same IDs [3P/C].
- **Your saves:** Wii 0 registered, DE template 0 registered. The converter copies all 300 bits, so for your save
  this means 0 → 0.
- **Completed collection rows and rewards:** none exist, so none are lost.
- **Not opened in-game:** the Collectopaedia screen was not captured (§6).

---

## 4. Smaller fields (Priority 3)

| Field | Finding | Rule |
|---|---|---|
| DE `+0xF0` | `0xBA9CC`: every non-Expert battle EXP gain is added to current EXP (`+0x18`, save `+0x04`) and to `+0x1C` (save `+0xF0`). The level routine `0xBA2A0` consumes only `+0x18`; `+0x1C` is the EXP since the current highest level | `= current EXP` [C]. Survived the re-save [G] |
| DE `+0xF4` reserve | Filled only with Expert Mode on (`0xBA9D0`, cap 199,999,998). The Wii has no Expert Mode | template [C] |
| Affinity Coins | DE adds one per new highest level (`0xBAAC0`); the Wii value is copied, capped at 999 | copy [C] |
| Palette order | Wii `palette[8·p + slot]` with a fixed default slot per art (`0x800A219C`), i.e. positional | slot-for-slot copy. Re-save byte-identical [G]. Arts screen not captured |
| DE stack `+0x0A` | No writer in the allocator (`0x9AB60`) or item-add (`0xBF350`); values vary across real saves (0, 0x093A, 0x0B70, 0x3FFF, 0x813A) | template empty-slot bytes [C/D] |
| Crystal `+0x24..+0x2B` | Effect slots 3–4; cleared by the initialisers `0x99FC8`/`0xBDC68` | template (0) [C] |
| Achievement counters | DE keeps `min(total, comp_value)` per tier. The Wii keeps the total at the lead tier or copies it across tiers | Per tier: `comp_value` if the Wii completion bit is set, else `min(group max, comp_value)`. 6 exceptions logged (unique-monster tiers whose Wii counter lives elsewhere) [D] |
| DE `0x149C04` | Re-save changed (9, 49) to (11, 11): a location ID derived from position | template; DE recomputes [G] |
| Facing angle | Wii degrees; DE radians | `radians()` [D/H]; the re-save kept it unchanged [G] |

---

## 5. Integrated converter (Priority 4)

Command:

```
python tools/convert.py work/originals/monado01 work/template/bfsgame00.sav work/phase2d
```

**Order of operations:**
1. Phase 2B flag transplant (`flag_transplant_eval.build`), plus the achievement-counter rule.
2. Inventory. Each template box is cleared to its own empty-slot pattern, then the Wii records are written: slot =
   Wii slot, serial = Wii serial, and per-type serial counters are advanced.
3. Character records 1–7: level, EXP, AP, coins, equipment references, palettes, tree, SP, learned counts, links,
   unlock indices (raised only), highest level and its EXP.
4. The art table.
5. Party, money, play time, map, position, angle, Collectopaedia.

**Guards:**
- Wii CRCs must pass.
- The template must be v10.
- Any unresolved inventory or character category aborts the run.
- Flag overflow or a write into a DE-only range aborts the run.
- A fourth socket in use aborts the run.
- A box index ≥ 500 aborts the run.
- The output path must be inside `work/`.

**Read-back:** `de_save` and `flagmap` re-decode the output. Checked:
- every flag;
- story, party and money;
- per-character fields;
- every equipment reference;
- every art;
- box slot sets;
- every gem;
- 0 stray bytes.

`manifest.json` records input hashes, counts and failures.

**Output:** `work/phase2d/save_0/bfsgame00.sav`, SHA-256 `62c92c20…7e5143`, with `.tmb` and `bfssystem.sav` copied
from the template.

**Tests:** `python -m unittest discover -s tests`, **23/23 pass**:
- the 13 Phase 2C tests;
- 10 Phase 2D tests: refusal outside `work/`, read-back, story/party/money/location, characters,
  equipment and gem references, inventory IDs and serials, crystals including the named rule, padding kept, the
  stray-byte check, and the in-game re-save normalization.

---

## 6. In-game validation in isolated Monado (Priority 5)

Monado was launched as `build\xcde.exe targets` with `LARECOMP_SAVE_DIR=work\runN`, `XCDE_SAVE_JOURNAL_OFF=1` and
`XCDE_SAVE_BACKUPS=0`. Input came from replayed routes (`work/routes/`), and evidence from frame captures
(`work/runN/shots/`).

| Check | Result | Run |
|---|---|---|
| Title / load list | Slot shows "Eryth Sea"; only the converted slot is present (isolation) | 1, 2 [G] |
| Load and placement | Field loads in Eryth Sea; Shulk, Dunban and Riki on screen; clock and minimap active; no crash | 2 [G] |
| Main menu | 375,150 G; 22:03; Shulk 52, Dunban 51, Riki 51, Sharla 52, Reyn 52, Melia 51 (HP shown) | 7 [G] |
| Equipment, gems (Shulk) | Monado, Sky Cap, Cool Oil, Sky Gloves, Makna Bottoms, Iron Boots. Gems: Blaze Plus V 47 %, Double Attack IV 20 %, Recovery Up IV 20 %, Blaze Defence III 10 % (built-in), Aquatic Cloak II 20 %, HP Up III 14 %, Strength Up III 25. **All 13 items equal the Wii save** | 7 [G] |
| Equipment (Riki) | Warrior Gnasher, Jungle Cap, Nopon Top, Sabre Gloves, Cool Trunks, Cool Sandals, gems shown; **equal to the Wii save** | 7 [G] |
| Quest log | "Mementos of a Lost Son" active with Tatty Armour 1/1 and gun/knife 0/1 (Wii: state 1, Tatty Armour held). "The Key to a Long Life" completed, and the game itself refused to reopen it ("already completed") | 3 [G] |
| In-memory image | Two load buffers dumped at frame 4200 are byte-identical to the converter output | 5 [G] |
| In-game save | Written to `work/run6/save_0` | 6 [G] |
| Normalization | 209 differing bytes, all accounted for (§1.6); **0 flag, character, art or inventory differences** | 6 [G] |
| Reload of DE's re-save | Loads; main menu identical; play time 22:05 | 8 [G] |
| Arts, Skill Trees, Affinity Chart, Collectopaedia, Items/crystals screens | **Not captured**: the generic route stayed in the Quest Log. These are covered only by the byte-identical re-save | — |
| Fast travel, combat, story 150→160 | **Not exercised** | — |

---

## 7. Completeness audit: every remaining persistent field

Classes: **GC** gameplay-critical · **PA** progression-affecting · **PV** noncritical but player-visible ·
**T** transient/derived/unused/safe default · **U** unknown, needs investigation.

| Wii data | Size / content in your save | Converted? | Class | Notes and next step |
|---|---|---|---|---|
| FLAG (story, quests, events, landmarks, affinity, Colony 6, achievement bits) | 0x1214 B | yes (Phase 2B rules) | GC | 0 differences after DE re-save. Story progression **untested in game** → **unverified GC dependency** |
| GAME party list, map, characters 1–7, ITEM | — | yes | GC | Verified [CDG] |
| Characters 3 (Fiora) / 8 / guests 9–13 | not joined at scenario 150 | 3: progression only; 8–13: template | PA (low) | Fiora's later rejoin is handled by DE's own join script, untested |
| Active-quest kill progress (quest 90 "Clearing Obstructions": 2+4+3 kills) | location not found | no | PA | The objective is replayable (re-kill up to 9 enemies). Next: diff two Dolphin saves before and after one kill, or trace the quest manager's kill handler |
| Quest objectives of types 2/4 (items / sub-quests) | 14 quests | yes (via inventory and quest flags) | PA | Quest log shows the item counts correctly [G] |
| Minimap exploration (Wii GAME `+0x200E–0x27F2` bitfields; DE bitmaps `0x3B5B0–0x148D6C`) | ~2.6 KB Wii | no | PV | DE re-reveals as you walk. Next: decode the Wii bitmap geometry against the DE 200-byte-row bitmaps |
| In-game time of day and day count (TIME `0x11EB4` float, `0x11EB8` day) | 6:36, day 30 | no (template time 10:02) | PV | Can be reset from the Change Time menu. Next: find the DE time field (the time-of-day setter) |
| GAME `+0x200–0xF00`, 8-byte entries (101 non-zero) | small values 1–5 | no | U | Not referenced by the direct getters. Candidates: per-map NPC or event state. Next: trace members of the game object |
| GAME `+0x3890–0x4000` (1,595 B, values 1–3, also present early) | — | no | U | Same next step |
| GAME `+0x3FB0`, `+0x4190`, `+0x1690`, `+0x0055` lists | < 200 B | no | U | Same next step |
| TBOX (21 field chest slots with position, rank, drop) | 226 B non-zero | no | T/PV | Unopened enemy-drop chests disappear; loot not yet obtained |
| MINE (150 collection-point cooldowns) | 416 B | no | T | Respawn timers |
| WTHR (weather), SNDS, CAMD | — | no | T | Re-rolled or defaults |
| PCPM members 2–3 | positions | no | T | Followers snap to the leader |
| OPTD (options) | 19 B | no | T | DE options are in `bfssystem.sav` (template kept) |
| THUM / `.tmb` | thumbnail | template `.tmb` | T | DE writes a new thumbnail on save [G] |
| Wii-only: equipment staging slots 151–161, inventory capacity masks, char `+0x2A0` EXP-earned counter, `+0x118`/`+0x130` UI bytes | — | no | T | No DE counterpart |
| DE-only: Expert Mode, cosmetics, Future Connected, header `0x4C`, char `+0x10/+0x2C/+0x6C/+0xF8`, `0x149C04/24` | — | template | T | `0x4C` and `0x149C04` are rewritten by DE itself [G] |
| Collectopaedia | 0 entries | yes | PV | Verified [C] |

**Unverified gameplay-critical dependencies (explicit):**
1. Story progression from scenario 150 (Alcamoth audience, Imperial Guards) under the transplanted flags.
2. Combat with the converted characters (arts, skills, gems in effect).
3. Fast travel to discovered landmarks.
4. Fiora's rejoin later in the story (character 3/8 template state).
5. Possible state inside the unknown GAME regions (U rows).

Flags and story state survived DE's own re-save unchanged, but behaviour can only be confirmed by playing.

---

## 8. Field-by-field fidelity

| Category | In save | Converted | In-game evidence | Fidelity |
|---|---|---|---|---|
| Story, quest states, event and landmark flags | Phase 2B | yes | quest log matches; flags 0 differences after re-save | high; progression **unverified** |
| Character core (7 × level, EXP, AP, coins) | 28 | 28 | menu levels; re-save identical | 100 % |
| Equipment references | 35 | 35 | Shulk and Riki screens exact | 100 % |
| Gems: 68 loose + 53 socketed | 121 | 121 | 7/7 on Shulk exact | 100 % |
| Weapons and armour (inventory) | 191 | 191 | re-save identical | 100 % |
| Crystals | 159 | 159 | re-save identical | 100 % (screen not captured) |
| Collectables / materials / key items | 255 stacks | 255 | quest item count shown; re-save identical | 100 % |
| Arts (level and manual flags) | 118 | 118 | re-save identical | 100 % (screen not captured) |
| Skill trees, SP, links | 35 trees, 42 link rows | all | re-save identical | 100 % (screen not captured) |
| Palettes | 8 | 8 | re-save identical | layout not seen in game |
| Money, play time, party, location | 4 | 4 | menu, field | 100 % |
| Collectopaedia | 0 entries | 0 | — | 100 % |
| Achievement counters | 199 tiers | rule | re-save identical | 6 tiers approximated |
| Minimap exploration | ~2.6 KB | no | DE starts unexplored | 0 % |
| Time of day | 1 | no | 10:02 instead of 6:36 | 0 % (one menu action) |
| Quest-90 kill progress | ≤ 9 kills | no | — | 0 % |
| Unknown GAME regions | ~2 KB | no | — | unknown |

---

## 9. Unresolved discrepancies

1. Minimap exploration not converted (PV).
2. Time of day not converted (PV).
3. Kill progress of quest 90 not converted (PA, small).
4. Unknown GAME regions `+0x200–0xF00`, `+0x3890–0x4000` and small lists (U).
5. Six achievement tiers approximated.
6. Arts, Skill Trees, Affinity Chart, Collectopaedia and Items screens not visually checked; fast travel, combat and
   story progression not exercised.

---

## 10. Recommended next step (not started)

A short **guided play session in the isolated folder** would close the gameplay-critical items, since scripted
routes cannot do it efficiently:
- load `work/phase2d/save_0`;
- open Arts, Skill Trees, Items (crystals) and the Affinity Chart;
- fight once;
- fast-travel twice;
- advance to the Alcamoth audience (scenario 154+).

Either you play it while I compare captures and saves, or I extend the routes screen by screen.

In parallel, the static work in §7 (time-of-day field, minimap bitmap geometry, quest kill counter, unknown GAME
regions) would raise fidelity further.

**Deployment** to your normal Monado profile still requires your explicit approval.

## Files

| File | Purpose |
|---|---|
| `tools/convert.py` | Integrated converter (writes only under `work/`) and read-back |
| `tools/a64.py` | ARM64 helpers: disassembly, address and call references |
| `tools/wii_save.py` (crystal fields), `tools/phase2c.py` (crystal and Collectopaedia mapping) | Updated decoders and mapper |
| `specs/wii_to_de_rules.json` | Rules, including the new `phase2d` block |
| `tests/test_phase2d.py` | Phase 2D tests |
| `work/template/` | Read-only copies of your DE template save, `.tmb` and `bfssystem.sav` |
| `work/phase2d/` | Converter output and `manifest.json` |
| `work/run1`–`run8`, `work/routes/` | Isolated game runs: captures, stderr logs, re-save, memory dumps, routes |
