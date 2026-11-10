# XC Save Converter: user guide (3A-rc1)

Moves one Xenoblade Chronicles playthrough between three games:

- **Wii** (Wii or Dolphin; saves `monado01`–`03`),
- **Definitive Edition** (DE 2.0 / Monado; saves `bfsgame00.sav`, `bfsgame01.sav` …),
- **New 3DS** — *Xenoblade Chronicles 3D* (Azahar, or a real New 3DS with Checkpoint; saves `monado01`–`03`).

Windows 10/11, 64-bit. No installation, no Python.

> Tested in Dolphin, Monado and Azahar. **Not yet tested on a real New 3DS.** Some game states are refused on purpose
> (see the end of this guide). Keep backups.

## Start

Keep the `XCSaveConverter` folder together and double-click **`XCSaveConverter.exe`**. First time only: if the window
says **One-time setup needed**, click **Set up game data…** (on your PC the release candidate finds the tables by
itself).

## Convert a save: three steps

| Step | What you do |
|---|---|
| **1 Your save** | Drop the save you want to convert onto the window, or click Browse. The converter recognises the game (Wii, Definitive Edition or New 3DS) and shows a one-line preview. While step 2 is empty, a small **Convert to** choice shows where it goes. |
| **2 Destination save** | Choose a save of the game you want to play next. That also sets the destination by itself. *This save is used as a starting point. It won't be changed.* (For **New 3DS → Wii** you may leave step 2 empty.) |
| **3 Save converted file to** | Keep the default (`Documents\XC Save Converter\Converted saves`) or choose another normal folder. The file name is chosen so it does not clash with a save next to your step-2 save. |

Click **Convert Save**. **Conversion complete** shows the game, the new save and the folder. Click
**Open Output Folder**, then install it yourself after a backup:

- **New 3DS in Azahar:** right-click Xenoblade Chronicles 3D → *Open Save Data Location*; back up that folder, then
  copy the `3ds\monado0N` file into it (same name). Use a slot you are not using, or one you backed up.
- **Real New 3DS (Checkpoint) — untested:** the output has a `checkpoint\xcconv_…` folder: a complete copy of your
  3DS save archive with one slot replaced. Back up your save with Checkpoint first. Then copy the `xcconv_…` folder
  into `SD:\3ds\Checkpoint\saves\<Xenoblade Chronicles 3D folder>\` on your SD card and restore it with Checkpoint.
  This only appears when your step-2 save sat in a folder with all three slot files (for example a Checkpoint backup
  folder you copied to the PC).
- **Definitive Edition:** back up Monado's `save\save_0` folder, then copy `save_0\bfsgameNN.sav` (and the `.tmb`).
  Do not copy `bfssystem.sav`.
- **Wii:** back up your Wii save slot, then copy the `monadoNN` file into Dolphin's
  `…\title\00010000\53583445\data` folder.

**Keep the output folder.** It holds the conversion record that lets the save come back without losing anything
(including Definitive-Edition-only things such as Expert Mode).

## Bringing a save back

Do exactly the same three steps: your save from the game you just played in step 1, your latest save of the game you
are going back to in step 2. The converter finds the record of your last conversion by itself and shows
*"Continuing your conversion of …"*. Your step-2 save is only read: it lets the converter check that no progress in
that game is lost. If you did not play the other game in between, you get its save back unchanged.

| Message | What it means / what to do |
|---|---|
| *More than one earlier conversion matches this save* | **Choose conversion…** and pick the one you continued from. |
| *This save matches an older conversion* | Convert the save from your latest conversion instead. |
| *This … save is from a different playthrough* | Choose the step-2 save you converted from last time, or one you saved after it. |
| *No record of your last conversion was found* | **Find record…** (in the old output folder), or **Start fresh…** after reading the warning. |
| *Your inventory is larger than this … save can hold* | **Keep extra items for later**: they wait in the record and come back in DE. |
| *Both games were played after the last conversion* | Progress is never merged. **Keep this save's progress…** converts anyway after you confirm that the other game's newer progress will not be in the new file. |

## When the converter says no

Nothing is written when it stops. Typical reasons: an empty or damaged save slot; going to the Definitive Edition with
Fiora's second form or a guest in the party; a DE save in the older format v7; the party is in a DE-only area; an
output folder inside a game, emulator, SD-card or live save folder. **Details** shows the exact reason.

## Advanced

**Advanced…** (bottom left): check only (write nothing), keep extra items, choose a record file, game data, tools
(save inspector, round-trip check, record details), log and diagnostics.

## Keyboard

Alt+S your save, Alt+D destination save, Alt+T output folder, Alt+C or Ctrl+Enter convert, Alt+A Advanced,
Ctrl+O browse.

## Safety

Your saves are only read. Output goes to a new folder every time; nothing is overwritten and nothing is written into
game, emulator, SD-card or live save folders. All files of a conversion appear together or not at all.
`xcconv.exe` in the same folder is the identical converter for the command line (`xcconv.exe --help`).
