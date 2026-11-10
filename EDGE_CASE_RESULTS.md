# Edge-case, adversarial and property-based results (Phase 2F, converter 2F-rc1)

All runs are reproducible: seeds are fixed in the tests, and synthetic fixtures are built by `tests/p2f_util.py` from
your real saves. "Synthetic" means valid game encodings written by the converter's rules, not game behaviour.
Failing cases are minimised automatically (delta debugging) and stored in `phase2f/fixtures/`.

## 1. Probes against the frozen 2E-rc1 code (before any fix)

Scripts: `phase2f/scripts/probe_cli.py`, `phase2f/scripts/probe_data.py` (run with the snapshot tools).

| Probe | 2E-rc1 result | 2F-rc1 result |
|---|---|---|
| `--slot "00/../../escaped"` | exit 0, `escaped.sav` written outside `save_0` | exit 2, nothing written |
| Pre-existing sidecar in the output folder | exit 2 **after** the save, `.tmb` and system file were written | exit 2, folder untouched |
| `--out` through a junction into a `Dolphin\User\Wii` folder | exit 0, written into it | exit 2 |
| Truncated Wii (1000 B, half), wrong-length DE, empty file | raw `struct.error` / `ValueError` traceback, exit 1 | exit 2 with a message |
| `de-to-wii --slot <absolute path>` | file written at that absolute path | exit 2 |
| `--dry-run --report r.json` | `r.json` written | nothing written |
| Stale sidecar without `--current-de` | DE-only item the player sold came back | `--current-de` or `--no-current-de` required; with the current DE save: refused even with `--branch wii` |
| Template with reserve EXP 123,456 and cosmetics | copied into all 7 characters | cleared |
| v7 DE save → Wii → (Wii play) → DE | export OK, re-import fails ("template is not a v10 save") | export refused with guidance |
| Party with character 8 | accepted, character 8 not converted | refused |

## 2. Property and metamorphic tests (`tests/test_phase2f_properties.py`)

| Property | Cases | Result |
|---|---|---|
| Same inputs → same bytes (DE, Wii, sidecar JSON) | 1 | pass |
| Wii → DE → Wii byte-identical | monado01, monado03, 12 seeded Wii progressions (10 mutations each) | pass |
| DE → Wii → DE (foreign base, no sidecar) shared state equal | 12 seeded DE progressions | pass |
| Repeated conversion is a fixpoint | 1 + 3 extra cycles | pass |
| DE → Wii, random Wii play, re-import = Wii state; DE-only unchanged; serials unique | 12 seeds × 12 mutations | pass |
| A pickup ages every Wii item; descent and merge still work | 3 pickups | pass |
| 4 alternating generations with play on both sides | seeds 300–403 | pass |
| One change → only the corresponding canonical fields change | money, quest, flag, pickup (Wii→DE); money, level, pickup, clock (DE→Wii) | pass |

Mutation kinds: money (±), play time, level-ups (EXP 0, EXP-earned counter advanced), 1-bit flags, item pickups
(Wii aging applied, DE counter advanced), removals of unreferenced items, quest objective bytes (each game's
encoding, only for open quests), clock, art levels (both records of a talent pair).

## 3. Inventory boundaries (`tests/test_phase2f_inventory.py`)

Wii base monado01 (capacity 140 for weapons, armour and materials).

| Box | 0 | 1 | cap−1 | cap | cap+1 | cap+50 |
|---|---|---|---|---|---|---|
| weapon, head (140) | fit | fit | fit | fit | refused / deferred 1, restored | refused / deferred 50, restored |
| material (140) | fit | fit | fit | fit | refused / deferred 1 | refused / deferred 50 |
| collectable, crystal, gem (300) | fit | fit | fit | fit | refused / deferred 1 | refused / deferred 50 |
| keyitem (200), artmanual (240) | fit | fit | fit | fit | refused / deferred 1 | refused / deferred 50 |

