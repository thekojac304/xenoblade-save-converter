# Phase 3D summary — XC Save Converter 3D-rc1

**What changed for you**

* **Fiora's return is no longer a dead end.** From the point where Fiora rejoins (scenario 275, her later form —
  character 8), saves now convert between the Wii, the New 3DS and the Definitive Edition. Tested with real
  late-game saves: the Wii game and the 3DS game loaded them, showed Fiora at level 53 with her Mechonis gear and her
  own skill trees, saved, and the saves came back to the DE (Monado) with everything in place.
* **Fixed a crash.** Converting a later DE save onto a very early Wii/3DS save (for example your story-8 3DS save)
  could crash the 3DS game or freeze the Wii on loading Fallen Arm. Fixed (defect D1).
* **New safety stop.** In a few story chapters some party members leave for a while and the game keeps their equipment
  until they come back (for example Alcamoth around scenarios 154–158, and Fallen Arm to the reunion, 269–288). The
  converter cannot carry that stored equipment yet, so it now **refuses** those saves and names the characters
  (defect D2). Convert before the split or after everyone is back, or play through that chapter on one platform.
  Bringing a save back to the save it came from still works. Earlier versions converted these saves and would have
  given those characters the wrong equipment after their return.
* Everything else behaves as in 3C (byte-identical results), the app looks the same, the Sync Hub is unchanged and
  blocks a sync with the same explanation when one of these saves appears.

**Where things are**

| | |
|---|---|
| Application | `release_candidate_3D\XCSaveConverter\XCSaveConverter.exe` (no Python needed) |
| Details | `XC_PHASE3D_REPORT.md`, `CHARACTER_STATE_MATRIX.md`, `STORY_TRANSITION_RESULTS.md`, `THREE_PLATFORM_REGRESSION.md` |
| Limits | `KNOWN_LIMITATIONS.md` (new: L-E … L-I) |
| Readiness | `RELEASE_READINESS.md` |

**Not done / still open:** the rejoin and reunion events themselves were not played on the Wii/3DS (could not be
reached in the emulators within a bounded effort); stored equipment of members who are away is refused, not
translated; real hardware remains untested. Earlier release candidates (2E–3C) are untouched.
