# Xenoblade Chronicles Wii → Definitive Edition
## Phase 2B: Executable-Backed Flag Mapping

Date: 2026-11-05. This phase was read-only static analysis of copies of your own executables.

| Executable | Source | Copy and hash |
|---|---|---|
| Wii `main.dol` | Extracted from `E:\Launchbox\Games\ROMs\Wii\Xenoblade Chronicles [NTSC-U].rvz` with DolphinTool, read-only | `exe/wii/main.dol`, SHA-256 `e048b800…3aa04` |
| DE `main` | NSO, build ID `7E1DF8E08D60544BBDCA1E333C153C97` | `exe/de/main`, identical hash to the installed file; decompressed to `exe/de/main.bin` |

Also extracted: Wii event scripts (`exe/wii/x/DATA/files/script/en/script.pkb`, 670 SB blobs). DE scripts were read in place from `targets/romfs/script` (616 files).

What was not done:
- No save was created, edited or loaded.
- Monado was not run.
- Nothing in the Monado install, the Dolphin NAND or the disc image was modified.
- Your saves still match `work/originals/SHA256SUMS.txt`.

Your money value (103,000 G) is treated as validated, as you confirmed. The money offset 0x151B40 (v7 = v10) is therefore confirmed against the in-game display.

Evidence labels:
- **[C] Code.** Read from disassembly, with an address.
- **[D] Data.** Reproduced against real saves by a script.
- **[CD]** Both.
- **[H] Hypothesis.**

---

## 1. Executive findings

1. **The flag system is the same engine design in both games, now proven in code [C].** One global flag-ID space is split by width:
   - 32-bit: `0x000–0x01F`
   - 16-bit: `0x020–0x21F`
   - 8-bit: `0x220–0xA1F`
   - 1-bit: from `0xA20`

   Both executables use exactly these thresholds:
   - Wii resolver `0x8009DB04`
   - DE getter `0xB2620` and setter `0xAEB10`

   The only bank-capacity difference is that the Wii 1-bit range ends at `0x36CF` and DE's at `0x371F`.
2. **Phase 2A misread the Wii 16-bit and 8-bit banks.** The Wii packs 16-bit and 8-bit flags into big-endian words and selects them by shift, so within each word they are stored byte-reversed [C].
   - That reversal caused the apparent "−2 offset", the story counter at "index 1", and the contradictory pair-affinity values.
   - With the exact accessors, the 16-bit bank maps by identity: 70 of 76 used entries agree, and the story counter, region affinity and pair affinity all line up [CD].
3. **The +300 shifts are explained and pinned [CD].** DE enlarged two ID ranges for Future Connected and inserted one new block:

   | Bank | Wii → DE change | Boundary |
   |---|---|---|
   | 8-bit quest states | 1,000 → 1,300 slots (`cmpwi id, 0x3E8` in Wii vs descriptor `0x02200514` in DE) | Wii 8-bit IDs ≥ `0x608` move **+300** |
   | 1-bit quest block | `0x2CC8`: 1,024 → 1,324 flags | Wii 1-bit IDs from `0x30C8` move **+300** |
   | 1-bit, DE-only | new 200-flag block at DE `0x3550` | Wii 1-bit IDs from `0x3424` move **+500** |

   This explains the "unresolved tail" from Phase 2A.
4. **All 24 previously unmapped event flags are now mapped.** 23 of 23 match under +500. The last one (Wii `0x33F6`) falls in the +300 segment and is a playthrough difference, not a mapping gap.
5. **Under the final rule set, 675 of your 702 set event flags (96.2 %) are also set in real later DE saves, and so are 151 of 151 quest states [D].**
   - The remaining 27 are in playthrough-dependent blocks: achievements, Colony 6 effects, and a 1,000-flag block at `0x20C8`.
   - They are not mapping errors (§7).
6. **Quest-state values have the same meaning in both games [CD]:**

   | Value | Meaning |
   |---|---|
   | 0 | not started |
   | 1 | accepted |
   | 0xFC | objectives met |
   | 0xFE | completed |
   | 0xFF | closed (compared by the quest code) |
   | 0xC8 (200) | set by engine events such as Colony 6 reconstruction (`CL6_uplist.rev_qstflag`) |

