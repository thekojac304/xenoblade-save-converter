# Bidirectional conversion design (Phase 2E, updated in Phase 2F)

Xenoblade Chronicles Wii (SX4E01 `monadoNN`, played in Dolphin) ⇄ Xenoblade Chronicles: Definitive Edition
(save format v10, played in the Monado recompilation).

This document describes how the converter is built, what the sidecar holds, and the rules both directions follow.
Evidence for the individual field mappings is in `XC_WII_TO_DE_PHASE2B.md` … `XC_WII_TO_DE_PHASE2F.md`.

## 0. Phase 2F changes (2F-rc1, canonical schema `xc1-canon/2`)

| Area | 2F rule | Why |
|---|---|---|
| Item acquisition order | Canonical `order` (rank in the box, oldest = 1) replaces the raw `serial`. Wii → DE writes the DE serial as that rank; DE → Wii writes Wii ages `N + 1 − order` (a box keeps its base ages only if its order is unchanged); re-import keeps the DE serial of every item that existed at export (paired by identity in acquisition order) and gives Wii pickups serials above the DE counter. | Wii header +4 is an **age** (code `0x80159080` ages all items on pickup, `0x80159488` renumbers 1..N); DE stores an acquisition number. 2E copied the values. |
| Descent check | Items are matched as a multiset of (box, id[, gem/crystal values]). | Serials change on every Wii pickup. |
| Link slots | `link_unlock` per source character is shared state. Wii: number of node state bytes set − 1; DE: `link_unlock_index`. | 2E treated it as DE-only. |
| Fiora | DE → Wii writes Fiora's record-3 skill object (`+0x1F4..+0x29F`) into its record-8 copy too. | The Wii game restores record 3 from the copy on load (Dolphin run d1). |
| Crafted cylinders | DE `source 0` ⇔ Wii kind-3 `source 1` (canonical 1). | DE-made cylinders had no Wii encoding. |
| Unsupported party | Ids 8–13 are refused in both directions. | No validated mapping for Fiora's second form or guests. |
| First export | The template's reserve EXP, fashion slots, Noponstones and link unlocks are reset. | They belong to the template's playthrough. |
| Re-import | Current save of the other game required (or explicit "none newer"). Stale-sidecar evidence refuses even with `--branch`. A current DE save that differs only in DE-exclusive fields becomes the template. | 2E could resurrect sold DE-only items or drop newer DE-only state. |
| Validation | Inputs: container headers, CRCs, versions; DE values must be valid game values. Outputs: the Wii file must pass the same mapping checks a later Wii → DE run applies (closure). | No guessing, no one-way exports. |
| CLI output | New folder only; staged, verified and renamed in one step; realpath/junction/marker-file guards. | Partial outputs and guard bypasses were possible in 2E. |

---

## 1. Architecture

```
            Wii save ──convert.build()──────────────▶ DE save       (Phase 2D converter + Phase 2E steps)
                │  ▲                                    │  ▲
   canon.from_wii  │                        canon.from_de  │
                ▼  │                                    ▼  │
           canonical state ("xc1-canon/1") ◀── compare() ──▶ canonical state
                   │                                       │
            de_to_wii.build() ◀───────────────────────────┘           (patches a base Wii image)
                   │
            sidecar.make() / reimport.wii_to_de_reimport()           (lineage, DE-only data, 3-way merge)
                   │
            xcconv.py  (CLI: inspect, validate, wii-to-de, de-to-wii, roundtrip-check, compatibility-check, sidecar-info)
```

Design choice: the Wii → DE converter that passed Phase 2D in-game validation was **not** rewritten around the
canonical model. It keeps writing a DE template field by field and is wrapped by a pure `build()` function
(`--baseline-2d` reproduces the Phase 2D bytes exactly, checked by a test). The canonical model is used:

- as an **independent read-back** of every conversion (both directions): canonical(input) must equal
  canonical(output) over the shared fields;
- as the **reverse converter's input** (`de_to_wii` reads `canon.from_de`);
- for **sidecar fingerprints**, descent and divergence checks.

