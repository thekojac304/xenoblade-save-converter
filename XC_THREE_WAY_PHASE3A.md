# Xenoblade Chronicles: Wii ⇄ Definitive Edition ⇄ New 3DS — Phase 3A

**Date:** 2026-11-07 (autonomous session). **Result:** release candidate `release_candidate_3A\` (XC Save Converter
3A-rc1) converts in all six directions between the Wii (Dolphin), the Definitive Edition (Monado) and Xenoblade
Chronicles 3D (Azahar). The Wii ⇄ DE engine is the unchanged 2H/2F engine: identical inputs still give
byte-identical outputs. Earlier release candidates (2E, 2F, 2G, 2H) are untouched.

Plain-language summary: `PHASE3A_SUMMARY.md`. Support matrix: `THREE_WAY_COMPATIBILITY.md`. Evidence:
`THREE_WAY_TEST_RESULTS.md`.

---

## 1. What exists on this PC

| Item | Finding |
|---|---|
| Game | `E:\Launchbox\Games\ROMs\3DS\Xenoblade Chronicles (USA).3ds`: NCSD, partition 0 NoCrypto (decrypted dump), product **KTR-P-CAFE**, title **000400000F700100**, v1.0, no update installed. Read-only; ExeFS `.code` extracted (BLZ) to `phase3a\research\rom\code.bin` for analysis (not distributed). |
| Azahar | `E:\Launchbox\Emulators\Azahar` (live user data in `%APPDATA%\Azahar`). The user's live config renders with Vulkan (`graphics_api=2`). |
| Real 3DS saves | `%APPDATA%\Azahar\sdmc\Nintendo 3DS\0…0\0…0\title\00040000\0f700100\data\00000001\`: `monado01` (**game-written, story 8, Colony 9, 0:12:09**, saved 2026-11-07 02:37), `monado02`/`monado03` empty slots; `00000001.metadata`. Copied to `phase3a\originals\azahar_live` (SHA-256 recorded). This is the user's own save and the only game-written 3DS save available. |
| Citra | `E:\Launchbox\Emulators\Citra\user\…\0f700100\data\00000001\`: three **empty** slots (identical to the Azahar empty slots). No progress. |
| Other titles | Citra's other title folders (`00033500`, `00049000`, `00055d00`, `000edf00`, `001bb200`) are other games, not Xenoblade. |

## 2. The community "Xenoblade Chronicles 3D Save Utility"

GBAtemp thread 420078 (WulfyStylez, March 2016, v1.2): the tool **compresses and decompresses** saves (`monado01–03`,
`specialmode`) and fixes checksums at compress time. Its own TODO: Wii ⇄ 3DS conversion — "offsets are identical,
needs to be mapped out for extensive endian-swapping". It was never done. The tool ships with source but **no
licence** ("you must give credit"); **none of its code is used here**. The codec in `phase3a\src\qlz.py` is a
clean-room implementation of the published QuickLZ 1.5 level-3 format; the save format was established
independently (below). The zip was not downloaded.

## 3. 3DS save format (all claims verified on the user's save, the game code or game behaviour)

Specification: `phase3a\specs\xc3d_layout.json` (structural) and `phase3a\src\xc3d.py` (`SCHEMA`, every byte typed;
coverage asserted at import).

### 3.1 Container

| Offset | Content | Evidence |
|---|---|---|
| 0x00 | `!qzb` | both files; code literal at 0x158380 |
| 0x04 | u32le 0x28000 = decompressed size | = Wii save size |
| 0x08 | u32le block size; file size = 12 + block | both files |
| 0x0C | one QuickLZ 1.5 **level-3** block, 9-byte header, flags 0x4F | `qlz.py` decompresses both files and **recompresses them byte-identically** (also the 3DS game's own later saves) |

Not encrypted, not signed: emulator saves are the plain archive files. The save *archive* (the 3DS savegame
partition) is handled by the 3DS/Azahar/Checkpoint; the game sees only these files.

### 3.2 Payload = the Wii save layout, little-endian

* Same 0x28000 size, same 12 sections at the **same offsets** (THUM, FLAG, GAME, TIME, PCPM, CAMD, ITEM, WTHR, SNDS,
  MINE, TBOX, OPTD). Section tags are u32 (`USRD` reads `DRSU`).
* File header version **0x00070003** (Wii 0x00070002). The 3DS serializer writes it (literal at 0x34F920).
* Section checksum: **CRC-16/XMODEM** (poly 0x1021, init 0) stored as **u32 at header+0xC** (Wii: u16 0 +
  CRC-16/ARC at +0xE). Found by search on three sections, then verified on all 12 sections of both files.
* Padding bytes inside structs and the space between sections are **0xE3** (heap fill) on the 3DS, 0 on the Wii.
  The padding positions confirmed the struct boundaries.
* Serializer `0x34F4F0`, GAME writer `0x34ED7C`, character loader `0x350390`, THUM writer `0x351238`: field widths
  for TIME, PCPM, CAMD, WTHR, SNDS, MINE, TBOX, the character records and THUM were read from these functions.

### 3.3 The three ways the 3DS layout differs from the Wii layout

1. **Byte order.** Every scalar is little-endian, so the width of every field has to be known: the Wii bytes
   `00 00 00 05` are `05 00 00 00` on the 3DS if they are one u32, but `00 00 05 00` if they are two u16 (0, 5).
   Widths come from the serializers, the Wii decoder's existing field map, and byte-level comparison of the 3DS save
   with Wii saves (identical default values reveal the width).
2. **C bitfields are allocated LSB-first** (ARM compiler) instead of MSB-first (PowerPC), in the same declaration
   order. Proven four ways:
   * item header word: a material in the 3DS save decodes to gid 2170, type 11, row 19, exactly the same item as in a
     native Wii save;
   * gem descriptor: code at 0x19F3CC extracts strength = bits 11–21 and rank = bits 22–24; effect = low 12 bits of
     the half-word (0x19F3DC, 0x44FA24); Dunban's weapon gem in the 3DS save decodes to the same values as in the Wii
     save (strength 100, rank 6, effect 97);
   * crystal: kind = flags byte `>> 6` (0x1982DC), source = u16 `>> 1`, cylinder = bit 0 (0x376B14/0x376B68), effect
     slots `& 0x0FFF` (0x450014);
   * header rank = bits 27–29 (crystal handler getter 0x450CBC); play time = {hours:20, minutes:6, seconds:6}
     (THUM writer 0x3512B4; the load menu showed 00:12 for the decoded 0:12:09).
3. **Enum size.** The ARM compiler stores enums in the smallest type. In the field treasure-chest records (TBOX) a
   Wii u32 becomes a 3DS u16, shifting the following u16/u8/u8 by two bytes (2 trailing zero bytes keep the 28-byte
   size). Found when the 3DS game re-saved a converted save (run a1) and rewrote the chests it had spawned in the
   shifted layout; fixed and regression-tested (`test_treasure_chest_layout_from_game_resave`).

### 3.4 THUM (load-menu summary)

u16 scenario, u8 minute, u8 second, u16 year, u16 month, u8 hour, u8 day, u16 play hours, u16 play minutes, u16 map
area, u8 0, u8 map sub, u32 party[8], 3 words, word, char[32] leader name, u16 leader level, u8 slot, … The 3DS keeps
a 116×164 thumbnail at +0x80; **the Wii stores a fixed 0x40-byte header and no picture** (identical in all six Wii
saves examined). 3DS → Wii writes that header; Wii/DE → 3DS takes the picture from the 3DS destination save.

### 3.5 Character stat blocks — a 3DS-only behaviour (important)

The 3DS game **does not recompute** a character's base stats or equipment caches when it loads a save: its loader
copies record +0x17C..+0x1F4 and the armour/weapon caches straight into the live character object. The Wii
recomputes them (2H limitation 12: a DE → Wii export keeps the base's stale caches and the Wii shows the right HP
anyway). Consequence found in run **a4**: a DE save converted to 3DS showed level-43 characters with the template's
level-2 HP and 0 defence.

Fix (`phase3a\src\xc3dstats.py`): the converter computes these blocks exactly as the game does:

* base stats: the game's level-up routine **0x2AB6B0** — for each level L′ and stat s ∈ (HP, Str, Agi, Eth):
  `s += trunc( s + 0.02·( (s_lv99 − s)·120/(120 − L′) + 25 ) ) − s` in single precision, starting from
  `BTL_pclist` at the join level. Reproduces **all 28 native records** (four saves, both platforms, levels 1–52);
* armour cache: `ITM_equiplist` dodge/phys/ether/type; weapon cache: `ITM_wpnlist` range·0.01f, speed·0.1f, damage,
  block, defences, type, element, flag; **Monados** (flag & 4): damage = int(dmg·level·1.4f / 1.5f), capped at 999
  (routine **0x277300**, run after each level-up). Reproduces every native record bit for bit;
* applied to every 3DS output; it changes nothing in a save the game itself wrote (tested), and repaired the DE → 3DS
  output (run a5: correct HP, strength, defences).

A related schema bug was found by reading 0x277300: character +0xE6 (weapon flag) is a u16, not two bytes. Fixed
before release; covered by `test_weapon_flag_is_u16`.

### 3.6 What is inferred rather than proven

Five spans have widths chosen from data, not code (listed in `xc3d.UNVERIFIED` and the spec): GAME 0xB2A8..0xB2B8
(zero or (1,1) in every sample — same bytes either way), GAME 0xD22C..0xD25C (always zero), GAME 0xF3F0..0xF410 (byte
values), character +0x1A0..+0x1B4 (always zero) and +0x1B8..+0x1F4 (floats whose values match the Wii defaults).
They are carried byte-for-byte reversibly in both directions; only their meaning on the other platform is inferred.
No game run showed a problem with them.

## 4. Gameplay identifiers

The 3DS port reuses the Wii data (story scenario numbers, flag ids, item ids/types/rows, quest ids, characters,
arts, skills, maps). Evidence: flag banks of the 3DS save are subsets of the user's later Wii saves (30/30 8-bit
flags, 46/48 1-bit flags shared); item, gem and crystal records decode to valid table rows; the 3DS game showed the
converted 22-hour Wii save's party, equipment, gems, skill trees, quest log, areas, landmarks and minimap correctly
and re-saved it with **identical canonical state** (run a1). Therefore no identifier translation is needed between
Wii and 3DS, and **3DS ↔ Wii is a lossless layout transcode**. DE identifiers are handled by the unchanged 2H engine.
Per-category table: `THREE_WAY_COMPATIBILITY.md` §3.

## 5. Implementation

```
3DS file ──qlz/xc3d.unpack──► 3DS payload ──xc3d.transcode──► Wii-layout image ──(2H engine)──► DE
3DS file ◄──xc3d.pack──────── 3DS payload ◄──xc3d.transcode── Wii-layout image + xc3dstats.rebuild ◄── DE (2H engine)
```

| Module (`phase3a\src`) | Purpose |
|---|---|
| `qlz.py` | QuickLZ level-3 codec (byte-exact recompression) |
| `xc3d.py` | container, checksums, typed schema, bitfield/enum-aware transcoder |
| `xc3dstats.py` | game-exact rebuild of base stats and equipment caches |
| `xc3dservice.py` | the four 3DS directions, conversion records (v3), lineage/divergence checks, path guards |
| `xcservice3.py` | the 2H service API extended to three platforms (used by the GUI) |
| `xcconv3.py` | CLI (all 2H commands unchanged + `wii-to-3ds`, `3ds-to-wii`, `de-to-3ds`, `3ds-to-de`, `record-info`, `unpack-3ds`) |
| `azahar_harness.py`, `arm.py`, `ctr.py` | research tools: isolated Azahar runs (RPC input/screens), ARM code analysis, read-only ROM access |

* **Wii ↔ 3DS** do not need a template except for the 3DS picture; every byte is carried. Wii → 3DS → Wii and
  3DS → Wii → 3DS are byte-exact (game-written saves only differ in the junk the Wii leaves between sections).
* **DE → 3DS** runs the 2H DE → Wii engine with the **3DS destination save as the structural base** (no Wii save
  needed), then transcodes and rebuilds the stat blocks. **3DS → DE** transcodes and runs the 2H Wii → DE engine.
  The 2H engine runs on temporary files in a private temp folder; only final files are committed.
* Outputs: one new folder, all or nothing (`safeio.commit`). 3DS: `3ds\monado0N`, plus `checkpoint\xcconv_<id>\` =
  the complete save archive (all slot files of the destination save's folder with one slot replaced) when the
  destination save sits in a complete archive folder. Every output is read back and compared before writing.
* Path guards (in addition to 2H): anything under `Nintendo 3DS`, `title\00040000\0f700100`, `3ds\Checkpoint\saves`,
  `Azahar\sdmc`, `Citra\user`, and folders holding `azahar.exe`, `citra-qt.exe`, `Checkpoint.3dsx` or `boot.firm`
  (an SD card) are refused, junctions resolved (tested).
* Records: `SIDECAR_V3_DESIGN.md`.
* GUI: the 2H window copied to `phase3a\gui` (2H GUI untouched) with a three-platform service; a **"Convert to"**
  choice appears only while step 2 is empty — a destination save decides the target by itself. 3DS → Wii needs no
  destination save. Results page gives Azahar / Checkpoint instructions.

## 6. Checkpoint (real New 3DS) — expected, not tested

Checkpoint backs up a title's whole save archive into `sdmc:/3ds/Checkpoint/saves/0x0F701 <title>/<backup name>/`
and restores a folder of that shape over the archive. The converter therefore writes `checkpoint\xcconv_<id>\` with
**every** file of the archive (`monado01–03`, `specialmode` when present), one slot replaced, so a restore keeps the
other slots. The folder name inside Checkpoint's title folder is the user's choice. The archive metadata (format
info) is not part of a Checkpoint backup. **Not written to an SD card; not tested on hardware** — physical
compatibility is pending a user test (`RELEASE_READINESS.md` checklist).

## 7. Defects found and fixed in 3A

| # | Defect | Found by | Fix |
|---|---|---|---|
| A1 | TBOX chest records shifted on the 3DS (enum size) | 3DS game re-save (a1) | `tbox` span type; regression test on the game-written file |
| A2 | 3DS uses saved stats/caches as live values; DE → 3DS showed template HP and 0 defence | Azahar a4 | `xc3dstats` (game routines 0x2AB6B0, 0x277300) |
| A3 | Character +0xE6 weapon flag transcoded as bytes (Monado level scaling flag lost) | ARM code 0x277330 | u16 span; regression test |
| A4 | Converter output not deterministic (timestamp in record, dated folder name) | determinism test | removed; folder named by session id |
| A5 | GUI history found unrelated records (search too deep; duplicate copies; wrong record type) | package test | 2H search rules, session de-duplication, "previous output platform = source platform" rule |
| A6 | GUI source line kept "→ Definitive Edition" after a 3DS destination was chosen; file-name row stretched | screenshots | refreshed on every change; fixed sizes |
| A7 | Azahar rendered black floors (OpenGL) in the first run | user report | harness forces Vulkan (as the user's own config) |

## 8. Emulator safety

Every run used a private copy of Azahar in portable mode (`phase3a\runs\azahar_bin\user`), Dolphin with its own user
dir and NAND root, Monado with its own save dir; inputs were copies. Azahar runs hashed 149 files of the live
Azahar/Citra folders before and after (all unchanged); the session manifest (`phase3a\scripts\protect3a.py`, 904
files: original saves, live emulator saves and configs, Monado and Dolphin, the 3DS ROM, the Wii disc image and all
earlier release candidates) was unchanged after every run and at the end. The 2F manifest reports Monado live-save
changes dated 2026-11-06 21:09–22:14, before this session (the user's own play); nothing in this session touched them.

## 9. Open items

* Physical New 3DS: untested (Checkpoint restore by the user).
* Story progression *after* a conversion was not played on any platform in 3A (combat, menus, travel, save/reload
  were). 2H's open item "Wii story event after a DE → Wii export" also applies to DE → 3DS.
* The thumbnail of a converted 3DS save shows the destination save's picture until the game saves again; the save
  time shown is the template's.
* Five inferred spans (§3.6). Japanese/European 3DS versions not examined (only USA v1.0 is available here).
