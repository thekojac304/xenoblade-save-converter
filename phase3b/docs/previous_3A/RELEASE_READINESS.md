# Release readiness: XC Save Converter 3A-rc1 (Wii, Definitive Edition, New 3DS)

## 3A decision per direction

| Direction | Emulator verdict | Real hardware | Basis |
|---|---|---|---|
| Wii -> DE | **GO** (VALIDATED, unchanged) | - | 2F/2H; 3A output byte-identical to 2H |
| DE -> Wii | **GO with the 2H caveat** (PARTIALLY VALIDATED) | - | 2E/2F; Wii story after export untested |
| Wii -> 3DS | **GO for Azahar** (VALIDATED) | **NO-GO until you test it** (Checkpoint restore untested) | runs a1, a2, a3, a6: your 22 h save loads, plays (combat, travel), saves and reloads on the 3DS game; canonical state identical |
| 3DS -> Wii | **GO** (VALIDATED) | n/a | lossless; Dolphin w1/w2: load, party, save, cold reload |
| DE -> 3DS | **GO for Azahar with care** (PARTIALLY VALIDATED) | NO-GO until tested | a5 + m2: loads, correct stats, saves; return to DE complete; no combat/travel on the 3DS for a DE-sourced save |
| 3DS -> DE | **GO** (VALIDATED) | n/a | m1/m2: loads and saves in Monado; Wii -> DE engine validated |

| Item | Verdict | Evidence |
|---|---|---|
| GUI (three platforms, same three steps) | **GO** | 39 GUI tests (30 from 2H + 9 new) pass; screenshots light/dark in `validation\screenshots` |
| Packaged app | **GO** | 32 / 32 clean-folder checks without Python (all 2H checks + 3DS) |
| Wii <-> DE regression | **none** | 136 unit tests OK; GUI and CLI output byte-identical to 2H |
| Safety | **stricter** | 3DS/Azahar/Citra/SD-card/Checkpoint paths refused; 904 protected files unchanged; every emulator run isolated |

## Your acceptance checklist (about 20 minutes)

**A. Wii -> New 3DS in Azahar (your 22-hour save)**
1. In Azahar: right-click Xenoblade Chronicles 3D -> *Open Save Data Location*; copy the whole folder somewhere safe.
2. Start `XCSaveConverter.exe`. Step 1: your Wii `monado01` (Eryth Sea, 22:01:57). Step 2: your 3DS `monado01` from
   that folder (Colony 9, 0:12). Convert Save.
3. Copy `3ds\monado02` from the output into the Azahar save folder (slot 2 is empty in your archive).
4. In Azahar (Vulkan renderer): Continue -> slot 2 shows **Lv 52 Shulk, Eryth Sea**. Load it. Check Party (levels
   51-52, 375,150 G), Shulk's equipment (Monado with Blaze Plus IV, Double Attack IV), a fight, a skip travel, then
   save into a free slot and load that slot again.
5. Expected: everything as on the Wii. If anything looks wrong, restore the backup of step 1.

**B. Back to the Wii (optional)**: Step 1 = the slot you saved in A4, step 2 = your Wii `monado01`. The converter
finds the record automatically. Copy the resulting `monado01` into a backed-up Dolphin slot and load it.

**C. Real New 3DS (hardware test, not done by me)**
1. On the 3DS, back up Xenoblade Chronicles 3D with Checkpoint. Copy that backup folder (it holds monado01-03) from
   `SD:\3ds\Checkpoint\saves\<title folder>\<backup>` to the PC.
2. Use a save from that folder as step 2. The output then has `checkpointÌonv_...` (the complete archive).
3. Copy that folder next to your backup on the SD card, restore it with Checkpoint, start the game and load the slot.
4. If the game reports corrupted data, restore your own Checkpoint backup. Please report the result: physical support
   stays "pending" until this works.

---

# Previous release readiness (2H, unchanged)


## 2H decision

| Item | Verdict | Evidence |
|---|---|---|
| **Simplified GUI ready for user acceptance** | **GO** | Three steps and one button; all 15 required test areas pass (`GUI_TEST_RESULTS.md`). |
| Conversion output | **Unchanged** | Byte-identical to the 2G release `xcconv.exe` (4 / 4) and to the CLI in every GUI test; saves byte-identical to the frozen 2F code. |
| Safety | **Unchanged or stricter** | Same engine checks and transactional writer; history is chosen only when unambiguous; a same-playthrough pair without a record is stopped; divergence needs an explicit confirmation. |
| Portable package | **GO** | Runs without Python from a clean folder, 20 / 20 checks, including 150 % and 200 % scale. |
| Not tested | — | Physical high-DPI monitor, Windows 10, screen readers, real Explorer drag (see `KNOWN_LIMITATIONS.md`). |

