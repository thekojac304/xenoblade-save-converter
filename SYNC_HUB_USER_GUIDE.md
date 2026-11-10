# Xenoblade Sync Hub - user guide (3B-rc1)

Keep one Xenoblade Chronicles playthrough across Wii (Dolphin), Definitive Edition (Monado) and Xenoblade
Chronicles 3D (Azahar / New 3DS). **Syncthing moves files. The Sync Hub decides which save is newest and makes
matching saves for every game version.** It runs only while its window is open; nothing runs in the background.

Daily use: **Open -> (it scans) -> Sync All Platforms -> Close.**

## 1. One-time setup (about 10 minutes)

1. Start `XCSaveConverter.exe`. If asked, set up the game data once (the same data tables as the converter).
2. On the **Sync Hub** tab click **Set up Sync Hub...**
   * **Hub folder**: choose an empty folder on this PC (for example `D:\Xenoblade Sync`). Not a game, emulator or
     save folder.
   * **Devices**: add only the devices you use, e.g. *Windows desktop* (Definitive Edition), *GPD Win Mini* (DE),
     *Odin 2 Mini* (Wii), *Android phone* (Wii), *New Nintendo 3DS* (Xenoblade 3D). Each device has
     * an **incoming folder**: where that device's save arrives (leave empty to use one inside the hub), and
     * a **ready folder** (shown in Settings): where the hub puts that device's new save.
   * **Templates**: one valid save for each game version you use (any save of that game; it supplies the file
     structure once and, for the 3DS, the save picture). A copy is stored in the hub; your file is only read.
     You can add a game version later.
3. In **Syncthing** (yourself, once; the hub never changes Syncthing):
   * share each device's **save folder -> this PC's incoming folder** for that device;
   * share each device's **ready folder -> the device**.
   * Desktop on this PC: you can point its incoming folder straight at Monado's `save\save_0` folder (only read).
   * Android (Dolphin): Dolphin keeps saves in app-private storage that Syncthing cannot reach on Android 11 and
     later. Copy `Wii/title/00010000/53583445/data/monado01` out of Dolphin into the shared incoming folder after
     playing (USB file transfer where your device allows it), and copy the ready file back before playing.
     Dolphin's *Config > User Data* export/import works too, but its import replaces all Dolphin data.
   * New 3DS: no Syncthing. Copy the save from the SD card (Checkpoint backup) to the incoming folder, and restore
     the `Checkpoint\XenobladeSync-gen...` folder from the ready folder with Checkpoint.
4. Click **Sync All Platforms** once to start: the hub makes generation 1 from your starting save.

## 2. Every day

1. Play on any device and **save in the game**. Let Syncthing deliver the save to this PC.
2. Open the app. It scans automatically:
   * "New progress found on Odin 2 Mini." -> check device, game, story location, play time, level -> **Sync All
     Platforms**.
   * "All available saves match the last sync." -> nothing to do.
   * "Waiting for a complete save from Win Mini." -> Syncthing is still copying: **Scan Again** (F5) later.
3. "All configured platforms updated." -> close the app. Syncthing delivers each ready folder.
4. Before playing on another device, **copy the new save from its ready folder into the game** (after a backup
   the first time). Each ready folder has `HOW_TO_INSTALL.txt`.

## 3. When two devices both have progress

"Progress was found on both the Win Mini and Odin 2 Mini. Choose which playthrough to continue."
Pick one (device, game, location, play time, level are shown) and click **Sync All Platforms**. The other save is
**not merged and not lost**: it is kept in History; *History > Save a copy of a kept save...* gets it back.

A save "from an older sync" means it was played on an old copy (you played before installing the latest ready
file). The hub never picks it by itself.

## 4. When something cannot be synced

* "Not every game version can be updated ... nothing was changed": for example a temporary guest in the party,
  which the Wii/3DS conversion cannot hold. Change the party in the game and save again, or choose **Update the
  others only...** (the generation is then marked partial; the blocked game keeps its old save).
* "A save is needed once as a template": add one in **Settings > Templates**.
* An interrupted sync (closed window, crash, power cut) never becomes current. The app notes it and cleans it at
  the next Sync. **Finish publishing** appears if a ready folder was not fully updated.

## 5. History

**History** lists every generation (number, time, source device, location, play time). Select one to see what was
made and checked. **Make this generation current again...** creates a new generation from it (nothing is deleted).

## 6. Rules the hub follows

* Scanning only reads. Incoming folders are never written. Saves are never installed into games.
* Higher play time, story or level alone never decides which save wins: a save must contain the newest sync's
  progress to continue it.
* A load-and-save without playing does not start a new sync.
* Definitive-Edition-only things (Expert Mode, outfits, DE-only items) wait in the history while you play on the
  Wii/3DS and come back on the next DE save.
* Nothing is ever merged.

Command line (optional): `xcsync.exe scan "D:\Xenoblade Sync"`, `xcsync.exe sync ...`, `history`, `rollback N`,
`publish` (set `XCCONV_DATA` to your game-data folder).
