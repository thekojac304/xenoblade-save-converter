"""Sidecar ("xc1-sidecar/1"): keeps what one game cannot hold while a playthrough visits the other, and the lineage
needed to bring progress back without loss or duplication. Pure functions plus JSON (de)serialisation.

A sidecar is written by every export (DE->Wii or Wii->DE) and read by the matching re-import. Fields:
  sidecar_schema, converter_version, direction ("de_to_wii" | "wii_to_de"), session_id (sha256 of the two images),
  lineage {playthrough_id, generation, parent_session},
  source {game, format, sha256, name, fingerprint_shared}, output {game, format, sha256, name, fingerprint_shared},
  snapshots {source, output}: zlib+base64 of both full save images (the source is the recovery snapshot and the
      template for the re-import; the output is the exact file the other game started from),
  deferred: DE data the Wii save does not carry (DE-only items, overflow items, Future Connected quest bytes/states),
  de_only / wii_only: informational copies of the canonical exclusive parts,
  notes, integrity {sha256 of the canonical JSON body without this field}.
Identity is never established by file names: descent checks use the snapshots, fingerprints and game state.
"""
import base64
import hashlib
import json
import zlib

import canon

SCHEMA = "xc1-sidecar/1"
CONVERTER_VERSION = "3F-rc1"   # 3F: Fiora-8 stored gear, F1 reunion room; 3E: stored equipment, D3; 3D-rc1: character 8, D1; 3C-rc1: items; "2G-rc1" 2G..3B
DIRECTIONS = {"de_to_wii": ("de", "wii"), "wii_to_de": ("wii", "de")}


class SidecarError(Exception):
    pass


def _pack(b):
    return {"encoding": "zlib+base64", "sha256": hashlib.sha256(b).hexdigest(), "size": len(b),
            "data": base64.b64encode(zlib.compress(b, 9)).decode()}


def _unpack(o):
    try:
        b = zlib.decompress(base64.b64decode(o["data"], validate=True))
    except (KeyError, TypeError, ValueError, zlib.error) as e:
        raise SidecarError(f"snapshot cannot be decoded (corrupted sidecar): {type(e).__name__}")
    if hashlib.sha256(b).hexdigest() != o.get("sha256") or len(b) != o.get("size"):
        raise SidecarError("snapshot does not match its recorded SHA-256 (corrupted sidecar)")
    return b


