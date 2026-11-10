# Xenoblade Chronicles Wii ↔ Definitive Edition: Phase 2G
## Desktop GUI, Windows packaging and usability validation (2026-11-06)

**Result:** `release_candidate_2G\XCSaveConverter\XCSaveConverter.exe`, a portable Windows x64 desktop application
(PySide6 / Qt 6.12, PyInstaller 6.22) with the identical command-line converter `xcconv.exe` next to it. It converts
in both directions without a command line, reuses the 2F-rc1 engine unchanged, and writes byte-identical output to
the CLI. Release candidate **2G-rc1**; the 2F and 2E releases are untouched.

---

## 1. Architecture

```
 XCSaveConverter.exe (xcgui)          xcconv.exe / python tools\xcconv.py
   window, plain-language messages      argparse, text output
            │                                    │
            └──────────────┬─────────────────────┘
                           ▼
                 tools\xcservice.py   (NEW: the only entry point for both)
     detect · preview · validate · compatibility · wii_to_de · de_to_wii · roundtrip
     sidecar discovery / classification · output planning · stage reporting
                           │
                           ▼
   2F-rc1 engine, unchanged: convert · de_to_wii · reimport · canon · sidecar · safeio · wii_save · de_save …
```

- **No conversion logic in the GUI.** The command bodies of `xcconv.py` (2F) were moved verbatim into
  `xcservice.py` as functions taking a request dataclass (`WiiToDeRequest`, `DeToWiiRequest`) and returning a
  `ConversionResult`. `xcconv.py` is now a thin argparse front end; its options, messages and exit codes are the same.
- The service reports **real stage boundaries** through a callback: *read → check → translate → verify → write →
  final*. The GUI shows exactly these; no percentages.
- **Engine changes (all behaviour-neutral):** `paths.py` gained `set_data_dir()` (GUI-selected tables),
  `FALLBACKS` and `spec()` (spec files inside the frozen bundle); `achievements.py` reads its spec through
  `paths.spec()`; `dump_bdat.py` accepts an output folder and writes atomically; `CONVERTER_VERSION = "2G-rc1"`.
- **New in the service (not in 2F):** `detect()` (header-only format detection for drag-and-drop), `preview()`
  (display summary from the verified decoders; map names from the user's Wii `FLD_maplist`, otherwise "Unknown"),
  `find_sidecars()` / `classify_sidecar()` (discovery with lineage classification), `plan_output()` (the commit's
  path rules, without writing), `wii_compatibility()` (early Wii → DE refusal of unsupported party members).

### Parity evidence
| Comparison | Result |
|---|---|
| CLI 2G vs frozen 2F-rc1 code (`phase2g\baseline_2F`), Wii → DE and DE → Wii | saves, `.tmb`, `bfssystem.sav`, `banner.bin` byte-identical; sidecars identical except `converter_version`; manifests identical except version and sidecar hash |
| GUI vs CLI, same absolute inputs (source tree) | whole output folders byte-identical: Wii → DE first export, DE → Wii return, Wii → DE return (= original DE save), DE-native export |
| Packaged GUI vs research CLI and packaged `xcconv.exe` | whole output folders byte-identical (clean-directory test) |
| GUI Wii → DE of the user's save | SHA-256 `1028f718…` = the 2F release save loaded and saved in Monado |

## 2. The application

**Convert tab** (one scrollable page, required inputs numbered, advanced options collapsed):

- *Conversion direction*: two radio buttons, set automatically from the detected save; a mismatch is explained.
- *1. Your save*: drag-and-drop zone (files or folders; folders with several saves ask which one) and Browse /
  typed path. The preview shows save type, location, story scenario, play time, party with levels, money and item
  count. DE format v7 is explained ("load and save it once in DE 2.0 or Monado to upgrade it to v10").
- *2. Conversion history*: a plain explanation of preservation files ("sidecars"), then "first time" (starting
  save of the other game) or "bringing it back" (preservation file + current save of the other game, or the explicit
  "I have not played … since that conversion"). Discovery runs automatically on the worker thread.
- *3. Where to put the converted save*: output location (default `Documents\XC Save Converter\Converted saves`),
  slot, and the exact new folder name; checked live with the commit's rules (live game folders, junctions, existing
  files).
- Advanced options: check only (dry run), overflow to the preservation file, keep one side's progress (branch),
  same-playthrough Wii base.
- Compatibility warnings appear before conversion; **Convert & Validate** is enabled only when nothing is missing,
  and a sentence says what is still needed.
- Result: stage list, plain summary, the converted save path in a bold read-only field, **Open output folder**,
  **Copy path**, and install instructions (including "do not copy bfssystem.sav").

**Advanced tools tab**: save inspector (inspect / validate), round-trip check, preservation-file details,
compatibility analysis, session log (including full JSON reports), copyable diagnostic report (versions, settings,
selected files with SHA-256, discovery result, last error with traceback only for internal errors).

**Game data tab**: first-run setup without a blocking dialog: choose an existing tables folder, or create the
tables from the user's extracted Wii `files` folder and DE romfs (inputs checked first; output written atomically).

### Sidecar safety rules in the GUI
1. A preservation file is selected automatically only if it matches the save (exactly, or the save continues its
   output) **and** no valid preservation file of the same save history has a higher generation, in either direction.
2. Otherwise the user must choose; the list marks files as *older* or *not usable* and says why.
3. A manually chosen file is classified (matches / different history / other direction / damaged) before Convert
   is enabled; an older-generation file gives a warning, and the engine's divergence and staleness checks still run.