7. **Two real DE semantic changes were found and both have exact conversion rules:**
   - **Wii 16-bit flag `0x108` became DE 32-bit flag `0`.** It is a bitmask: the Wii accessors test `(1<<i) & v`. Values match across games: 0x60E early, 0xEFE later [CD].
   - **Achievement counters (16-bit `0x40+id`).** The Wii keeps one running total per metric; DE keeps a copy per tier, capped at that tier's `MNU_playaward.comp_value` [D].
8. **A scenario-150 game state can very probably be built from your own early DE save, without an Eryth Sea template [CD/H].**
   - Story, quests, landmarks, affinity, Colony 6 and achievements all live in the flag array. It is one contiguous block in both games: Wii memset size `0x1214` at `0x8009DA28`, which equals the CRC-covered FLAG range.
   - That array now has a code-backed rule for every region.
   - Outside the flags, the story needs four more things:
     - the party table (offset known)
     - the current map (DE `0x149C00`, same encoding as Wii `0xB260`, found this phase)
     - position (world coordinates are identical; 430 of 431 landmark positions match between Wii and DE)
     - **equipment for party members who join later**, which is the main crash risk (§8)

---

## 2. How the flags are stored (code)

### 2.1 Wii (`main.dol`, SX4E01)

| Address | Function | Detail |
|---|---|---|
| `0x80571848` | flag array (global) | cleared with `memset(…, 0, 0x1214)` at `0x8009DA28` / `0x8009DE7C`; saved verbatim as the FLAG payload at file `0xA030` |
| `0x8009DB04` | resolver(base, id) → word pointer, type, sub-index | `id ≤ 0x1F`: word id. `id−0x20 ≤ 0x1FF`: word `0x20+(s>>1)`. `id−0x220 ≤ 0x7FF`: word `0x120+(s>>2)`. `id−0xA20 ≤ 0x2CAF`: word `0x320+(n>>5)` |
| `0x8009DBD0` | getter | 16-bit shift `16·(s&1)`; 8-bit shift `8·(s&3)`; 1-bit shift `n&31`; masks from tables at `r13−0x7C10` and `0x80528048` / `0x80528058` |
| `0x8009DCA0` | setter | clamps to 0xFFFF / 0xFF / 1 |
| `0x8009D964` / `0x8009D9F0` | public `getFlag(id)` / `setFlag(id, v)` | 600 call sites (`tables/wii_flag_callsites.tsv`) |

Byte formula, with P = `0xA030`:

| Bank | Location |
|---|---|
| 32-bit g | `P+4g` (big-endian) |
| 16-bit s = g−0x20 | `P+0x80+4·(s>>1)+(s&1 ? 0 : 2)` |
| 8-bit s = g−0x220 | `P+0x480+4·(s>>2)+3−(s&3)` |
| 1-bit n = g−0xA20 | BE word `P+0xC80+4·(n>>5)`, bit `n&31` |

### 2.2 DE (`main`, 7E1DF8E0…)

| Address | Function | Detail |
|---|---|---|
| `0xB2620` | getter(desc, idx) | `desc = (start<<16) \| count`. `(desc>>21) ≥ 0x51` → 1-bit at `ctx+0x700`, bounded by `n>>8 < 0x2D`. `≥ 0x11` → 8-bit at `ctx+0xCA0`. `desc ≥ 0x200000` → 16-bit at `ctx+0x14A0`. Otherwise 32-bit at `ctx+0x18A0+4·idx`. Achievement descriptors `0x325800C8` / `0x004000C8` reduce idx modulo 200 |
| `0xAEB10` | setter | same dispatch |
| `0xB4200` / `0xB59F0` / `0xB565C` | block wrappers | descriptors `0x2CC8052C`, `0x346C00E4`, `0x20C803E8` |

Save offset = runtime offset − 0x6B0:

| Bank | Save location |
|---|---|
| 1-bit | `0x50` (LE u32 words) |
| 8-bit | `0x5F0` |
| 16-bit | `0xDF0` |
| 32-bit | `0x11F0` (prefix ends `0x1270`) |

The v10 layout keeps all four (Phase 2A §5). All 174 DE descriptor constants are in `tools/desc_de.txt`.

---

## 3. Block map (Wii engine bases vs DE descriptors)

