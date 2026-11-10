# Xenoblade Chronicles (Wii) → Definitive Edition (Monado) Save Conversion
## Phase 1 Technical Feasibility Study (read-only)

Date: 2026-11-05. Scope: research only. No game save, Monado file or Dolphin setting was changed. All binary
analysis ran on copies in a scratch directory. The SHA-256 of the originals was checked before and after the work:
`monado01` 78f67f19…5ce3, `bfsgame00.sav` 19d33489…4c99, unchanged.

Evidence labels used throughout:
- **[V] Verified.** Checked directly against the user's files, the installed binary, or source code, and cited.
- **[D] Documented.** Stated in third-party code or docs with a citation, but not re-tested here.
- **[H] Hypothesis.** Inference or partial evidence. Must be tested before anyone relies on it.

---

## 1. Executive verdict

**PARTIALLY FEASIBLE. Full-fidelity conversion is UNKNOWN; it depends on one reverse-engineering question.**

- **Character progression, money and inventory can be converted with high confidence.** This covers levels and EXP,
  money, weapons and gems, and probably arts, skills and affinity values. That requires moderate reverse engineering
  on the Wii side, and a Definitive Edition (DE) save already at the matching story point to write into.
- **Story progress can be placed correctly.** The Wii scenario ID and the DE story counter use the same numbering.
  Of the 403 Wii scenario rows, 402 have identical text in DE and the one remaining difference is cosmetic [V].
  But story progress is more than one counter. The thousands of event flags behind it live in an undecoded Wii
  section. The game can only be trusted to behave correctly if a real DE save at that same point is used as the base.
- **Quest states are the hard part.** Quest and flag identifiers are about 99.8 % identical between the Wii and DE
  data tables [V]. No tool decodes the Wii save's flag banks, though. DE made a small number of real changes, such as
  shifted enemy IDs and altered quest prerequisites [V].
  - If the Wii flag banks turn out to map onto DE's game-flag banks by index (likely, but unproven [H]), quests and
    events could be carried over almost mechanically.
  - If they do not, quests have to be rebuilt by hand or by replaying them.
- **A character-stats-only conversion is clearly achievable** and is a solid fallback.

---

## 2. Format findings: Wii, DE and Monado

### 2.1 The user's Wii save (Dolphin, unencrypted)

