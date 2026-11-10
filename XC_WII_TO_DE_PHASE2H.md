# Xenoblade Chronicles Wii ↔ Definitive Edition: Phase 2H
## GUI simplification and usability polish (2026-11-06)

**Result:** `release_candidate_2H\XCSaveConverter\XCSaveConverter.exe` (2H-rc1). The window is now three steps and one
button: **Your save → Destination save → Save converted file to → Convert Save**. Conversion history is handled
internally; the user is asked only when the converter cannot decide safely. The engine, the save formats and every
safety protection are unchanged; GUI output is byte-identical to the Phase 2G release CLI. 2G and earlier releases are
untouched.

## What changed for the user

| Phase 2G | Phase 2H |
|---|---|
| Tabs (Convert / Advanced tools / Game data), direction radio buttons, "first time / bringing it back" choice, history picker, current-save picker, "I have not played…" box | One page. Direction follows the save. **One "destination save"** serves as the starting template of a first conversion *or* as the current save of that game on a return trip; the converter decides which. |
| Paragraph explanations of preservation files | One sentence: *"Used as a starting template. Your existing save won't be changed."* The word "sidecar" is gone; it is a "conversion record", mentioned only when the user must act. |
| Slot chosen by the user (default 01) | File name suggested so it does not clash with a save next to the destination save. |
| Stage list and long result text | Progress shown in one line under the button; a separate **Conversion complete** screen: game, new save, folder, warnings, one action **Open Output Folder**, two-sentence install guidance. |
| Advanced options inline | **Advanced…** window: options, game data, tools, log, diagnostics. |

## How history is decided (`xcservice.resolve_history`, new; reads only)

1. Look for conversion records next to the save, one folder up, next to the destination save, and in every output
   folder the app has used (`find_sidecars`, unchanged rules).
2. Exactly one matching record that is the newest of its history → **return conversion**. The destination save must be
   the save that conversion started from or a continuation of it (`scmod.descent`), otherwise **"from a different
   playthrough"**.
3. Several matching records → **ask** (dialog). Only an older one matches → **ask, warned** (and the engine's lineage
   and staleness checks still run).
4. No matching record → first conversion, **unless** the two saves look like one playthrough (≥ 80 % of story/quest
   flags in common; measured one playthrough ≥ 93 %, different playthroughs ≤ 49 %): then the user must **find the
   record** or explicitly **start fresh**. An unsafe return trip is never silently treated as a first conversion.
5. Divergence (both games played) is detected by the engine as before; the user can only proceed with the explicit
   "keep this save's progress" confirmation (the CLI's `--branch`), valid for one conversion.

`suggest_slot` (new) picks a DE slot or Wii slot not used next to the destination save. Nothing is ever written there.

## Defects found and fixed in 2H

| # | Defect | Fix |
|---|---|---|
| H1 | **2G error translation bug:** the DE → Wii divergence message ("…or this sidecar is older than your latest conversion…") was shown as *"Older preservation file selected"*; the Wii → DE one could be shown as *"different save history"*. Users would have been told the wrong reason. | stale rule matches only the engine's staleness message; lineage rule no longer matches the divergence wording; regression test with both engine messages |
| H2 | Destination-save preview ran on the GUI thread (table cache is not thread-safe) | moved to the worker thread |
| H3 | Changing the destination save while the source preview was loading discarded the source result (window stuck) | separate result counters for source and destination/history |
| H4 | Empty labels left gaps; empty file-name box before a save was chosen; window taller than its content | labels hide when empty; file-name row appears with the direction; default size 700×600 |
| H5 | Main action not prominent; disabled accent button looked clickable; accent colour did not follow a live theme switch | accent-filled primary button with muted disabled state and focus ring, re-styled on colour-scheme change |
| H6 | Live-folder warning for the output location appeared only after a valid save was chosen | output folder checked at once |
| H7 | Convert button wider than the step fields; Alt+O clash in Advanced | aligned; mnemonics unique (tested) |

## Validation

| Check | Result |
|---|---|
| Converter regression 2C–2F + 2G service + 2H service (unittest) | 136 tests OK (1 skipped, as since 2F) |
| GUI tests (pytest-qt; all 15 required areas + parity, wording, mnemonics, advanced, first run) | 30 passed |
| GUI output vs CLI (same inputs) | byte-identical folders: first Wii → DE, first DE → Wii, automatic return trips both ways, ambiguous choice, divergence with explicit choice, "no current save" |
| GUI output vs frozen 2F-rc1 code | saves and companion files byte-identical; records differ only in the converter version |
| GUI output vs **2G release `xcconv.exe`** | 4 / 4 byte-identical (first both ways, return both ways) |
| Packaged app, clean folder, no Python on PATH | 20 / 20 checks, including starts at scale 1.5 and 2.0 |
| Visual review | light and dark × 100 / 150 / 200 %, 480×420 – 1920×1080; issues H4–H7 fixed |
| Protected files / earlier releases | 106 / 106 protected files unchanged; 2F (69) and 2G (332) release files unchanged. Two files were **added** to Monado's live `save_0` on 2026-11-06 21:09 (`bfsgame01.sav` = the converted checklist save `1028f718…`, and its `.tmb`); not written by this phase (the converter refuses that folder) — apparently the manual install from the 2G checklist. See `GUI_TEST_RESULTS.md`. |

The engine (`convert`, `de_to_wii`, `reimport`, `canon`, `sidecar`, `safeio`, …) and the CLI were not changed in 2H;
`CONVERTER_VERSION` stays `2G-rc1` so conversion records and manifests stay byte-identical to 2G. The app reports
`2H-rc1`.
