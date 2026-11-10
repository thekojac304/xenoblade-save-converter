# Known limitations (XC Save Converter 3E-rc1), ranked by impact

3E keeps the 3D application and Sync Hub and adds the translation of **stored equipment** - the gear (and socketed
gems) the games keep for party members who are away in a story event - between the Wii, the New 3DS and the DE,
validated in reunions played by the Wii, 3DS and DE games (`REUNION_VALIDATION.md`). It also fixes a 3DS transcoding
defect (D3). The 3D copy of this file is in `phase3e\docs\previous_3D`. Mapping: `STORED_EQUIPMENT_MAPPING.md`.

## What 3E changed in this list

| Item | 3D | 3E |
|---|---|---|
| Saves made while party members are away in a story event (Alcamoth 154-158, Fallen Arm 269-288) | refused (L-E) | **converted**, stored gear and gems included; the Wii, 3DS and DE games gave the returning characters exactly their own gear in played reunions |
| Fiora's later form away (story 288) | refused | still refused (no reunion with her stored gear could be played) - L-J |
| 3DS staged-gem links | byte-swapped by the 3A transcoder (no effect before 3E: no save had any) | fixed (D3) |
| Returning a file exported by 3C/3D during a split | kept the DE's stored gear | same (3-way: the DE's entries are kept when the Wii/3DS session did not change the stored gear) |

## New in 3E

| # | Limit | Detail | Severity |
|---|---|---|---|
| L-J | **Fiora's later form away (288) is refused** | Same table and routine, but no reunion with her stored gear was reachable in the emulators. Convert after the reunion (291) or play the split on one platform. | Medium (one chapter) |
| L-K | **Stored items carry no Wii-only header bits** | The age byte and low header bits of a staging record are written as 0; the games rebuild the item at the return and do not use them (verified by the reunions). | Cosmetic |
| L-L | **More than 8 socketed gems stored for one character cannot go to the Wii/3DS** | The Wii keeps 8 per absent character; such a DE save is refused (never seen in real saves: maximum 6). | Low |
| L-M | **Fallen Arm reunions not played** | 269-291 translate exactly in every direction (static, all genuine saves), but those reunions themselves were only played for Alcamoth (156 -> 158 -> 160). | Low |

## What 3D changed in this list (L-E superseded by 3E)

| Item | 3C | 3D |
|---|---|---|
| Fiora's later form (character 8) in the party | refused in every direction involving the DE | **converted** from scenario 275 (era rule from the party journal); loaded, viewed and saved by the Wii (Dolphin) and 3DS (Azahar) games, returned to DE and cold-loaded by Monado |
| Character 3 in a party from 275, or 8 before 275 | (8 refused) | refused - 3 is never substituted for 8 or back |
| DE save from a story split (members away, gear stored by the game) | converted; their stored gear silently replaced by the destination's | **refused** with their names (D2) unless the destination stores the same gear or is the playthrough's own save |
| Early 3DS/Wii base below story 20 used for a later save | Shulk could keep arts flag 0 -> 3DS crash / Wii hang at Fallen Arm | fixed (D1) |

## New in 3D

| # | Limit | Detail | Severity |
|---|---|---|---|
| L-E | **(3D; superseded in 3E)** Story splits cannot be converted (D2) | While main characters who have joined are away in a story event (public saves: Alcamoth 154-158 - Melia or Shulk alone; Fallen Arm to the reunion 269-288), both games keep their equipment in a stored-equipment table (DE 0x3BB50; Wii/3DS staging slots 150+id) and give it back at the reunion. The converter does not translate that table, so such saves are refused (the DE scan of 359 public saves: only 269-288 in that archive; the 3C story fixtures 154-158 too). Convert before the split or after the reunion, or play through it on one platform. A return to the playthrough's own save is allowed (its stored gear is kept). | **High** for players in those chapters (temporary) |
| L-F | **Reunion events not played on the Wii/3DS** | Fiora's rejoin (269 -> 276) and the 288 -> 291 reunion were not reached on the Wii/3DS (navigation); the post-event states were validated instead. | Medium |
| L-G | **Record 3 after 275 on a foreign Wii base** | For a DE-native playthrough exported after scenario 275, Fiora's retired record 3 keeps the base's values on the Wii; the games never show it again and the DE's own record 3 returns from the sidecar. | Cosmetic |
| L-H | **Wii skill ids of a game-written post-rejoin record 8 unknown** | The Wii keeps the converter's own-skill ids (176+) for record 8 and mirrors them into record 3; a genuine Wii save written at the rejoin was not available. A record 8 holding Fiora-3 ids (51-75) is refused, not guessed. | Low |
| L-I | **The 3DS raises skill-link unlocks on viewing the skill screens** | After opening Fiora-8's Skill Trees, nine unlock levels went up (including Fiora-8 slots); they return to DE as raised (limitation 5). | Cosmetic |