The Wii build passes block bases as `addi r3, rIdx, BASE` before `getFlag` / `setFlag`; DE passes `(BASE<<16)|COUNT` descriptors.

| Wii base (count) | Code site (Wii) | DE descriptor | Δ | Meaning | Evidence |
|---|---|---|---|---|---|
| 8-bit `0x220` (1,000) | `cmpwi id,0x3E8` at `0x8013FC64`, `0x8013FCC0`, `0x8014092C`… | `0x02200514` (1,300) | 0 | quest state by quest ID | [CD] all 151 on valid IDs; 151/151 persist |
| 8-bit `0x608` | base at 7 sites | `0x0734018F` / `0x07340190` | +300 | post-quest block | [CD] |
| 8-bit `0x798` | 3 sites | `0x08C40064` | +300 | Colony 6 self/resident flags | [CD] |
| 8-bit `0x7FC` | 10 sites | `0x09280008` | +300 | Colony 6 levels (dev, pop, 4 facilities, overall) | [CD] Wii scenario-150 values 10/18/1/2/1/1/1 |
| 8-bit `0x804` | 21 sites | `0x09300008` | +300 | (8 bytes after Colony 6) | [C] |
| 8-bit post-quest overall | — | — | **+300** | 48 of 48 bytes match at exactly +300; ±1–3 gives 22–31 | [D] |
| 1-bit `0xA20` | 9 sites | `0x0A20012B` / `012C` | 0 | per-landmark state (not discovery) | [CD] |
| 1-bit `0x1D44` | 6 | `0x1D44012C` | 0 | Colony 6 effect flags (`rev_effflag1`) | [CD] |
| 1-bit `0x1E70`+landmark ID | — | `0x1E7001F4` (500) | 0 | **landmark discovered** | [D] discovery tracks story progress in all saves (§4) |
| 1-bit `0x20C8` | 12 | `0x20C803E8` (1,000) | 0 | (per-ID block, 1,000) | [CD] |
| 1-bit `0x278A` | 3 | `0x278A012C` | 0 | Colony 6 effect flags 2 | [C] |
| 1-bit `0x2CC8` (1,024) | `0x8013CA30`, `0x8020B504` | `0x2CC8052C` (1,324) | 0 | per-quest 1-bit block | [CD] |
| **1-bit `0x30C8`** | (= `0x2CC8 + 0x400`) | `0x31F40064` | **+300** | first block after the quest block | [CD] data boundary window (9459, 9897] contains n = 9896 |
| 1-bit `0x312C` (200) | 6 sites | `0x325800C8` | +300 | achievement completion bits | [CD] |
| 1-bit `0x31F4` (30) | loop to `0x1E` at `0x80084F88` | (DE `0x3320`) | +300 | 30-flag block | [C] |
| 1-bit `0x3212` / `0x3213` | — | `0x333E0001` / `0x333F0001` | +300 | singles | [C] |
| 1-bit `0x3214` (300) | `0x801435B8` | `0x3340012C` | +300 | 300-flag block | [C] |
| 1-bit `0x333F+i`, `0x33BF+i` (128 + 100) | `0x802AF3B8`, `0x802AF14C` | `0x346C00E4` (228) | +300 | probably tips/help (DE sets 5 extra at a new game) | [CD]; meaning [H] |
| — | — | **DE-only `0x3550` (200)** | — | mirror of the block above. In 10/10 DE saves its set indices are a subset of the `0x346C` block's | [D] |
| 1-bit `0x3440` | `0x801BE4FC`, `0x80274D0C` | (DE `0x363C`) | **+500** | — | [C] |
| 1-bit `0x3508` / `0x3509` (15) | `0x8026C310` (5-character loop) | `0x36FC0001` / `0x36FD000F` | +500 | hidden skill-tree flags | [CD] |
| 1-bit `0x3518` | — | `0x370C0008` | +500 | — | [C] |

**About the +500 boundary (Wii `0x3424`).** Wii blocks `0x3340` (128) + `0x33C0` (100) together equal DE's 228-flag `0x346C` block. DE then adds 200 flags, so everything from Wii `0x3424` shifts +500. The data agrees: Wii `0x33F6` behaves as +300 and Wii `0x3441`… behave as +500, 23 of 23. The upper bound of the Wii `0x33BF` block has not been read from code; the boundary itself follows from the two descriptor sizes.

