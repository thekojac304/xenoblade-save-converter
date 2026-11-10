# Known limitations (XC Save Converter 3A-rc1), ranked by impact

3A adds Xenoblade Chronicles 3D (New 3DS). The Wii <-> DE engine is the unchanged 2F/2H engine (identical output for
identical inputs), so every 2H limitation further below still applies to Wii <-> DE and, through it, to DE <-> 3DS.

## New 3DS (3A)

| What | Detail | Severity |
|---|---|---|
| **No real New 3DS tested** | All 3DS evidence is from Azahar (isolated copy, Vulkan). The `checkpointÌonv_...` folder is built to Checkpoint's backup shape (a complete save archive) but no restore on hardware was performed [untested]. Test with a backup first (RELEASE_READINESS.md). | **High** until tested |
| Only the USA version v1.0 was available | Other regions/updates were not examined. The converter checks the save format (header, sizes, checksums, decoding) but not the region. | Medium |
| Story progression after a conversion was not played | Load, menus, combat, skip travel, save and cold reload were [game]; a story scene after conversion was not triggered on the 3DS. For DE -> 3DS the 2H caveat "no Wii story event after a DE -> Wii export" applies as well. | Medium |
| DE -> 3DS: inventory capacity comes from the 3DS destination save | A 3DS save from an earlier chapter (fewer characters joined) holds fewer items; the converter stops and offers to keep the extra unequipped items in the record (they return in DE) [static + game]. Prefer a 3DS save from a similar chapter. | Low |
| DE -> 3DS: Wii-only data the DE does not have comes from the 3DS destination save | e.g. staging gear of characters who have not joined yet (2H rule for a "foreign base"). | Low |
| Character stats and equipment caches are rebuilt for the 3DS | The 3DS uses the saved values directly (the Wii recomputes). The converter computes them exactly as the game's level-up and equipment routines do; it changes nothing in a save the 3DS or Wii wrote itself, but it does set current HP to maximum when a stale block is rebuilt [code + game]. | Low |
| Load-menu picture and save time of a converted 3DS save | The picture and the shown save time come from the 3DS destination save until the game saves again; area, level, party and play time are correct [game]. | Cosmetic |
| Five save regions have inferred types | GAME 0xB2A8-0xB2B8, 0xD22C-0xD25C, 0xF3F0-0xF410 and character +0x1A0-+0x1F4: carried reversibly, meaning on the other platform inferred from data (zero or identical defaults in all samples) [data]. No game run showed a problem. | Low |
| 3DS `specialmode` file | Special Mode / extras, not a playthrough: not converted (kept unchanged in the Checkpoint folder). | - |
| Fiora's second form / guests | Carried between Wii and 3DS (lossless), still refused towards DE (2H rule). | as 2H |
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
| Fiora's second form (character 8) or a guest (9–13) in the party | No real save with Fiora rejoined was available; her record and skill-link rows have no validated mapping. Converting would silently drop her progress. | **High** for late-game players: from Fiora's rejoin on, conversion is not possible yet |
| DE save format v7 (game 1.x / Switch 1.x saves) | Re-import needs v10. Load and save once in DE 2.0 / Monado (verified lossless on 6 real saves [game]). | Low |
| DE maps the Wii does not have (`ma2501`, `ma2601`, `ma2701`, `ma4001`, Future Connected) | No Wii map to place the party in. Move to a shared map first. | Medium |
| Future Connected in progress | DE-only content. | Low |
| Inventories larger than the Wii save can hold | Use `--overflow sidecar` (extra unequipped items wait in the sidecar and come back). [static + game: s232, 46 items] | Low |
| Impossible values (EXP ≥ next level cost, coins > 999, invalid quest bytes, dangling references, damaged containers, inconsistent sidecars) | Never repaired or guessed. | — |
| DE states the Wii → DE mapping would not accept back (e.g. a gem whose chance is not the table's) | The export would be a one-way trip. | Low |

## High impact

1. **Story progression on the Wii after a DE → Wii export has never been played** [untested].
   - Covered on the Wii: load, menus, party, combat to victory, skip travel, in-game save and reload (2E);
     a late-game DE-native export at story 232 loads, saves and comes back to DE (2F) [game].
   - A Wii story event after an export has not been triggered.
2. **Wii → DE story is verified from scenario 150 to 156 only** [game, 2E]. Later chapters rest on the static
   checkpoint matrix (game-generated DE saves at story 20, 206, 232, 241, 258, 269 round-trip exactly) [static on
   real data].
3. **Use the newest sidecar, and give the current save of the other game.**
   - The converter detects an old sidecar when the other save already holds the newer progress [static].
   - With `--no-current-…` it trusts your statement. An old sidecar can then bring back DE-only items you sold.

## Medium impact

4. **Wii 1-bit flags `0x352C–0x36CF` (e.g. `0x36C5`/`0x36C7`, set when visiting Colony 9 / Frontier Village) have no
   DE slot** [game + code + data].
   - They stay in the Wii file via the sidecar lineage, are never sent to DE, and are reset on a foreign base.
   - Their meaning is not identified. No code constant, script constant or dumped table addresses them; they are
     probably set through per-map data that was not extracted [hypothesis].
   - The neighbouring block **`0x3440 + i` is Heart-to-Heart "registered"** [code: `CMenuKizunaTalk` 0x801BE4FC].
     Its DE placement `0x3634 + i` (+500) is confirmed by six game-generated DE saves [data]. It transfers.
5. **Skill-link slots are partly derived by the games.** Monado raised one unlock (Shulk ↔ Dunban, 1 → 2 slots) on
   loading your converted save [game]; it recomputes from pair affinity. Unlocks only ever go up. Nothing is lost,
   but a canonical comparison after a game load can show this difference.
6. **Inventory compaction.** When a DE item sits in a slot beyond the Wii's box, it moves to a free Wii slot and
   keeps that slot when it comes back. Equipment and gem references follow [static + game]. Its DE favourite mark is
   kept only if it did not move.
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

- Wii story progression after an export; a full Wii quest completion after an export.
- Fiora rejoined (character 8), guest party members (refused).
- Completing a gem craft in either game, then converting.
- A real Wii item pickup followed by re-import. The aging rule is read from code [code]; the re-import logic is
  tested with that rule [static].
- Saves with a full 150-item equipment box on the Wii.
