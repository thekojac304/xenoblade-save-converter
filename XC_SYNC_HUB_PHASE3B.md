# Xenoblade Chronicles Sync Hub — Phase 3B

**Date:** 2026-11-08 (autonomous session). **Result:** release candidate `release_candidate_3B\` (XC Save Converter
3B-rc1) adds an on-demand **Sync Hub** to the three-platform converter: open the app, it scans the device folders
that Syncthing fills, shows the newest progress, and **Sync All Platforms** makes a validated Wii, Definitive
Edition and 3DS save from it in one transaction. No background process. The 3A conversion engine is unchanged
(byte parity tested); the 3A three-step converter is the second tab. `release_candidate_3A\` is unchanged (312/312
checksums verified at the start and at the end).

Plain-language summary: `PHASE3B_SUMMARY.md`. Setup and daily use: `SYNC_HUB_USER_GUIDE.md`. History/ancestry/
recovery design: `SYNC_HISTORY_DESIGN.md`. Evidence: `SYNC_TEST_RESULTS.md`. Limits: `SYNC_KNOWN_LIMITATIONS.md`.
Readiness: `RELEASE_READINESS.md`.

## 1. What was found on this PC

| Item | Finding |
|---|---|
| Syncthing | Installed (SyncTrayzor). Config read once, read-only: three send-only folders (`E:\VR Chat`, `E:\Launchbox`, `C:\Users\lawma\Documents`) to two devices (HuskyBox, HuskyServer). **No Xenoblade save folder is shared yet**, and no Android/handheld/3DS device is configured. Nothing was changed; `config.xml` is in the protected manifest (unchanged). Note: `Documents` and `E:\Launchbox` (Dolphin, Azahar, ROMs) are already backed up by Syncthing. |
| Monado | Updated by the user on 2026-11-07 (v9.0.0; exe and ini hashes changed after 3A, not by this session). All harness switches (`LARECOMP_SAVE_DIR`, `XCDE_INPUT_REPLAY`, `XCDE_SHOTS`, ...) still present. The live `save_0` holds `bfsgame00.sav` and an autosave `bfsgame00a.sav` (the scanner accepts `bfsgameNNa.sav`). |
| Android Dolphin | Not accessible from here. Public documentation: Dolphin 5.0-15348+ keeps its user folder in `Android/data/org.dolphinemu.dolphinemu/files` (app-private on Android 11+); Config > User Data export/import zips the whole user folder and import replaces it. So Syncthing cannot share Dolphin's save folder directly on the user's phone or Odin 2 Mini; see SYNC_KNOWN_LIMITATIONS L2. |

## 2. Architecture

```
 devices --Syncthing--> incoming\<device> (read only) --scan--> decision --Sync All--> staging --> history\gen-N
                                                                                         |  (one rename + one
 devices <--Syncthing-- ready\<device> <------ publish (per file, READY.json last) -------+   pointer replace)