---

## 4. Verification against story events and BDAT

| Check | Result |
|---|---|
| Story counter = 16-bit `0x20` | Wii 150 / 18 ↔ DE scenario texts identical (Phase 1) [CD] |
| Region affinity 16-bit `0x22–0x26` (`0x00210007` region ID + 1) | Wii scenario 150: Colony 9 2500, **Colony 6 1850**, Central Bionis 2550, Upper Bionis 0, Hidden Village 0. Matches progress (Alcamoth not yet visited) [CD] |
| Pair affinity 16-bit `0x29–0x3D` (`0x00280015` / `16`) | Early Wii: Shulk–Reyn 1610, Shulk–Fiora 970, Reyn–Fiora 50; DE scenario 20: 910 / 580 / 100. The same pairs are nonzero [CD] |
| Landmark discovery `0x1E70`+ID | Wii scenario 18: IDs ≤ 22 (all Colony 9). Wii scenario 150: up to 168 (Frontier Village). DE scenario 206: up to 234 (Prison Island). Your DE save (scenario 6): 0–7 [D] |
| Quest states by area | Wii scenario 150 has states only in quest tables 0101–0701 and 1401; DE scenario 206 additionally has 1001 and 1101 [D] |
| Colony 6 (`CL6_uplist`, identical in both versions) | `rev_qstflag` 991–995 … set to 200 → the 931–999 value-200 cluster matches by identity across games [CD] |
| Achievements (`JNL_playaward` 200 rows, identical; `MNU_playaward`) | Wii completion bits at `0x312C+id` agree with Wii totals (enemies 738: tiers 50 and 200 set, 1000 not) [CD] |
| Event scripts (670 Wii / 616 DE SB files, paired by int-pool similarity) | Every flag-range constant in script pools maps by identity (about 4,000/4,000). **No script references the shifted ranges**, which the engine manages alone (`tools/sb_flagdiff.py`) [D] |

---

## 5. Exact rule set (converter specification)

Each rule is applied by global ID on top of a DE template. The reference implementation is
`tools/flag_transplant_eval.py`, with accessors in `tools/flagmap.py`.

| Bank | Wii source | DE target | Rule |
|---|---|---|---|
| 32-bit | — | `0x000` | `DE32[0] = Wii16[0x108]` (bitmask, widened) |
| 32-bit | `0x00–0x1F` | `0x01–0x1F` | keep template (Wii never uses its 32-bit bank) |
| 16-bit | `0x020–0x03F`, `0x108–0x21F` | same | identity |
| 16-bit | `0x108` | `0x108` | set 0 (moved to 32-bit) |
| 16-bit | `0x040–0x107` (achievement counters) | same | `DE[id] = min(WiiTotal(group(id)), comp_value[id])`, where a group is a lead ID plus following tiers. If the Wii counter is absent but the completion bit is set: `DE[id] = comp_value[id]` |
| 16-bit | `0xB7, 0xBE, 0xBF, 0xC3, 0xF9` | — | **hold**: Wii-used, never set by DE |
| 8-bit | `0x220–0x607` | same | identity (quest states, value codes shared) |
| 8-bit | `0x608–0x8F3` | +300 | shift |
| 8-bit | — | `0x608–0x733` | keep template (Future Connected quest slots) |
| 1-bit | `0xA20–0x30C7` | same | identity, except DE `0x1E70` (index 0): keep template |
| 1-bit | `0x30C8–0x3423` | +300 | shift. For DE `0x346C–0x354F`, write `Wii-mapped OR template` |
| 1-bit | `0x3424–0x352B` | +500 | shift |
| 1-bit | — | `0x30C8–0x31F3`, `0x3550–0x3617` | keep template. Option: rebuild `0x3550+i` from the new `0x346C+i`, preserving B ⊆ A |
| 1-bit | `0x352C–0x36CF` | — | must be zero (all your saves: max used ID `0x351C`) |

**Dry run** (in memory only; no save written): your `monado01` onto your v10 save gives:
- story 150, `DE32[0] = 0xEFE`
- 199 nonzero quest/8-bit bytes
- 720 set 1-bit flags, of which 689/720 are also set in the real DE scenario-206 save and 693/720 in the scenario-232 save
- 0 overflows, 0 writes into DE-only ranges

