# Phase 3C — what was achieved (plain language)

**New release:** `release_candidate_3C\` — XC Save Converter **3C-rc1** (same app and Sync Hub as 3B, improved engine).
Your saves, emulator folders, game files, Syncthing setup and every earlier release (including 3B) were not touched.

## Your DE-only data now survives the trip

* **Favourite marks and the other Definitive-Edition-only item details** now come back after a save visits the Wii or
  3DS. Before, items that had to be moved to fit the Wii's smaller inventory lost them (on a big late-game save: 86 of
  176 crystals). Now every item record comes back exactly — checked with a save the 3DS game itself wrote.
* The converter follows each **physical item**: if you sell an item on the Wii/3DS, it does not come back; if you buy an
  identical one, it does *not* inherit the old one's favourite mark (the 3B version got this wrong). When the save
  cannot tell an item from an identical replacement (the newest item of a pocket you changed, or a material stack you
  picked up more of), the mark is dropped rather than guessed.
* **Expert Mode, outfits, link unlocks and DE-only flags** keep coming back exactly; one Expert Mode value is now also
  updated correctly after you earn EXP on the Wii/3DS (found by comparing real game saves).
* Converting a DE save to the Wii/3DS and straight back without playing used to be refused for big saves; it now gives
  your original file back unchanged.

## The story keeps working after conversion

* **Definitive Edition (Monado):** your converted playthrough continued **from scenario 156 to 160** through the game's
  own events — the Emperor's audience, Shulk alone in the guest room, talking to Riki, Sharla, Reyn and Dunban, Alvis's
  arrival, the party re-forming. The 160 save was reloaded, saved normally and loaded again. The old "stuck at 157"
  problem was a fault in the 2E test tool (it jumped away in the middle of the audience), not your save.
* **Wii (Dolphin) — first time ever:** a DE save converted to the Wii played a real story event on the Wii (Melia
  reaching the Emperor's palace, 154 → 156), changed exactly what the DE version changes, saved and reloaded. Converted
  back to DE, it continued the story to 158 — the same state as without the Wii trip.
* **Later in the game:** a scenario-232 save that had been through the Wii and back played the Valak Mountain event
  (232 → 233).
* **3DS (Azahar) — also a first:** the same DE save converted to the 3DS played the same event on the 3DS, saved,
  reloaded, and came back to the DE identical to the DE's own result (all items included).

## Also investigated

* The ~420 "unexplained" Wii-only flags: the Definitive Edition simply has no room for the Wii's last 420 flags; your own
  untouched Wii save sets two of them by itself when you travel to Colony 9 and Frontier Village. They are normal Wii
  state, and the game recreates them — low risk.

## What is still not covered

* Fiora rejoining the party (late game) still cannot be converted to the DE (the converter stops and explains).
* Endgame story events, Future Connected, and real hardware (New 3DS, Android) were not tested.
* Only a handful of story transitions were played; this is strong evidence, not proof for the whole game.

Details: `XC_PHASE3C_REPORT.md`. Limits: `KNOWN_LIMITATIONS.md`.
