# Phase 3E checkpoint log (newest last)

## Setup
- Workspace phase3e/; protect3e.py = 3D set + release_candidate_3D (2,935 files), start recorded.

## Decode
- DE stash 0x3BB50: 7 x 0xB4 per character = verbatim equipment record (+0 old slot, sockets normal 3<<16|gem slot,
  fixed 1<<16|gem id) + verbatim gem record copies matched by their +0 slot; present byte +0x10 (stale bytes in
  non-present gem records ignored). References (0,0). Return: re-added in free slots, new serials, entry zeroed.
- Wii 0x8007F368(char, join): leave copies the equipped 0x34 record to staging slot 150+k, socketed gems to the
  staged-gem table item+0x11AB8 + 16*(8(k-1)+i) with 2-byte links item+0x12038 (slot+1, socket), reference keeps
  gid (row 0, idx 0xFFFF). Join creates a NEW item from the reference gid, socket count from staging, gems from links.
  Script command 0x8004A24C writes scripted gear (prologue Dunban).
- Encoder vs game staging: equal except age byte and low header bits (not used at join).

## Implementation
- tools/stored_gear.py: readers (de_read, wii_read), writers (write_wii, write_de), apply() policy; canon
  shared["stored_gear"] only when stored characters exist; de_to_wii / convert integrate; reimport 3-way
  (unchanged stored gear -> DE entries kept; returned on the Wii -> cleared).
- Static: 9 genuine split saves, all directions equal; unchanged returns byte-identical.

## Reunions played (debug positioning only)
- Wii a1: 156 -> 158 (Shulk gear + 6 gems = native DE); a2-a5c: 158 -> 160 (Reyn, Dunban, Sharla, Riki = native);
  a6 cold reload; return to DE = native 160 (items, equipment, stored gear).
- DE m1: Wii 158 -> DE first-time -> Monado friends 158 -> 160: returning gear = native.
- 3DS x1c: items back, gems missing -> D3: xc3d swapped the 2-byte link table as u16; fixed (bytes); x2: 156 -> 158
  gear + gems = native.
- Dolphin focus note: runs a4c/a5 failed while other windows covered Dolphin (hotkey screenshots need focus; controller
  input works in background); a5b showed the event played but the post-event quest window blocked the fixed save
  sequence -> a5c with a pause and two save attempts.
- 3DS menu bar wraps (7 icons); fresh session cursor on Party -> 3 RIGHT to System (azsave.sh).

## Policy
- VALIDATED characters {1,2,4,5,6,7}; Fiora-8 stored (288) still refused (no reunion played).
- 2E/2F tests restored to original (unpatch_tests_d2.py); 3D tests updated to 3E behaviour (patch_tests_3d_for_3e.py).

## Completion
- 3DS 158 -> 160 (x3b..x6c) gear+gems = native; cold reload x7; 3DS -> DE with record = native 160. Monado m2 cold reload.
- Re-import: byte-signature keep (unchanged stored-gear bytes -> DE entries kept, before reading); read-back accepts kept.
- 2F synthetic rejoin test now synthetic money (party-list edit unreachable with stored refs); 3C story test allows
  stored_gear diff (3C export had none); 3D first-time 288 refused (Fiora leftover refs).
- User's own story-8 3DS save: Reyn stored (genuine).
- Suites: 2H 136 OK (1 skip), 3A 41, 3B 65, 3C 22, 3D 21, 3E 24; GUI 18 + 39; parity vs 3D: 14 identical outside
  windows, s160 = Melia's stored gear (21 bytes). Package tests 3E 13/13, 3B 19/19, 3A 32/32.
- Versions 3E-rc1; release_candidate_3E (712 files, no game data). Protected manifest final: unchanged.
