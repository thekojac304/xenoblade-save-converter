# Sync Hub history design (Phase 3B)

How the Sync Hub stores generations, proves ancestry, detects conflicts, rolls back and recovers from crashes.
Code: `phase3b\src\xcsync\` (`store.py`, `scan.py`, `sync.py`). Engine (unchanged): `tools\` (2H) and
`phase3a\src\` (3A).

## 1. Folder layout

```
<Sync Hub folder>\
  xcsync-hub.json                 marker (schema xc1-synchub/1, hub id); a folder without it is never a hub
  metadata\devices.json           device profiles: stable random id, display name, platform, incoming folder,
                                  slot, enabled, ready-folder name (fixed at creation; renaming a device keeps it)
  metadata\sync-state.json        THE commit pointer: current generation, SHA-256 of its generation.json,
                                  committed-generation list (number, hash, kind, time)
  metadata\sync-state.prev.json   the pointer before the last commit
  metadata\hub.lock               only while a Sync / publication / rollback runs
  templates\wii|de|3ds\           verified copies of the starting saves + template.json (hashes; 3DS: full archive)
  incoming\<device>\              default incoming folder (a device may point anywhere else, read-only)
  ready\<device>\                 published files for the device + READY.json + HOW_TO_INSTALL.txt
  history\gen-NNNNNN\             one immutable folder per committed generation
  history\interrupted\            prepared generations that never became current (set aside, not deleted)
  staging\                        transactions in progress (tx-*) and publications in progress (pub-*)
