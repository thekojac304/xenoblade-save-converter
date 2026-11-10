# xcconv: Xenoblade Chronicles save converter (Wii ⇄ Definitive Edition), release candidate 2G-rc1

> **2G: there is now a desktop application.** `XCSaveConverter.exe` (portable folder, no Python needed) does
> everything below through a guided window; see `GUI_USER_GUIDE.md`. The same folder contains `xcconv.exe`, this
> command-line converter, so the commands below also work as `xcconv.exe …` without Python. Both use one shared
> service layer (`tools/xcservice.py`); for identical inputs they write byte-identical files. The conversion engine
> and the command-line options are unchanged from 2F-rc1; only the version string in sidecars and manifests changed.

`xcconv` moves one playthrough between:

- **Xenoblade Chronicles (Wii)**: `monado01` / `monado02` / `monado03` in Dolphin's NAND,
  `title/00010000/53583445/data/`;
- **Xenoblade Chronicles: Definitive Edition**, save format **v10**: `bfsgame00.sav` etc. in Monado's `save\save_0`.

It never writes into a game or emulator folder. Every run creates **one new output folder** that appears complete or
not at all. You copy the result into a game yourself, after making a backup.

> 2F changes that affect you: re-imports now **require your current save of the other game** (or an explicit
> `--no-current-…`), the output folder must be **new**, format-v7 DE saves must be re-saved once in DE 2.0/Monado,
> and Fiora's second form / guest party members are refused. See "What changed in 2F" at the end.

## What you need

- `xcconv.exe` from the 2G portable folder, or Python 3.11 or newer (no extra packages for the converter;
  the GUI from source needs PySide6).
- Your own game tables `bdat_wii.json` and `bdat_de.json`, made from your own copies of the games with
  `tools/dump_bdat.py`. They are game data, so they are **not** part of the converter package. Point to them with
  `set XCCONV_DATA=<folder>`, or keep them in `user_data\data` next to the `converter` folder.
- A **template** for the first Wii → DE export: any DE v10 save of yours, ideally an early one. Its option settings
  and Expert Mode switch are kept. Its playthrough-specific resources (reserve EXP, fashion slots, Noponstones, link
  unlocks) are **not** carried over (2F).
- A **Wii base** for the first DE → Wii export of a playthrough that started in DE: any valid Wii save of yours,
  ideally from about the same chapter.

## Commands

Run from the `converter` folder (or use `xcconv.cmd`). `python tools\xcconv.py --help` lists everything.

```
python tools\xcconv.py inspect <save>
python tools\xcconv.py validate <save>
python tools\xcconv.py compatibility-check --de <bfsgame00.sav> [--base <monado01>]
python tools\xcconv.py sidecar-info <file.sidecar.json>
python tools\xcconv.py roundtrip-check --wii <monado01> --template <bfsgame00.sav>
python tools\xcconv.py roundtrip-check --de <bfsgame00.sav> --base <monado01>
python tools\xcconv.py cleanup-staging <folder>
```

Common options: `--dry-run` (convert and verify, write nothing at all), `--report <file.json>` (full report; not
written in a dry run), `--json` (print the full report), `--debug` (traceback on an internal error).

Exit codes: `0` done · `1` a check failed (validate, roundtrip-check, compatibility-check) · `2` refused, nothing
written · `3` internal error, nothing written.

### 1. Wii → DE (first time)

```
python tools\xcconv.py wii-to-de --wii <monado01> --template <your DE bfsgame00.sav> --out <NEW folder> --slot 01
```

Creates `<out>\save_0\bfsgame01.sav` (+ `.tmb` and `bfssystem.sav` copied from the template folder for isolated
testing), `<out>\wii_to_de.sidecar.json` and `<out>\manifest.json`. **Keep the sidecar.**

### 2. DE → Wii (going back to the Wii)

The playthrough came from the Wii (use the sidecar of the last Wii → DE step):

```
python tools\xcconv.py de-to-wii --de <current DE save> --sidecar <wii_to_de.sidecar.json> --current-wii <your current monado01> --out <NEW folder>
```

`--current-wii` is only read. It lets the converter detect Wii play after the export (divergence) and old sidecars.
If you are sure there is no Wii save newer than that export, use `--no-current-wii` instead.

A playthrough that started in DE:

```
python tools\xcconv.py de-to-wii --de <bfsgame00.sav> --base <any valid monado01> --out <NEW folder>
```