def _body_hash(sc):
    body = {k: v for k, v in sc.items() if k != "integrity"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def make(direction, src, out, src_canon, out_canon, deferred=None, parent=None, notes=None, names=("", "")):
    s_sha, o_sha = hashlib.sha256(src).hexdigest(), hashlib.sha256(out).hexdigest()
    session = hashlib.sha256((direction + s_sha + o_sha).encode()).hexdigest()[:32]
    if parent:
        lineage = {"playthrough_id": parent["lineage"]["playthrough_id"],
                   "generation": parent["lineage"]["generation"] + 1, "parent_session": parent["session_id"]}
    else:
        lineage = {"playthrough_id": s_sha[:32], "generation": 1, "parent_session": None}
    sg, og = ("de", "wii") if direction == "de_to_wii" else ("wii", "de")
    sc = {
        "sidecar_schema": SCHEMA, "converter_version": CONVERTER_VERSION, "canon_schema": canon.SCHEMA,
        "direction": direction, "session_id": session,
        "lineage": lineage,
        "source": {"game": sg, "format": src_canon["source"]["format"], "sha256": s_sha, "name": names[0],
                   "fingerprint_shared": canon.fingerprint(src_canon)},
        "output": {"game": og, "format": out_canon["source"]["format"], "sha256": o_sha, "name": names[1],
                   "fingerprint_shared": canon.fingerprint(out_canon)},
        "snapshots": {"source": _pack(src), "output": _pack(out)},
        "deferred": canon.jsonable(deferred or {}),
        "de_only": canon.jsonable((src_canon if sg == "de" else out_canon).get("de_only", {})),
        "wii_only": canon.jsonable((src_canon if sg == "wii" else out_canon).get("wii_only", {})),
        "notes": notes or [],
    }
    sc["integrity"] = {"sha256": _body_hash(sc)}
    return sc


def dumps(sc):
    return json.dumps(sc, indent=1, sort_keys=True, default=str)


def load(text):
    """Parse and check a sidecar. Every failure is a SidecarError (never a partial result)."""
    try:
        sc = json.loads(text)
    except (ValueError, TypeError) as e:
        raise SidecarError(f"sidecar is not valid JSON (corrupted or not a sidecar): {e}")
    if not isinstance(sc, dict):
        raise SidecarError("sidecar is not a JSON object")
    if sc.get("sidecar_schema") != SCHEMA:
        raise SidecarError(f"unsupported sidecar schema {sc.get('sidecar_schema')!r} (expected {SCHEMA})")
    integ = sc.get("integrity")
    if not isinstance(integ, dict) or integ.get("sha256") != _body_hash(sc):
        raise SidecarError("sidecar integrity hash mismatch (edited or corrupted)")
    check_consistency(sc)
    return sc


def check_consistency(sc):
    """Internal consistency (Phase 2F): the integrity hash only detects accidental damage; these checks reject a
    sidecar whose fields contradict each other (hand edits that recomputed the hash, mixed-up files)."""
    try:
        d = sc["direction"]
        if d not in DIRECTIONS:
            raise SidecarError(f"unknown sidecar direction {d!r}")
        sg, og = DIRECTIONS[d]
        if sc["source"]["game"] != sg or sc["output"]["game"] != og:
            raise SidecarError("sidecar games do not match its direction")
        for part in ("source", "output"):
            snap = sc["snapshots"][part]
            if snap.get("sha256") != sc[part]["sha256"]:
                raise SidecarError(f"sidecar {part} hash does not match its snapshot")
            _unpack(snap)          # decodes and checks the embedded image now, not when it is first used
        want = hashlib.sha256((d + sc["source"]["sha256"] + sc["output"]["sha256"]).encode()).hexdigest()[:32]
        if sc["session_id"] != want:
            raise SidecarError("sidecar session id does not match its contents")
        lin = sc["lineage"]
        if not isinstance(lin.get("generation"), int) or lin["generation"] < 1:
            raise SidecarError("sidecar lineage generation is invalid")
        if lin.get("parent_session") == sc["session_id"]:
            raise SidecarError("sidecar names itself as its parent")
        if (lin["generation"] == 1) != (lin.get("parent_session") is None):
            raise SidecarError("sidecar lineage is inconsistent (generation vs parent)")
        if not isinstance(sc.get("deferred", {}), dict):
            raise SidecarError("sidecar deferred data is malformed")
    except (KeyError, TypeError, AttributeError) as e:
        raise SidecarError(f"sidecar is missing required fields ({type(e).__name__}: {e})")


def source_image(sc):
    return _unpack(sc["snapshots"]["source"])


def output_image(sc):
    return _unpack(sc["snapshots"]["output"])


def info(sc):
    return {k: sc.get(k) for k in ("sidecar_schema", "converter_version", "canon_schema", "direction", "session_id",
                                   "lineage", "source", "output")} | {
        "deferred": {k: (sum(len(x) for x in v.values()) if isinstance(v, dict) and v and
                         all(isinstance(x, dict) for x in v.values()) else len(v) if hasattr(v, "__len__") else v)
                     for k, v in sc["deferred"].items()}, "notes": sc["notes"]}


# ------------------------------------------------------------------------------------------- descent / divergence
def descent(exported, current, T, game):
    """Does `current` plausibly continue `exported` (same playthrough, same game)? -> (ok, reasons, changed)."""
    if current == exported:
        return True, ["identical to the exported file"], False
    ce = canon.from_wii(exported, T) if game == "wii" else canon.from_de(exported, T)
    cc = canon.from_wii(current, T) if game == "wii" else canon.from_de(current, T)
    e, c = ce["shared"], cc["shared"]
    bad, why = [], []
    if c["play_time_s"] < e["play_time_s"]:
        bad.append(f"play time went back ({e['play_time_s']} -> {c['play_time_s']} s)")
    if c["story"] < e["story"]:
        bad.append(f"story went back ({e['story']} -> {c['story']})")
    for k, ch in e["characters"].items():
        if c["characters"][k]["level"] + 10 < ch["level"]:
            bad.append(f"character {k} lost more than 10 levels")
    ef, cf = set(e["flags"]), set(c["flags"])
    kept = len(ef & cf) / max(len(ef), 1)
    if kept < 0.9:
        bad.append(f"only {kept:.0%} of the exported flags are still set")
    # Phase 2F: items are matched as a multiset of (box, id[, gem/crystal values]); the acquisition serial is not an
    # identity - the Wii ages every item whenever one is picked up (canon.order_ranks)
    old_items, new_items = _items(e), _items(c)
    ikept = sum(min(n, new_items.get(k, 0)) for k, n in old_items.items()) / max(sum(old_items.values()), 1)
    if ikept < 0.5:
        bad.append(f"only {ikept:.0%} of the exported items are still present")
    why.append(f"flags kept {kept:.0%}, items kept {ikept:.0%}, play time +{c['play_time_s'] - e['play_time_s']} s, "
               f"story {e['story']} -> {c['story']}")
    return not bad, bad or why, canon.fingerprint(ce) != canon.fingerprint(cc)


def _items(shared):
    out = {}
    for b, recs in shared["inventory"].items():
        for r in recs.values():
            k = canon.item_key(b, r)
            out[k] = out.get(k, 0) + 1
    # Phase 3E: gear and gems the game keeps for party members who are away are still owned - a departure or a reunion
    # moves them between the inventory and the stored-equipment table without being progress or loss
    for d in (shared.get("stored_gear") or {}).values():
        for sl, r in (d.get("slots") or {}).items():
            if r:
                k = canon.item_key(sl, r)
                out[k] = out.get(k, 0) + 1
        for g in d.get("gems") or ():
            k = canon.item_key("gem", g)
            out[k] = out.get(k, 0) + 1
    return out


def _canon(b, game, T):
    return canon.from_wii(b, T) if game == "wii" else canon.from_de(b, T)


def divergence(sc, current_other, T):
    """Has the save that was exported FROM (sidecar source game) progressed independently since the export?
    current_other: the user's current save of the source game (None = the caller vouched there is none newer).
    -> (diverged, detail). The comparison recomputes the source state from the embedded snapshot with the current
    canonical model (sidecars of earlier converter versions stay usable)."""
    if current_other is None:
        return False, "no current source-game save supplied (explicitly declared: no newer save exists)"
    src = source_image(sc)
    if current_other == src:
        return False, "the source-game save is unchanged since the export"
    game = sc["source"]["game"]
    cs = _canon(current_other, game, T)
    if canon.fingerprint(cs) == canon.fingerprint(_canon(src, game, T)):
        return False, "the source-game save differs only in game-exclusive fields since the export"
    return True, "the source-game save has changed since the export (shared state differs)"


def stale_evidence(sc, current_other, current_played, T):
    """Is the save being imported (current_played, the game the sidecar exported TO) a continuation of a LATER export
    of current_other rather than of this sidecar's export? Measures how much of the progress current_other made since
    this sidecar's export is also present in current_played. -> (ratio, facts). A high ratio with real progress
    means this sidecar is older than the user's latest conversion (or both games repeated the same content)."""
    game = sc["source"]["game"]
    s0 = _canon(source_image(sc), game, T)["shared"]
    s1 = _canon(current_other, game, T)["shared"]
    p = _canon(current_played, sc["output"]["game"], T)["shared"]
    facts = []
    for f, v in s1["flags"].items():
        if s0["flags"].get(f) != v:
            facts.append(p["flags"].get(f) == v)
    i0, i1, ip = _items(s0), _items(s1), _items(p)
    for k, n in i1.items():
        if n > i0.get(k, 0):
            facts.append(ip.get(k, 0) >= n)
    for k, ch in s1["characters"].items():
        if ch["level"] > s0["characters"][k]["level"]:
            facts.append(p["characters"][k]["level"] >= ch["level"])
    return (sum(facts) / len(facts) if facts else 0.0), len(facts)


STALE_RATIO, STALE_MIN_FACTS = 0.8, 3