| Item | Finding |
|---|---|
| Path | `C:\Filen\Video Game Stuff\Game Saves & Memory Cards\Wii\title\00010000\53583445\` |
| Title | `53583445` = `SX4E` (USA). `content/title.tmd` contains `SX4E…01` [V] |
| Files | `data/monado01`, `data/monado02` and `data/monado03` (163,840 bytes = 0x28000 each); `data/banner.bin` (61,600); `content/title.tmd` (520) [V] |
| Slots | **monado01**: 22h01m play, Shulk Lv52, scenario **150**, map `ma1001` (Eryth Sea), 375,150 G, party Shulk/Dunban/Riki/Sharla/Reyn/Melia. File date 2024-11-14 [V]<br>**monado02**: empty (`DMMY`) [V]<br>**monado03**: a different, older run. Lv10, Tephra Cave (`ma0201`), scenario 18 [V] |
| Encoding | Big-endian; no compression or encryption [V]. Dolphin stores the bytes as plain files. |
| Structure | 16-byte file header `USRD 000248F0 00000010 00070002`, followed by 12 tagged sections: THUM, FLAG, GAME, TIME, PCPM, CAMD, ITEM, WTHR, SNDS, MINE, TBOX, OPTD. Data ends at 0x248F0 and is zero-padded to 0x28000 [V] |
| Integrity | Each section has a CRC-16/ARC (poly 0xA001 reflected, init 0) stored at section header +0xE. The covered range is sometimes shorter than the section. All 12 CRCs verify on monado01 and monado03 [V] |
| Version | Header words `0x0007 0x0002` are probably a version; this is unconfirmed [H] |
| Tool support | Readable by xc1-save-editor-cpp, which also rewrites CRCs, and partially by XenobladeSave. Most of the content is undecoded (§6). |
| Related evidence | Xenoblade 3D (3DS) saves are reported to be the Wii format inside an extra compression layer ([GBAtemp](https://gbatemp.net/threads/release-xenoblade-chronicles-3d-save-utility.420078/)) [D] |

### 2.2 The user's DE save (Monado)

| Item | Finding |
|---|---|
| Path | `C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save\save_0\` |
| Files | `bfsgame00.sav` (manual save) and `bfsgame00a.sav` (autosave), 1,392,432 bytes = 0x153F30 each; `bfsgame00.tmb` and `bfsgame00a.tmb` (172,800 bytes = 320×180 RGB thumbnails); `bfssystem.sav` (1,688 bytes, system/options) [V] |
| Slots | `bfsgame00/01/02.sav` are manual slots, `00a` is the autosave. The game also probes for `bfsmeria0N.sav` (Future Connected) [V, from `build/last_game.log`] |
| Content | Format **version 10** (u32 at offset 0) [V]. A **new game started on 2026-11-05**: 430 s of play, story counter 6, party Shulk and Reyn [V]. It is not a usable template for Eryth Sea. |
| Encoding | Little-endian, no compression or encryption [V/D] |
| Integrity | **No checksum.** Monado's author edited the party bytes in a save file and the game loaded it (`docs/party_switch_research.md:24-26` in the Monado repo) [D]. Neither DE editor computes one [D]. |
| Header | The game reads 48 bytes first, then the remaining 1,392,384 bytes. This is the game's own I/O pattern [V, from the log]. Fields at 0x00 (version), 0x04 (play seconds) and 0x08–0x0F (timestamp) match the v7 docs [V/D]. |
| Tool support | **No public editor accepts this file.** hanyu1774 and hashcade both require 0x153860 bytes, which is the older v7 layout (`XCDESaveData.cs:54`, `SaveDocument.cs:10`) [D]. |

**The DE layout has changed across game versions** [V/D]. The table below compares the v7 layout (older game
versions, documented by hashcade) with the v10 layout (game 2.0.0, which Monado requires).

| Field | v7 (0x153860) | v10 (0x153F30, the user's file) |
|---|---|---|
| version / play time / story u16 | 0x00 / 0x04 / 0xDF0 | Same offsets, values plausible [V] |
| item boxes (e.g. collectables 0x31970) | as documented | The autosave/manual diff touches 0x31972, 0x340A8 and 0x46928, which fits the same layout [H] |
| party ids | 0x152318 | **0x1526D8** (+0x3C0) [V] |
| position x,y,z | ? | 0x149C10 [V] |
| character records | 0x152368, stride 0x138 | Probably 0x152728 (+0x3C0): Shulk Lv1/33 EXP, Dunban template Lv27 [H] |
| money | 0x151B40 | Unknown. The v7 offset reads 103,000, which is implausible at 7 minutes of play, so it has probably moved [H] |

The game is documented to upgrade older-format saves when it rewrites them (Monado `runtime/services/fs.c:490-492`,
task T208). The hashcade docs describe an upgrade routine in the executable (`docs/achievements.md:35-40`) [D].

### 2.3 Monado's save backend

The installed copy is the portable v6.0.0 build (`version.txt`). `README.md` names the vinitaison and TheMonadoGuy
lineage. No source ships with it; the source analysed is the GitHub HEAD of Ivanprestef2/Monado-FIX-Portable
(pushed 2026-11-05). The installed `build/xcde.exe` contains the strings `LARECOMP_SAVE_DIR`,
`XCDE_SAVE_JOURNAL_OFF`, `XCDE_SAVE_BACKUPS`, `XCDE_TOUR`, `XCDE_INPUT_REPLAY`, `XCDE_FIND` and `XCDE_DUMP_MEM`. So
these features exist in the installed build [V], though their exact behaviour can still differ from HEAD [H].

- **Passthrough storage [V].** `OpenSaveDataFileSystem` mounts `<save dir>/save_<type>` as a plain host directory,
  and reads and writes are raw `pread`/`pwrite` (`fs.c:444,464,796-821`). The save-editor and flag hooks are empty
  stubs (`runtime/host/stubs.c:21-24`). The files on disk are exactly the Switch save image, so any valid Switch 2.0.0
  save works and converter output can be a plain file.
- **Isolated test environment [V].** Setting `LARECOMP_SAVE_DIR=<dir>` redirects all saves to `<dir>/save_0`
  (`fs.c:790`). The default is the relative path `save`, so it depends on the working directory.
- **Journal [V].** On the first write after a commit, `save_0` is copied to `save_0.journal`. At the next mount, if a
  journal exists, it **replaces `save_0`** (`fs.c:566-716`). Any injected file must therefore go into a folder with no
  `.journal`, or be run with `XCDE_SAVE_JOURNAL_OFF=1`.
- **Backups [V].** On the first mount of each session, `save_0` is copied to `save/backup/save_0_<timestamp>`, keeping
  the newest 5. Empty folders are skipped (`fs.c:620-656`). No `backup/` folder exists yet in the user's install.
- **Automation [D].** Several facilities can drive validation without a human. The `drive_env.sh` script assumes a
  source build tree; the rest are present in the installed binary.

  | Facility | What it does |
  |---|---|
  | Input-route replay (`XCDE_INPUT_REPLAY`) | `tests/routes/load_a.txt` loads the newest save |
  | `XCDE_TOUR` | Commands to warp, poke the `story` value, play events and start battles |
  | `XCDE_FIND`, `XCDE_DUMP_MEM` | Memory probes; the loaded save image is one contiguous block in guest memory |
  | `XCDE_FRAME_HASH`, `XCDE_SHOTS` | Per-frame hashes and screenshots |

---

## 3. Compatibility matrix

Columns: **W** = present in the Wii save; **W-enc** = Wii encoding understood; **DE-enc** = DE representation
understood; **IDs** = identifiers map reliably; **Xfer** = direct transfer feasible.

| # | Category | W | W-enc | DE-enc | IDs | Xfer | Work needed |
|---|---|---|---|---|---|---|---|
| 1 | Story / scenario | Yes | **Scenario u16 only** (FLAG+0x82 = 150) [V]. The rest of FLAG (4,628 B, 474 non-zero) is undecoded | Story u16 at 0xDF0 [D]; the 1-bit bank at 0x50 (0x5A0 B) and the 8-bit bank at 0x5F0 are located but not labelled [D] | **Scenario IDs 1–403 identical** [V]. DE adds 404–486 for Future Connected | Counter yes; flags **unknown** | Map the Wii FLAG banks to DE banks (§4.3) |
| 2 | Map, position, landmarks, fast travel | Yes | Map ID and party X/Y/Z decoded [D/V]; **landmarks undecoded** | Position at 0x149C10 (v10) [V]; **map ID and landmarks undecoded** | Area naming (`ma1001`) is the same in both data dumps [H] | Partial | Find the DE map field and the landmark bits in both. Coordinate equivalence is untested [H] |
| 3 | Quests: completed / active / available | Yes (inside FLAG) [H] | **No** | Only quest bytes linked to Colony 6 (0x5F0+qstflag) [D] | Quest IDs and the `flg_*` columns of the quest tables match about 99.8 % [V] | Unknown | Locate per-quest state in both; verify against the journal in game |
| 4 | Quest objectives and counters | Yes [H] | No | No | **Kill-target enemy IDs shift (+4) in some rows** [V] | Unknown | Build an enemy-ID remap table from the full BDAT diff |
| 5 | Party, level, EXP, AP, SP | Yes | Party and levels yes [V]; EXP/AP/SP **no** (0x304-byte blocks, mostly unmapped) | v7: level/EXP/AP/SP and coins documented [D]; v10 offsets probable [H] | Character IDs 1–7 match (Shulk=1 … Melia=7) [D/V] | Yes, once Wii EXP/AP/SP are located | Map fields in the Wii character block (differential saves) |
| 6 | Arts, art levels, skill trees, links | Yes | **No** | Documented by hashcade [D]; hanyu has a misaligned skill-link field [D] | Art IDs from the BDAT `pc_arts` tables are probably shared [H] | Likely | Wii RE of the character block |
| 7 | Equipment, gems, inventory, money | Yes | Weapons (150×52 B, bit-packed) and gems (300×16 B) partly decoded; money decoded [V/D]; armour, collectables, key items and materials **not** | All boxes documented for v7 (500 slots each) [D]; v10 money offset unknown [H] | Item IDs shared (e.g. Bomber Lancer #284; quest items 2733, 2168) [V] | Weapons, gems, money yes; others after RE | Decode the rest of the Wii ITEM section (~74 KB) |
| 8 | Character and area affinity | Yes [H] | **No**, but the u16 bank right after the scenario ID holds values typical of affinity (1240, 980, 600 …) [H] | Region u16×5 at 0xDF4 and pair u16×21 at 0xE02 [D] | Pair order **does not line up 1:1** in a first test [V, see §4.3] | Unknown | Differential tests |
| 9 | Collectopaedia | Yes [H] | No | Bitfield at 0x148D6C [D] | Item IDs are shared [V] | Likely | Wii RE |
| 10 | Colony 6 | Yes [H] (not reached yet at scenario 150) | No | Documented: 0xCF8–0xCFE and flags [D] | — | Not needed for this save | Low priority |
| 11 | Unique monsters, achievements, misc flags | Yes [H] | No | Achievements documented [D]; unique monsters undecoded | **Enemy IDs differ** [V] | Unknown | Enemy remap and RE |
| 12 | Version and DE-only fields | Header words only | — | Expert Mode, Casual, outfits, Time Attack and Future Connected exist only in DE; partly undecoded [D] | n/a | Take from the DE template | Use template defaults |

---

## 4. Story and quest progression

### 4.1 Where the user actually is (not inferred from the location alone)

The Wii slot `monado01` has scenario **150** [V]. The scenario text at that row (Wii and DE tables) is: "No one can
enter Prison Island without first obtaining the sanction of the High Entia Emperor…". The DE table assigns rows
148–152 to **Eryth Sea** and 153–159 to Alcamoth.

So the save is on the first visit to Eryth Sea, after the High Entia Tomb and **before the Alcamoth audience with the
Emperor** (scenarios 154–158). Melia is a full party member [V].

Sources: [Wii MNU_scenario](https://xenobladedata.github.io/xb1/bdat/MNU_scenario.html) ·
[DE MNU_scenario](https://xenobladedata.github.io/xb1de/bdat/MNU_scenario.html)

### 4.2 Are the two games' identifiers equivalent?

Evidence from a cell-by-cell comparison of the community BDAT dumps. The table pages were downloaded and
diffed with resolved link IDs:

- **Scenario:** 403 Wii rows against the first 403 DE rows. The texts are identical, ignoring markup [V].
- **Quests:** JNL_quest0101, 0501 and 1101 (188 quests, 14,288 cells) [V].
  - Titles, prerequisite quests, rewards and almost all flag columns (`flg_s`, `flg_relate_*`) are identical.
  - About 21 cells are real changes:
    - Some kill-target enemy IDs shift by +4 (306→310, 315→319, …).
    - Quest 19 gains a prerequisite (`flg_s` 0→36, `npcmeetID1` 0→109).
    - Two quests swap genre.
    - One quest's `flg_famous` changes from 0 to 1.
  - DE adds a `menu_text` column and the quest tables JNL_quest2501 and 2601 (Future Connected).
- **Items:** spot checks show the same IDs [V]. A full ITM diff has not been done.

**Conclusion.** DE kept the Wii identifier spaces almost entirely: scenario, quest, item and probably flag indices.
It made targeted edits, most visibly to enemy IDs. So identifiers must go through a **verified remap table**, never
an assumed identity.

### 4.3 How progression is encoded

| | Wii | DE |
|---|---|---|
| Story counter | u16 at FLAG+0x82 (0xA0B2), big-endian | u16 at 0xDF0 ("Gameflag16"), little-endian |
| Event, quest and NPC flags | Somewhere in FLAG (0xA030–0xB244). It looks like several banks: a byte-valued bank (0xFE/0x01 patterns at 0xA4B0+) and a dense bitfield (0xAF30+) [H] | 1-bit bank at 0x50 (0x5A0 B), 8-bit bank at 0x5F0, 16-bit bank around 0xDF0, achievement counters at 0xE30 [D] |

**First alignment test [V].** In both games the slots after the story counter hold affinity-like u16 values:

| Save | Values after the story counter |
|---|---|
| Wii monado01 | 150, 1850, 2500, 0, 2550, 0, 0, 3790, 0, 1240, 980, 600, 650, 60, 40, 510 … |
| DE fresh | 6, 0, 0, …, 900 (at 0xE02), 550 (at 0xE04) |
| Wii early save | 970 at +0x14 and 0 at +0x12 |

**The banks look similar but do not line up exactly.** In the Wii early save the value sits at +0x14, while DE's
fresh game has its first pair value at +0x12. The structure therefore looks analogous, but **neither index identity
nor field order is established.**

### 4.4 Specific answers

- **Can a valid DE save be placed at the equivalent checkpoint?**
  - Yes, if a DE save that was **actually played** to scenario 150 is used.
  - Not by poking the story counter. Monado's `story <n>` tour command shows the counter is writable, but the
    party-join, event and NPC flags that should go with it would be missing [H, high-confidence inference].
- **Can quest states be transferred independently of story?**
  - Only once the per-quest storage is decoded on both sides.
  - Quests that were already completed or accepted before scenario 150 are the safe subset.
  - Quests the DE base cannot have unlocked yet must never be marked.
- **Can a fresh DE save serve as the template?** **No.** The user's current DE save is at scenario 6. Story-gated
  flags (party members, Melia joining, area unlocks, cutscenes already seen) would be missing.
- **Is a set of baseline saves required?**
  - For a single conversion, one DE save at scenario 148–152 is enough.
  - For a general converter, and for the reverse-engineering itself, pairs of saves taken at the same scenario
    points in both games are needed (§9).

### 4.5 Risk assessment

| Risk | Cause | Mitigation |
|---|---|---|
| Softlock or broken cutscene | Story counter and event flags inconsistent | Never synthesise story; take it from a real DE save at scenario 150 |
| Missing or extra party members | Party table out of step with join flags | Keep the base save's party flags; only reorder the party (that edit is proven safe in Monado) |
| Wrong NPC state | Quest flags transferred into a base that is not ready for them | Transfer only quests whose prerequisites are met in the base; verify in the quest log |
| Unavailable fast travel | Landmark bits undecoded | Use the base save's landmarks, or play to unlock them. Landmarks are cosmetic for progression [H] |
| Quest kill counters wrong | Enemy ID remap missing | Build the full ENE/quest diff remap |
| DE-specific balance | DE changed EXP curves, Expert Mode and affinity UI [H] | Transfer raw level/EXP and let DE recompute derived stats; verify the stat screens |
| v10 layout surprises | Editors only know v7 | Diff-map v10 against v7; validate every write with Monado memory probes |

---

## 5. Conversion strategies

| | **A. Direct field conversion** | **B. DE template transplantation** | **C. Hybrid (recommended)** |
|---|---|---|---|
| Method | Synthesise a complete v10 save from the Wii data | Use a real DE save at scenario 150 and copy compatible Wii data into it | Same base as B. Copy decoded data, transplant flag banks only where the Wii→DE mapping is proven per bank, and close remaining gaps by controlled editing or in-game play |
| Feasibility | **Low.** About 1.39 MB of v10 layout is largely undocumented; map and landmark fields are unknown | **High** for stats and inventory; quests are not handled | **Medium–high.** Each tier can ship on its own |
| Fidelity | High in theory, unattainable in practice | Story: exact to the template's scenario. Stats and items: high. Quests and affinity: whatever the template has | Stats and items high. Quests and affinity high *if* the flag mapping holds, otherwise selective |
| Complexity | Very high | Moderate | Moderate–high, but staged |
| Dependencies | Full RE of both formats | A DE save at Eryth Sea, Wii character-block and ITEM RE, v10 offsets | Same as B, plus a Wii FLAG ↔ DE flag-bank study (Dolphin and Monado differential saves, and/or disassembly of the user's own Wii `main.dol`) |
| Validation | Extensive | Load, stat screens, inventory, battle, save and reload | Same as B, plus quest log, NPC checks and progressing through scenarios 150→160 |
| Major risks | Silent corruption; softlocks | Lost quest and affinity state | The flag-bank mapping may be non-identical; enemy ID remaps |
| Estimate | 400–900 h (±50 %) | 60–140 h | MVP (stats, items, money): **40–90 h**. Plus quests and affinity via flag mapping: **+80–200 h** (wide uncertainty; depends on the §7 unknown) |

**Recommended: Strategy C,** with a go/no-go gate after the flag-bank study. For this save it means:
1. The user produces, or already has, a DE save at scenario 148–152.
2. Character progression, money and items are transplanted.
3. Quests and affinity are added only after the bank mapping is proven.

---

## 6. Existing tools and their limitations

| Tool | Status | Useful for | Limitations |
|---|---|---|---|
| [Thealexbarney/XenobladeSave](https://github.com/Thealexbarney/XenobladeSave) | C, 2017, 6★, read-only | Thumbnail, play time, map | Reads only the first 0x11EB4 bytes; no CRC; no gameplay data |
| [enderslash1010/xc1-save-editor-cpp](https://github.com/enderslash1010/xc1-save-editor-cpp) | Qt/C++, last push 2025-05, "WIP" v0.1 | **Best Wii reference:** section table, CRC routine, scenario, map, party, levels, money, weapon and gem arrays, time, weather, options | No EXP/AP/SP, arts, skills, quests, affinity, armour or other items. **Opening a file rewrites it** (`SaveFile.cpp:82`), so it must never be pointed at the original. Constructor bug in `DataObject.cpp:43` |
| [hashcade/xbde-save-editor](https://github.com/hashcade/xbde-save-editor) | C#, last push 2026-10, MIT, round-trip tests, atomic writes | **Best DE reference:** offsets derived from native code for stats, arts, skills, links, inventory, gems, affinity, Colony 6, achievements, Collectopaedia; BDAT-derived TSV name tables | **v7 only (0x153860), so it rejects Monado/2.0.0 v10 files.** Map, landmarks, quests and unique monsters undecoded; several features still awaiting in-game verification (`docs/roadmap.md`) |
| [hanyu1774/XCDE-Save-File-Editor](https://github.com/hanyu1774/XCDE-Save-File-Editor) | C#/Photino, last push 2026-08, GPL-3.0 | Item name tables, character record layout | v7 only; misaligned skill-link field; "not fully tested" |
| [samihan-m/xcde-save-manager](https://github.com/samihan-m/xcde-save-manager) | C#, last push 2025-05 | Versioned backups of the save folder through git; reads the chapter from 0xDF0 | No editing; v7 parser |
| [3096/xde-party](https://github.com/3096/xde-party) | 2020 homebrew | Confirms DE has no checksum (it edits party bytes without rehashing) | Old layout; party only |
| [Ivanprestef2/Monado-FIX-Portable](https://github.com/Ivanprestef2/Monado-FIX-Portable) | Active (pushed 2026-11-05) | Passthrough saves, `LARECOMP_SAVE_DIR`, journal and backups, tours and replay, memory probes, v10 party and position offsets | Not a save tool; dev scripts assume a source build |
| [xenobladedata.github.io](https://xenobladedata.github.io/) | Updated 2026-10 | Wii (`xb1/`) and DE (`xb1de/`) BDAT dumps, the basis for every ID remap table | Community dump; verify against the user's own game data where it matters |

No public Wii→DE converter or conversion attempt was found. A GBAtemp thread
([Convert old Xenoblade 1 save to Switch?](https://gbatemp.net/threads/convert-old-xenoblade-1-save-to-switch.643072/))
asks for one, with no tool resulting [D].

**Net effect:** the existing tools save roughly 30–40 % of the work. They give the Wii container and CRCs, a large set
of DE v7 offsets, and the name tables. They do **not** cover the hardest parts: Wii flags, quests, the v10 layout, and
the Wii→DE flag correspondence.

---

## 7. Key technical blockers

1. **Biggest unknown: does the Wii FLAG section correspond to DE's game-flag banks?** Specifically, whether each Wii
   bank (bit widths 1/2/4/8/16/32) maps to a DE bank with the same flag indices, differing only by endianness and
   ordering.
   - **Evidence for:** the BDAT flag references are about 99.8 % identical, and the scenario numbering is identical.
   - **Evidence against:** the first u16 alignment test is offset, and DE added fields.
   - **What it decides:** whether quests, events, affinity and Collectopaedia transfer mechanically or must be
     rebuilt.
2. **The v10 (2.0.0) DE layout is undocumented.** All mature offsets are for v7, and at least one block shifts by
   +0x3C0. The total growth is +0x6D0, in at least two places.
3. **No DE base save at Eryth Sea yet.** The user's current DE save is 7 minutes into a new game.
4. **Wii-side gaps.** The character block (0x304 B: EXP/AP/SP, arts, skills) and most of ITEM (armour, collectables,
   key items, materials) are undecoded.
5. **Enemy ID shifts and DE-only quest edits** require a complete, verified BDAT remap.
6. **DE map ID and landmark storage** are undecoded, so the converter cannot relocate the party itself. The base save
   must already be in Eryth Sea.

---

## 8. Estimated engineering effort

| Work package | Hours (low–high) | Notes |
|---|---|---|
| Wii container parser and round-trip test (CRC) | 4–8 | Logic from xc1-save-editor-cpp |
| v10 layout mapping (diff a v7 save against its upgraded v10 form, or probe memory) | 15–40 | Needs a v7 sample, or Monado probes |
| Wii character block RE (EXP/AP/SP, arts, skills) | 15–35 | Differential Dolphin saves |
| Wii ITEM RE (armour, collectables, key items, materials) | 10–25 | |
| BDAT remap tables (items, enemies, arts, skills) and verification | 8–20 | Scripted from the BDAT dumps |
| Transplant MVP (stats, items, money) and validation | 15–30 | |
| **Subtotal: MVP fallback** | **~40–90** (realistically ~65) | |
| Flag-bank correspondence study (gate) | 25–60 | Determines everything below |
| Quest-state transfer and enemy remap | 25–70 | |
| Affinity, Collectopaedia, unique monsters, landmarks | 20–60 | |
| Full in-game validation playthrough (scenarios 150→160 and beyond) | 10–20 | |
| **Total: high-fidelity Strategy C** | **~120–290** | ±50 %; the flag study can roughly halve or double the rest |

---

## 9. Safe proof-of-concept roadmap (Investigation E)

**Ground rules**
- Originals are never opened for writing.
- Every artefact lives in `XC_Wii_to_DE_Research\work\` with a SHA-256 manifest.
- The live `save\save_0` is never touched.

1. **Snapshot.** Copy `monado01` and `save_0\*` into `work\originals\`, mark them read-only, and record their hashes.
   Re-check the originals' hashes at every step.
2. **Isolated Monado runs.**
   - Create `work\monado_saves\save_0\` and run with `LARECOMP_SAVE_DIR=<that dir>`.
   - Also set `XCDE_SAVE_JOURNAL_OFF=1` and `XCDE_SAVE_BACKUPS=0`, or leave the journal on, but always start from a
     folder that has no `.journal`.
   - Confirm from `build/last_game.log` (`[fs] mounted host directory …`) that the redirect took effect before any
     save happens.
   - Unverified: whether the launcher passes the environment through. Launching `build\xcde.exe` directly from a
     script that sets `cd` and the env vars avoids the question.
3. **Parser round-trip.**
   - Wii: parse, re-serialise, and require a byte-identical result and matching CRCs.
   - DE: parse a v10 file, re-serialise, and require a byte-identical result.
4. **Differential mapping (gate).**
   - In Dolphin, using a *copy* of the save in a separate Dolphin user folder (`-u`), and in Monado (isolated), take
     paired saves around single, controlled actions: accept a quest, finish a quest, gain affinity, pick up one
     collectable, level up once.
   - Diff each save pair within its own game, then compare the changed indices across games.
   - **Pass:** at least 90 % of observed flag changes map to the same index (after endian and bank adjustment) on
     ≥ 3 independent actions.
5. **MVP conversion.**
   - Input: a DE base save at scenario 148–152, made by the user.
   - Transplant levels/EXP/AP/SP, arts, skills, equipment, gems, items and money into a *copy*.
   - Verify with `XCDE_DUMP_MEM`/`XCDE_FIND` that the loaded save block contains the written values.
6. **In-game validation.** Load the converted copy and check, in order:
   - title screen and slot preview
   - field load
   - status, equipment, arts, skills and inventory screens
   - one battle
   - fast travel to two landmarks
   - save to a new slot, reload, and confirm the bytes are stable
   - play scenario 150→160 (Alcamoth audience, Imperial Guards) to check cutscenes and the party
7. **Quest tier.** Only if the gate passed. Transfer quest states, then check the quest log against the Wii journal
   and talk to 5 affected NPCs.

**A successful proof of concept** is a converted copy that:
- loads at Eryth Sea with the Wii party, levels, gear, inventory and money;
- survives a battle and a save/reload cycle;
- plays through to scenario 160 without a softlock.

**Stop the project, or settle for the MVP, if any of these happens:**
- The flag-bank study shows no consistent index correspondence. Then stop at the MVP.
- The 2.0.0 game rejects or wipes any externally modified v10 file. This is unlikely, given the evidence of no
  checksum.
- Edits to the v10 file cannot be confirmed in memory.
- The user cannot provide a DE base at Eryth Sea, and replaying to it is unacceptable. Then only a stats-only
  conversion onto an earlier base is possible, with a story mismatch.

---

## 10. Information and files needed from the user

1. **Which Wii slot is the Eryth Sea playthrough?** This study assumes **monado01** (22h01m, Lv52, scenario 150, 2024-11-14).
   monado03 is a separate 2.4 h run at Tephra Cave.
2. **Is `C:\Filen\…\Wii` Dolphin's live NAND, or a copy?** Please give the Dolphin user-folder path, so that test
   runs can use a separate `-u` folder.
3. **A DE base save near Eryth Sea.**
   - Do you already have one of your own (from a Switch or another emulator)? An older-version (v7, 1,390,688 byte)
     save of your own would also help with the v10 mapping.
   - If not, are you willing to play DE in Monado, isolated, to scenario 148–152?
4. **Your current DE save in `save_0`.** Is it disposable? It is a 7-minute new game from 2026-11-05. It will not be
   touched either way, but its status determines how Phase 2 test runs are organised.
5. **The path to your own Wii disc image (SX4E01).** This is only for local differential testing in Dolphin and
   optional disassembly of `main.dol`. Nothing will be downloaded.
6. **Your fidelity floor.** Is the MVP (stats, items, money on a real DE Eryth Sea save) acceptable if the quest/flag
   gate fails?
7. **Explicit authorisation for Phase 2.**

---

### Appendix: reproducible evidence

- `inspect_saves.py` (in this folder) is a read-only inspector. It verifies the Wii CRCs and prints the scenario,
  map, levels, money and party, plus the DE version, story counter, party and position. Run it only on copies.
- The BDAT comparisons used the HTML tables at `xenobladedata.github.io/{xb1,xb1de}/bdat/…` (MNU_scenario,
  JNL_quest0101/0501/1101).
- Third-party sources were downloaded only as source archives and read, never built or run. Exact code citations are
  given inline (`file:line`, relative to each repository root).