Template values changed by the transplant: 7 bits. Two are early transient flags that are correctly cleared. Five (DE `0x34CB–0x34D9`) are kept by the OR rule.

---

## 6. Rebuilding scenario 150 from your early DE save

| State | Where (DE v10) | Source | Status |
|---|---|---|---|
| Story, events, quests, landmarks, affinity, Colony 6, achievements | flag prefix `0x50–0x1270` | Wii FLAG under §5 | **Rule complete** [CD] |
| Party list | `0x1526D8` (u16 × 12), count `0x1526F0` | Wii `0xD1FE + 4i` → [1,4,6,5,2,7] | Offsets known [CD]; edit proven safe by Monado author |
| Current map | **`0x149C00` u32 `(sub<<16)\|area`** | Wii GAME `0xB260` = `0x0001000A` | Same encoding in 8 DE saves and 2 Wii saves [D] |
| Position | `0x149C10` x,y,z | Wii PCPM `0x11EE0` | World coordinates are identical: `landmarklist` posX/Y/Z match in 430/431 rows [D] |
| Unknown location word | `0x149C04` (two u16, e.g. 0x0031/0x0009) | ? | **Unresolved**. Possibly a respawn landmark; safest is a value taken from an Eryth Sea landmark |
| Levels | char record +0 (v10 `0x152728 + 0x138·k`) | Wii `0xF8D0 + 0x304·n` | known [D] |
| EXP / AP / SP / arts / skill trees / links | DE known (v7 docs, +0x3C0 in v10) | **Wii 0x304 block undecoded**: it holds runtime-style HP floats and packed stats, not DE's layout | **Open** |
| Equipment (party members joining later) | DE equip refs (box indices) | Wii weapon / gem arrays partly decoded | **Crash risk**: xde-party documents that DE crashes on a party member with no weapon equipped |
| Inventory, collectables, key items | DE v7 item boxes (unchanged in v10) | Wii ITEM mostly undecoded | Open. No story key item is needed at scenario 150 [H] |
| Collectopaedia | `0x148D6C` bitfield | Wii unknown | Open (cosmetic) |
| Chests and collection points (Wii TBOX/MINE), weather, time of day | DE unknown | Wii decoded (MINE/TBOX/WTHR) | Template defaults are acceptable [H] |
| Play time, thumbnail | header `0x04`; `.tmb` | Wii THUM 22h01m | cosmetic; the game rewrites `.tmb` on the next save |

**Verdict.** An Eryth Sea template is **not required**. Story-critical state is the flag array (rule complete), party, map and position. The real obstacles to a *playable* rather than merely *loadable* result are character progression and equipment, which are Wii-side decoding work.

---

## 7. Remaining unknowns

