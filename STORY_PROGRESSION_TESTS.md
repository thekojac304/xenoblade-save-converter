# Story progression tests (Phase 3C)

Chronological evidence of real story transitions after conversion, in Monado (Definitive Edition), Dolphin (Wii)
and Azahar (3DS). Rules followed in every run:

* the game's own event system advances the story — no scenario counter, story flag, quest, party or event state was
  written by any tool (Monado's `XCDE_EVENT` and tour `story` step were never used);
* debug teleport (Monado `XCDE_WARP`) only to a site taken from the game's event table `EVT_sev`, in the field after
  the save has loaded, never during a scene;
* every run is isolated (own save folder, live saves hashed before/after, the 1,679-file protected manifest checked
  before and after each run), and starts from a preserved copy of the previous game-written checkpoint
  (`phase3c/inputs/`);
* a transition counts only when the game wrote a save with the new scenario, that save loads again, and the next
  objective is still available.

Run folders: `phase3c/runs/<emulator>/<run>/` (captures, emulator log, `run_manifest.json` with input/output save
states and the protected-manifest result). Checkpoint analysis: `phase3c/scripts/b_checkpoint.py`.

## Background: the "scenario 157 blocker" (2E)

2E advanced the user's converted save 150 → 154 → 156 and then reported that the 157 trigger could not be found.
Re-reading the 2E logs (`work/phase2e/monado/s2_story/stderr.log`, `sheet.png`): s2 *did* warp to the scenario-156 site
(`EVT_sev` vs08070100, ma1101 629.65 / 715.07 / 0.005) and the Emperor's audience started (captures f8200–f14200), but
the tour helper jumped to the next site after its fixed 60 s scene limit ("still in a scene after 60 s, jumping
anyway"), mid-audience; the game then sat on a black screen. s3 started from the 156 autosave and only tried the 158,
159 and 160 sites. **The blocker was the test harness, not the save or the converter.** Scenario 157 has no own site
because its event (vs08080150) follows the audience directly.

## Monado (Definitive Edition)

### M1 — c1_s156_audience: 156 → 158 (two transitions, party change Melia → Shulk)

| | |
|---|---|
| Start | 2E game-written autosave, scenario 156, ma1101 Alcamoth, party [Melia] (`work/phase2e/start_s156`) |
| Action | one warp to the 156 site (vs08070100, Audience Chamber) after load; then only A every 1.5 s (dialogue) |
| Game events | Emperor Sorean's audience with Melia, Kallian and Lorithia (f4300–f12438), the guest-room scene with Reyn and Sharla (f13920); control returns to Shulk in the Whitewing Palace guest room (f15516+) |
| Game-written save | autosave `bfsgame00a.sav`: **scenario 158**, party **[Shulk]**, ma1101 (101.6, 154.62, 454.34), +236 s play time; Melia level 51 → 52, 5 flags changed, gem box 55 → 61 (game's own changes) |
| Evidence | `phase3c/runs/monado/c1_s156_audience/` (captures, sheet, stderr with the warp and the save writes) |
| Safety | live save_0 unchanged; protected manifest unchanged; isolation mount verified |
| Next objective | EVT_sev 158 = vs08090100; objective text (MNU_scenario help 81): "Shulk needs to talk to his friends to find out what is going on" |

### M2 — c2_s158_warp: the 158 site is not a trigger

Warp onto the vs08090100 position: the game autosaved there (still 158, position = the site) and nothing started —
Shulk stood beside Dunban. Consistent with the objective text: 158 → 159 is triggered by **talking to the friends**,
not by a coordinate (the brief's caution was right).

### M3 — c4 … c9: 158 → 160 by talking to the friends (party re-forms: Shulk alone → five members)

| Step | Run | Finding |
|---|---|---|
| face Dunban | c4 | warp to the 158 site facing 180°: Shulk talks to Dunban, generic lines loop ("We need the High Entia if we are to get to Prison Island") — Dunban alone does not advance the story |
| find the friends | c6, c7 | stick walks towards Reyn from the 158 position: reached him, but no conversation (not facing) |
| where are they? | c3, c8 | `XCDE_ENT_SCAN` (frame list) prints positions only for playable characters; `XCDE_DUMP_MEM` (16 MB of guest heap at frame 5000) + `phase3c/scripts/memscan.py`: four figures on the guest-room floor (y ≈ 154.6): Dunban (113.3, 445.2) and three at (115.0, 475.1), (117.2, 477.1), (129.2, 473.3) |
| talk to each, Dunban last | **c9** | warps 1.8 units in front of each figure, facing it (angle = atan2(dx, dz), verified on Dunban), A every 1.5 s: **Riki** ("Bird People not bad."), **Sharla** ("The ones who came to meet Melia were also wearing those masks…", "Melia didn't seem like a bad person"), **Reyn** ("What is all this? How can they treat us like this?"), then Dunban → **the game's event plays**: Alvis arrives ("The real reason you have been detained is not because you are outsiders."), the guard, Riki ("Riki find Molly for Shulk!"), then the game opens **Organise Party** (f13236–f21558) |

Game-written save (c9 autosave): **scenario 160**, party **[Shulk, Reyn, Dunban, Sharla, Riki]**, ma1101 (133.76, 154.12,
464.62), +343 s; 9 flags changed; the rejoining members' equipment and gems returned to the inventory (weapons 44 → 48,
gems 61 → 68 — the game's own change). Next objective: EVT_sev 160 vs08100100 at Alcamoth's entrance (−35, −0.544, 0);
objective text: "Shulk and the others are now allowed to move freely and agree to search for the transporter repair
worker. He was last seen at Eryth Sea."

Disclosure: the tour helper's fixed 60-second limit moved Shulk from the Sharla conversation to Reyn while the
A taps kept that (non-story, repeatable) conversation open (`[tour] … still in a scene after 60 s, jumping anyway`). No
cutscene was interrupted: after the final warp to Dunban the tour only waited.

### M4 — c10_s160_reload_save: reload and normal save

A new game process loaded the 160 autosave (field with Reyn, Shulk, Sharla), then System → Save → slot → "Overwrite
save data?" Yes; the slot shows Alcamoth, Lv 52 Shulk, 22:16, Chapter Eight, five portraits. The manually saved file:
scenario 160, same party and position (`phase3c/fixtures/de_s160_monado_manual_save_c10.sav`).

### M5 — c11_s160_entrance: cold reload of the manual 160 save; the 160 site

A new process loaded the manually saved 160 file (the party of five appears in the field: Reyn, Shulk, Sharla); one warp
to the EVT_sev 160 site (vs08100100, Alcamoth's garden plaza): no event while standing inside it for 8 minutes — like the
158 site, it is not a stand-on trigger (an approach or another interaction is needed). The next objective as the game
words it: search Eryth Sea for the transporter repair worker. See M6 for the approach attempt.

### M6 — c12_s160_approach: walking into the 160 site (bounded stretch attempt)

Warp 10 units short of the site, then walk forward through it: no event; the game's route marker points away (towards
the exit / Eryth Sea), as the objective text says. Stretch attempts stop here (bounded retries); the next transition
needs travel to Eryth Sea and finding the repair worker.

## Dolphin (Wii) — DE → Wii, then a real Wii story event (Part C1)

### W1 — d1_s154_story: converted DE save, 154 → 156 on the Wii

| | |
|---|---|
| Input | Monado's own autosave at **scenario 154** (Melia alone in Alcamoth, ma1101 −328.0 / −6.29, facing 90°), the save 2E's s1 run wrote (`phase3c/inputs/s154`) |
| Conversion | DE → Wii with the 3C engine, base = the user's own story-150 Wii save of the same playthrough (`--same-playthrough`); output `phase3c/work/cw_d2w_s154/monado01` + `de_to_wii.sidecar.json` |
| Action in Dolphin | load from the title menu; hold the stick forward 12 s (the EVT_sev 154 site vs08060100 lies 71 units straight ahead, bearing 90°); A every 1.5 s for 150 s; in-game save (menu → System → Save → slot 1 → Yes) — no warp exists or was used on the Wii |
| Game-written Wii save | **scenario 156**, party [Melia], ma1101 (126.92, 62.00, 0.0) — the same spot Monado's own 156 autosave has; play time +212 s |
| State check vs the DE game doing the same transition | the Wii game changed **exactly the same 6 flags** as the DE game (story 32, last landmark 63, 7967, 7968, 8608, 8614); no level, item or quest change in either; remaining differences: derived award counters (documented projection), Shulk's palette[0] (the DE event sets it to 2, the Wii game leaves 1 — game behaviour), clock, play time |
| Next objective | EVT_sev 156 = vs08070100 (the audience) — the M1 transition |
| Safety | NAND root = the run folder; watchdog on the protected Wii folders; protected manifest unchanged |
| Evidence | `phase3c/runs/dolphin/d1_s154_story/` (NAND output, route, manifest); no captures — Dolphin ignored the screenshot hotkey without window focus (fixed for later runs: `HotkeysRequireFocus = False` in the run's own Dolphin.ini) |

This is the first Wii story event ever played on a converted DE → Wii save in this project (2E–3B: "never played").

Back to DE (`phase3c/work/c1_wii156_to_de`, 2H re-import with the export's sidecar onto the s154 DE save): scenario 156;
shared state equal to Monado's own 156 autosave except Shulk's palette[0], clock and play time; Expert/appearance/
DE-only flags of the DE save restored exactly; item metadata: nothing unresolved.

## Later-game checkpoint after a real Wii trip (Part C3)

### L1 — l1_s232_valak: 232 → 233 (Valak Mountain, Sealed Tower), save that went DE → Wii → Wii game → DE

| | |
|---|---|
| Input | public DE save at scenario 232 (Expert Mode, full party, Monado-resaved v10) → 2F DE → Wii export → **the Wii game's own save of it** (Dolphin run d2, 2F `game_chain_s232/w_saved_by_wii_game`) → 3C re-import to DE with the export's sidecar (`phase3c/inputs/l1_s232`; item metadata: all 12 boxes resolved, nothing uncertain) |
| Action in Monado | one warp to the EVT_sev 232 site (vs10110150, ma1301 −1939.0 / −1233.4 / −843.0) after load; A every 1.5 s |
| Game events | Alvis's scene at the Sealed Tower ("In the cave next to it, we will find…"), control returns at the Sealed Tower (captures f6396–f12438) |
| Game-written save | autosave **scenario 233**, ma1301, party [Riki, Reyn, Dunban, Shulk, Melia, Sharla] unchanged, 7 flags changed, no item/level/quest change |
| Next objective | "Thick ice blocks the entrance … obtain a Magma Rock from the cave near Jakt Geyser" (a fetch quest; not attempted) |

### W2 — d2_s156_reload: cold reload of the Wii-written 156 save

A fresh Dolphin process loaded the save the Wii game wrote in W1 (title → load → slot 1), and saved it again in-game:
scenario 156, party [Melia], same position; compared with the W1 save only clock and play time differ. (Captures: none
— the pad screenshot hotkey did not fire even with `HotkeysRequireFocus = False`; later Dolphin runs use the
harness's window capture.)


## Azahar (3DS) — DE → 3DS, then a real 3DS story event (Part C2)

### X1 — x1_s154_story: converted DE save, 154 → 156 on the 3DS

| | |
|---|---|
| Input | the same Monado 154 autosave, converted DE → 3DS with the 3C engine; 3DS template = the user's own 3DS save (story 8), so the extra materials were parked in the conversion record (documented 3A behaviour); output `phase3c/work/cx_d23_s154` |
| Load | title → Continue → load list shows **Alcamoth, Lv 51 Melia, 22:04, Melia's portrait** (picture from the template, documented) → Yes → "Load Complete" → field: Melia, HP 2833, in the corridor; the story marker straight ahead (78 units) |
| Action | circle pad forward ~10 s (marker 78 → 25 → trigger) — no warp on the 3DS; A every 1.2 s through the scene |
| Game event | Melia's scene with Yumea (captures t7_trigger, t8_scene_20); control returns in the palace hall, story marker 831 units away (the audience) |
| Save | menu → System → Save → slot 1 → "Overwrite save data?" Yes → **Save Complete**, play time 22:08, new 3DS thumbnail (palace hall) |
| Game-written 3DS save | **scenario 156**, party [Melia], same position as the DE and Wii 156 saves; **the same 6 flags as the DE and Wii games** |
| Back to DE | 3DS → DE with the record onto the DE 154 save: gameplay state = Monado's own 156 save except Shulk's palette[0], clock, play time; all 126 materials back from the record; every DE-only character field equal to Monado's 156 save |
| Safety | private portable Azahar copy, 149 live Azahar/Citra files hashed before/after (unchanged), 3C protected manifest unchanged |

### X2 — x2_s156_reload: cold reload on the 3DS

A fresh Azahar session loaded the 3DS game's 156 save: load list shows the 3DS game's own thumbnail (palace hall), Lv 51
Melia, 22:08; the field resumes in the palace hall with the next objective marker (831). Protected manifest unchanged.

## Summary per game version

| Game | Legitimate story events completed after conversion (this phase) | Scenarios reached | Evidence | Save / reload |
|---|---|---|---|---|
| **DE (Monado)** | Emperor's audience (156 → 158, Melia → Shulk alone); friends + Alvis (158 → 160, party re-forms to five); after a Wii trip: audience again (156 → 158); late game: Valak Mountain (232 → 233) | **160** main line; 233 late | captures c1, c4, c9, c10, c11, c5, L1; autosaves; checkpoint deltas | autosaves 158, 160; 160 reloaded, saved normally (c10) and cold-reloaded (c11) |
| **Wii (Dolphin)** | Melia reaches the palace (154 → 156) on a DE → Wii converted save | **156** | NAND output, flag comparison with the DE event | in-game save; cold reload + save (d2); back to DE and continued in Monado to 158 |
| **3DS (Azahar)** | Melia reaches the palace (154 → 156) on a DE → 3DS converted save | **156** | captures x1, x2; flag comparison | in-game save; cold reload (x2); back to DE |

**Remaining untested transitions:** 160 → 162 (Eryth Sea, repair worker), Fiora's return (refused for DE), the
Mechonis/endgame chapters, Future Connected, quest-gated steps such as 233's Magma Rock; any event on real hardware.
