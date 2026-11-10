# Xenoblade Chronicles Wii ⇄ Definitive Edition
## Phase 2E: finalization, bidirectional conversion, release candidate

Date: 2026-11-06 (overnight, autonomous). Input: `monado01` (scenario 150, Eryth Sea, 22:01:57). DE template: your
v10 save (scenario 6). Converter version `2E-rc1`.

Evidence labels:
- **[C] code**: an address in the Wii `main.dol` (SX4E01) or the DE `main` (7E1DF8E0…);
- **[D] data**: reproduced by a script against saves or tables;
- **[G] observed in a game**: an isolated Monado or Dolphin run;
- **[S] synthetic fixture**: a test input built from your save, not evidence of game behaviour;
- **[H] hypothesis**.

### Safety record

- Every game run used its own folder under `work/phase2e/monado/<run>` or `work/phase2e/dolphin/<run>`.
- **Monado** ran with `LARECOMP_SAVE_DIR`, the journal and backups off, and `XCDE_INI` pointing at a copy of
  your settings. The harness killed the game unless its log showed the run's own `save_0` mounted. Your live
  `save_0` was hashed before and after every run.
- **Dolphin** ran with `-u <run>\user`, its own config and NAND, and copies of the test save only. Input came from
  a local DSU virtual pad, so no keystrokes went to the desktop. The normal NAND (Proton Drive), the Filen Wii save
  folder and the portable `User\Wii` folder were hashed before and after every run.
- **26 isolated runs** (16 Monado, 10 Dolphin): every run mounted its own folder, and **0 isolation problems**
  were recorded (`work/phase2e/validation_summary.json`).
- **End-of-run check** (`work/phase2e/input_manifest_end.json`): all 21 tracked original and live files are
  unchanged. This covers the Wii `monado01/02/03` and `banner.bin`, the live Monado `save_0` files, the Proton
  Drive NAND copies, and the research originals and template. Nothing was deployed, pushed or downloaded.

---

## 1. Results at a glance

| Capability | Status | Basis |
|---|---|---|
| Wii → DE | **VALIDATED** for your playthrough (scenario 150), story verified 150 → 156 | load, menus, combat to victory, 2× fast travel, story events, save/reload in Monado [G]; canonical read-back 0 differences [D] |
| DE → Wii | **PARTIALLY VALIDATED** | load, party/inventory, Quest Log, combat to victory, 2× skip travel, Wii save and reload in Dolphin [G]; **story progression on the Wii not exercised** |
| Bidirectional | **VALIDATED for the tested chain** | Wii → DE → (Monado play) → Wii → (Dolphin play) → DE → (Monado load/save/reload): independent canonical comparisons at every step, in-game tests on both sides |
| Static round trips | Wii → DE → Wii byte-identical (`monado01`, `monado03`); DE → Wii → DE byte-identical when the Wii side is unchanged | 40 automated tests |

---

## 2. Part A: Wii → DE fidelity

| Item | Result | Rule / location | Evidence |
|---|---|---|---|
| **A1 GAME object** | Every byte of the 0x41F0-byte object now belongs to a named region. | `work/phase2e/re_wii_game.md/.json` | [C][D] |
| `+0x58…0x1F97` | Quest objective counters, 1000 × 8 bytes; covers the old "unknown" `+0x50–0xF00` and `+0x1690` lists. | see A2 | [C][D] |
| `+0x3890…0x41EF` | Story-scene costume snapshot, 32 slots (old "unknown" `+0x3890–0x4000`, `+0x3FB0`, `+0x4190`). Player-visible, noncritical. DE: `0x149CB4` equipment ids, `0x14DC40` cosmetics. | not converted | [C][H] |
| `+0x54/+0x56` | Two u16 set to 1 at init; no reader found. | kept from base | [C] |
| **A2 quest counters** | **Phase 2D defect found and fixed.** Wii `0xB2B8 + 8q` ⇄ DE `0x1270 + 8q`; done = 0xFF in DE, ≥ num / ≥ 1 on the Wii. Phase 2D left the template's counters, so quests 221 and 287 (objectives done, items consumed) would have reverted. Now converted for 123 quests. Quest 90's "2+4+3" is the *requirement*; progress is 0/0/0. | `tools/quest_counters.py` | [C][D] |
| **A3 minimap** | Verified geometric transform. Wii: 24×24 cells per floor, bits at file `0xD25C`. DE: per-map bitmaps from `0x46F40`, about 4×4-unit cells. Self-test 45/45; 148/149 visited Wii landmarks fall in transferred cells. Display mode reproduces the Wii squares. | `tools/minimap.py` | [C][D]; [G]: Eryth Sea, Colony 9 and Frontier Village maps show the exploration in Monado |
| **A4 clock** | Phase 2D read the time as 6:36; **it is 13:13 on day 30**. Wii float in 2-second units (1800 per hour) → DE hour/minute `0x149C04/06`, day `0x149C24`, last sunrise day `0x149C26` (from Wii 16-bit `0xAF`). The "location word `0x149C04`" of Phase 2D was the clock. The clock gates 495 quest markers, 1,353 spawns and 255 collectables. | `convert.convert_clock` | [C][D][G] Monado showed 13:25 after load |
| **A4 awards** | The six approximations now have exact rules (unique-monster and landmark flag counts, max art level, fevers). 11 more counters were wrong in Phase 2D (awards 10, 73, 74, 87, 150, 151, 195–197, 199, 200); corrected. Latent bug: Wii `0xAF` (sunrise day) is not an award counter. | `tools/achievements.py` | [C][D] |
| **A5 characters / inventory** | All six characters' equipment and gems, Skill Trees, Skill Links, Arts, Gem Crafting crystal list, Items, Collectopaedia and Affinity Chart screens open correctly; Expert Mode and appearance fields kept from the template. | | [G] |
| Absent characters | Phase 2E converts all seven main characters' progression (a Wii save made in a temporary party, such as Melia alone, still holds everyone); equipment only for party members (DE keeps none for absent characters). | `features: all_characters` | [D] |

