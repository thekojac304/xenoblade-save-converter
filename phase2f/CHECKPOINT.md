# Phase 2F checkpoint log (resume from the last entry)

Workspace: `phase2f/` (scripts, manifests, fixtures, results, runs). Dev tree: `tools/`, `tests/` (2E source frozen in
`phase2f/snapshot_2E/source`, 2E RC copy in `phase2f/snapshot_2E/release_candidate_copy`; the live 2E RC in
`release_candidate/` is never modified). New RC: `release_candidate_2F/`.

## 2026-11-06 session start
- Protected-input manifest: `phase2f/manifests/protected_start.json` (106 files: Filen / Proton / Dolphin-portable Wii
  data, live Monado save_0, research originals + template, the 2E RC, xcde.exe, xcde.ini, Dolphin.exe, the .rvz).
  Re-check: `python phase2f/scripts/protect_manifest.py check <name>`.
- Snapshot of 2E: `phase2f/manifests/snapshot_2E_sha256.json` (129 files); 2E RC `SHA256SUMS.txt` verifies (74/74).
- Baseline: 2E suite 40/40 OK (`phase2f/results/baseline_2E_tests.log`).
- CLI probes (`phase2f/scripts/probe_cli.py`, frozen 2E tools): 6 defects confirmed (see EDGE_CASE_RESULTS when written):
  --slot traversal, partial multi-file output on refusal, junction bypass of the live-path guard, uncontrolled
  struct.error/ValueError on truncated input, absolute --slot escapes --out, --dry-run writes --report.

## Fixes implemented (dev tree tools/, converter 2F-rc1, canon xc1-canon/2)
- canon: item "serial" -> acquisition-order rank "order" (Wii header serial is an AGE, code 0x80159080 ages every item on
  pickup, 0x80159488 renumbers a box 1..N; DE serial is a counter number, larger = newer). Raw values in wii_only.item_ages
  / de_only.item_serials. convert (Wii->DE) writes DE serial = rank; de_to_wii writes Wii ages N+1-rank (whole box
  rewritten unless its order is unchanged); reimport.assign_serials keeps DE serials of pre-existing items, new Wii
  pickups get serials above the DE counter. sidecar.descent matches items as a multiset (box, id[, gem/crystal values]).
- reimport: current DE required (or no_newer_de=True); stale-sidecar evidence refusal (even with branch); template =
  current DE when it differs only in DE-exclusive fields; serial policy; deferred-item snapshot check.
- sidecar: JSON/structure errors -> SidecarError; consistency checks (direction/games/hashes/session id/lineage) and
  eager snapshot decoding; divergence recomputes fingerprints from the embedded snapshot; stale_evidence().
- convert: FEATURES_2F (serial_order, template_reset: reserve EXP / cosmetics / Noponstones of the template's playthrough
  cleared on first export; party_check: party ids outside 1..7 refused); gem strength/chance > 255 refused.
- de_to_wii: unsupported party (8..13) refused; EXP >= next-level cost, coins > 999, AP, money, invalid open-quest
  counter bytes, gem/crystal field widths refused explicitly; serial ages as above; verify() re-ranks.
- xcconv + new safeio: all-or-nothing output folder (staging + one rename; must not exist or be empty), realpath /
  junction / marker-file guards, slot validation, bounded validated inputs, v7 refused for export, --current-* or
  --no-current-* required with --sidecar, read-back check also on re-import, exit codes 0/1/2/3, no tracebacks,
  --dry-run writes nothing (incl. --report), cleanup-staging command.
- tests: 2E suite updated for the API (no assertion removed; RealChain W1 now asserts the 2E order inversion and that the
  2F export is exact) -> 40/40. New: tests/p2f_util.py, test_phase2f_properties.py (10), test_phase2f_sidecar.py (13).

## Game runs (phase2f/runs/monado)
- g1_s232_v7load: public v7 Expert-Mode save loaded in isolated Monado, saved in-game -> v10 (fixtures/real/
  s232_v10_monado.sav). Canonical shared state identical except clock minute + play time; Expert fields identical [G].
- g1_s020/s206/s241/s258/s269 queued (same route).
- g1_s020/s206 saved to new slots (bfsgame02/01), s241/s258/s269 to bfsgame00: all six game-generated v10 fixtures in
  phase2f/fixtures/real (PROVENANCE.md). Canonical equal to the v7 sources except clock/play time [G].
- d1_s232_load_save (Dolphin): DE-native story-232 export loads/saves; Wii game restored Fiora's record 3 from record 8
  -> defect, fixed in de_to_wii (sync copy). d2_s232_fiora_fix: only clock/play time/position differ [G].
- m3_s232_back_from_wii (Monado): re-import of the Dolphin-written file loads/saves; only clock/play time [G].
- m2_user_2f (Monado): the 2F user file (sha 1028f718...) loads in Eryth Sea and saves; Monado raised one link unlock.

## Later fixes
- link_unlock shared (both directions; first export no template max); DE crafted cylinders (source 0 -> canonical 1);
  exact Wii map list; closure check; dangling gem refs; Wii container headers; Expert highest-EXP kept; identity
  pairing of DE serials on re-import (moved items, parked deferred slots); Fiora record-8 copy sync.
- D4: Wii 0x3440+i = Heart-to-Heart registered (CMenuKizunaTalk), DE 0x3634 (+500) confirmed on real DE saves;
  0x352C-0x36CF unexplained (results/d4_flag_blocks.md).

## Final (09:59)
- Full suite 109 tests OK (1 skipped) - results/full_suite_final.log; coverage matrix 67/68 PASS + 1 SKIPPED.
- Package test (clean dir, no XCCONV_DATA) 10/10 - results/package_test.json.
- protected_end.json: 106/106 unchanged. Deliverables written; release_candidate_2F built by tools/build_rc_2f.py.