| Module | Role |
|---|---|
| `tools/wii_save.py` | Wii container, character records, ITEM boxes (read, lossless IR) |
| `tools/de_save.py` | DE v7 / v10 reader |
| `tools/flagmap.py`, `flag_transplant_eval.py` | exact flag accessors, Phase 2B flag map |
| `tools/convert.py` | Wii → DE (Phase 2D rules + Phase 2E steps: quest counters, minimap, clock, exact awards, all characters) |
| `tools/quest_counters.py`, `achievements.py`, `minimap.py` | Phase 2E rules, both directions |
| `tools/canon.py` | canonical state, compare, fingerprint |
| `tools/de_to_wii.py` | DE → Wii (base image patching, capacity, compaction, compatibility) |
| `tools/sidecar.py`, `tools/reimport.py` | sidecar format, descent / divergence, 3-way re-import |
| `tools/xcconv.py` | command-line interface, output safety |

---

## 2. Canonical state (`xc1-canon/1`)

Versioned JSON-compatible structure produced by `canon.from_wii` / `canon.from_de`:

| Part | Content | Representation |
|---|---|---|
| `shared.story`, `flags` | story counter (16-bit flag 0x20) and every flag both games hold | DE flag ids (Phase 2B map), non-zero only |
| `shared.flag_bitmask_0` | Wii 16-bit 0x108 ⇔ DE 32-bit 0 | integer |
| `shared.achievements` | award counters per DE slot (`0x40 + id % 200`) | exact DE value (`achievements.wii_to_de`) |
| `shared.characters[1..7]` | level, EXP, AP, Affinity Coins, SP ×5, selected tree, learned count ×5, skill links by source, arts by art id, palette (talent + 8), Shulk's Monado palette (8), equipment box indices (party members only) | integers |
| `shared.inventory[box][slot]` | id, quantity, serial; equipment sockets (`fixed gid` / `gem slot`) and socket count; gems (effect, rank, strength, chance); crystals (list id, source, rank, attribute, cylinder flag, effects) | DE conventions: crafted gem id 0, drop/cylinder crystal id 0 |
| `shared.quest_counters[q]` | objective counters of quests that are not closed (state ≠ 254/255) | DE byte encoding (0xFF = done) |
| `shared.clock` | hour, minute, day | integers |
| `shared.money`, `play_time_s`, `party`, `map`, `position`, `angle_rad`, `collectopaedia` | | seconds, radians, ids |
| `wii_only` | EXP-earned counters, Wii-only 16-bit flags (HOLD16), Wii 1-bit flags 0x352C–0x36CF (block 0x3440+i above the DE flag range; set by normal Wii play), Wii TIME float/day/year | raw |
| `de_only` | Expert Mode fields per character (highest level, its EXP, reserve EXP), cosmetics, Shulk's second talent byte, link unlock indices, raw char fields, favourites / padding, DE-only flags, Future Connected quest counters, header, location words, serial counters | raw |

Exactness: integers and floats are kept bit-exact (positions rounded to 1/1000 only for comparison).
Nothing is forced into a lossy generic form; raw source data for fields not understood is kept in the save image
(the conversions patch templates instead of rebuilding files).

---

## 3. Wii → DE

`convert.build(wii, template, T, features, minimap_base)`:

1. Phase 2B flag transplant onto the template (DE-only flag ranges keep the template), story, landmarks, Colony 6.
2. Inventory boxes: template boxes cleared, Wii records written at the same slot with the same serial.
3. Characters 1–7 (Phase 2E: all seven, not only party members; equipment only for party members — DE keeps no
   equipment for absent characters).
4. Arts, palettes, party, money, play time, map, position, angle, Collectopaedia.
5. Phase 2E steps: quest objective counters (q < 1000), minimap exploration (display mode; template bitmaps
   of shared maps cleared on a first export, OR-merged on a re-import), clock (hour/minute/day/last sunrise day),
   exact award counters.
6. Independent read-back (`verify_bytes`): every flag, story/party/money, characters, equipment and gem
   references, arts, box slot sets, gem values, Phase 2E bytes, and **0 bytes changed outside logged ranges**.

