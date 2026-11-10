# Conversion records, version 3 (three platforms)

3A keeps the 2H sidecar (`xc1-sidecar/1`, `wii_to_de.sidecar.json` / `de_to_wii.sidecar.json`) unchanged for Wii ⇄ DE
and adds **conversion records** for the four 3DS directions: `<direction>.record.json`, schema **`xc1-record/3`**
(`phase3a\src\xc3dservice.py`). The GUI calls both "conversion records" and finds them automatically.

## 1. Why records are needed

* **Ancestry:** every conversion has a session id; a record names its parent session, the playthrough id and the
  generation, so the converter can tell "continue" from "different playthrough" and "older record".
* **DE-only state:** Wii and 3DS hold exactly the same state, so Wii ⇄ 3DS loses nothing. DE has more (Expert Mode,
  cosmetics, DE-only items and flags, Future Connected, link-unlock indexes). When a playthrough leaves DE, that state
  must wait somewhere until it returns: in the 2H sidecar. A v3 record **embeds** that 2H sidecar and carries it
  forward across any number of Wii ⇄ 3DS hops, so `DE → 3DS → Wii → 3DS → DE` restores it.

## 2. Content

```
record_schema      "xc1-record/3"
converter_version  "3A-rc1";  canon_schema "xc1-canon/2"
direction          wii_to_3ds | 3ds_to_wii | de_to_3ds | 3ds_to_de
session_id         sha256(direction + source sha + output sha)[:32]
lineage            playthrough_id, generation, parent_session, platforms (history, e.g. ["wii","de","3ds","wii"])
source, output     platform, sha256, canonical fingerprint (shared state), story, play_time_s, file name
snapshots          zlib+base64 of the exact source file and output file (recovery; descent checks)
de_sidecar         the pending 2H sidecar (de_to_wii or wii_to_de) or null
notes, extra       e.g. "return trip…", "character stats rebuilt…", slot, template hash
integrity          sha256 of everything above (an edited or damaged record is refused)
```

Deterministic: the same inputs give a byte-identical record (no timestamps).

## 3. Rules

| Converting | A previous conversion applies when… | Then |
|---|---|---|
| Wii → 3DS, 3DS → Wii | it produced a save on the **source** platform (Wii → 3DS record for 3DS → Wii, etc.) and the source save **continues** that output (`sidecar.descent`: same or later story/play time, ≥ 90 % of flags, ≥ 50 % of items) | return trip: lineage +1, pending DE state carried forward |
| 3DS → DE | it holds a pending `de_to_wii` sidecar (a DE → 3DS record, or a DE → Wii 2H sidecar whose Wii output the 3DS save continues) | the 2H re-import runs on the DE save the playthrough came from: DE-only data comes back; unchanged → DE file byte for byte |
| DE → 3DS | it holds a pending `wii_to_de` sidecar (3DS → DE record, or 2H Wii → DE sidecar) | the 2H DE → Wii re-import runs on the original Wii/3DS state, then → 3DS |
| none applies | — | first conversion (a "same playthrough" similarity check asks before treating it as one) |

* **Several matching records** of the newest generation → the user chooses; copies of one conversion (same
  session) count once. An **older** record is refused by the engine checks (2H staleness rules for DE).
* **Current save of the destination game** (only read): with a record it is required, or the explicit statement
  that there is none. If the destination game was played after the last conversion **and** the source progressed
  too → **divergence**: refused unless the user explicitly keeps this save's progress (GUI dialog; CLI
  `--keep-this-progress`); never merged. If only the destination progressed → refused ("nothing new").
* A current save that does not belong to the record's history → refused (different playthrough).
* Higher story or play time alone never establishes ancestry: flags and items must also be kept.
* Divergent branches are never merged; the explicit choice is valid for one conversion.

## 4. Preventing the listed hazards

| Hazard | Protection |
|---|---|
| Record from another playthrough | descent check of the source against the record's output snapshot |
| Restoring stale items / sold items | 2H staleness + divergence rules on the DE side; on Wii ⇄ 3DS nothing is restored from records except embedded DE state, which only returns to DE through the 2H engine |
| EXP duplication, quest regression | the source save is converted as is; records never add progress; descent refuses saves that went back |
| Accidental merge of branches | divergence refused unless explicitly chosen; the chosen branch replaces, never merges |
| Reusing incompatible metadata | integrity hash; embedded sidecar re-validated with the 2H consistency checks |

## 5. Files in an output folder

`3ds\monado0N` or `monado0N` or `save_0\bfsgameNN.sav` · `<direction>.record.json` · (`de_to_wii.sidecar.json` /
`wii_to_de.sidecar.json`: the embedded 2H sidecar also as a file, for the 2H tools) · `manifest.json` (SHA-256 of all
inputs and outputs) · `checkpoint\xcconv_<id>\` (3DS outputs from a complete archive folder).
