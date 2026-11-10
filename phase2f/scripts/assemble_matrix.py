"""Write TEST_COVERAGE_MATRIX.md from phase2f/results/coverage_matrix.json (+ the generated table)."""
import json
import os

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
d = json.load(open(os.path.join(P2F, "results", "coverage_matrix.json")))
table = open(os.path.join(P2F, "results", "coverage_matrix_table.md"), encoding="utf-8").read()
suite = d["suite"]
FEATURES = """
| Feature | Proven by static checks | Proven in a game | Synthetic only | Unverified | Refused / incompatible |
|---|---|---|---|---|---|
| Wii → DE conversion (your save) | read-back, byte round trip | 2E: load, combat, travel, story 150→156; 2F: load + save of the 2F file | — | story beyond 156 | — |
| DE → Wii conversion | read-back + closure check, 6 game-generated checkpoints | 2E: load, combat, travel, save; 2F: story-232 DE save loads, saves, returns | — | Wii story events after export | Fiora (8), guests, DE-only maps, v7 |
| Re-import (3-way, sidecar) | properties, 4 generations | 2E chain; 2F story-232 cycle through both games | Wii pickups (aging rule from code) | real Wii pickup + re-import | stale / divergent without branch |
| Item acquisition order | code (aging, renumbering) | 2F file loads and saves | random pickups | DE "newest" sort viewed on screen | — |
| Inventory capacity / overflow | code formula, all boxes × 6 sizes | story-232: 46 deferred items came back after a Wii save | — | full 150-item Wii box | — |
| Equipment, gems, crystals | references, compaction, sockets, cylinders | story-232 equipment on the Wii Party screen | extreme gem values | gem craft completed in a game | invalid gem/crystal values |
| Characters, levels, EXP | boundaries | 2E: level-ups from combat | — | level 99 in a game | EXP ≥ next level, levels 0 / 100 |
| Expert Mode | real data from 6 game-generated saves round trip | story-232 cycle kept reserve / highest | level-down state | Expert menu used after conversion | — |
| Arts, skills, links, unlocks | random states | Monado recomputed one unlock (expected) | — | link costs paid after conversion | — |
| Fiora skill copy (record 8) | real saves hold the copy | Dolphin d1 (bug) → d2 (fixed) | — | — | — |
| Quests | every quest × objective × value; 90 / 221 / 287 | 2E: Quest Log coherent | partial kill progress | quest completed on the Wii after export | invalid quest bytes |
| Story / world flags | flags × 2 cycles; Heart-to-Heart block (+500) checked on real DE data | 2E story events | — | Wii story events | — |
| Wii flags 0x352C–0x36CF | kept Wii-side (lineage) | set by Dolphin in 2E | — | meaning | no DE slot |
| Clock, maps, minimap | boundaries, all 28 Wii maps | 2E: clock / minimap shown | — | — | DE-only maps |
| Sidecar safety | corrupt / forged / stale / divergent / other playthrough | — | all | — | — |
| Filesystem safety | failure injection, junction, markers, case, traversal | — | all | symlinks (need Developer Mode) | live folders |
| Packaging / CLI | clean-directory test 10/10, help, exit codes | — | — | GUI (not built) | — |
"""
runs = "\n| Run | Emulator | Isolated | Game wrote a save | Evidence |\n|---|---|---|---|---|\n" + "".join(
    f"| {r['run']} | {r['emulator']} | {'yes' if r['isolated'] else 'NO'} | "
    f"{'yes' if r['save_written_by_game'] else 'yes (new slot)' if r['run'] in ('g1_s020_v7load', 'g1_s206_v7load') else 'no'}"
    f" | `{r['evidence']}` |\n" for r in d["game_runs"])
text = f"""# Test coverage matrix (Phase 2F, converter {d['revision']})

Full suite: **{suite[0]} tests, {suite[2]}** in {float(suite[1]):.0f} s
(`python -m unittest discover -s tests -v`, log `validation/full_suite_final.log`). The 40 Phase 2C–2E tests are
included. The table below lists the 68 Phase 2F checks with their actual result from that log.

Data kinds: **game-generated** (written by Monado or the Wii game in an isolated run), **real save data** (your saves
or the public archive, unmodified), **code (static)** (executable or tables), **synthetic** (a real save with
game-plausible edits; tests logic, not game behaviour).

## Feature summary
{FEATURES}
## Phase 2F checks (actual results)

{table}
## Game runs (Phase 2F)
{runs}
The g1_s020 and g1_s206 runs saved into a new slot (bfsgame02 / bfsgame01), so the harness's slot-00 check shows no
change. The files were collected from those slots (`phase2f/fixtures/real/PROVENANCE.md`).

## Remaining gaps

- Wii story progression after a DE → Wii export; a quest completed on the Wii after an export.
- A real Wii item pickup followed by a re-import (the aging rule is from code; the logic is tested synthetically).
- Fiora's second form and guests (refused; no fixture).
- No in-game check of DE's "newest" sort order on screen.
- Symlink output paths (junctions tested).
"""
open(os.path.join(ROOT, "TEST_COVERAGE_MATRIX.md"), "w", encoding="utf-8").write(text)
print("TEST_COVERAGE_MATRIX.md written", suite)