| # | Item | Size of impact | How to resolve |
|---|---|---|---|
| 1 | 27 Wii flags not set in the DE reference saves | 3.8 % of your set event flags: achievements (4), Colony 6 effects (2), `0x20C8` block (7), `0x3340` tips (4), misc (10) | Playthrough differences (the references are another player's run), not mapping. In-game check after transplant |
| 2 | 16-bit IDs `0xB7, 0xBE, 0xBF, 0xC3, 0xF9` | 5 small values | Trace their Wii and DE call sites (`tables/wii_flag_callsites.tsv`) |
| 3 | Meaning of the `0x3340` / `0x346C` block (tips?) and the DE-only mirror block | cosmetic [H] | Static: follow `0x802AF3B8`. In game: tip menu |
| 4 | Wii upper bound of the `0x33BF` block (fixes +500 at `0x3424`) | Boundary already consistent with data | Read the bound check near `0x802AF14C` |
| 5 | Achievement metric groups whose Wii counter lives outside 16-bit (e.g. unique monsters 8–10: Wii completion set, counter 0) | a few counters | Use the `comp_value` repair rule (§5) |
| 6 | DE `0x149C04` | possible respawn point | Diff two isolated Monado saves at different landmarks (needs a game run) |
| 7 | Wii character block (0x304), ITEM section | large | Differential Dolphin saves, or trace the GAME/ITEM serializers in `main.dol` |
| 8 | v10 insertion point (0x3C0) in v7 `[0x151B44, 0x152318)` and the 0x310 tail | does not affect flags | v10 schema tables in DE `main` (hashcade cites `0xE02A0`) |

**Falsified in this phase:**

| Earlier claim | Correction |
|---|---|
| "Wii 8-bit base 0xA4AE" | Byte reversal; exact formula in §2 |
| "16-bit pair affinity contradicts" | Contradiction came from the half-swap |
| "1-bit tail unresolved / maybe +500" | Proven +500 |
| "DE-only persistent flags 11057–11074" | They are the new DE `0x3550` block |
| "DE-only flag 5200" | It is landmark index 0, which only DE sets |

---

## 8. Proposed first safe conversion experiment (Phase 2C, not started; needs your authorisation)

**Goal:** prove that a flag-transplanted copy of your own early DE save loads at scenario 150 and behaves coherently. Character data is deliberately left out of this first step.

1. **Build, in the research folder only.** `work/poc/save_0/bfsgame00.sav` = a copy of your v10 save with:
   - the flag prefix written by the §5 rules
   - map `0x149C00 = 0x0001000A`, position = Wii PCPM slot 0
   - **party left as Shulk + Reyn**, so no member without equipment can appear and trigger the documented crash. Copy `.tmb` and `bfssystem.sav` unchanged.
   - Self-check by re-reading every written field with `flagmap.py`; confirm that bytes outside the edited ranges are identical to the template.
2. **Isolated run** (needs authorisation; never touches `save\save_0`):
   - Set `LARECOMP_SAVE_DIR=<research>\work\poc`, `XCDE_SAVE_JOURNAL_OFF=1` and `XCDE_SAVE_BACKUPS=0`.
   - Launch `build\xcde.exe` directly. Check `last_game.log` for `mounted host directory …\work\poc/save_0` before anything else.
3. **Observe, without saving:**
   - title-screen slot
   - field loads in Eryth Sea
   - quest log against your Wii journal (completed and active)
   - landmark list and fast travel to two discovered landmarks
   - affinity chart
   - Colony 6 status
4. **Stop rules:** stop if any of these happens:
   - load failure or crash
   - wrong area
   - more than 5 % of quest states wrong
   - any softlock on talking to the next story NPC
5. **Next step if it passes:** add party [1,4,6,5,2,7] with default weapons from the DE tables. Then, after Wii character and ITEM decoding, transfer full progression.

**Estimated effort from here:**

| Work | Hours |
|---|---|
| First experiment (generator + checks) | 8–15 |
| Achievement counter rule and §7 items 2–4 | 4–8 |
| Party, equipment and location PoC | 8–15 |
| Wii character block and inventory decoding plus transfer | 30–60 |
| Validation | 15–30 |
| **Total to high fidelity** | **~65–130** |

---

## 9. Files produced in this phase

| File | Purpose |
|---|---|
| `tools/nso_extract.py` | NSO → flat image |
| `tools/xdis.py` | ARM64 / PPC disassembly and constant search |
| `tools/flagmap.py` | Exact code-derived flag accessors for both games |
| `tools/flag_transplant_eval.py` | In-memory transplant dry run |
| `tools/sb_flagdiff.py`, `tools/sb_immdiff.py` | Script pairing and constant comparison |
| `tools/desc_de.txt`, `tools/desc_wii.txt` | Descriptor constants harvested from each executable |
| `tables/wii_flag_callsites.tsv` | 600 Wii flag call sites |
| `tables/sb_pairs.tsv`, `tables/sb_subst.tsv` | Script pairing results |
| `tables/transplant_dryrun_notes.tsv` | Dry-run exceptions |
| `bdat/*` | `landmarklist`, `CL6_uplist`, `JNL_playaward`, `MNU_playaward` pages for both versions |
| `exe/` | Executable copies and extracted Wii scripts. **Your own game data; do not share** |

`flag_banks.py` from Phase 2A uses the superseded Wii layout for the 8-bit and 16-bit banks; use `flagmap.py` instead.

A 5 GB temporary extraction of the Wii data partition remains in the session scratch folder (`…\scratchpad\wiidisc`) and can be deleted.
