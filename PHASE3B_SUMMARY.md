# Phase 3B in plain words

**What's new:** the converter now has a **Sync Hub** tab. You open the app; it looks at the save folders your devices
send to this PC (through Syncthing), tells you which device has the newest progress, and one button —
**Sync All Platforms** — makes matching Wii, Definitive Edition and 3DS saves from it. Then you close it.
Nothing runs in the background. New release: `release_candidate_3B\XCSaveConverter\XCSaveConverter.exe`
(3B-rc1). The old three-step converter is still there (second tab, unchanged). Earlier releases are untouched.

## How it decides

* It only **reads** your device folders; it never writes into them or into any game.
* A save is "new progress" only if it really continues the last sync. **Higher play time or level alone never
  wins.** A device that kept playing an old copy is caught, even when it has more play time.
* Loading and saving without playing (or a file the hub made coming back) is **not** new progress, so there are no
  endless syncs.
* If two devices both have progress, it **asks you** which one to continue. The other save is kept in History and
  can be copied back out. Nothing is ever merged.
* Every sync is a numbered **generation**, checked in full before it becomes current. A crash or power cut cannot
  leave a half-finished one in charge. You can go back to any earlier generation.

## What was tested

* A full trip with your own 22-hour Wii save and the real games (all in isolated test copies):
  Wii save → Sync → **Monado** loaded it, walked, saved → Sync → **3DS (Azahar)** loaded it, **won a battle**, saved
  → Sync (the battle's EXP arrived in the DE save, Monado's own changes were kept) → **Dolphin** loaded it, saved →
  Sync → Monado and Azahar both loaded the result. Monado re-saving without playing did not start another sync
  (after a fix — see below).
* 65 automated Sync Hub tests (including simulated crashes at 8 points and killed processes), 18 window tests, all
  earlier converter tests, and the packaged program in a clean folder without Python.
* None of your saves, emulator folders, Syncthing settings or earlier releases changed.

## Problems found and fixed on the way

* Monado's load-and-save nudges your character's position by a hair; the first version took that as new progress.
  Fixed.
* A Wii save written by the game after playing can contain leftover junk bytes between its sections; the 3A
  converter then refuses to make a 3DS save from it. The Sync Hub now cleans just those unused bytes (proven
  harmless every time). The manual converter tab still has the old 3A behaviour.
* Two devices with progress could be reduced to one suggestion. Fixed: that is always your choice now.

## What you still do by hand

* **Share the folders in Syncthing yourself** (the guide says which). The hub doesn't touch Syncthing.
* **Copy the new save into each game** from its ready folder (each has HOW_TO_INSTALL.txt).
* **Android (phone, Odin 2 Mini):** Dolphin keeps saves where Syncthing can't reach them on modern Android, so the
  save file has to be copied in and out by hand (USB or Dolphin's export/import).
* **New 3DS:** restore the Checkpoint folder from its ready folder with Checkpoint. Not tested on the real console.

Start with `SYNC_HUB_USER_GUIDE.md`. Details: `XC_SYNC_HUB_PHASE3B.md`, `SYNC_TEST_RESULTS.md`,
`SYNC_HISTORY_DESIGN.md`, `SYNC_KNOWN_LIMITATIONS.md`, `RELEASE_READINESS.md`.