---

## 3. Part B: gameplay acceptance in Monado (isolated)

| # | Test | Result | Runs |
|---|---|---|---|
| 1 | Load into Eryth Sea | PASS | m1, m2 |
| 2 | Party members | PASS | m3 |
| 3 | Arts, Skill Trees | PASS | m2, m3 |
| 4 | Affinity Chart | PASS (opens; NPC list not inspected) | m3 |
| 5 | Equipment, gems, crystals | PASS (6 characters; crystal list; a craft was not completed) | m3 |
| 6 | Collectopaedia | PASS (Eryth Sea, 0) | m3 |
| 7 | Change active party | **NOT TESTED** (Party screen opened only) | — |
| 8–9 | Battle, arts and skills | PASS: arts executed, Bind/Bleed/Break/Topple, Hero Time; **victory**: kill counter 738 → 739, EXP/AP/SP to all six | b1, c2 |
| 10 | Two fast travels | PASS: Frontier Village (Entry Bridge), Colony 9 (Gem Man's Stall) | f3 |
| 11 | Quests | PASS | r1, v1 |
| 12 | Next story objective | PASS: scenario-150 event `vs08030100` at Centre Gate played | s1 |
| 13 | Progress to scenario 160 | **PARTIAL: 150 → 156** (two DE autosaves record 154 and 156; Melia's audience scenes played). The scenario-157 trigger could not be located in the tables. | s1, s2, s3 |
| 14–16 | Save, reload, state again | PASS (only clock and play time differ) | f3, c2, r1, e3 |

Method: `tools/monado_harness.py` + `tools/route.py` (frame-scripted input; captures). Travel to the story trigger
used Monado's debug teleport (`XCDE_WARP`) instead of a 2,400-unit walk; the events themselves were the game's own
triggers. Old Phase 2D quest-log stall: the main menu reopens at the top item, and routes now rely on that.

---

## 4. Parts C–D: bidirectional architecture and sidecar

See `BIDIRECTIONAL_DESIGN.md`. Summary:
- `tools/canon.py`, canonical state `xc1-canon/1`: shared / wii_only / de_only / derived. **canonical(`monado01`)
  = canonical(Phase 2E DE output)** over every shared field [D].
- `tools/de_to_wii.py`: patches a lineage or foreign Wii base, keeps exact base bytes wherever the DE value is
  what the base converts to, and has an inventory capacity rule (code `0x80158490`: `10·bits + 60 + bonus`;
  140 for your save) with compaction and remapping. `--overflow refuse|sidecar`. It enforces compatibility
  refusals (Future Connected, non-Wii maps and scenarios, equipped DE-only items, …).
- `tools/sidecar.py`, `xc1-sidecar/1`: integrity hash, both full snapshots, lineage, deferred DE-only items, and
  fingerprints.
- `tools/reimport.py`: 3-way delta re-import. The Expert Mode policy keeps the highest level and leaves the reserve
  EXP untouched. Divergence is refused without an explicit `--branch`.
- `tools/xcconv.py`: the CLI. No implicit writes, no overwrites, atomic writes, dry runs, manifests, and refusal of
  live game folders.

---

## 5. Part E: validation

### E1 static

| Case | Result |
|---|---|
| Wii → DE → Wii (`monado01`, `monado03`) | **byte-identical** |
| DE → Wii → DE, Wii unchanged | **byte-identical** (original DE restored) |
| DE → Wii for Monado-played saves (fast travel, story 154, story 156), your DE-native save (foreign base), public scenario-206/232 saves | CRCs valid; canonical read-back 0 differences; scenario 206 and 232 (145/163 weapons > 140) **refused** unless `--overflow sidecar` (46 weapons deferred, 114 crystals compacted) |
| Synthetic DE-only state [S]: Expert Mode, cosmetic, reserve EXP, highest level, DE-only collectable, favourite, DE-only flag, Future Connected counter | All restored after DE → Wii → (simulated Wii progress) → DE; level-up applied, highest level kept, reserve neither lost nor duplicated |
| Divergence, tampered sidecar, foreign Wii save | refused as designed |

### E2 Dolphin

The converted save W1 came from DE1, the Monado-played save.
- **Wii load list:** play time 22:04 shown.
- **Field and Party screen:** levels, HP and money match.
- **Quest Log:** coherent.
- **Combat:** won, with EXP/AP/SP awarded.
- **Skip travel:** Colony 9 and Frontier Village.
- **Saving:** the Wii game saved twice, and its own re-saves reloaded.
- **Section checksums:** valid (`xcconv validate`).
- **DE-native export** (your scenario-6 save on a foreign base): loads in Colony 9 and saves.
- **Not exercised on the Wii:** story progression.

### E3 back to Monado

- W2 and W3 (files written by the Wii game itself) re-imported through the sidecar.
  - **DE2** differs from DE1 only in the Wii-side play: clock, play time, position.
  - **DE3** lands in Frontier Village, where the Wii session ended.
- Both loaded, were saved, and reloaded in Monado.
- Monado's re-save of DE3 vs the Dolphin file W3 in canonical form: **only clock minute and play time differ**.
- **Finding during E3:** the Wii set 1-bit flags `0x36C5/0x36C7` (block `0x3440 + 645/647`, NPC registration or
  update notices) that have no DE slot. The converter now treats Wii `0x352C–0x36CF` as Wii-only instead of
  refusing. See `KNOWN_LIMITATIONS.md` 3a: the Phase 2B +500 placement of this block is not code-backed.

---

## 6. Parts F–G: CLI and release candidate

`release_candidate/`:

| Folder | Contents |
|---|---|
| `converter/` | Distributable code, docs, specs, tests, `xcconv.cmd`. No game data. |
| `user_data/data/` | Your BDAT dumps. **Not for distribution.** |
| `user_saves/` | `wii_to_de_monado01/save_0/bfsgame01.sav` (SHA-256 `9879757e…a63a`, the file validated in Monado), its sidecar and manifest, plus `chain_example/` with every chain artifact. **Personal.** |
| `validation/` | Manifests, test log, validation summary. |
| `SHA256SUMS.txt` | Hashes of everything above. |

The packaged converter was run standalone: round trip byte-identical, dry run writes nothing, and live paths are
refused.

Tests: `python -m unittest discover -s tests` → **40/40 OK** (Phase 2C 13, Phase 2D 11 including the Phase 2D
baseline-identity check, Phase 2E 16 including the real Dolphin/Monado chain).

---

## 7. Files added in Phase 2E

| File | Purpose |
|---|---|
| `tools/xcconv.py`, `canon.py`, `de_to_wii.py`, `sidecar.py`, `reimport.py` | CLI and bidirectional core |
| `tools/quest_counters.py`, `achievements.py`, `minimap.py`, `paths.py` | Phase 2E rules, table location |
| `tools/convert.py` | `build()` API and Phase 2E steps (`--baseline-2d` = Phase 2D bytes) |
| `tools/monado_harness.py`, `route.py`, `dolphin_harness.py`, `droute.py`, `contact.py` | Isolated game automation |
| `tools/build_rc.py` | Release-candidate assembly |
| `tests/test_phase2e.py` | 16 tests |
| `work/phase2e/re_*.md/.json` | Reverse-engineering reports (GAME object and quest counters; clock, awards and DE-only fields; minimap) |
| `work/phase2e/monado/`, `dolphin/`, `chain/` | Runs, captures, manifests, chain artifacts |
| `baseline_phase2d/` | Frozen Phase 2D tools, specs, tests, output and hashes |
| `BIDIRECTIONAL_DESIGN.md`, `README_CONVERTER.md`, `KNOWN_LIMITATIONS.md`, `OVERNIGHT_SUMMARY.md` | Documentation |