---

## 4. DE → Wii

`de_to_wii.build(de, base, T, lineage, overflow)` patches a **base Wii image**:

- **Lineage base** (the Wii save this playthrough came from, taken from the sidecar): every shared field is
  written from the DE state, but where the DE value equals what the base converts to, the base's exact bytes are
  kept. Unchanged data therefore round-trips byte for byte, including Wii-only details: item header bits, crystal
  byte +0x16, EXP-earned counters, award lead slots, quest counter bytes of closed quests, and node state bytes.
- **Foreign base** (DE-native playthrough; any valid Wii save used as a structural template): all shared fields
  are re-encoded; per-playthrough Wii-only regions are reset (minimap bits, field chests TBOX, collection
  cooldowns MINE). A warning is given if the base is at a later story point than the DE save, because Wii
  "staging" gear of not-yet-joined characters comes from the base.

Reverse rules (inverse of Wii → DE):

| Category | Rule |
|---|---|
| Flags | inverse Phase 2B map (identity / −300 / −500 segments); DE 32-bit 0 → Wii 16-bit 0x108 (must fit 16 bits) |
| Award counters | `achievements.de_to_wii`: lead slot = max of the DE tier counters, other tier slots 0, flag/art/Colony-6-derived slots 0 (the Wii recomputes them). Lossy above the top tier → base kept when unchanged |
| Quest counters | 0xFF → `num` (kill) or 1 (other types); kill progress kept; q ≥ 1000 (Future Connected) → sidecar |
| Characters | level, EXP, AP, coins, SP, tree, palettes, arts per art index; skill nodes `id = (k−1)·25 + 5t + e + 1` for e < learned; links by source; EXP-earned counter `+0x2A0` advanced by the EXP gained (lineage) or the cumulative EXP (foreign) |
| Equipment | gid / row / box index per slot, through the compaction remap |
| Inventory | Wii slot = DE slot when it fits, else lowest free slot (references remapped). Headers `gid<<20|type<<16|row<<5|low5`; gems `low5 = rank<<2`, flags 3 for crafted (gid 3747); crystals `low5 = rank<<2 | (drop?1:0)`, flags `attribute<<2 | kind`, drop crystals' ITM_dropcrystallist row found by (rank, attribute, cylinder, effects); built-in gem descriptors from the gem item (effect = itemID, strength = percent, rank = rankType) |
| Capacity | weapons, armour and materials: `10 × (bits 1–11 of ITEM+0x12108) + 60 + min(ITEM+0x12110, 30)` (box getter `0x80158490`); gems/crystals/collectables 300, key items 200, art manuals 240 |
| Map, position, clock, play time | map word + map string `"AASSf"` (both copies), PCPM leader and followers, TIME float = 1800·h + 30·m, THUM scenario / play time / area / party / leader level |
| Minimap | `minimap.de_to_wii` strict (a Wii cell only if all DE cells inside it are explored), OR-merge |
| CRCs | every section's CRC-16/ARC recomputed |

---

## 5. Sidecar (`xc1-sidecar/1`)

Written next to every export as `<direction>.sidecar.json`. All keys are explicit; identity never relies on
file names.

```json
{
  "sidecar_schema": "xc1-sidecar/1",
  "converter_version": "2E-rc1",
  "direction": "de_to_wii | wii_to_de",
  "session_id": "sha256(direction + source sha + output sha)[:32]",
  "lineage": {"playthrough_id": "...", "generation": 1, "parent_session": null},
  "source": {"game": "de", "format": "de-v10", "sha256": "...", "name": "bfsgame00.sav", "fingerprint_shared": "..."},
  "output": {"game": "wii", "format": "sx4e", "sha256": "...", "name": "monado01", "fingerprint_shared": "..."},
  "snapshots": {"source": {"encoding": "zlib+base64", "sha256": "...", "size": 1392432, "data": "..."},
                "output": {"encoding": "zlib+base64", "sha256": "...", "size": 163840, "data": "..."}},
  "deferred": {"de_only_items": {...}, "overflow_items": {...}, "future_connected_quest_counters": {...},
               "future_connected_quest_states": {...}},
  "de_only": {...}, "wii_only": {...},
  "notes": [...],
  "integrity": {"sha256": "sha256 of the canonical JSON body without this field"}
}
```

