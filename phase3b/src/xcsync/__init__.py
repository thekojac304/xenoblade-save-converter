"""xcsync - Xenoblade Chronicles Sync Hub (Phase 3B).

On-demand cross-device save synchronisation on top of the unchanged 3A conversion engine. Syncthing (or any other
tool) moves files between devices; this package interprets them:

  store   managed folder layout, device profiles, templates, atomic commit pointer, lock
  scan    read-only startup scan: stable-file checks, validation, ancestry against the sync history, decision
  sync    the Sync All transaction (one immutable generation, validated, committed by a single pointer), publication
          into per-device ready folders, rollback, crash recovery
  cli     xcsync command line (same functions; used by tests and the emulator acceptance scripts)

The conversion engine (tools/xcservice, phase3a/src/xc3dservice) is called, never modified.
"""
HUB_SCHEMA = "xc1-synchub/1"
GENERATION_SCHEMA = "xc1-generation/1"
APP_VERSION = "3F-rc1"
