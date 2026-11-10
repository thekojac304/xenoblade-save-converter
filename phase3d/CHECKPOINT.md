# Phase 3D checkpoint log (newest last)

## 2026-11-08 evening start
- Protect manifest 3D: phase3d/scripts/protect3d.py (3C set + release_candidate_3C = 2,323 files), start recorded.
- Public DE archive history (tables/de_history.tsv, public/xcde-saves.git) has genuine saves with character 8:
  story 276 [8,1], 283 [8,2,1,5], 288 [4,6,7] (Fiora absent, temporary split), 291 [8,6,5,7,2,1,4]; plus 260-269 before.
  Extracted to phase3d/fixtures/public_v7; Monado load+save -> v10 (g_s269..g_s291) -> phase3d/fixtures/de_sNNN_v10_monado.sav.
- DE: record 8 separate character; at rejoin (269->276) seeded from 3 (skill tree/SP), level 40->53, gear added to
  inventory; record 3 frozen at lv 9. DE link slots: slot 3 (Fiora-3) and slot 8 (Fiora-8) separate; unlock
  mirrored 3/8; c3 and c8 unlock arrays equal.
- Wii: 0x800A3644..0x800A3690 mirrors the skill object (+0x3534 mem / +0x1F4 save) 3->8 and 8->3 after each skill
  update; pre-rejoin rec 8 rows hold Fiora-3 ids (51+); learn routine 0x800A34C8 uses per-character ids (8: 176-200).
  Rec 8 accrues EXP while absent on the Wii (DE: 0).
- Era boundary: JNL_PCrelatelist (both games): pc 3 shown for 11..274, pc 8 from 275 -> canon.FIORA_ERA = 275.
- Guests 9-13 (BTL_pclist guest=1: Dickson, Mumkhar, Alvis, Dunban x2): never in a saved party (359 archive saves).
- Engine: canon.main_chars/fiora/unsupported_party era-aware; phase2c map_characters, convert links/unlock,
  de_to_wii links/mirror/absent equipment, xc3dservice stat rebuild chars, service party checks. Pre-era canonical
  fingerprints identical to 3B (fp_check.py). Static s276 DE->Wii->DE: works; unchanged return byte-identical.
- DEFECT D1 (found by 3DS crash, x_s269_rejoin): Shulk's Wii-only byte +0x118 = 0 from early base (user's story-8 3DS
  save as template) -> 3DS stack overflow (PC 0x2CA438) loading Fallen Arm; Wii hangs too (wd_s269_flag0).
  Bisected (bisect3ds.py: bs0..bs11) to that byte. Fix: de_to_wii sets it to 1 from story 20 when base has 0.
  Verified: bs13_fixed loads.
- Open: Wii rec-8 skill ids after the rejoin (own 176+ vs mirrored 51+) -> play the rejoin on the 3DS.

## Post-rejoin validation (Wii, Dolphin)
- m1_s269_lock (Monado warp probe near the 269 field area): story stayed 269 - rejoin trigger not found by warp;
  x4_s269_rejoin (Azahar) navigation by marker failed. Per brief, bounded: moved to converting the genuine
  post-rejoin DE saves instead.
- DE s276/283/288/291 (v10) -> Wii (base W150, overflow sidecar) and -> 3DS (user story-8 template): all convert.
- Dolphin wd_s276/283/288/291_save: converted save loads, in-game save written by the Wii game. Canonical diff
  (converted vs Wii-game re-save) = clock / play time / position only (party [8,1], [8,2,1,5], [4,6,7], ...).
  Wii game KEEPS record 8's own skill ids (176+) and the 3<->8 mirror; normalises node/link state bytes for every
  character (known limitation 14).
- Wii re-save -> DE with sidecar: s276 = clock/time/position only (+ minimap bits, limitation 11); s283/s288: same
  plus equipped items that were compacted keep their Wii slot and deferred items shift (limitation 6). itemset.py:
  every box has the same item multiset, every character wears an item of identical content.
- New tests phase3d/tests/test_phase3d_characters.py (13): era rule, party checks, genuine saves, DE->Wii->DE and
  DE->3DS->DE unchanged = byte-identical (4 saves), Wii records after rejoin, split party, 3 multi-hop paths,
  adversarial (DE parties outside the era rule / guests refused for Wii and 3DS; Wii parties refused for DE,
  carried losslessly Wii->3DS; foreign skill ids in active Fiora refused), D1.

## 3DS + Monado validation, D2, release (end of Phase 3D)
- Azahar x5_s291_save: converted DE 291 loads; Party (Fiora-8 lv 53 leading), Change Equipment (Mechonis Swords +
  gems, Ether Goggles, Ether Frame), Skill Trees (Daring/Courage/Zeal) shown; in-game save. Diff: clock/time/pos +
  9 link unlocks raised by the game (limitation 5). Back to DE with record; Monado cold load + save (m_r_x2d_s291)
  and of the Wii-played 283 return (m_r_w2d_s283): clock/time only.
- D2 found via the Sync Hub (283 -> 288 judged an older-sync branch): DE stored-equipment table 0x3BB50 (7 x 0xB4 per
  char = equip record + 3 gem records) holds departing members' gear and is restored at the reunion; Wii staging
  slots 150+id (0x80158308). Not translated -> tools/stored_gear.py refuses (joined members, not record 3, non-default
  gear) unless the destination stores the same gear or has the member away itself (returns allowed). Archive scan:
  269-288; 3C story fixtures 154-158 too.
- 4 earlier 2E/2F tests updated (assert D2 refusal for those saves; other assertions kept): patch_tests_d2.py.
- Versions 3D-rc1 (patch_gui3d.py); GUI copy phase3d/gui; GUI tests phase3d/tests_gui (18), tests_gui_3a (39).
- Suites: 2H 136 OK (1 skip), 3A 41, 3B 65, 3C 22, 3D 21. Parity vs 3C: 8/12 byte-identical, 3 differ only in the D1
  byte + checksum, s269 refused. fp_check 12/12 identical.
- PyInstaller phase3d/dist; package tests 3D 11/11, 3B 19/19, 3A 32/32.
- release_candidate_3D (611 files, no user_data/game tables). Protected manifest final: unchanged.