```

* `phase3b\src\xcsync\store.py` — hub folder, device profiles (stable ids), verified templates, atomic file
  writes, the commit pointer, the lock.
* `scan.py` — read-only startup scan: Syncthing temp files (`~syncthing~*.tmp`, `.syncthing.*.tmp`), conflict copies
  (`*.sync-conflict-*`), `.stversions` ignored, size/mtime/hash stability over two reads, a 5 s settle time,
  content-based platform detection and full engine validation, canonical state, ancestry classification
  (in-sync / older / new-progress / divergent / unrelated / unknown / start) and the decision.
* `sync.py` — the transaction (anchors, engine calls, validation, commit), publication, rollback, recovery.
* `cli.py` — `xcsync.exe`. GUI: `phase3b\gui\xcgui\synchub_view.py`, `shell.py` (tabs), `app.py`
  (`--sync-automate`).

### Conversions: two families and anchors

Wii and 3DS hold the same state (3A: lossless transcode) — the **W family**; the Definitive Edition holds more — the
**D family**. Within a family nothing is converted beyond the 3A transcode. Between families the unchanged 2H engine
runs, always as one of its validated return trips, onto the **anchor** = the last save of the other family that was
actually played, with the sidecar the hub made from it (details: SYNC_HISTORY_DESIGN §3). Example from the
acceptance cycle: generations 3 (3DS) and 4 (Wii) both re-import onto generation 2's DE save (Monado), so
Monado-side changes survive two non-DE generations.

Each output is produced by the 3A engine functions themselves (`xcservice.wii_to_de`, `de_to_wii_convert`,
`xc3dservice.convert3`), into the transaction's staging folder. Byte parity with the 3A engine for identical inputs
is tested (Wii -> DE, Wii -> 3DS, DE -> Wii, DE -> 3DS, 3DS -> DE return).

### Validation of every generation (independent of the engine's own checks)

Every output is re-read from disk and loaded with the engine's validators (structure, checksums, references);
W outputs must hold exactly the source's canonical state (the Wii file *is* the source for a Wii source); Wii vs
3DS must be identical; DE vs W: every non-inventory field equal (equipment compared by the items worn and their
gems), inventory multiset difference equal to the DE-only/overflow items the engine kept for DE — nothing lost or
duplicated (e.g. DE s232 -> Wii/3DS: exactly the 269 items the engine set aside).

## 3. Implementation highlights and design decisions

* **Strictly read-only scan** (tested by hashing the hub and every incoming folder before/after; the packaged
  window scan too).
* **"Continues" needs more than descent.** The 2H `sidecar.descent` alone accepted a Dolphin save that was played on
  an *old* copy for longer (W150_LATER: flags/items kept 100 %, +114 s) as continuing a newer 3DS generation. The
  scanner also requires the generation's own new facts (story, flag values, level-ups, items) to be present. EXP,
  money and play time are never evidence (they grow on every branch).
* **No sync loops.** The progress key ignores save time, thumbnail, play-time seconds, clock and position within
  5 units: Monado's load-and-save (height +0.001), the 3DS game's re-saves (3A runs a1, a5) and generated files
  coming back are all "in sync".
* **Conflicts**: two devices with progress since the same sync, or any save that continues an older/abandoned
  generation, require an explicit choice; all candidates are snapshotted into the new generation; nothing merges.
* **Transaction**: immutable generation folders + one atomic pointer; lock; revalidation of the source bytes and of
  the history between scan and sync; cancel before commit; all-or-nothing by default, explicit partial generations
  labelled as such.
* **Publication** per device with READY.json last; Finish publishing repeats an interrupted one; never claims
  delivery.
* **Rollback** is a new generation (append-only history).

## 4. Defects found and fixed in 3B

| # | Defect | Found by | Fix |
|---|---|---|---|
| B1 | 3A engine refuses Wii -> 3DS for a game-written Wii save with heap junk between sections (9,269 bytes) | sync test with a Dolphin save | hub clears only schema gap/pad bytes + checksums before the transcode, proven harmless per call (engine unchanged) |
| B2 | 3A/2H refuse an unplayed DE -> Wii/3DS -> DE return with overflow items (read-back by slot number) | parity test | hub never runs it (unplayed = in sync); documented for the manual converter |
| B3 | DE-only per-item fields partly lost after the Wii/3DS game rewrote items (176 -> 90 crystal entries) | alternating-platform test | engine behaviour, identical in 3A; documented |
| B4 | hub audit compared equipment by slot number | DE-source test | compare by item identity |
| B5 | no `.tmb` after a DE return trip | acceptance (gen 4) | previous/template thumbnail published |
| B6 | Monado re-save without moving counted as progress (sync loop) | acceptance step s5 | 5-unit place tolerance |
| B7 | two-device progress reduced to one proposal | package test | different devices always conflict; containment relative to the base, no EXP evidence |
| B8 | conflict message said "both" for three devices; long texts in the device table; raw ISO times | screenshots | wording and layout fixes |

## 5. Tests (details and numbers: SYNC_TEST_RESULTS.md)

* `phase3b\tests\test_synchub.py` (unittest): scanning, ancestry, conflicts, sync from each platform, multi-hop
  DE-only preservation with 3A parity, items/EXP/quests, overflow, unsupported party, partial, templates, lock,
  cancel, failure injection at 8 points, **process kill at 8 points** (subprocess `os._exit`), interrupted
  publication, rollback, snapshots, setup, and a replay of the emulator cycle from the game-written saves.
* `phase3b\tests_gui\test_phase3b_gui.py` (pytest-qt): setup, automatic startup scan, Scan Again (F5), new
  progress, waiting, conflict choice, Sync (Ctrl+Enter), duplicate submissions, cancel, blocked -> partial,
  history + rollback, Finish publishing, damaged history, offline device, light/dark, converter tab.
* Regression: 2H unittest (136), 3A unittest (41), 3A/2H GUI tests run against the 3B GUI, package tests (3B and the
  unchanged 3A one) on the packaged build in a clean folder without Python.
* **Emulator acceptance**: a full cycle with real in-game saves — user's Wii save -> generation 1 -> Monado (walk,
  save) -> generation 2 -> Azahar (battle won, save) -> generation 3 -> Dolphin (walk, save) -> generation 4 ->
  Monado and Azahar load generation 4 -> Monado re-save is not progress. Every Sync Hub step through the real window.

## 6. Safety

* Protected manifest (1,226 files: Wii originals in Filen and Proton Drive, Dolphin/Monado/Azahar/Citra live saves
  and configs, emulator executables, the Wii disc image and 3DS ROM, every earlier release candidate including 3A,
  Syncthing `config.xml`) recorded at the start and checked after every emulator run and at the end: unchanged.
* Nothing was written outside the research folder; Syncthing configuration and shares were not touched; no save was
  installed into a live emulator folder; Monado wrote only its own cache/log files inside its installation during
  the isolated runs (listed per run in `run_manifest.json`, as in 2F/3A).

## 7. Open items

* Real devices: New 3DS Checkpoint restore, Android Dolphin (phone, Odin 2 Mini), GPD Win Mini — untested here.
* Android: a device-side helper (or a Dolphin build with a shared user folder) would be needed for automatic file
  flow; out of scope.
* Story progression after a conversion was not played (as in 3A); battles, travel, menus, saving and reloading were.