```

Device identity comes from the profile, never from a folder name. Incoming folders are only read.

## 2. A generation

`history\gen-NNNNNN\`:

| Path | Content |
|---|---|
| `generation.json` | schema `xc1-generation/1`, number, kind (`start`, `sync`, `branch`, `rollback`, `restart`), parent, previous, source (device, platform, file hash, progress key, summary), outputs (per platform: files + SHA-256 + how made), family images, **anchors**, conversions (direction, mode, anchor), validation checks, notes, snapshots, branch choice, partial/blocked, engine versions, `files` (SHA-256 of every file in the folder) |
| `source\<name>` | exact copy of the chosen save |
| `outputs\wii\monado01` (+banner.bin) | Wii save |
| `outputs\de\bfsgame.sav` (+.tmb) | DE save |
| `outputs\3ds\monado01`, `outputs\3ds\archive\*` | 3DS save + the other slots for a complete Checkpoint backup |
| `family\wii.bin`, `family\de.sav` | the state of each family (see 3) — what later saves are compared with |
| `sidecars\*.sidecar.json` | the cross-family conversion sidecar made in this generation (2H format) |
| `engine\...` | the engine's own output folders (manifests, 3A records) |
| `snapshots\<device>\<hash>\<name>` | every save with its own progress seen at sync time (the unselected branches) |

The pointer stores the SHA-256 of `generation.json`; `generation.json` stores the SHA-256 of every other file.
Any edit or damage is detected before use (scan reports it; sync refuses).

## 3. Two families and anchors

* **W family**: Wii and 3DS. Same layout, lossless transcode (3A). One image `family\wii.bin`.
* **D family**: DE, which holds more (Expert Mode, outfits, DE-only items/flags, ...). Image `family\de.sav`.

Saves are only ever compared with images of their own family. Conversions between families use the unchanged 2H
engine with an **anchor**: the last save of the other family that was actually *played*, plus the sidecar the hub
made from it.

| Generation N sourced from | anchors[source family] | anchors[other family] |
|---|---|---|
| W (Wii or 3DS) | N, with the `wii_to_de` sidecar made in N | inherited from the generation the source continued |
| D | N, with the `de_to_wii` sidecar made in N | inherited |
| rollback to k | copy of k's | copy of k's |
| restart (explicit) | N | none (fresh templates) |

W -> D: `wii_to_de` re-import onto the D anchor (`--sidecar` = anchor sidecar, `--current-de` = the anchor's own DE
save, which by construction has not been played since), or a first export onto the DE template. D -> W:
`de_to_wii` return onto the W anchor, or a first conversion onto the Wii/3DS template. This is exactly the engine's
validated return trip; DE-only state survives any number of Wii/3DS generations, Wii-only state survives DE
generations. The source is never altered; the other family contributes only its exclusive state.

Example (acceptance run): gen 1 Wii -> gen 2 DE (Monado) -> gen 3 3DS -> gen 4 Wii: gens 3 and 4 both re-import onto
gen 2's DE save (the last DE save actually played), so Monado's own changes are kept.

## 4. Ancestry (scan.classify)

For a valid save `c` of family F (all comparisons within F):

1. **Hash** equals a generation's output or source: `in-sync` (current generation) or `older` (earlier one).
2. **Lineage chain** = current generation and its parents (rolled-back generations are not in the chain). For each
   generation g in the chain, newest first:
   * same progress as g (progress key equal and same place, see 5): `in-sync` / `older`;
   * `sidecar.descent(g, c)` (flags ≥ 90 % kept, items ≥ 50 %, story/play time/levels not back) **and** c contains
     the progress g added over its parent (`delta_facts`: story, flag values, level-ups, items gained; story and
     levels strictly, the rest ≥ 80 %): c continues g. If g is current: `new-progress`; else if the current
     generation already contains c's own progress and c has no more play time: `older`; else `divergent`.
3. A save that continues a generation **outside** the lineage (replaced by a rollback or by a branch choice) and
   holds that generation's own progress is `divergent`.
4. Otherwise: ancestor of the current state -> `older`; flag similarity < 0.8 -> `unrelated`; else `unknown`.

The delta check is what stops a long-played old copy from passing as newer: the 2H descent check alone accepted
`W150_LATER` (played on an old copy, more play time) as a continuation of a newer generation; with the delta check
it is `divergent` (test `test_played_on_an_older_copy_is_divergent_even_with_more_play_time`).

Play time, story or level alone never decide anything.

## 5. What is not progress

`progress_key` hashes the canonical shared state without play-time seconds, in-game clock, position and facing
(plus DE-only characters/items/flags/quest counters for DE). Position is compared separately: same map and within
5 world units = same place. Found in the acceptance run: Monado's load-and-save without moving changed the height by
0.001; that is a re-save, not progress. Save time, thumbnail, file name, Syncthing copy, emulator re-save: no new
generation, so no sync loop. A real walk (50 units in run m1) is progress.

## 6. Decision (scan.decide)

* any save still arriving (Syncthing temp file, changed during the scan, modified < 5 s ago): **waiting** - Sync
  disabled;
* no history: one distinct save -> **start** (proposed), several -> **choose-start** (explicit choice);
* exactly one distinct new-progress save and no divergent save -> **new-progress** (proposed). Copies of the same
  progress on several devices count once. Several saves of **one device** collapse to the newest only if it
  continues each of the others (descent, at least their play time, and it holds every fact the others added since
  the base generation). New progress on **two different devices** is always a choice: both were played after the
  same sync (found by the package test: a longer-played old copy "contained" a 3DS battle by EXP alone, so EXP,
  money and play time are never evidence of containment);
* two or more distinct candidates, or any divergent save -> **conflict**: no proposal, Sync disabled until the user
  chooses. Nothing is merged; every candidate is kept as a snapshot in the new generation.

## 7. Transaction (sync.sync)

Inside the lock: re-check that the history did not change since the scan; re-read the chosen file twice (must be
identical to the scanned bytes); re-validate; clean leftovers of interrupted runs (staging folders deleted, prepared
generations moved to `history\interrupted\`); build everything in `staging\tx-*` (engine calls write only there);
write; read back; independent validation (structure, checksums, references of every output; W outputs = source
state exactly; DE vs W: every non-inventory field equal, equipment compared by the items worn, inventory multiset
difference equal to the documented DE-only/overflow items kept in the history, nothing lost or duplicated);
`generation.json` with file hashes; **commit = `os.rename` of the folder to `history\gen-N`, then atomic replace of
`sync-state.json`** (the only commit point); publish.

Default all-or-nothing: if any configured platform cannot be produced (unsupported party member, missing template,
engine refusal) nothing is committed and the reason is shown per platform. An explicit "update the others only"
creates a generation marked `partial` with the blocked platforms listed; their ready folders keep the old files and
report "no output (blocked)"; the result never says "All configured platforms updated".

## 8. Publication

From the immutable generation folder into `ready\<device>\`: each file is staged in `staging\pub-*` and moved into
place with `os.replace` (atomic per file); files of the previous publication that no longer belong are removed (only
files listed in the previous READY.json — nothing else in the folder is touched); `READY.json` (generation, file
hashes) is written last. A crash part-way leaves READY.json at the old generation: the scan shows the folder as
outdated and **Finish publishing** repeats it from the generation. Publication is not atomic across devices or
volumes and says nothing about delivery: Syncthing delivers; the user installs.

## 9. Rollback and recovery

* **Rollback to k** creates a new generation N+1 that copies k's outputs, images, sidecars and anchors (history is
  append-only; N stays recoverable). Saves continuing the replaced generations become `divergent`.
* **Snapshots**: History > "Save a copy of a kept save" copies any snapshot into a new folder the user chooses.
* **Crash before the pointer** (killed process): the old generation stays current; the scan reports the interrupted
  work; the next Sync removes the staging folder or sets the prepared folder aside and numbers correctly.
* **Crash after the pointer**: the generation is complete and validated; READY.json files show which devices still
  need publishing.
* **Damaged pointer or generation**: the scan reports an error and Sync is disabled (no guessing);
  `sync-state.prev.json` and the immutable folders allow manual recovery.
* **Lock**: a second window/PC cannot sync at the same time; a lock left by a dead process on this PC is taken over;
  a lock from another PC is trusted for 6 hours.
