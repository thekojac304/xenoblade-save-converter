# GUI test results: XC Save Converter 2H-rc1 (2026-11-06)

Environment: Windows 11 Enterprise 10.0.26300, Python 3.14.5, PySide6 6.12.0, pytest-qt, PyInstaller 6.22.3.
All conversions use copied or synthetic saves; outputs go to `work\test_phase2h\…` or `%TEMP%\xcconv_2h_pkgtest`.
Logs are in `validation\` of the release.

## Summary

| Suite | Result |
|---|---|
| Converter regression 2C–2F + 2G service + 2H service (`python -m unittest discover -s tests -v`) | **136 tests OK** (1 skipped, as since 2F), 277 s |
| GUI (`python -m pytest tests_gui -v`, real window) | **30 passed**, 72 s |
| Packaged app from a clean folder, no Python on PATH | **20 / 20 checks** |
| GUI output vs the Phase 2G release `xcconv.exe` | **4 / 4 byte-identical** |
| Phase 2F and 2G release folders | unchanged (69 / 69 and 332 / 332 files match their `SHA256SUMS.txt`) |
| Protected files (originals, emulator / game installs, 2E release) | 106 / 106 unchanged — see the note below about two **added** files in Monado's live `save_0` |

## Required test areas → tests

| # | Area | Test(s) |
|---|---|---|
| 1 | First-time Wii → DE | `test_01_first_wii_to_de_matches_cli_and_2f` (CLI byte-identical; 2F saves byte-identical; user save `1028f718…`) |
| 2 | First-time DE → Wii | `test_02_first_de_to_wii_matches_cli_and_2f` |
| 3 | Automatic return-trip detection | `test_03_automatic_return_trips` (Wii → DE → Wii → DE, history never shown; last step restores the DE save byte for byte) |
| 4 | Missing conversion history | `test_04_missing_history_same_playthrough` (stops, Find record…, wrong record rejected, Start fresh with confirmation) |
| 5 | Stale history | `test_05_stale_history_not_chosen_and_still_refused` (older record not chosen; deliberate choice still refused by the engine, nothing written) |
| 6 | Ambiguous histories | `test_06_ambiguous_histories_ask` (dialog with both; chosen one converts = CLI) |
| 7 | Divergent histories | `test_07_divergent_histories_need_explicit_choice` (refused, plain message, explicit confirmation, = CLI `--branch de`) |
| 8 | Missing destination save | `test_08_missing_destination_save` (disabled until step 1, wrong game, same file) |
| 9 | Unsupported formats | `test_09_unsupported_inputs[junk/record/empty_slot/v7_destination/fiora]` |
| 10 | Safe output slot | `test_10_safe_output_slot` (free name suggested, clash warning, live folder refused, destination folder untouched, new folder each time) |
| 11 | Transactional failure | `test_11_transaction_failure_leaves_nothing`, `test_11b_worker_error_repeated_clicks_and_close` |
| 12 | Keyboard-only use | `test_12_keyboard_only` (Alt+S / Alt+D, typed paths, Tab reaches every control, Ctrl+Enter, focus moves to Open Output Folder) |
| 13 | Drag-and-drop | `test_13_drag_and_drop_both_steps` (both steps, folder drop, text rejected) |
| 14 | Light and dark | `test_14_light_and_dark` (notices and accent button follow a live scheme switch) |
| 15 | Small windows and high DPI | `test_15_small_and_large_windows[480×420/700×600/1920×1080]`, `test_15b_high_dpi_start[1.5/2]` (real processes) |
| – | Also | first run without game data, plain wording (no "sidecar/lineage/canonical/json" in the main window, no line over 120 characters), advanced dialog (check-only, tools, diagnostics), "no current destination save" option = CLI `--no-current-wii`, unique mnemonics, error-message regression (H1) |

## GUI tests

| Test | Result |
|---|---|
| `test_01_first_wii_to_de_matches_cli_and_2f` | PASSED |
| `test_02_first_de_to_wii_matches_cli_and_2f` | PASSED |
| `test_03_automatic_return_trips` | PASSED |
| `test_04_missing_history_same_playthrough` | PASSED |
| `test_05_stale_history_not_chosen_and_still_refused` | PASSED |
| `test_06_ambiguous_histories_ask` | PASSED |
| `test_07_divergent_histories_need_explicit_choice` | PASSED |
| `test_08_missing_destination_save` | PASSED |
| `test_09_unsupported_inputs[junk]` | PASSED |
| `test_09_unsupported_inputs[record]` | PASSED |
| `test_09_unsupported_inputs[empty_slot]` | PASSED |
| `test_09_unsupported_inputs[v7_destination]` | PASSED |
| `test_09_unsupported_inputs[fiora]` | PASSED |
| `test_10_safe_output_slot` | PASSED |
| `test_11_transaction_failure_leaves_nothing` | PASSED |
| `test_11b_worker_error_repeated_clicks_and_close` | PASSED |
| `test_12_keyboard_only` | PASSED |
| `test_13_drag_and_drop_both_steps` | PASSED |
| `test_14_light_and_dark` | PASSED |
| `test_15_small_and_large_windows[size0]` | PASSED |
| `test_15_small_and_large_windows[size1]` | PASSED |
| `test_15_small_and_large_windows[size2]` | PASSED |
| `test_15b_high_dpi_start[1.5]` | PASSED |
| `test_15b_high_dpi_start[2]` | PASSED |
| `test_first_run_without_game_data` | PASSED |
| `test_main_window_text_is_short_and_plain` | PASSED |
| `test_advanced_dialog_tools_and_options` | PASSED |
| `test_no_current_destination_option` | PASSED |
| `test_no_duplicate_mnemonics` | PASSED |
| `test_plain_language_messages` | PASSED |

## Packaged application (clean folder)

| Check | Result |
|---|---|
| gui starts without Python and without game data (no blocking dialog) | PASS |
| gui runs from the clean copy | PASS |
| gui starts at scale 1.5 | PASS |
| gui starts at scale 2 | PASS |
| xcconv.exe --help | PASS |
| xcconv.exe validate | PASS |
| xcconv.exe without tables refuses clearly | PASS |
| xcconv.exe refuses a live output folder | PASS |
| GUI Wii -> DE succeeds (first conversion detected) | PASS |
| GUI Wii -> DE identical to CLI (all files) | PASS |
| GUI Wii -> DE save is the validated 2F save | PASS |
| preview shown | PASS |
| GUI DE -> Wii found the conversion history automatically | PASS |
| GUI DE -> Wii identical to packaged CLI | PASS |
| GUI Wii -> DE return restores the DE save byte for byte | PASS |
| GUI DE -> Wii (first conversion) identical to CLI | PASS |
| GUI refuses wrong inputs before converting | PASS |
| GUI check-only run writes nothing | PASS |
| inputs unchanged | PASS |
| portable folder unchanged by running it | PASS |

## Parity with the Phase 2G release CLI

The `xcconv.exe` of `release_candidate_2G` (run unchanged) was given the inputs of the packaged-GUI runs:

| Check | Result |
|---|---|
| 2H GUI w2d identical to the 2G release xcconv.exe | PASS |
| 2H GUI d2w_first identical to the 2G release xcconv.exe | PASS |
| 2H GUI d2w_return identical to the 2G release xcconv.exe | PASS |
| 2H GUI w2d_return identical to the 2G release xcconv.exe | PASS |

## Visual acceptance

The real window was rendered (`gui\tools\shots.py`) in light and dark mode at Qt scale 1.0, 1.5 and 2.0, at
480×420, 700×600 and 1280×900, in these states: first run, empty, first conversion ready, result, return trip found,
missing record, errors (empty slot + live output folder), Advanced options / game data / tools. Screenshots:
`validation\screenshots\`. Fixed after review: gaps from empty labels, empty file-name box, oversized default window,
weak main button and a disabled state that looked clickable, accent colour not following a live theme switch, late
live-folder warning, button wider than the fields, an Alt-key clash (see `XC_WII_TO_DE_PHASE2H.md`, H4–H7).

## Note: two files added to Monado's live save folder

The end-of-phase protected-file check lists **no changed or missing file**, but two **added** files in
`…\XenobladeChroniclesDefinitiveEdition-Monado\save\save_0`: `bfsgame01.sav` and `bfsgame01.tmb`, both dated
2026-11-06 21:09. `bfsgame01.sav` has SHA-256 `1028f718…`, the converted Eryth Sea save of the 2F/2G manual acceptance
checklist; `bfssystem.sav` carries the same time stamp with unchanged content. The converter refuses to write into
that folder and no test or tool of this phase targeted it, so this looks like the save was installed by hand following
the checklist, followed by a run of the game. Nothing was removed or changed by Phase 2H.