**First conversion in 2H:** start `XCSaveConverter.exe` → drop your Wii `monado01` on step 1 → choose any DE save of
yours in step 2 (with your early `bfsgame00.sav`, SHA-256 `19d33489…`, the result is the validated `1028f718…` save)
→ Convert Save → Open Output Folder → copy `save_0\bfsgameNN.sav` and its `.tmb` into Monado's `save\save_0` after a
backup. Keep the output folder for the way back.

**Observed during the 2H checks:** Monado's live `save_0` now contains `bfsgame01.sav` (= `1028f718…`) and
`bfsgame01.tmb`, added 2026-11-06 21:09, apparently by the manual install from the checklist below. Nothing in the
converter wrote there. If that was you, the in-game checks of the checklist are the next step.

---

# Phase 2G record (the desktop application baseline; still valid)

| Item | Verdict | Evidence |
|---|---|---|
| GUI ready for user acceptance (2G) | GO | All 10 completion criteria met. |
| Engine behaviour vs 2F-rc1 | Unchanged | Byte-identical saves both directions. |
| Portable package (2G) | GO | 18 / 18 package checks. |

---

# Engine verdict (from 2F-rc1; still valid, the engine is unchanged)

## Decision

| Use | Verdict | Conditions |
|---|---|---|
| **Wii → DE** for your playthrough (scenario 150, Eryth Sea) | **GO** | Back up Monado's `save_0` first; use a free slot (01). The release file is byte-identical to the one loaded and saved in Monado in Phase 2F; the 2E file it replaces passed combat, travel and story 150 → 156. |
| **Round trips at your current chapter** (DE → Wii → DE, with sidecars) | **GO with care** | Always pass the current save of the other game (`--current-…`) and the newest sidecar. Keep every output folder. |
| **Long play on the Wii after a DE → Wii export** | **CONDITIONAL** | Loading, menus, combat, travel and saving work on the Wii [game]. A Wii story event after an export was never played. Back up the Wii slot, and check the first story event yourself. |
| Late game after Fiora rejoins (character 8 in the party) | **NO-GO** (refused) | Not supported yet. The converter stops with an explanation. |
| DE saves from game version 1.x (format v7) | **NO-GO until re-saved** | Load and save once in DE 2.0 / Monado (lossless [game]). |

Status by direction:
- **Wii → DE: VALIDATED.**
- **DE → Wii: PARTIALLY VALIDATED.**
- **Bidirectional: VALIDATED for the tested chains.**

The converter is **not** universally compatible; see `KNOWN_LIMITATIONS.md`.

## Why this verdict

- **Defects.** 25 found and fixed in Phase 2F. Four would have hit regular play:
  - a re-import refused after any item pickup on the Wii;
  - Fiora's DE skill progress reverted by the Wii game;
  - late-game DE saves refused;
  - an old sidecar able to bring back sold items.
- **Tests.** 109 automated tests pass (1 skipped). They include:
  - seeded property tests;
  - capacity boundaries for every box;
  - a 60-case fuzz run;
  - failure injection at every write stage;
  - stale and divergent sidecars;
  - a checkpoint matrix of 6 game-generated DE saves (story 20–269, Expert Mode).
- **Game runs.** 10 isolated runs. The strongest evidence is a full cycle through both games with game-written files
  at each step: DE (story 232) → Wii (load, save) → DE (load, save). Only clock, play time and position changed;
  all 1,256 items and the Expert Mode data were kept.
- **Package.** The clean-directory test passed 10/10, including a byte-exact reproduction of your release save.
- **Safety.** Every protected file is unchanged (106 hashes).

## Residual risks (what could still go wrong)

1. **Wii story progression after an export** (untested). Mitigation: back up the Wii slot; if a story event fails,
   reload the backup.
2. **Wii flags `0x352C–0x36CF`** have no DE slot. They stay on the Wii side; the effect of losing them on a foreign
   base is unknown (low).