- **Snapshots**: the full source image is the recovery snapshot and the template for the re-import. The output
  image is the exact file the other game started from, which is used for the descent check and the 3-way merge.
  Only the user's own save files are embedded, never game data.
- **Integrity**: any edit or corruption makes `sidecar.load` fail, and snapshot hashes are checked on unpack.
- **Lineage**: `playthrough_id` is inherited, `generation` increases, and `parent_session` links each export to
  the previous one.

---

## 6. Re-import (Wii → DE with a DE → Wii sidecar)

`reimport.wii_to_de_reimport(current_wii, sidecar, T, current_de=None, branch=None)`:

1. Verify the schema, integrity and direction.
2. **Descent.** The current Wii save must continue the exported one. Refused if the play time or story went back,
   a character lost more than 10 levels, fewer than 90 % of the exported flags remain set, or fewer than 50 % of
   the exported items (matched by id and acquisition serial) are still present.
3. **Divergence.** If the user passes their current DE save and its shared state has changed since the export,
   and the Wii save has also changed, the import stops with `DivergenceError`. It runs only with an explicit
   `branch="wii"`. If only the DE side changed, there is nothing to import. Neither save is ever chosen by play
   time or story value.
4. **Wii unchanged since export:** the original DE save is returned byte for byte.
5. **Otherwise:** `convert.build(current_wii, template = original DE, minimap_base="merge")`, then a 3-way pass.
   - Characters and items whose shared content did not change since export get their **exact original DE
     record** back (Expert Mode fields, cosmetics, favourites, padding).
   - Awards, quest counters, clock, location, play time and Shulk's second talent byte: where the value derived
     from the Wii did not change since export, the original DE value is kept.
   - Minimap: the original DE bitmaps plus only the DE cells explained by **new** Wii exploration.
   - **Expert Mode:** the active level comes from the Wii; highest level = max(original highest, new level); reserve
     EXP is left untouched. Wii EXP went into the level, never into the reserve, so nothing is duplicated or lost.
6. Deferred DE-only and overflow items are restored to their original slot when it is free, otherwise to the
   first free slot (index field updated).

The DE → Wii direction with a Wii → DE sidecar is `de_to_wii.build(current_de, base = sidecar source,
lineage=True)`, with the same descent and divergence checks.

---

## 7. Compatibility rules (DE → Wii)

Refused (`IncompatibleError`):

- the current map is not a Wii map (Future Connected `ma50xx`–`ma60xx`, or an area above 24);
- the story scenario is outside 1–486;
- the party is empty or contains ids outside 1–13;
- a character level is outside 1–99;
- a DE-only item is equipped;
- a DE flag value does not fit the Wii bank;
- more items than the Wii save's box capacity, unless `--overflow sidecar` (unequipped, unreferenced extras
  only);
- equipment references to empty slots;
- no Wii drop-crystal row matches a DE drop crystal;
- the DE save is not v7/v10, or the Wii base is not a valid used slot.

Deferred to the sidecar (never silently dropped):

- DE-only items that are not equipped;
- overflow items;
- Future Connected quest counters and states;
- Expert Mode, cosmetics, DE-only flags, Time Attack and options. These stay in the original DE image, which is
  the re-import template.

---

## 8. Safety rules of the CLI

- Every input and output path is explicit.
- Writes are refused under the Monado install, any Dolphin `User\Wii` folder, the Proton Drive NAND root and
  the Filen Wii save folder.
- Existing files are never overwritten. Writes go to a temporary file and are then renamed (atomic).
- `--dry-run` converts and verifies but writes nothing.
- Every output is accompanied by `manifest.json` (SHA-256 of inputs and outputs) and a sidecar.
- Any read-back difference refuses the output.
