# XC Save Converter: user guide (2H-rc1)

Moves one Xenoblade Chronicles playthrough between the **Wii** version (Wii or Dolphin; saves `monado01`–`03`) and
the **Definitive Edition** (DE 2.0 / Monado; saves `bfsgame00.sav`, `bfsgame01.sav` …). Windows 10/11, 64-bit. No
installation, no Python.

> Some game states are refused on purpose (see the end of this guide), and Wii story progress after a DE → Wii
> conversion has not been tested in play. Keep backups.

## Start

Keep the `XCSaveConverter` folder together and double-click **`XCSaveConverter.exe`**.

First time only: if the window says **One-time setup needed**, click **Set up game data…** and choose the folder
with the two tables `bdat_wii.json` and `bdat_de.json` made from your own copies of the games, or create them from
your extracted game files. On your PC the release candidate finds them by itself.

## Convert a save: three steps

| Step | What you do |
|---|---|
| **1 Your save** | Drop the save you want to convert onto the window, or click Browse. The converter recognises the game and shows a one-line preview (version, area, play time, leader level) and where it goes. |
| **2 Destination save** | Choose any save of the *other* game. For a first conversion it is only a starting template (its options and Expert Mode setting). Your existing save is never changed. |
| **3 Save converted file to** | Keep the default (`Documents\XC Save Converter\Converted saves`) or choose another normal folder. The file name is chosen so it does not clash with a save in your game folder. |

Click **Convert Save**. The converted save is checked by an independent reader before anything is written.

**Conversion complete** shows the game, the new save, and the folder. Click **Open Output Folder**, then:

- **Definitive Edition:** back up Monado's `save\save_0` folder, then copy `save_0\bfsgameNN.sav` (and the `.tmb`
  file) into it. Do not copy `bfssystem.sav`.
- **Wii:** back up your Wii save slot, then copy the `monadoNN` file into Dolphin's
  `…\title\00010000\53583445\data` folder.

**Keep the output folder.** It holds the conversion record that lets the save come back without losing anything.

## Bringing a save back

Do exactly the same three steps: your save from the game you just played in step 1, your latest save of the other
game in step 2. The converter finds the record of your last conversion in your output folder by itself and shows
*"Continuing your conversion of …"*. Your step-2 save is only read: it lets the converter check that no progress in
that game is lost. If you did not play the other game in between, you get its save back unchanged.

The converter only asks you something when it cannot decide safely:

| Message in step 2 | What it means / what to do |
|---|---|
| *More than one earlier conversion matches this save* | Click **Choose conversion…** and pick the one you continued from. |
| *This save matches an older conversion* | A later conversion exists. Convert the save from your latest conversion instead (or choose deliberately; the converter still checks). |
| *This … save is from a different playthrough* | Choose the step-2 save you converted from last time, or one you saved after it. |
| *No record of your last conversion was found* | The two saves look like the same playthrough, but the record is missing. **Find record…** (in the old output folder), or **Start fresh…** after reading the warning. |
| *Your inventory is larger than this Wii save can hold* | **Keep extra items for later**: unequipped extras wait in the record and come back in DE. |

If both games were played after the last conversion, conversion stops with **Both games have new progress**.
Progress is never merged. **Keep this save's progress…** converts anyway after you confirm that the other game's
newer progress will not be in the converted file (your original files stay unchanged).

## When the converter says no

Nothing is written when it stops. Typical reasons: Fiora's second form or a guest in the party (not supported yet);
a DE save in the older format v7 (load and save it once in DE 2.0 / Monado); the party is in a DE-only area; a damaged
or edited file; an output folder inside a game or emulator folder. **Details** under a message shows the exact reason.

## Advanced

**Advanced…** (bottom left) holds what a normal conversion does not need:

- **Options:** check only (convert and verify, write nothing); keep extra items for later; the Wii save in step 2 is
  an earlier save of this playthrough; "I no longer have a save of the destination game"; choose a record file.
- **Game data:** set up or create the tables.
- **Tools:** save inspector and validation, round-trip check, conversion-record details, compatibility check.
- **Log** and **Diagnostics** (copy this when you report a problem: paths and checksums, no save contents).

## Keyboard

Alt+S your save, Alt+D destination save, Alt+T output folder, Alt+C or Ctrl+Enter convert, Alt+A Advanced,
Ctrl+O browse for your save. Tab moves between all controls; paths can be typed or pasted.

## Safety

Your saves are only read. Output goes to a new folder every time; nothing is overwritten and nothing is written into
game, emulator or live save folders. All files of a conversion appear together or not at all. `xcconv.exe` in the
same folder is the identical converter for the command line (`xcconv.exe --help`).