3. **Using `--no-current-…` with an old sidecar** can resurrect sold DE-only items. Mitigation: pass `--current-…`.
4. **Inactive-character normalisation by the games** (Fiora's copy is handled; others unknown). Mitigation: canonical
   read-back reports differences; keep backups.

---

## MANUAL ACCEPTANCE CHECKLIST: your converted Eryth Sea save in Monado

Files: `release_candidate_2F\user_saves\wii_to_de_monado01\`
(`save_0\bfsgame01.sav`, `save_0\bfsgame01.tmb`, `wii_to_de.sidecar.json`, `manifest.json`).

**Before you start**

1. **Back up Monado's save folder.** Copy the whole folder
   `C:\Program Files\Quiver Launcher\Apps\XenobladeChroniclesDefinitiveEdition-Monado\save\save_0`
   to, for example, `C:\Users\lawma\Documents\xc_backup_2026-11-06\save_0`.
2. **Check the file.** In a terminal in the release folder:
   `certutil -hashfile user_saves\wii_to_de_monado01\save_0\bfsgame01.sav SHA256`
   It must print `1028f718c0c567e75e03184492287b20b5f78b8280b7e0d70ba1eecc943673b2`.
3. **Check slot 01 is free.** If `save_0` already has `bfsgame01.sav`, either back it up and move it out, or make a
   copy for a free slot:
   `python converter\tools\xcconv.py wii-to-de --wii <your monado01> --template <your bfsgame00.sav> --slot 02 --out <new folder>`

**Install**

4. Copy `bfsgame01.sav` and `bfsgame01.tmb` into `...\save\save_0\`. **Do not copy `bfssystem.sav`.**

**In the game**

5. Start Monado normally → Load. The new entry should read: **Eryth Sea · Lv 52 Shulk · Play Time 22:02 ·
   Chapter Eight**. Load it.
6. Field: Eryth Sea, clock about **13:13–13:30**, the explored minimap areas visible.
7. Main menu checks:
   - **Party:** Shulk, Dunban, Riki active; Sharla, Reyn, Melia in reserve; levels as on the Wii.
   - **Equipment:** each character wears the same gear and gems as on the Wii.
   - **Arts / Skill Trees / Skill Links:** same arts and levels. Shulk ← Reyn shows 4 unlocked link slots. One pair
     (Shulk ↔ Dunban) may show one more slot than on the Wii; the game recomputes it from affinity.
   - **Items:** money and item counts as on the Wii; "newest" sort puts your latest Wii pickups first.
   - **Quest Log:** quests in progress as on the Wii (e.g. 221 with 2 of 3 objectives done).
   - **Affinity Chart:** Heart-to-Hearts discovered on the Wii are listed.
8. Fight one enemy; fast travel to Frontier Village or Colony 9.
9. Save to **another free slot**, return to the title screen, and reload that save.

**After**

10. Keep `wii_to_de.sidecar.json` (and the whole output folder) next to your saves. You need it to go back to the Wii:
    `python converter\tools\xcconv.py de-to-wii --de <your current DE save> --sidecar <that sidecar> --current-wii <your current monado01> --out <new folder>`
11. **If anything looks wrong:** quit, put the backup folder back, and keep the screenshots.

---

## The same checklist with the desktop application (2H)

You do not need to convert again: the 2F release save is the file the GUI produces (identical SHA-256
`1028f718…`). If you prefer to make it yourself:

1. Start `release_candidate_2H\XCSaveConverter\XCSaveConverter.exe`. The game data is found automatically
   (`release_candidate_2H\user_data\data`); otherwise the window offers the one-time setup.
2. **1 Your save:** drop your Wii `monado01` (a copy is fine). The preview line reads
   `Wii · Eryth Sea · 22:01:57 · Shulk Lv 52 → Definitive Edition`.
3. **2 Destination save:** your early DE `bfsgame00.sav` (SHA-256 `19d33489…`; a copy is
   `XC_Wii_to_DE_Research\work\template\bfsgame00.sav`). It is only read.
4. **3 Save converted file to:** keep the default; the file name is suggested (`bfsgame01.sav` when the folder of the
   step-2 save already holds `bfsgame00.sav`). Click **Convert Save**.
5. On **Conversion complete**, click **Open Output Folder**. `certutil -hashfile "<folder>\save_0\bfsgame01.sav" SHA256`
   must print `1028f718c0c567e75e03184492287b20b5f78b8280b7e0d70ba1eecc943673b2` (with another step-2 save the options
   part differs, so the checksum differs; that is expected).
6. Continue with step 4 of the checklist above (install, then check in the game).
