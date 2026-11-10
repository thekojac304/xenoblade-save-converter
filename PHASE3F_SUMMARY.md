# Phase 3F summary — XC Save Converter 3F-rc1

**What changed for you**

* **The last Fiora restriction is gone.** Saves made while Fiora (her later form) is away near the end of the game
  (scenario 288) now convert between the Wii, the New 3DS and the Definitive Edition, her stored weapon, armour and
  gems included.
* **Proven in the games.** The reunion was played on the Definitive Edition (Monado) and on the 3DS (Azahar) from a
  converted save: Fiora, Shulk, Reyn and Sharla came back wearing exactly their own gear with their own gems, the same
  as the Definitive Edition does on its own; saved, reloaded and converted back with nothing lost or duplicated.
* **Fixed a real problem (F1).** If an equipment pocket on the Wii/3DS is full at a reunion, the game silently skips
  giving a character's gear back. Conversions made by 3E during the Fallen Arm split (scenarios 269-283) could fill
  those pockets. 3F keeps room for the returning gear (a few extra spare items wait in the conversion record until you
  return to the DE), and refuses, with the names, a save in which the game already skipped a return.
* **If you converted a Fallen Arm save with 3E and play the reunion on the Wii/3DS:** free a few slots in each
  equipment pocket first, or re-convert the DE save with 3F (KNOWN_LIMITATIONS L-O).
* Everything else gives the same result as 3E, byte for byte. The app looks the same.

**Where things are**

| | |
|---|---|
| Application | `release_candidate_3F\XCSaveConverter\XCSaveConverter.exe` (no Python needed) |
| Details | `XC_PHASE3F_REPORT.md`, `FIORA_REUNION_ANALYSIS.md`, `FIORA_REUNION_GAMEPLAY_TESTS.md`, `THREE_PLATFORM_REGRESSION.md`, `SYNC_HUB_REGRESSION.md` |
| Limits | `KNOWN_LIMITATIONS.md` (new: L-N … L-Q) |
| Readiness | `RELEASE_READINESS.md` |

**Not done / still open:** the Wii game did not play this reunion — the PC stayed locked the whole session, which
stops Dolphin; three commands to run it are in `FIORA_REUNION_GAMEPLAY_TESTS.md`. The Fallen Arm reunions 269 → 276
and 276 → 283 were not played; real hardware remains untested. `release_candidate_3E` and earlier releases are
untouched.