4. Choosing "first time" while a matching preservation file exists gives a warning (DE-only data would not return).
5. Divergent progress is never merged; the only way past it is the explicit "keep only the progress from this save"
   option, worded as discarding the other side's newer progress.

### Plain-language errors
`xcgui\messages.py` maps every engine refusal to a title and a sentence without option names or hex IDs, keeping the
exact engine message under *Show technical details*. Examples:
- party member 8 → "This save contains a temporary character form (Fiora's second form) or a guest character in the
  party. The converter cannot safely transfer these characters yet…"
- lineage mismatch → "The selected preservation file belongs to a different save history. Conversion has been
  stopped to protect your progress…"
- unexpected exceptions → "An unexpected problem stopped the converter. Nothing was written and your original files
  are unchanged." (traceback only in the diagnostic report).

### Responsiveness and robustness
- All engine work runs on one worker thread (`QThreadPool` with one thread): the window never blocks, and engine
  calls never overlap (the table cache is not thread-safe). Results of a superseded selection are discarded
  (generation counter).
- The Convert button is disabled and a `running` flag set before the job is queued; repeated clicks, Enter and
  Ctrl+Enter start exactly one conversion (tested). Inputs are locked while it runs. Closing the window during a
  conversion is refused with a short message.

## 3. Packaging

`gui\xcsaveconverter.spec` builds one portable folder with two programs sharing a runtime:
`XCSaveConverter.exe` (windowed) and `xcconv.exe` (console). About 100 MB (Python 3.14, Qt 6.12; the unused
software-OpenGL DLL is removed). Bundled data: only the converter's own `specs\*.json`. **Not bundled:** game
tables, saves, game executables, ROMs or extracted assets (audited after every build). Settings are stored per user
in `HKCU\Software\XCSaveConverter`.

The release candidate places the user's own tables in `release_candidate_2G\user_data\data` (marked not for
distribution); the app finds that folder automatically. A copy of `XCSaveConverter\` alone (the distributable part)
starts with the first-run setup instead.

## 4. Validation

See `GUI_TEST_RESULTS.md` for the full list. Summary:

| Suite | Result |
|---|---|
| Phase 2C–2F converter regression (unittest) | 109 tests, OK (1 skipped, as in 2F) |
| Phase 2G service tests (unittest, in the same suite) | 19 tests, OK |
| Phase 2G GUI tests (pytest-qt, real window) | 31 tests, passed |
| Clean-directory package test (packaged exes, no Python on PATH) | 18 / 18 checks |
| Visual review (light/dark, scale 1.0/1.5/2.0, 560×460 – 1920×1080) | defects found and fixed (§5) |
| Protected files (originals, live saves, emulators, 2E release) | 106 / 106 unchanged; 2F release 70 / 70 files unchanged |

## 5. Defects found and fixed during 2G

| # | Defect | Fix |
|---|---|---|
| G1 | Direction/mode signals fired during window construction; the slot list stayed empty and the first conversion was refused (`--slot ''`) | signals connected after all widgets exist |
| G2 | Wrapped hint texts inside form rows got far too tall (Qt height-for-width in `QFormLayout`), leaving large gaps and oversized error boxes | step sections rebuilt as vertical stacks |
| G3 | Long paths in labels forced horizontal scrolling at narrow widths | example/result paths in read-only fields; label paths wrap after separators |
| G4 | Grey hint text had low contrast on the light theme | hints use the normal text colour |
| G5 | Wii slot box truncated "monado01" | combo sized to contents |
| G6 | Drop-zone border almost invisible in dark mode | border derived from the text colour; re-coloured on theme change |
| G7 | Alt+D was ambiguous ("&Definitive Edition → Wii" and "Starting &DE save"); two Advanced-tab mnemonics clashed with the &Convert tab | unique mnemonics; a test now checks every tab for duplicates |
| G8 | Status colours were computed once; a live Windows theme switch left old colours | notices and drop zone re-colour on `PaletteChange` |
| G9 | Default window size 940×820 could exceed small laptop screens | initial size limited to 90 % of the available screen |
| G10 | Monkey-patching `paths.ROOT` in tests also moved the spec folder | explicit `paths.FALLBACKS` list |

## 6. What was not done / limits

- Not run on a physical high-DPI monitor, on Windows 10, or with a screen reader; Explorer drag-and-drop was
  simulated with Qt events.
- "Create tables" was exercised through its input checks, not by a full dump from an extracted disc (the dump code is
  the 2F one that created the user's tables).
- No installer, no code signing, nothing published. No converted save was deployed into a live profile.
- The engine's limitations are unchanged (`KNOWN_LIMITATIONS.md`): Wii story progression after a DE → Wii export
  is still untested in play; Fiora's second form and DE v7 are refused.

## 7. Files

| Path | Content |
|---|---|
| `tools\xcservice.py` | service layer (new) |
| `tools\xcconv.py` | CLI front end (refactored) |
| `gui\xcgui\*.py`, `gui\xcconv_gui.py`, `gui\xcconv_cli.py` | application |
| `gui\xcsaveconverter.spec`, `gui\version_info.txt` | packaging |
| `gui\tools\shots.py` | screenshot renderer used for the visual review |
| `tests\test_phase2g_service.py`, `tests_gui\` | new tests |
| `phase2g\scripts\package_test.py` | clean-directory package test |
| `phase2g\baseline_2F\` | frozen copy of the 2F-rc1 code used for parity tests |
| `phase2g\results\`, `phase2g\screenshots\` | logs, package test, screenshots |
| `tools\build_rc_2g.py` | assembles `release_candidate_2G\` |
