# Phase 3E summary — XC Save Converter 3E-rc1

**What changed for you**

* **Saves from the "party split" chapters convert again.** When the story sends party members away (Alcamoth around
  scenarios 154–160, Fallen Arm 269–288), the games keep their equipment and gems until they come back. 3D refused
  those saves; 3E carries that stored equipment between the Wii, the New 3DS and the Definitive Edition.
* **Proven in the games themselves.** Converted saves were played through the reunions on the Wii (Dolphin), the 3DS
  (Azahar) and the DE (Monado): Shulk, Reyn, Dunban, Sharla and Riki came back wearing exactly their own gear with
  their own gems — the same result the DE game gives on its own, with nothing lost or duplicated.
* **Fixed a 3DS bug (D3)** that would have dropped the socketed gems of returning characters on the 3DS.
* **One case is still refused:** while Fiora (her later form) is away near the end of the game (scenario 288), because
  that reunion could not be played to confirm it. Convert after she is back (291) or play that chapter on one
  platform. The converter names her when it stops.
* Everything else gives the same result as 3D, byte for byte. The app looks the same; the Sync Hub is unchanged.

**Where things are**

| | |
|---|---|
| Application | `release_candidate_3E\XCSaveConverter\XCSaveConverter.exe` (no Python needed) |
| Details | `XC_PHASE3E_REPORT.md`, `STORED_EQUIPMENT_MAPPING.md`, `REUNION_VALIDATION.md`, `THREE_PLATFORM_REGRESSION.md` |
| Limits | `KNOWN_LIMITATIONS.md` (new: L-J … L-M) |
| Readiness | `RELEASE_READINESS.md` |

**Not done / still open:** the Fallen Arm reunions themselves were not played (their saves convert exactly in every
direction); Fiora's stored gear (288) stays refused; real hardware remains untested. Earlier releases are untouched.