Creates `<out>\monado01` (+ `banner.bin` when the base folder has one), `de_to_wii.sidecar.json`, `manifest.json`.

- If your DE inventory is larger than this Wii save can hold, the command stops. Add `--overflow sidecar` to keep
  the extra unequipped items in the sidecar; they come back when you return to DE.
- DE-only data (Expert Mode, fashion, DE-only items, Future Connected, Time Attack, Noponstones) stays in the sidecar
  and comes back on re-import.

### 3. Wii → DE (returning to DE after playing on the Wii)

```
python tools\xcconv.py wii-to-de --wii <updated monado01> --sidecar <de_to_wii.sidecar.json> --current-de <your current DE save> --out <NEW folder>
```

- Your Wii progress is applied to the DE save you exported from. DE-only data comes back as it was.
- If the Wii save is unchanged, you get your DE save back byte for byte.
- If **both** games were played after the export, the command stops. It never merges two branches.
  - `--branch wii` keeps the Wii progress and **discards** the DE progress made after the export.
  - The converter refuses even with `--branch` when the sidecar looks **older** than your latest export (the Wii
    save already contains your newer DE progress). Use the sidecar of your most recent DE → Wii export.
- `--no-current-de` (instead of `--current-de`) states that no DE save is newer than the export. Use it only if
  that is true: with an old sidecar it can bring back items you sold in DE.

**Always use the sidecar from your most recent conversion.** `sidecar-info` shows its generation and parent.

## Safety rules built in

- Writes are refused under game/emulator installations (folders with `xcde.exe`, `xcde.ini`, `Dolphin.exe`,
  `portable.txt`, `Play Monado.bat`), Dolphin `User\Wii`, any `title\00010000` NAND folder, and your Filen / Proton
  Drive Wii save folders. Junctions, symbolic links, `..` and upper/lower-case variations are resolved first.
- The output folder must not exist (or be empty). Everything is written and re-read in a hidden
  `.xcconv-staging-*` folder, then renamed into place in one step. A crash can only leave such a staging folder;
  `cleanup-staging <folder>` removes it.
- Inputs are checked first: size, header, version, every section header and checksum. Damaged or edited files are
  refused, never repaired.
- Every output is re-read by an independent decoder and compared field by field before anything is written.
- `manifest.json` holds the SHA-256 of every input and output.

## Installing a converted save (manual, after backups)

- **Monado:** copy `save_0\bfsgame01.sav` (and optionally `bfsgame01.tmb`) into
  `...\XenobladeChroniclesDefinitiveEdition-Monado\save\save_0\`. Use a slot number you are not using, and back up
  the folder first. Do not copy `bfssystem.sav` (it is the template's system file, included only for isolated tests).
- **Dolphin:** copy `monado01` into `<NAND root>\title\00010000\53583445\data\`, replacing a slot you have backed
  up. `banner.bin` must already be there (it is if you have played the game). Your NAND root is set in Dolphin under
  Config → Paths.

`RELEASE_READINESS.md` has a step-by-step manual acceptance checklist for your Eryth Sea save.

## What converts

Story and every story/quest/event flag, quest objective counters, Heart-to-Heart flags, characters (level, EXP, AP,
Affinity Coins, arts, skill trees, SP, linked skills and unlocked link slots, palettes), party, equipment and gems,
all inventory boxes including crystals and cylinders (with acquisition order), money, play time, map, position, time
of day and day, Collectopaedia, landmarks, Colony 6, affinity, award counters and minimap exploration.

See `KNOWN_LIMITATIONS.md` for what is approximate, untested or refused.

## What changed in 2F (from 2E-rc1)

- Re-import / export with a sidecar needs `--current-de` / `--current-wii` (or `--no-current-…`).
- New output folder per run; all-or-nothing output; stronger path guards; `cleanup-staging`.
- Item acquisition order is now correct in both games. 2E-rc1 reversed DE's "newest" order and would have refused
  a re-import after any item pick-up on the Wii.
- DE skill progress of Fiora (before she leaves the party) is no longer reverted by the Wii game on load.
- Unlocked skill-link slots move in both directions; a first export no longer inherits the template's reserve EXP,
  fashion, Noponstones or link unlocks.
- Late-game DE saves with DE-crafted crystal cylinders can be exported (2E-rc1 refused them).
- More inputs are refused instead of guessed: format v7, Fiora's second form / guests in the party, impossible
  values, damaged containers, inconsistent sidecars, DE maps the Wii does not have.
