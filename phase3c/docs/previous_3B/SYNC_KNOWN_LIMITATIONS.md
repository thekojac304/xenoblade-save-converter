# Sync Hub known limitations (Phase 3B, 3B-rc1)

The 3A conversion limitations still apply to every conversion the Sync Hub makes (`KNOWN_LIMITATIONS.md`,
3A copy in `phase3b\docs\previous_3A`). Below: what is specific to the Sync Hub, and engine behaviour found in 3B.

## Not supported / not done

| # | Limitation | Consequence / workaround |
|---|---|---|
| L1 | **Nothing is installed into games.** Outputs wait in `ready\<device>\`. | You copy the file into the emulator/SD card after a backup (HOW_TO_INSTALL.txt in every ready folder). |
| L2 | **Android Dolphin storage.** Dolphin 5.0-15348+ keeps its user folder in `Android/data/org.dolphinemu.dolphinemu/files` (app-private on Android 11+). Syncthing normally cannot read or write there, and neither can the hub. | Per session: copy `Wii/title/00010000/53583445/data/monado01` out of Dolphin (USB/MTP where the device allows it, or Dolphin's Config > User Data export) into the Syncthing incoming folder, and copy the ready file back. Dolphin's User Data **import replaces all Dolphin data** - not a per-save import. Not tested on the user's phone or Odin 2 Mini (no access). An Android-side helper app would be a separate future feature. |
| L3 | **New 3DS untested.** The hub writes a complete Checkpoint-style folder; restoring it with Checkpoint on hardware was not tested (as in 3A). Files arriving on the SD card are not a restore. | Test once with a backup (RELEASE_READINESS.md, part C). |
| L4 | **3DS Checkpoint folder: other slots** come from the 3DS source's own archive folder (3DS source), else the previous generation's archive, else the template's archive (as stored at setup). A Checkpoint restore replaces all three slots. | If you use other 3DS slots for something else, restore only `monado0N` manually or keep them in Checkpoint first. |
| L5 | **Delivery is not observed.** No Syncthing API is used; the hub cannot know whether a device received a file. `.stfolder` and Syncthing temp files are recognised (read-only). | The result page says "ready", never "delivered". |
| L6 | **Offline devices.** A device whose save has not arrived is treated as having nothing new. If it later returns with independent progress, the scan reports a conflict (divergent). | Sync when the device's save has arrived, or resolve the conflict then. |
| L7 | **One playthrough per hub.** Saves of another playthrough are shown as "different playthrough" and ignored. | Use a second hub folder for a second playthrough. |
| L8 | **No automatic merge, ever.** Two devices with independent progress need an explicit choice; the other branch is kept as a snapshot, not combined. | By design. |
| L9 | **Partial sync** (explicit only) leaves blocked platforms at their previous generation; a later save from a blocked device then usually conflicts. | Prefer fixing the cause (e.g. change the party in the game) and syncing all platforms. |
| L10 | **Positions within 5 units count as the same place.** A walk of fewer than 5 world units with no other change is not synced. | Negligible; needed so that a load-and-save does not cause a sync loop. |
| L11 | **First DE save after a Wii/3DS hop**: Monado recomputes two affinity-link unlock values on load (seen in 3A m1 and 3B m1). A Monado load+save of a freshly converted save is therefore one "new progress" step once; later re-saves are not. | Harmless (one extra generation). |
| L12 | **Rollback** creates a new generation; it does not delete or rewind anything, and does not install anything. | By design (recoverable). |
| L13 | **Hub on a network/removable drive**: the commit is atomic on one volume (folder rename + file replace). Do not put the hub on a share that other PCs write at the same time; the lock trusts another PC's lock for 6 h. | Use a local folder; share device folders through Syncthing. |
| L15 | **A generation whose only change is position/time** (e.g. a short walk and save) cannot be told apart from an older copy by its progress: a save that continues the previous generation is then accepted as continuing it (only the walk is not in it). Any story, flag, level-up or item difference is detected. | Negligible (nothing but the standing position can be lost); documented. |
| L16 | **Saves with new progress on two devices are always a conflict**, even if one was copied from the other and played further. | Choose the newer one once. |
| L14 | **Not validated**: European/Japanese game versions, DE format v7 (game 1.x) saves (refused: load and save once in DE 2.0/Monado), real devices other than this PC's emulators. | |

## Engine behaviour found in 3B (3A/2H engine unchanged)

| # | Finding | Handling |
|---|---|---|
| B1 | A Wii save written by the game **after play** can hold leftover heap bytes between sections and in struct padding (9,269 bytes in a Dolphin save of the user's playthrough; none in the user's own s150 save). The 3A engine's strict read-back then **refuses Wii -> 3DS** for that save (also in the 3A manual converter). | The hub clears exactly the bytes the 3A schema marks as gap/padding (and recomputes checksums) before the 3DS transcode; each call proves only those bytes and checksum fields changed and the gameplay state is identical. The Wii output itself stays the exact source file. The manual converter tab still refuses (unchanged 3A behaviour). |
| B2 | **Unplayed** DE -> Wii/3DS -> DE return of a save with overflow/DE-only items is refused by the 2H read-back ("equipment" slot numbers differ after renumbering) in the manual converter. | The hub never runs it: an unplayed save is "in sync". |
| B3 | DE-only **per-item** fields (favourite marks and one unidentified field) are not all restored when the Wii/3DS game rewrote the items: s232 crystals 176 -> 90 entries after a 3DS play session (the 3A engine alone gives the identical result). All items, equipment, flags, Expert Mode, cosmetics and DE-only character data are restored. | Documented; byte parity with the 3A engine tested. |
| B4 | The hub's own first draft compared equipment by inventory slot number and a DE -> Wii conversion renumbers slots (overflow items set aside): false "differs" refusal. | Fixed: equipment compared by the items worn and their gems. |
| B5 | Return trips (Wii/3DS -> DE re-import) produce no `.tmb` thumbnail. | Fixed: the previous generation's/template thumbnail is published (Monado also writes its own; generation 4 of the acceptance run loaded without one). |
| B6 | Hub defect found by the emulator cycle: Monado's load-and-save without moving shifted the height by 0.001, which the first scanner counted as new progress (a sync loop). | Fixed: positions within 5 units on the same map are the same place (test on the game-written pair). |
| B7 | Hub defect found by the package test: two Wii-family saves on two devices after a walk-only generation were reduced to one proposal (the "contains" check compared a save with itself; EXP made a longer-played copy look newer). | Fixed: different devices always conflict; containment uses only story/flag/level/item facts relative to the base generation; regression test on game-written saves. |