Also verified:
- Capacity formula against code for 8 bit/bonus patterns (60, 70, 140, 170, 200, and the bonus clamp).
- An equipped weapon at DE slot 300 with a socketed gem at slot 450: both move, and every reference follows.
- Equipped items are never deferred.
- 3 / 0 sockets, built-in gem, removable gems, a loose rank-S gem at its table maximum.
- Gem rank 8 or a non-table chance: refused. A Wii gem strength above 300: refused.
- All 159 of your crystals round-trip byte for byte; an unmatched drop crystal is refused.
- A DE-only weapon is deferred when unequipped and refused when equipped.
- Quantity 0 or 100, or an unknown id: refused. Quantity 99 is kept.
- Acquisition order is preserved both ways; DE serials are unique; Wii ages are a dense 1..N.

## 4. Corruption and filesystem (`tests/test_phase2f_safety.py`)

| Input | Cases | Result |
|---|---|---|
| Wii container | truncated ×2, +1 byte, empty, wrong header, empty slot, CRC flips in GAME/ITEM, damaged section tag | all exit 2, no output, no traceback; validate exit 1 |
| Wii values with recomputed CRCs | level 0/150, EXP over next, coins 5000, guest in party, unknown item id, qty 0, equipment → empty slot | all refused |
| DE | truncated, +1 byte, header/size mismatch, v7, level 0/100, EXP over, party id 99, dangling equipment, dangling gem socket, story 0/9999, Future Connected map, invalid quest byte | all refused |
| Random bit flips (seed 2026) | 60 (1–8 bits; 30 Wii, 30 DE) | 28 converted (every output re-read and matched to its manifest), 32 refused; 0 crashes, 0 partial outputs. Which flipped bytes were inert was not analysed. |
| Failure injection | write ×3, flush, verify, rename | exit 3, no output folder, no staging left |
| Interrupted run | leftover staging folder | next run OK; `cleanup-staging` removes it |
| Paths | `Dolphin\User\Wii` (and case variants), `..` traversal, NAND `title\00010000`, folders with `xcde.exe` / `build\xcde.exe` / `Dolphin.exe` / `portable.txt` / `xcde.ini`, junction into a live-looking tree, output folder that is itself a junction, other working directory, bad slot names ×10 | all refused (or worked, for the cwd case) |

## 5. Sidecar and lineage (`tests/test_phase2f_sidecar.py`)

| Case | Result |
|---|---|
| 6-step CLI cycle twice; DE-only item parked through 2 Wii sessions per cycle | restored exactly once each time; generation 2 → 5 |
| Missing file, truncated JSON, not JSON, unknown schema, one-digit edit | refused, "nothing was written" |
| Forged fields with recomputed integrity (source hash, session id, self-parent, games, snapshot data) | refused at load |
| Wrong direction, missing `--current-de` | refused with explanation |
| Sidecar of another playthrough (your DE-native save) / another slot (monado03) | refused (not a descendant) |
| Wii save edited without fixing checksums | refused |
| Stale sidecar (generation 1 when generation 3 exists) | refused with or without `--branch wii`; the newest sidecar keeps the sold item sold |
| Divergent branches (money, items, flags, levels, a deletion on one side) | refused without `--branch`; `--branch wii` / `--branch de` keep one branch with no leakage from the other |
| Current DE save changed only in DE-exclusive fields | the newer DE-only value is kept |
| Expert switch, highest level, reserve, cosmetics, Noponstones, DE-only item and flag, FC byte; Wii level-up above the highest; Wii stack increase | all kept; Wii progress wins on shared items |

## 6. Test-harness errors found and corrected (not converter defects)

| Symptom | Cause | Correction |
|---|---|---|
| Wii → DE → Wii differed for seed 10 (3 bytes) | The mutator raised a level without updating the THUM preview level the game rewrites on save | Mutator emulates the THUM rewrite |
| Capacity tests refused for crystals / gems | Fixture crystals and gems were not table-valid (rank 0, wrong chance) | Copies of real records; gems from BTL_skill. This also exposed defect 21 (closure check) |
| An equipped item was deferred | Fixture equipped an absent character (DE never stores that) | Party members only |
| Quest 221 assumed completed | It is accepted with 2/3 objectives done | Asserts the exact values |
| Map test used minimap ids as areas | `WII_MAPS` is keyed by map id | Uses `FLD_maplist` |
| Random skill trees refused | Fixture un-learned the armour skill while the armour stayed equipped | Learned counts only increase |

## 7. Minimised failing fixtures

None remain: no property test failed after the fixes. `phase2f/fixtures/F1_bitflip_fuzz_summary.json` records the
fuzz run.
