# Xenoblade Chronicles Wii → Definitive Edition
## Phase 2A: Flag Mapping and Eryth Sea Save Recovery

Date: 2026-11-05. This phase was research only.
- No save was edited, injected or loaded into the game, and Monado was not run.
- The originals were not opened for writing. Their SHA-256 values in `work/originals/SHA256SUMS.txt` match the
  Phase 1 values.
- The installed Monado version was re-checked: `version.txt` reads `v6.0.0XCDE-Portable-V6-.recomendado.zip`.

Evidence labels are the same as in Phase 1:
- **[V] Verified.** Reproduced by a script in `tools/` against real files.
- **[S] Strong.** Several independent consistent observations, but no code-level proof.
- **[H] Hypothesis.**
- **[X] Falsified.**

All statistics in this report can be regenerated with the scripts listed in §10.

---

## 1. Executive findings

1. **No public DE save near scenario 150 exists [V].** The archive
   [samihan-m/xcde-saves](https://github.com/samihan-m/xcde-saves) holds 379 commits and 358 distinct save blobs.
   Its story counters are only 20 and 23 (0.8–0.9 h) and 206–291 (51–69.5 h). Nothing lies in the range 24–205.
   **This archive cannot spare you the 22-hour replay.**
2. **The flag-bank question has largely been answered, and the answer is better than expected.** Wii and DE store
   the same logical game flags. They use the same indices over most of the space. The exceptions are a few
   block shifts that fit DE's Future Connected expansion (Wii quest IDs stop at 970; DE adds 1001–1204).
   - **1-bit event flags:**
     - The Wii stores big-endian u32 words at 0xACB0; DE stores little-endian u32 words at 0x50. Flag numbering is
       otherwise the same.
     - Indices below about 9,460 map one-to-one. Indices from 9,897 to about 10,620 move by **+300** [S/V].
     - Under this rule, 94–96 % of the Wii's set flags are also set in later DE saves. A random alignment gives
       about 9 % on average, 41 % at best.
   - **8-bit quest-state bytes:** both games index them by quest ID, using Wii 0xA4AE+q and DE 0x5F0+q [V].
   - **Story counter and region affinity:** same index in both [V/S].
   - **Still unresolved:** the end of the 1-bit bank, the post-quest 8-bit range (Colony 6 and resident flags,
     shifted by roughly +300 but not pinned exactly), pair affinity and most 16-bit counters.
3. **Story progression can probably come from your own Wii flags rather than someone else's playthrough.** Because
   most flags transfer by rule, the strongest strategy is now **"flag-bank transplant"** (§8): write your Wii flag
   state into a copy of *your own* DE save, keeping DE-only flags from that template. This is plausible but
   untested in the game.
4. **The DE v10 layout is unchanged from v7 for everything up to at least 0x14DC50**, which includes the entire flag
   region [V/S]. A 0x3C0-byte block is inserted somewhere between v7 0x151B44 and 0x152318, and 0x310 bytes are
   appended at the end [V]. Party data, character records and art records sit at v7 offset + 0x3C0 [V].

---

## 2. Public DE save archive investigation

| Item | Value |
|---|---|
| Repository | https://github.com/samihan-m/xcde-saves (last push 2026-09-26) |
| Local clone | `public/xcde-saves.git` (bare, full history, 956 MB) |
| HEAD | `012c8366782837d6a2fc494fa72ebc53955b99db` |
| Commits | 379 (`git rev-list --count HEAD`) |
| Save blobs | 359 file versions, 358 distinct SHA-256 values (`tables/de_history.tsv`) |
| Format | **All v7, 0x153860 bytes**, version u32 = 7 [V]. Not the v10 (2.0.0) format Monado writes. |
| Files per commit | `bfsgame00/00a/01/02.sav` and `.tmb`, `bfssystem.sav` (changed in 45 commits), `saves.png` (the manager's render). **No `bfsmeria*.sav`**, so Future Connected was not tracked. |
| Story counter values | 20, 23, 206, 232, 233, 238 … 291 |
| Lineages | Slots 00a and 02 in the initial commit come from an early run: 0.8–0.9 h, scenarios 20/23, Colony 9, Lv 6, 3,000 G. Every other save is a main run that starts at scenario 206 (51.1 h, Prison Island) and reaches 291 (69.5 h). |
| New Game+? | No evidence. Levels are consistent with an ordinary first run: Lv 6 at 0.8 h, Lv 42 at 51 h. The NG+ flag offset in DE is not documented, so this is **not verified**. |

The story counter at 0xDF0 holds up as an interpretation for these v7 files [V]:
- It rises monotonically along the main run.
- Each value matches its scenario description and the party: Melia (ID 7) joins by 206, and Fiora returns as ID 8
  at 276+.
- It agrees with the documented reading in hashcade (`core/SaveDocument.cs:115`), xcde-save-manager
  (`Extractor.cs:307-329`) and Monado (`runtime/hle/party.c:548-558`).

**Thumbnails and system data.** Every candidate has its `.tmb` and `bfssystem.sav` beside it. The game writes
`.tmb` itself, and Monado passes files through unchanged. Whether the game would rebuild a *missing* `.tmb` is
**untested** [H].

**Upgrading to v10.** No upgrade was attempted, since that requires running the game. The evidence that it would
work is documentary [D]:
- The 2.0.0 executable contains a v7→v8 schema converter, loader 0x86C20 and converter 0xD4020 (hashcade
  `docs/achievements.md:35-40`).
- Monado task T208 records that a downloaded save from another game version loaded and was rewritten at the
  current size (`docs/dev/tasks.md:907-910`, `runtime/services/fs.c:490-492`).

---

## 3. Candidate saves (exact metadata)

None is at 148–152. The nearest on each side:

| Role | Commit | File | Story | Play time | Party (IDs) | Size / version | SHA-256 |
|---|---|---|---|---|---|---|---|
| Nearest earlier | `72259cca38d8cb96d2581d304e1b3982001272d2` (2024-01-09 03:08) | bfsgame02.sav | 23 (Mechon attack on Colony 9) | 0:56 | 3,1,2 | 1,390,688 / v7 | `e48ee162712c9dda2d3f9fcf66e16e8da1176da4e1a8ce40e6f237b67b82da63` |
| Earlier (alternatives) | `8567d9d96fd7faf2aae89bd258e9c4c33440b833` | bfsgame02.sav | 23 | 0:55 | 3,1,2 | same | `b7c4d79d4da559f5445f2a703e88fea5c893ab06ab14d077db5ce9a05c652ef9` |
| | `207aed635e03c2d38139a68a1e6da17c776d11f8` | bfsgame02.sav | 23 | 0:55 | 3,1,2 | same | `037c7b0e63afd4a4ae597c1e1c19f392607ff260837c8cb1bd618d20a457581e` |
| | `207aed635e03c2d38139a68a1e6da17c776d11f8` | bfsgame00a.sav | 20 | 0:48 | 3,1,2 | same | `1e86fc2ea498358a8e3500392bd4665c18446ac44f2e8ac9c6893db58ac0a6c8` |
| Nearest later (**skips ahead, not usable as a base**) | `207aed635e03c2d38139a68a1e6da17c776d11f8` | bfsgame01.sav | 206 (Prison Terrace, Prison Island) | 51:06 | 7,1,4,6,2,5 | same | `eaa45afd85ade3332b26534c9e0b9cb2220cfb289807de249901ac0b39f813af` |

**Selection:** no candidate meets the requirement of being close without skipping ahead. The scenario-23 saves are
useful as *structural* v7 references and as possible templates. The scenario-206/232 saves are useful as
*late-game references* for flag statistics. All were used only as read-only copies in `public/blobs/`.

---

## 4. Wii FLAG bank structural map

The section spans 0xA020–0xB250: a 16-byte header, then a 0x1220-byte payload, big-endian. The CRC covers
0xA030–0xB244.

| Wii offset | Content | Element | Evidence | Status |
|---|---|---|---|---|
| 0xA030–0xA0B1 | All zero in both Wii saves | ? | — | Unknown |
| **0xA0B2 + 2j**, j = 0…230 | **16-bit flag bank** | u16 BE | j=0 is the scenario ID (150 / 18) [V]. The highest nonzero index is 230 (Wii) vs 231 (DE), and DE's own usage stops there too | [S] |
| ↳ j = 2…6 | Region affinity (Colony 9, Colony 6, Central Bionis, Upper Bionis, Hidden Village) | u16 | Matches the DE layout `0xDF2 + 2·regionId` (hashcade `docs/region-affinity.md`). Values fit the story: at scenario 150 only Colony 9 (2,500) and Central Bionis (2,550) are nonzero; at scenario 18 only Colony 9 (950) | [S] |
| ↳ j = 1, 7 | Wii-only values (1,850 / 3,790; 1,610 at scenario 18) | u16 | Always 0 in all 7 DE saves | Wii-specific or relocated [H] |
| ↳ j = 9…29 | Pair affinity in DE (21 pairs) | u16 | Nonzero sets agree at scenario 150 (j = 9–16), but **values at scenario 18 contradict DE at scenario 20** (Wii Shulk–Reyn 0 vs DE 910) | Unresolved |
| **0xA280** | **32-bit bank [0]** | u32 BE | **Values identical to DE 0x11F0 in all four comparisons:** 1,550 at scenarios 18/20/23 and 3,838 at scenarios 150/206/232 | [S] |
| **0xA4AE + q**, q = 1…999 | **8-bit quest-state bytes, indexed by quest ID** | u8 | Base 0xA4AE puts all 151 states of the scenario-150 save on real quest IDs; base 0xA4B0 puts 3 on non-existent IDs 0, 172 and 173 [V]. States appear only in quest tables 0101–0701 and 1401 (areas already visited); none in 1001/1101 (Eryth Sea / Alcamoth), which the later DE save does have [V] | **[V]** |
| ↳ q = 921–999 | Value-200 entries | u8 | The same index cluster with the same value in both games | [S] |
| 0xA4AE + 1000…1507 | Post-quest 8-bit flags (values 1–18): Colony 6 and resident flags | u8 | The equivalent DE cluster sits about 300 higher (DE 1,700–1,808). The exact shift does not fit a single value (297–301) | Unresolved |
| **0xACB0–0xB24F** | **1-bit flag bank**: 360 u32 words, flag n = word n>>5, bit n&31 | u32 BE | Word-endian alignment beats every other bit order 3–6× (`flag_banks.py compare`) | **[V]** |

**How the game accesses flags.** This is documented for DE only (hashcade):
- A generic setter at 0xAEB10 takes a **descriptor** `(global_index << 16) | count`.
- The values recovered decode to one global numbering: **32-bit 0x000–0x01F, 16-bit 0x020–0x21F, 8-bit
  0x220–0xA1F, 1-bit 0xA20–0x371F**.
- Examples that check out:
  - `0x02200514`: quest flags, 8-bit index 0, count 1,300
  - `0x08C40064`: Colony 6 self flags, 8-bit 0x6A4 = save 0xC94
  - `0x09280008`: Colony 6 levels, 8-bit 0x708 = save 0xCF8
  - `0x278A012C`: Colony 6 effect flags, 1-bit 0x1D6A
  - `0x00210007`: region affinity, 16-bit 1
  - `0x004000C8`: achievement counters, 16-bit 0x20 = save 0xE30
- No Wii executable was examined, so the Wii descriptors are **unknown**. This is the main gap (§7).

---

## 5. DE v10 layout and game-flag bank map

### 5.1 Flag region (identical in v7 and v10)

| DE offset | Bank | Size | Global IDs | Evidence |
|---|---|---|---|---|
| 0x0050–0x05EF | 1-bit, 360 × u32 LE | 11,520 flags | 0xA20–0x371F | hashcade `achievements.md:21,37`; descriptor algebra [S] |
| 0x05F0–0x0DEF | 8-bit | 2,048 | 0x220–0xA1F | quest q at 0x5F0+q: all 282 states in the scenario-206 save are on valid IDs at base 0x5F0; any ±1 shift breaks this [V] |
| ↳ 0x5F0 + 0…1299 | Quest states (1,300) | | | descriptor 0x02200514 [D] |
| ↳ 0xC94… | Colony 6 self flags (100) | | | [D] |
| ↳ 0xCF8–0xCFE | Colony 6 development, population, facilities, overall | | | [D]; population = 12 at a new game in v7 *and* v10 [V] |
| 0x0DF0–0x11EF | 16-bit | 512 slots, ≤ 232 used | 0x020–0x21F | story at 0xDF0; region affinity at 0xDF4–0xDFC; pairs at 0xE02–0xE2A; achievement counters at 0xE30+ [D/V] |
| 0x11F0–0x126F | 32-bit | 32 | 0x000–0x01F | [0] = 1,542–3,838 [V] |

**v10 prefix check [V].**
- Every 1-bit flag in your v10 save (scenario 6) is also set in both v7 scenario-20/23 saves (65/65).
- The 8-bit pattern at a new game is identical: quests 711–714 = 254, and population = 12 at 0x5F0+1801.

### 5.2 v7 → v10 differences (from `tools/align_v7_v10.py`, 32-byte unique-window anchors)

| v7 range | v10 offset | Evidence | Confidence |
|---|---|---|---|
| 0x000000–0x14DC50 | same (Δ 0) | anchors at 0x03CD98–0x03F030 (31) and 0x149CF0–0x14DC50 (7); flag prefix as above | [V] for the anchored ranges; [S] in between (no net insertion possible before an anchor with Δ 0) |
| 0x151B40 money | same (Δ 0) | the block-occupancy map is unshifted. **Value 103,000 in your 7-minute save is unexplained.** Please check the in-game money display | [S] offset, value unconfirmed |
| **insertion of 0x3C0 bytes** | somewhere in v7 [0x151B44, 0x152318) | all bytes there are zero in your v10 file, so the exact point is unresolvable from data | [V] bounds |
| 0x152318–0x15385F (party, 16 character records, art records) | **+0x3C0** | 24 anchors at 0x152750–0x153828; party at 0x1526D8 [V]; character template levels line up (Dunban 27, etc.) | [V] |
| — | 0x153C20–0x153F2F | 0x310 appended bytes, all zero in your file | [V] existence; content unknown |

Whether Monado's upgrade routine itself exposes mapping data:
- Monado has **no** save-conversion code. It passes the files through untouched.
- The game's own converter is in the 2.0.0 executable. Reading its schema tables (hashcade cites 0xDD660/0xDEBF0
  and 0xE02A0/0xE05A0) would give the complete v7→v10 map.
- That means reading your local `targets/exefs/main`, which this phase did not do (§10).

---

## 6. Wii-to-DE correspondence table

| Logical data | Wii | DE | Rule | Evidence | Status |
|---|---|---|---|---|---|
| Scenario / story counter | u16 BE @0xA0B2 | u16 LE @0xDF0 | copy | 150↔150 semantics, 403 identical scenario texts, both saves consistent | **Verified** |
| Region affinity (5) | u16 BE @0xA0B6 + 2(r−1) | u16 LE @0xDF4 + 2(r−1) | copy | relative position identical to the story counter on both sides; values fit the story | Strong |
| 16-bit slots j = 1, 7 | 1,850 / 3,790 | always 0 | **do not copy** | DE never uses them | Wii-only [H] |
| Pair affinity (21) | candidate j = 9…29 | 0xE02… | identity candidate | contradicted by early-game values | **Unresolved** |
| Other 16-bit counters (~50 used) | j ≤ 230 | j ≤ 231 | identity candidate | nonzero co-occurrence above chance (63 vs ~49 expected) | Weak |
| 32-bit [0] | u32 BE @0xA280 | u32 LE @0x11F0 | copy | exact values in 4 cross-game pairs | Strong |
| Quest state, quest q < 1000 | u8 @0xA4AE+q | u8 @0x5F0+q | copy | quest-ID validity on both sides; area coverage consistent with progress; same value codes (254, 200, 1–4) | **Verified (mapping)**. The meaning of each value code is not decoded |
| Post-quest 8-bit (Colony 6 levels, self flags, misc) | @0xA4AE+1000… | @0x5F0+1300… | ≈ +300 | cluster boundaries 297–301; Colony 6 field order disagrees by one | **Unresolved (±3)** |
| 1-bit flag n < 9,460 | word_be @0xACB0 | word_le @0x50 | n → n | 455 of 472 scenario-150 flags are set in the later DE saves (96 %) | **Strong** |
| 1-bit flag 9,460 ≤ n < 9,897 | — | — | boundary lies here | no Wii save sets any flag in this range | **Gap** |
| 1-bit flag 9,897 ≤ n ≤ ~10,621 | | | **n → n + 300** | 197/206 matched (96 %); +300 is the sharp optimum (shift 0 gives 0–25 %); DE has *no* flags set in the 300-flag inserted window [9,897, 10,197) in any save | **Strong** |
| 1-bit flag n ≥ ~10,622 | | | +300 or +500? | 24 flags; +300 explains 13, +500 explains all 23 in two windows (overfitting risk in dense DE regions) | **Unresolved** |
| DE-only 1-bit flags | — | 21 flags persistent from a new game: 5200, 10923–10937, 11057–11074, 11160 | keep the template's values | set in every DE save from scenario 6; no Wii counterpart under the rule | DE-exclusive candidates |

**Overall 1-bit result (`tools/flag_mapping_eval.py`)**

| Wii save → DE save | Rule | Identity | Random shift (mean / max) |
|---|---|---|---|
| scenario 150 → scenario 206 | **94.3 %** | 70.9 % | 9.1 % / 31.3 % |
| scenario 150 → scenario 232 | **94.7 %** | 71.2 % | 9.7 % / 29.6 % |
| scenario 18 → scenario 206 | **95.9 %** | 56.1 % | 9.3 % / 40.9 % |

For comparison, within one game, early-save flags are still set in later saves 99–100 % of the time. The remaining
4–6 % is expected from playthrough-specific content.

**Is there a common rule?** Yes for most of the space: identical indices, with fixed block shifts where DE enlarged
an ID range. For the quest-sized ranges the shift is +300 (1,000 Wii quest slots vs 1,300 in DE). The rule is
complete for the 1-bit bank below about 10,620, for quest states and for the story counter. Three boundaries remain
open (§7).

---

## 7. Remaining unknowns and falsified hypotheses

**Falsified [X]**

| Hypothesis | Evidence against it |
|---|---|
| A public save exists at scenario 148–152 | Nothing between 24 and 205 |
| The Wii and DE 1-bit banks are index-identical throughout | Of 63 persistent new-game DE flags, only 41 have Wii counterparts; identity explains only 71 % |
| The Wii 8-bit bank starts at 0xA4B0 | 3 invalid quest IDs; corrected to 0xA4AE |
| The Wii FLAG section is DE's four banks with identical sizes, reversed | The Wii 32-bit word sits at 0xA280, directly after ≤ 231 16-bit slots. The matching total length (0x1220) was a coincidence |
| v7 offsets apply unchanged to v10 | Wrong from about 0x152318 onward (+0x3C0); 0x310 bytes appended |
| Pair affinity maps 1:1 (Phase 1 lead) | Early-game values contradict it |

**Open, smallest first**

1. **The 1-bit +300 boundary B1** lies in (9,459, 9,897]. One descriptor constant from the Wii executable, or one
   Dolphin differential save, would pin it.
2. **The 1-bit tail (≥ 10,622):** the shift may be +500. This affects 24 of 702 flags in your save.
3. **The post-quest 8-bit shift** (297–301) and the Wii Colony 6 field order. This affects 48 bytes; Colony 6
   reconstruction has not started yet at scenario 150.
4. **The meaning of 16-bit slots** j = 1, 7 and 9–230 (pair affinity, counters).
5. **Wii 0xA030–0xA0B1** (all zero) and the rest of the 32-bit bank.
6. **The exact v10 insertion point** inside [0x151B44, 0x152318), and the appended 0x310 bytes.
7. **Per-quest state semantics:** values 254, 200, 1–5. Both games share the code set, but no code has been
   decoded.

**The decisive experiment for items 1–5** is static: read the flag-descriptor constants (`(index << 16) | count`)
from both executables. These are DE `targets/exefs/main` (already on your PC) and the Wii `main.dol` from your
SX4E disc. With those, the bank capacities and every insertion point fall out directly, with no game run needed.
Both files are your own game data, so this needs your explicit authorisation.

---

## 8. Updated conversion strategy

| | **A′ Flag-bank transplant (new, recommended)** | B. Historical DE base at scenario 150 | C. Hybrid (Phase 1 recommendation) |
|---|---|---|---|
| Base save | **Your own** DE save (scenario 6, v10), or the scenario-20/23 v7 save | Not available (§2) | A DE save you play to Eryth Sea |
| Story and quests | **Your Wii flags**, mapped by the rule: story counter, 1-bit events, quest states, region affinity | — | From the base; Wii quests added selectively |
| DE-only state | Kept from the template (21 known DE-only flags; Expert/Casual/Future Connected fields) | — | Base |
| Character and inventory | Party and levels (decoded); EXP/AP/SP, arts, skills and items need Wii reverse engineering | — | Same |
| Location | **Gap:** the DE map field is unknown. A Monado `warp` (test tour) or a load at the template's location may be needed | — | Base is already there |
| Fidelity | **Highest possible**: your quest history, not someone else's | n/a | Story from your replay; quest history partly lost |
| Main risks | Unresolved flag ranges; inconsistent quest-state codes; NPC and event state that lives outside the flag banks (unknown); location field | n/a | 22 hours of replay |
| Verdict | Go, gated on §7 items 1–3 | **Dead** | Fallback |

Strategy B could become viable only if you supply a DE save of your own near Eryth Sea, for example from a Switch.

---

## 9. Revised engineering effort

| Work package | Hours |
|---|---|
| Static descriptor extraction (DE NSO decompression and descriptor scan; Wii DOL) | 15–35 |
| Finish the flag rule, plus a dry-run transplant generator writing to the research directory only | 15–30 |
| Location: find the DE current-map field (diff two isolated Monado saves in different areas) | 5–15 |
| Wii character-block reverse engineering (EXP/AP/SP, arts, skills, skill links) | 15–35 |
| Wii ITEM reverse engineering (armour, collectables, key items, materials) and BDAT ID remaps | 15–35 |
| v10 tail and insertion mapping (descriptor tables, or one authorised v7→v10 upgrade) | 5–15 |
| In-game validation (isolated) | 15–30 |
| **MVP:** story, flags, quests, party, levels, money onto your own DE save | **55–110** |
| **Full:** adds EXP/AP/SP, arts, skills, inventory | **85–195** |

Phase 1 estimated 120–290 h for high fidelity. The flag study removed most of the riskiest work.

---

## 10. Proposed Phase 2B proof of concept (needs your authorisation; not started)

1. **2B-0 (read-only, static).** Read the flag descriptors and save schemas from DE `targets/exefs/main` and from the
   Wii `main.dol`, using copies. Resolve §7 items 1–6. Proceed to 2B-2 only if every bank boundary is pinned.
2. **2B-1 (first game run, isolated).** Run with `LARECOMP_SAVE_DIR=<research>\work\monado_saves`, no journal, no
   backups, launching `build\xcde.exe` directly.
   - (a) Load a copy of your own v10 save and re-save it. Confirm a byte-stable round trip outside volatile fields.
   - (b) Load a copy of the scenario-23 v7 archive save. Confirm the v7→v10 upgrade and diff the result to complete
     the v10 map.
3. **2B-2 (transplant dry run).** Generate `poc_v10_s150.sav` from copies only, then confirm with the evaluation
   script that every written field reads back.
4. **2B-3 (transplant load test, isolated).** Check, in order:
   - title-screen slot
   - field load
   - quest log against your Wii journal
   - affinity chart
   - party: Shulk, Dunban, Riki, Sharla, Reyn, Melia
   - one battle and a save/reload
   - progression from 150 to 160 (Alcamoth audience, Imperial Guards)
5. **Stop rules:**
   - Stop if any unresolved range is needed for a coherent load.
   - Stop if the quest log shows wrong states for more than 5 % of the quests you completed.
   - Stop if the scenario-150→160 progression softlocks.

**Tools produced in this phase** (`XC_Wii_to_DE_Research/`). All are read-only, take explicit input paths, and
write only into this folder.

| Tool | Purpose |
|---|---|
| `tools/scan_de_history.py` | Scans a git save archive and writes `tables/de_history.tsv` |
| `tools/align_v7_v10.py` | Unique-window alignment; writes `tables/align_s020_vs_user_v10.tsv` |
| `tools/flag_banks.py` | Bank extraction and bit-order/shift scoring (`dump` / `compare` / `byte8`) |
| `tools/flag_mapping_eval.py` | Rule evaluation with a random-shift baseline; writes `tables/flag_mapping_evidence.tsv`, 1,069 per-flag rows |
| `tables/candidates.tsv` | Candidate saves with SHA-256 |
| `bdat/` | Cached BDAT pages for MNU_scenario and all JNL_quest tables, both versions |
| `public/blobs/` | Extracted candidate save copies |
| `work/originals/` | Read-only snapshot copies of your saves, plus `SHA256SUMS.txt` |

---

## Decision criteria: explicit answers

1. **Did we find a usable DE save at or near scenario 150?** **No.** The nearest are scenario 23 (earlier) and 206
   (later, which skips ahead).
2. **Can it serve as a valid Monado v10 baseline?** Not applicable for 150. The archive's v7 saves would need the
   game's own upgrade, which is documented but untested here.
3. **Are Wii and DE game flags indexed compatibly?** **Mostly yes**, with fixed block shifts.
   - Verified or strong: about 96 % of the 1-bit flags set in your save, all quest-state bytes, the story counter,
     region affinity and one 32-bit value.
   - Unresolved: three boundaries and the 16-bit counter semantics.
4. **Can story progression be reproduced without someone else's quest history?** **Probably yes**, by transplanting
   your own Wii flags into your own DE save. This is plausible on the evidence but untested in game.
5. **How much of the playthrough appears transferable, by category, on current evidence?**

   | Category | Status |
   |---|---|
   | Story counter | **100 %** (1 field) |
   | 1-bit event, quest and NPC flags | **97 %** mapped (678/702), of which 67 % identity and 29 % +300; **3 %** unresolved (24) |
   | Quest-state bytes | **100 % of index mapping** (151/151), value semantics shared but undecoded |
   | Post-quest 8-bit (Colony 6, residents) | **0 % verified** (48 bytes; roughly +300 ± 3) |
   | Region affinity | 5/5 (strong) |
   | Pair affinity | 0/21 verified |
   | Other 16-bit counters | about 0 % verified (~50 used) |
   | Party composition, levels, money | decoded on both sides (100 % mechanically; game acceptance untested) |
   | EXP/AP/SP, arts, skills, armour, materials, collectables, key items | **0 %** (Wii side undecoded) |
   | Weapons and gems | partially decoded |
   | Map/location | 0 % (DE field unknown) |
   | Landmarks and fast travel | unknown (likely inside the 1-bit bank [H]) |
6. **Single most valuable next experiment:** 2B-0, static extraction of the flag-descriptor constants and save
   schemas from your own DE `main` and Wii `main.dol`. It resolves every remaining bank boundary without running a
   game or writing a save.
7. **Is high-fidelity conversion now realistically achievable?** **More likely than after Phase 1.**
   - The hardest Phase 1 unknown, flag correspondence, turned out mostly compatible and rule-based.
   - High fidelity for story, events and quests looks achievable if 2B-0 closes the three boundaries and the
     isolated load test passes.
   - Character and inventory fidelity still depend on ordinary Wii-side reverse engineering, estimated at 30–70 h.