## What 3C changed in this list (unchanged in 3D)

| Item | 3B | 3C |
|---|---|---|
| Story after DE → Wii | never played | **played**: 154 → 156 on the Wii game, saved, reloaded, back to DE equal to the DE's own result |
| Story after DE → 3DS | not played | **played**: 154 → 156 on the 3DS game, saved, reloaded, back to DE equal |
| Wii → DE story coverage | 150 → 156 | **150 → 160** (audience, party change to Shulk alone, talks, party re-forms), plus 232 → 233 after a Wii trip |
| DE favourite marks and other DE-only item bytes | lost for items that moved slot; could go to an identical replacement | follow the physical item; see the new limit L-A below |
| Unplayed DE → Wii/3DS → DE return with overflow/compaction | refused | byte-identical |
| Expert Mode highest-level EXP after EXP earned on the Wii/3DS | kept the old value | moves as the DE game moves it |
| Wii flags 0x352C–0x36CF | meaning open | the DE has no storage for them; normal Wii state (the user's own save sets two on travel); low risk |

## New in 3C (unchanged in 3D)

| # | Limit | Detail | Severity |
|---|---|---|---|
| L-A | **Ambiguous items keep no DE-only bytes** | After Wii/3DS play, the newest surviving item of an inventory pocket that changed, and a material/collectable stack that was added to, cannot be told apart from an identical replacement in the same slot. Their favourite mark, list-crystal "named" byte and residue bytes are dropped (reported in the conversion log as `uncertain`), never guessed. Items obtained on the Wii/3DS have no DE-only data. | Low |
| L-B | **Purpose of some preserved bytes unidentified** | list-crystal `+0x18` (1/2) and the Wii equipment header bits (0/1/2) and crystal `+0x16` are preserved for the same item but their effect in game is not known. | Low |
| L-C | **Story coverage is a sample** | Played after conversion: DE 156 → 158 → 160 and 232 → 233; Wii 154 → 156; 3DS 154 → 156. 3D: post-rejoin states 276-291 loaded, saved and returned on all three games. Not played: Eryth Sea after 160, the rejoin/reunion events on Wii/3DS, the Mechonis and endgame chapters, Future Connected, quest-gated steps. | Medium |
| L-D | **Platform behaviour differences remain** | e.g. the DE story event 154 → 156 sets Shulk's palette slot 0 to 2, the Wii event leaves 1 — the converter carries whatever the played game wrote. | Cosmetic |

## New 3DS (3A)

| What | Detail | Severity |
|---|---|---|
| **No real New 3DS tested** | All 3DS evidence is from Azahar (isolated copy, Vulkan). The `checkpointÌonv_...` folder is built to Checkpoint's backup shape (a complete save archive) but no restore on hardware was performed [untested]. Test with a backup first (RELEASE_READINESS.md). | **High** until tested |
| Only the USA version v1.0 was available | Other regions/updates were not examined. The converter checks the save format (header, sizes, checksums, decoding) but not the region. | Medium |
| Story progression after a conversion: one event played | 3C: a DE -> 3DS converted save played the 154 -> 156 event in Azahar, saved and reloaded [game]. Other transitions on the 3DS: not played. | Low-Medium |
| DE -> 3DS: inventory capacity comes from the 3DS destination save | A 3DS save from an earlier chapter (fewer characters joined) holds fewer items; the converter stops and offers to keep the extra unequipped items in the record (they return in DE) [static + game]. Prefer a 3DS save from a similar chapter. | Low |
| DE -> 3DS: Wii-only data the DE does not have comes from the 3DS destination save | e.g. staging gear of characters who have not joined yet (2H rule for a "foreign base"). | Low |
| Character stats and equipment caches are rebuilt for the 3DS | The 3DS uses the saved values directly (the Wii recomputes). The converter computes them exactly as the game's level-up and equipment routines do; it changes nothing in a save the 3DS or Wii wrote itself, but it does set current HP to maximum when a stale block is rebuilt [code + game]. | Low |
| Load-menu picture and save time of a converted 3DS save | The picture and the shown save time come from the 3DS destination save until the game saves again; area, level, party and play time are correct [game]. | Cosmetic |
| Five save regions have inferred types | GAME 0xB2A8-0xB2B8, 0xD22C-0xD25C, 0xF3F0-0xF410 and character +0x1A0-+0x1F4: carried reversibly, meaning on the other platform inferred from data (zero or identical defaults in all samples) [data]. No game run showed a problem. | Low |
| 3DS `specialmode` file | Special Mode / extras, not a playthrough: not converted (kept unchanged in the Checkpoint folder). | - |
| Fiora's second form / guests | Carried between Wii and 3DS (lossless). Towards DE: character 8 converted from 275 (3D); guests refused. | Low |
| Junk bytes between Wii save sections | The Wii leaves memory leftovers outside every section; they are not data and are not carried to the 3DS (a Wii -> 3DS -> Wii trip writes zeros there). | - |
| GUI tested on this PC only | As 2H; the 2H display tests pass on the real display, 4 of them fail only under an off-screen Qt platform (same for the 2H GUI). | Low |

## Wii <-> DE (2H text, unchanged)

2H-rc1 simplifies the desktop application. **The conversion engine is unchanged** (2F-rc1 engine; output
byte-identical to the 2G release and, apart from the version string in records, to 2F), so every engine limitation
below applies to the GUI and the CLI alike. Application limitations come first.

## Desktop application (2H)

| What | Detail | Severity |
|---|---|---|
| "Same playthrough without a record" is a similarity check | When no conversion record matches, the converter compares the story/quest flags of your two saves. At 80 % or more in common (measured: one playthrough ≥ 93 %, different ones ≤ 49 %) it stops and asks (find the record, or start fresh). Two different playthroughs that happen to be at the same point could trigger the question; a lost record for saves that drifted far apart would not. Either way nothing unsafe is written: a first conversion never reuses the destination save's progress. | Low |
| History search looks in fixed places | Next to your save (and one folder down), one folder up, the destination save's folder, and the output folders you used (two levels down; at most the 60 newest records). A record kept elsewhere: **Find record…** or Advanced → Choose a record file. | Low |
| Suggested file name checks only the destination save's folder | It picks a name not used next to the step-2 save. If you install into a different folder, check names there. | Low |
| Tested on this PC only (Windows 11) | Light and dark at Qt scale 1.0 / 1.5 / 2.0, windows 480×420 to 1920×1080. No physical high-DPI monitor, no Windows 10, no screen reader; Explorer drag-and-drop simulated with Qt events. | Low |
| The preview is one line | Version, area, play time and leader level only (the full read-out is in Advanced → Tools → Save inspector). DE-only areas show "Unknown area"; the chapter is not shown because no verified mapping exists. | — |
| About 100 MB, unsigned, no installer | Windows SmartScreen may warn on first start. | Low |
| "Create tables" exercised through its input checks only | It runs the 2F table dump with an explicit output folder. | Low |
| Settings in the registry | `HKCU\Software\XCSaveConverter` (game-data folder, output folder, folders used before). Delete the key to reset. | — |

## Engine (unchanged from 2F-rc1)

Evidence labels: **[game]** observed in an isolated Monado or Dolphin run · **[code]** read from a game executable ·
**[data]** measured on real saves or game tables · **[static]** converter tests only (synthetic fixtures) ·
**[untested]** never exercised · **[hypothesis]**.

Severity: **High** = can block your normal use or lose progress if ignored · **Medium** = visible but recoverable ·
**Low** = cosmetic or edge case.

## Refused by design (the converter stops with an explanation; nothing is written)

| What | Why | Severity |
|---|---|---|
| A guest (9–13) in the party; character 8 before scenario 275 or character 3 from 275 | Guests exist only in scripted battles (never in a saved party in any real save); the Fiora records follow the era rule (`CHARACTER_STATE_MATRIX.md`). | Low |
| Main characters away with stored gear (story split, D2) | See L-E. | **High** (temporary) |
| DE save format v7 (game 1.x / Switch 1.x saves) | Re-import needs v10. Load and save once in DE 2.0 / Monado (verified lossless on 6 real saves [game]). | Low |
| DE maps the Wii does not have (`ma2501`, `ma2601`, `ma2701`, `ma4001`, Future Connected) | No Wii map to place the party in. Move to a shared map first. | Medium |
| Future Connected in progress | DE-only content. | Low |
| Inventories larger than the Wii save can hold | Use `--overflow sidecar` (extra unequipped items wait in the sidecar and come back). [static + game: s232, 46 items] | Low |
| Impossible values (EXP ≥ next level cost, coins > 999, invalid quest bytes, dangling references, damaged containers, inconsistent sidecars) | Never repaired or guessed. | — |
| DE states the Wii → DE mapping would not accept back (e.g. a gem whose chance is not the table's) | The export would be a one-way trip. | Low |

## High impact

1. **Story progression after a DE → Wii export: one event played** [game, 3C].
   - The Wii game played 154 → 156 on a converted save (same flags as the DE event), saved, cold-reloaded; back to DE
     it equals the DE's own 156 save and continued 156 → 158 in Monado. Other Wii story transitions: not played.
2. **Wii → DE story is verified from scenario 150 to 160** [game, 2E + 3C], and 232 → 233 after a Wii trip [game, 3C].
   Later chapters rest on the static checkpoint matrix (game-generated DE saves at story 20, 206, 232, 241, 258, 269
   round-trip exactly) [static on real data].
3. **Use the newest sidecar, and give the current save of the other game.**
   - The converter detects an old sidecar when the other save already holds the newer progress [static].
   - With `--no-current-…` it trusts your statement. An old sidecar can then bring back DE-only items you sold.

## Medium impact

4. **Wii 1-bit flags `0x352C–0x36CF` have no DE storage** [code + data + game, 3C].
   - The Wii has 11,440 one-bit flags; the DE inserted 500 new ones in an 11,520-flag field, so the Wii's last 420 fall
     off the end. The DE cannot depend on them.
   - They are normal Wii state: the user's own unconverted save, skip-travelled to Colony 9 and Frontier Village in
     Dolphin, gets `0x36C5`/`0x36C7` from the game itself (3C run dD); 0 of 420 are set in the user's 22 h save.
   - They stay in the Wii file via the sidecar lineage, are never sent to DE, and are 0 on a foreign base — the state
     the user's save had before the visit; the game sets them again on arrival. Individual meanings: unknown.
   - The neighbouring block **`0x3440 + i` is Heart-to-Heart "registered"** [code: `CMenuKizunaTalk` 0x801BE4FC], DE
     `0x3634 + i`; it transfers.
5. **Skill-link slots are partly derived by the games.** Monado raised one unlock (Shulk ↔ Dunban, 1 → 2 slots) on
   loading your converted save [game]; it recomputes from pair affinity. Unlocks only ever go up. Nothing is lost,
   but a canonical comparison after a game load can show this difference.
6. **Inventory compaction.** When a DE item sits in a slot beyond the Wii's box, it moves to a free Wii slot and
   keeps that slot when it comes back. Equipment and gem references follow [static + game]. Since 3C its DE-only bytes
   (favourite mark etc.) follow it (limit L-A for ambiguous items).
7. **DE-native playthroughs need a Wii base save.**
   - Wii-only "staging" gear of characters who have not joined yet comes from the base; use a base from about the
     same chapter (a warning is printed otherwise).
   - A foreign base resets the minimap, field chests and collection-point timers [static].
8. **Award counters are lossy from DE to the Wii** (per-tier vs per-metric). With a sidecar, unchanged counters come
   back exactly; completion bits always transfer exactly [static].
9. **The Wii game rewrites inactive characters' records on load** [game]. Absent Fiora's skill object is restored
   from record 8. 2F writes both copies, so this no longer loses data (verified in Dolphin, run d2). Any other
   game-side normalisation of inactive records would be imported as Wii state.

## Low impact

10. **Item acquisition order** is the order, not the number. The Wii renumbers ages on pickup [code]. DE serials are
    preserved for items that existed at export; new items get fresh serials. A 2E-rc1 DE save shows Wii items in
    reverse "newest" order until re-converted with 2F (cosmetic).
11. **Minimap resolution differs** (Wii 24×24 cells per map vs DE ~4-unit cells). Wii → DE shows slightly more than
    walked; DE → Wii marks a Wii cell only when fully explored [static; game: maps display].
12. **Wii equipment stat caches are not rebuilt.** The Wii recomputes stats when it runs: after loading the s232
    export, the Party screen showed level-43 HP while the saved cache still held the base's values, and the game
    did not rewrite them [game]. No visible effect.
13. **Clock seconds and the Wii year counter are not transferred.** Hour, minute and day are [static, game].
14. **Some Wii-only bytes get defaults when rebuilt**: header low bits, crystal byte +0x16, node state bytes, the
    EXP-earned counter. None is known to matter [static].
15. **The story-scene costume snapshot is not converted** (Wii GAME +0x3890, DE 0x149CB4); it affects replayed
    cutscene outfits only [static].
16. **Save thumbnails are not regenerated.** The games rewrite them on the next save [game].
17. **Expert Mode with a level-down in progress** is tested with a synthetic edit of a game-generated Expert save
    only. Real Expert data (reserve EXP pool, highest level) from six game-generated saves round-trips exactly
    [static on real data].
18. **Symbolic-link output paths** are tested only through junctions on this PC (symlinks need Developer Mode);
    the guard resolves both.

## Not tested at all

- A full Wii or 3DS quest completion after an export; Wii/3DS story transitions other than 154 → 156.
- The rejoin and reunion events themselves on the Wii/3DS (L-F); guest party members (refused).
- Completing a gem craft in either game, then converting.
- A real Wii item pickup followed by re-import. The aging rule is read from code [code]; the re-import logic is
  tested with that rule [static].
- Saves with a full 150-item equipment box on the Wii.
