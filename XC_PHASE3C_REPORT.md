# Xenoblade Chronicles save converter — Phase 3C

**DE metadata preservation, automated story progression and fidelity hardening.** 2026-11-08, autonomous session.
Release candidate: `release_candidate_3C\` (XC Save Converter **3C-rc1**, Sync Hub + converter). `release_candidate_3B\`
and every earlier release candidate are unchanged (protected manifest of 1,679 files, checked before and after every
emulator run and at the end).

Plain-language summary: `PHASE3C_SUMMARY.md`. Details: `DE_METADATA_FIDELITY.md` (Part A), `STORY_PROGRESSION_TESTS.md`
(Parts B/C, chronological evidence), `GAMEPLAY_COMPATIBILITY_MATRIX.md`, `REGRESSION_RESULTS.md`,
`KNOWN_LIMITATIONS.md`. Progress log: `phase3c/CHECKPOINT.md`.

## 1. Results at a glance

| Goal | Result |
|---|---|
| DE-only per-item metadata (3B finding B3) | **Fixed.** Root cause found (export compaction + same-slot-only restore). Item-instance correspondence (`tools/itemcorr.py`): every DE item record returns byte-identical through a real 3DS game session (176/176 DE-only crystal entries; 3B: 90). Never revives disposed items, never moves a mark to another copy, refuses to guess where the save cannot tell an item from an identical replacement. |
| A mis-association hazard in 3B | **Fixed.** 3B gave an item's old DE record (favourite included) to an *identical replacement* in the same slot; DE → Wii likewise kept stale Wii-only item bits. Both now follow the physical item (Wii: order chain; DE: acquisition serial). |
| Unplayed return refused (3B finding B2) | **Fixed** in the manual converter: DE → Wii/3DS → DE with compaction/overflow now returns the original byte for byte. |
| Expert Mode bookkeeping after Wii/3DS play (new, "E1") | **Found with real game saves and fixed**: the highest-level EXP now moves as the DE game moves it. |
| DE story beyond 156 | **Scenario 156 → 158 → 160** in Monado through the game's own events (audience; talking to the friends; Alvis; the party re-forms Shulk alone → five members); 160 reloaded in a new process, saved normally and reloaded again (c11). |
| "Scenario 157 blocker" | **Explained**: a 2E harness artefact (the tour jumped away mid-audience after a fixed 60 s). 157 has no own trigger; 158 is triggered by talking to the friends, not by a coordinate. |
| Wii story after a DE → Wii export (never played before) | **Played**: converted DE 154 save → Dolphin: the Wii game ran the 154 → 156 event, changed exactly the same 6 flags as the DE game, saved, cold-reloaded; back in DE it continued 156 → 158 to the same state as the pure-DE line. |
| 3DS story after DE → 3DS | **Played**: the same converted 154 save in Azahar: the 3DS game ran 154 → 156 (same 6 flags), saved in-game, cold-reloaded; back in DE = the DE game's own 156 state. |
| Later-game transition | 232 → 233 (Valak Mountain) in Monado on a save that had gone DE → Wii → *the Wii game* → DE. |
| Wii-only flags 0x352C–0x36CF | **Explained structurally and empirically**: the DE dropped the Wii's last 420 one-bit flags (500 new DE flags inserted inside an 11,520-flag field); the user's *unconverted* save sets 0x36C5/0x36C7 itself on travel → normal Wii state; low progression risk. |
| Regression | 2H 136, 3A 41, 3B 65, 3C 21 unit tests; GUI 18 + 39; package tests 3C 8/8, 3B 19/19, 3A 32/32. |

## 2. Part A — DE-only metadata fidelity

### A1. The data loss, exactly

DE item records hold bytes the Wii/3DS records do not (full table: `DE_METADATA_FIDELITY.md` §1):

* `+0x11` **favourite mark** — read only into the item-list UI entry (DE code `0x3FA2F4`/`0x3FA404` → `0x4C2EB0`); cleared by
  item-add (`0xBF480`). Presentation/inventory management; no gameplay read found (not proven absent everywhere).
* crystal `+0x18` for **list crystals** ("named", 1/2; 58 of 713 real list crystals = 2) — the Wii has no field for it;
  purpose unidentified, treated as meaningful and preserved.
* `+0x0A..0x0B`, `+0x12..0x13`, unused crystal effect slots — **never initialised by the game**: item-add copies a
  record from a caller's stack buffer (`0xBF454..0xBF46C`), so these are stack leftovers (same multi-byte patterns on
  unrelated items in unrelated saves).

**Where it disappeared:** (1) the export moves items whose DE slot lies beyond the Wii box to free Wii slots
(compaction); (2) the Wii/3DS games never move items between slots (0 moves on every game-written pair); (3) the 3B
re-import restored a DE record only "at the same DE slot with the same content" — a compacted item never is, so it was
rebuilt from the empty-slot pattern. Measured on DE s232 → 3DS → the 3DS game's own save (a5) → DE: 104 records changed,
crystal DE-only entries 176 → 90. Serial changes did not cause misassociation (serials are mapped by order since 2F),
but the same-slot rule **did**: an identical item bought into a freed slot received the old record (demonstrated with
the frozen 3B engine).

### A2. Item correspondence (`tools/itemcorr.py`, used by `reimport.restore_item_metadata`)

1. **Export map** (DE slot → Wii slot) reconstructed from the sidecar's own snapshots with the exporter's rule and
   validated item by item (content incl. socket gems through the gem map; acquisition order). No sidecar format change;
   old sidecars work; a box that does not validate is left unresolved.
2. **Survivors** (Wii slot → same Wii slot): same item, and on *every* longest chain that keeps the exported acquisition
   order. Code evidence: the Wii makes every added or stacked-up item the newest (`0x80159024..0x80159100`), the DE does
   not re-age stacks (`0xBF564..0xBF5B4`). A replacement or a stack that was added to falls off the chain; the newest
   chain member of a changed box is indistinguishable from a replacement and stays unresolved.
3. **Restore** the original record with the Wii-owned fields from the converted record (index, quantity, serial; for
   equipment armour class, socket count, sockets). The canonical gameplay state must not change (checked every time).

Reverse direction: the Wii's own per-item bits (equipment header low 5 bits, crystal `+0x16`) are kept only for the
same DE item instance — same slot, id and DE acquisition serial (the DE never re-issues a serial, `0x9AB70..0x9AB88`).

### A3/A4. Sidecar preservation and validation

No sidecar schema change was needed: the sidecar already held both snapshots; what was missing was a correct way to
follow items through them. Verified (all on game-written saves, marks/inventory changes synthetic where no game-written
equivalent exists): unchanged and progressed returns, DE → Wii → 3DS → Wii → DE, compaction, overflow items, duplicates,
disposal, stacks used or added to, equipment changes, a 5-generation Sync Hub history with a disposed marked item and a
rollback. Expert Mode, appearance, link unlocks, DE-only flags and Future Connected counters: exact. Metadata fidelity is
reported separately from gameplay fidelity in `DE_METADATA_FIDELITY.md`.

**E1 (found in Part C):** the DE keeps a highest-level EXP value that, while no EXP is banked, moves with every EXP gain
at the highest level (+858/+661 on five characters in Monado's own 154 → 156 → 158 saves) and restarts on a level-up.
After EXP earned on the Wii, 3B's re-import kept the old value. 3C mirrors the DE rule when the pair was tracking at
export; the Wii-played 156 save, converted back, now equals Monado's own 156 save in every DE-only character field.

## 3. Part B — DE story progression (Monado)

See `STORY_PROGRESSION_TESTS.md` M1–M5. In short:

| From | Interaction | To | Party | Evidence |
|---|---|---|---|---|
| 156 (2E autosave) | warp to the EVT_sev 156 site (Audience Chamber) | **158** (157 chained) | Melia → **Shulk alone** | c1 captures: audience, guest room |
| 158 | warp beside Riki, Sharla, Reyn, then Dunban (talk; positions read from guest memory) | **160** | Shulk → **Shulk, Reyn, Dunban, Sharla, Riki** | c9: Alvis's scene, Organise Party |
| 160 autosave | reload in a new process, System → Save | 160 (manual save) | same | c10 captures of the save screens |
| 160 manual save | cold reload; stand on / walk through the EVT_sev 160 site | no event (next step: travel to Eryth Sea) | five members | c11, c12 (bounded stretch attempt) |

How the blocker was resolved: (1) the 2E logs show the 156 audience *had started* and was cut by the tour's 60 s limit;
(2) the game's own objective texts (`MNU_scenario.help` → `gb:MNU_scenario_ms`) say what each scenario waits for —
158: "Shulk needs to talk to his friends"; (3) NPC positions are not in the extracted tables, so they were read from a
guest-memory dump (`XCDE_DUMP_MEM`) — a read-only diagnostic. No scenario, flag, quest, party or event value was ever
written; `XCDE_EVENT` and the tour's `story` step were never used.

Checkpoint validation (B3 steps 1–10) is recorded per transition: start scenario, interaction, the game's autosave with
the new scenario, captures, party and map, state delta (flags, levels, items, quests), normal save, reload, and the next
objective from the game's event table.

## 4. Part C — reverse-conversion story tests

### 4.1 DE → Wii (Dolphin)
Converted Monado 154 autosave → Wii (base: the user's own story-150 save). In Dolphin the stick held forward walked Melia
into the EVT_sev 154 trigger; the Wii game played the event, saved in-game (story 156, the same position as the DE's 156
autosave), and changed exactly the same 6 flags as the DE game did for this transition. Cold reload in a new Dolphin
process: state unchanged except clock/time. Back to DE (re-import with the export's sidecar): gameplay state equal to
Monado's own 156 save except Shulk's palette slot 0 (the *DE* event changes it, the Wii event does not), clock and play
time; DE-only data restored. That DE save then played 156 → 158 in Monado to the same state as the pure-DE line (c5).

### 4.2 Later-game transition
s232 (Expert Mode, full party): DE → Wii → the Wii game's own save (2F) → DE → Monado: the Valak Mountain event
(Alvis at the Sealed Tower) → 233.

### 4.3 DE → 3DS (Azahar)
The same Monado 154 autosave converted DE → 3DS (template: the user's own early 3DS save; extra materials parked in the
conversion record). The 3DS load list showed Alcamoth / Lv 51 Melia; with the circle pad held forward Melia reached the
trigger, the 3DS game played the scene with Yumea, and the game saved in-game (play time 22:08, its own thumbnail):
scenario 156, the same six flags as the DE and Wii games. A fresh Azahar session reloaded it (marker to the audience
active). Converted back with the record: the DE game's own 156 state except palette[0]/clock/time, all 126 materials
returned, every DE-only character field equal. 3DS-specific caches (stats, equipment) were rebuilt by the converter
at export (3A routine) and the 3DS game used them without complaint (HP 2833 shown, Lv 51).

## 5. Part D — Wii-only flags

**What they are structurally.** The Wii keeps 11,440 one-bit flags (ids 0xA20–0x36CF). The Definitive Edition keeps
11,520 and inserted 500 new ones inside the range (300 at 0x30C8, 200 at 0x3550 — DE-only blocks, both used by DE
saves: 35–81 flags set in the six real DE saves at 0x3550+). Every Wii flag from 0x3424 on therefore sits 500 higher in
the DE, and the Wii's **last 420 flags (0x352C–0x36CF) have no DE storage at all**. They are the tail of the block
that starts at 0x3440 (Heart-to-Heart "registered" = 0x3440 + JNL_kizunalist row, rows < 84, DE 0x3634 + row).

**Who sets them.** Of the 83 call sites of the Wii flag setter (0x8009D9F0), none uses a constant or base in this
range (`phase3c/scripts/d_flagsites.py`); the dynamic sites take ids from script/table data (e.g. 0x80124B24 is
region affinity 0x21+id). Data:

| Save | set in 0x352C–0x36CF |
|---|---|
| the user's own Wii save (22 h, story 150) | **0** |
| the user's story-18 Wii save, another playthrough (story 6), the 3DS save (story 8), 3B Dolphin save | 0 |
| 2E d6: a converted save, skip-travelled to Colony 9 and Frontier Village in Dolphin | 0x36C5, 0x36C7 |
| **3C dD: the user's UNCONVERTED story-150 save, same skip-travel route in Dolphin** | **0x36C5, 0x36C7** |

So they are ordinary Wii game state, set by the game itself on arrival in Colony 9 / Frontier Village at this point
of the story (with map flags 0x31FD/0x3200 and an award counter), not something the converter caused. The DE, on the
same trip (2E f3), sets nothing comparable.

**Impact on progression.**
* DE: cannot depend on them (no storage); Monado advanced the converted story 150 → 158 in this phase.
* Wii/3DS: the converter keeps them exactly within the W family (Wii ⇄ 3DS lossless) and across DE trips through the
  sidecar lineage (the Wii base keeps them); a first DE → Wii export on a foreign base writes 0, which is the state the
  user's own save had before the visit, and the game sets them again on arrival (observed in dD).
* The Wii story event after a DE → Wii export (Part C, 154 → 156) ran with all 420 at 0 and changed exactly the same
  flags as the DE game.

**Unresolved:** the meaning of each individual flag (420; two observed). Classified *low risk*: normal Wii state the
game recreates, never read by the DE, not touched by any fixed-id code path.


## 6. Part E — Sync Hub regression

The hub code is unchanged; its conversions use the 3C engine. Verified: alternating Wii/DE/3DS generations with item
disposal and marks (5 generations), unchanged re-saves (in sync), rollback (exact), divergent branches, interrupted
publication, transactional failure injection and process kill (the retained 65 hub tests). A stale anchor sidecar cannot
revive a deleted item: the correspondence only ever restores bytes onto items the current Wii/3DS save holds.

Parity with the frozen 3B engine (`phase3c/scripts/e_parity_3b.py`): first conversions both ways on 8 real saves, a 3DS
export and a DE → Wii return are byte-identical; Wii/3DS → DE returns differ only inside DE item records (identical
gameplay state); unplayed returns 3B refused now succeed; the E1 case differs only in the highest-level EXP word. Lineage
checks, staleness/divergence rules and transactional guarantees are untouched.

## 7. Defects found and fixed in 3C

| # | Defect | Found by | Fix | Test |
|---|---|---|---|---|
| A-1 (B3) | DE-only per-item bytes lost for items the export compacted | 3B; root cause 3C | item correspondence | `test_b3_real_3ds_session…`, 5 more |
| A-2 | old DE record (incl. favourite) given to an identical replacement in the same slot | 3C analysis, shown with frozen 3B | survivors on the order chain | `test_identical_replacement_in_same_slot_gets_no_mark` |
| A-3 | DE → Wii kept stale Wii-only item bits for a replaced DE item | 3C analysis | DE serial identity | `test_identical_replacement_gets_fresh_record` |
| A-4 (B2) | unplayed return with compaction/overflow refused | 3B; fixed 3C | read-back through the export map | `test_unchanged_wii_is_byte_identical`, 3DS variant, package test |
| A-5 | sidecar `deferred` keys (strings after JSON) ignored by the DE → Wii read-back helper | 3C test | keys normalised | (covered by A-4 tests) |
| E1 | Expert Mode highest-level EXP not advanced by EXP earned on the Wii/3DS | **game saves** (Dolphin + Monado) | DE tracking rule | `test_return_to_de_reproduces_the_de_games_state_incl_expert_pair` |
| H-1 | 2E "157 blocker" | 3C log review | (harness) single warp, no fixed scene limit | M1 |
| H-2 | Dolphin captures missing | d1 | `HotkeysRequireFocus = False`; window capture option | — |

## 8. Unresolved risks

See `KNOWN_LIMITATIONS.md`. Most important: Fiora's rejoin (character 8) is still refused for DE; no endgame event was
played; the newest surviving item of a changed box and stacks added to on the Wii/3DS keep no DE-only bytes; real
devices (New 3DS, Android Dolphin) remain untested; the meaning of most Wii-only high flags is unknown (low risk).
