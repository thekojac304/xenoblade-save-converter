# Phase 3A in plain words

**Your playthrough can now move between all three versions:** Wii (Dolphin), Definitive Edition (Monado) and
Xenoblade Chronicles 3D (Azahar). New release candidate: `release_candidate_3A\XCSaveConverter\XCSaveConverter.exe`
(3A-rc1). Same three-step window as before; it now also accepts 3DS saves. Earlier releases are untouched.

## What I found

* The 3DS save (`monado01`–`03`) is the Wii save in disguise: the same layout, compressed (QuickLZ) and stored in
  the 3DS's byte order. Three details differ: packed fields are bit-reversed, one treasure-chest field is shorter,
  and the checksums use a different formula. Each was confirmed in the 3DS game's own code or by its own saves.
* Because the layouts match, **Wii ⇄ 3DS loses nothing at all**: a save converted there and back is identical to the
  byte. DE ⇄ 3DS goes through the proven Wii ⇄ DE converter. Definitive-Edition-only things (Expert Mode, outfits, DE
  items) wait in the conversion record and come back when you return to DE.
* One 3DS-only surprise: the 3DS trusts the HP/strength/defence numbers stored in the save, while the Wii recalculates
  them. The converter now calculates them exactly as the 3DS game does, which matches every save the game wrote itself.

## What was tested

* **Your 22-hour Wii save on the 3DS (Azahar):** loads in Eryth Sea with the right party, levels, money, equipment
  and gems, skill trees, quest log, map and landmarks; a battle, a skip travel, saving and reloading all work. The
  save the 3DS game wrote contains exactly your progress plus the battle.
* That 3DS-played save **back to the Wii** (Dolphin) and **to the Definitive Edition** (Monado): loads, saves, reloads.
* A late-game **DE save (story 232, Expert Mode) to the 3DS and back to DE**: correct stats on the 3DS, saved there,
  and back in DE every item, quest, flag and DE-only setting is restored.
* 41 new automated tests, the unchanged 136 earlier ones, 39 window tests, and 32 checks of the packaged program on
  a clean folder without Python all pass. None of your saves, emulator folders or earlier releases changed.

## What did not happen / what remains

* **Nothing was tested on your real New 3DS.** The converter also builds a complete Checkpoint-style backup folder,
  but restoring it on hardware is your test (`RELEASE_READINESS.md`, part C). Until then, real-3DS support is pending.
* No story scene was played after a conversion (battles, menus, travel and saving were).
* A converted 3DS save shows the destination save's picture and save time in the load menu until you save once.
* Only the USA 3DS version (yours) could be examined.

## How to try it (Azahar, about 10 minutes)

1. Back up Azahar's save folder for the game (right-click the game → *Open Save Data Location*).
2. Open `XCSaveConverter.exe`: step 1 = your Wii `monado01`, step 2 = your 3DS `monado01` from that folder, **Convert Save**.
3. Copy `3ds\monado02` from the output into the Azahar save folder, start the game (Vulkan renderer), *Continue*,
   choose slot 2 (Lv 52 Shulk, Eryth Sea).
4. Keep the output folder: it is what makes the way back safe.

Details: `XC_THREE_WAY_PHASE3A.md` (findings), `THREE_WAY_COMPATIBILITY.md` (what works in which direction),
`THREE_WAY_TEST_RESULTS.md` (evidence), `KNOWN_LIMITATIONS.md`, `GUI_USER_GUIDE.md`.
