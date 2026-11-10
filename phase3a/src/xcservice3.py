"""xcservice3 - the Phase 2H service API extended to three platforms (Wii, DE, New 3DS) for the 3A desktop app.

Everything not overridden here is the unchanged 2H xcservice (Wii <-> DE detection, preview, history, conversion).
3DS saves are detected, previewed and checked through their Wii-layout translation; the four 3DS directions run
xc3dservice.convert3; history for 3DS directions uses conversion records (*.record.json) and 2H sidecars.
"""
import os
import re
import tempfile
from dataclasses import dataclass, field

import canon
import safeio
import sidecar as scmod
import xc3d
import xc3dservice as s3
from xcservice import *  # noqa: F401,F403  (the 2H API)
import xcservice as _xs

Refused = safeio.Refused
REFUSALS = s3.REFUSALS
ThreeDSRequest = s3.ThreeDSRequest
GAMES = ("wii", "de", "3ds")
DIRECTIONS = {("wii", "de"): "wii_to_de", ("de", "wii"): "de_to_wii", ("wii", "3ds"): "wii_to_3ds",
              ("3ds", "wii"): "3ds_to_wii", ("de", "3ds"): "de_to_3ds", ("3ds", "de"): "3ds_to_de"}
TARGET = {d: t for (s, t), d in DIRECTIONS.items()}
SOURCE = {d: s for (s, t), d in DIRECTIONS.items()}
NICE = s3.NICE3
RECORD_NAMES = {d: f"{d}.record.json" for d in s3.DIRECTIONS3}


def is3(direction):
    return direction in s3.DIRECTIONS3


def direction_for(src_game, target):
    return DIRECTIONS.get((src_game, target))


# ------------------------------------------------------------------------------------------------- detection
def detect(path):
    if path and os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                head = f.read(4)
        except OSError:
            head = b""
        if head == xc3d.MAGIC:
            return {"kind": s3.kind_of(safeio.read_input(path, "save")), "path": path}
        if os.path.basename(path).lower().endswith(".record.json"):
            try:
                kind, r = s3.load_record(path)
                return {"kind": "sidecar", "path": path, "direction": r["direction"]}
            except Refused:
                return {"kind": "unknown", "path": path, "note": "damaged conversion record"}
    if path and os.path.isdir(path):
        return {"kind": "folder", "path": path, "saves": saves_in_folder(path)}
    return _xs.detect(path)


def saves_in_folder(folder):
    out = list(_xs.saves_in_folder(folder))
    for d in (folder, os.path.join(folder, "00000001"), os.path.join(folder, "data", "00000001"), os.path.join(folder, "3ds")):
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if os.path.isfile(p) and re.fullmatch(r"monado0[1-3]", n) and p not in out:
                if detect(p)["kind"] == "3ds":
                    out.append(p)
    return out


def _wii_image(path, what="save"):
    return s3.load_3ds(path, what)[2]


def _tmp_wii(path):
    d = tempfile.mkdtemp(prefix="xc3a-pv-")
    p = os.path.join(d, "monado01")
    with open(p, "wb") as f:
        f.write(_wii_image(path))
    return d, p


def preview(path):
    k = detect(path)["kind"]
    if k == "3ds-empty":
        raise Refused(f"save: {path} is an empty 3DS save slot")
    if k == "3ds-damaged":
        raise Refused(f"save: {path} is a damaged 3DS save; it is not repaired or converted")
    if k != "3ds":
        return _xs.preview(path)
    d, p = _tmp_wii(path)
    try:
        pv = _xs.preview(p)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    pv.update(game="3ds", path=os.path.abspath(path), format="ctr-xc3d",
              sha256=_xs.sha(safeio.read_input(path, "save")))
    return pv


def wii_compatibility(path):
    if detect(path)["kind"] != "3ds":
        return _xs.wii_compatibility(path)
    d, p = _tmp_wii(path)
    try:
        return _xs.wii_compatibility(p)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def compatibility(de, base=None):
    if base and detect(base)["kind"] == "3ds":
        d, p = _tmp_wii(base)
        try:
            return _xs.compatibility(de, p)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
    return _xs.compatibility(de, base)


def _image(path):
    """Wii-layout image (Wii or 3DS file) or DE bytes, for history checks."""
    b = safeio.read_input(path, "save")
    if xc3d.is_3ds_file(b):
        return "wii", _wii_image(path)
    return ("wii" if b[:4] == b"USRD" else "de"), b


# ------------------------------------------------------------------------------------------------- history
@dataclass
class Candidate:
    path: str
    status: str            # "exact" | "continues" | "unrelated"
    session: str
    generation: int
    newest: bool = True
    detail: str = ""
    created: float = 0.0


def _record_files(folders):
    seen, out = set(), []
    for f, depth in folders:
        if not f or not os.path.isdir(f):
            continue
        for dp, dns, fs in os.walk(f):
            if dp[len(f):].count(os.sep) >= depth:
                dns[:] = []
            for n in fs:
                if n.endswith((".record.json", ".sidecar.json")):
                    p = os.path.normcase(os.path.abspath(os.path.join(dp, n)))
                    if p not in seen:
                        seen.add(p)
                        out.append(os.path.join(dp, n))
    return out


def _returns_to(rec_kind, rec, direction):
    """Can this record/sidecar be the previous conversion of a conversion in `direction`?  The previous conversion
    must have produced a save on the source platform (the save the user then continued playing)."""
    src, tgt = SOURCE[direction], TARGET[direction]
    if rec_kind == "sidecar":                      # 2H sidecar
        return (rec["direction"], direction) in {("de_to_wii", "3ds_to_de"), ("wii_to_de", "de_to_3ds"),
                                                 ("de_to_wii", "wii_to_3ds")}
    ps, pt = s3.DIRECTIONS3[rec["direction"]]
    if pt != src:
        return False
    pending = (rec.get("de_sidecar") or {}).get("direction")
    if tgt == "de":
        return pending == "de_to_wii"
    if src == "de":
        return pending == "wii_to_de"
    return True


def _classify(path, src_path, direction, T):
    try:
        kind, rec = s3.load_record(path)
    except Refused as e:
        return None
    if not _returns_to(kind, rec, direction):
        return None
    g, img = _image(src_path)
    if kind == "sidecar":
        out_img, game = scmod.output_image(rec), rec["output"]["game"]
        session, gen = rec["session_id"], rec["lineage"]["generation"]
    else:
        out_img = s3.record_output_wii(rec) if rec["output"]["platform"] in ("wii", "3ds") else s3._unpack(rec["snapshots"]["output"])
        game = "wii" if rec["output"]["platform"] in ("wii", "3ds") else "de"
        session, gen = rec["session_id"], rec["lineage"]["generation"]
    if game != g:
        return None
    if img == out_img:
        st = "exact"
    else:
        ok, reasons, changed = scmod.descent(out_img, img, T, g)
        st = "continues" if ok else "unrelated"
    return Candidate(path, st, session, gen, created=os.path.getmtime(path))


def resolve_history(source, direction, dest=None, folders=(), chosen=None, start_fresh=False):
    if not is3(direction):
        return _xs.resolve_history(source, direction, dest, folders, chosen, start_fresh)
    T = _xs.tables()
    plan = _xs.HistoryPlan("blocked")
    if chosen:
        c = _classify(chosen, source, direction, T)
        if not c or c.status == "unrelated":
            plan.issue, plan.detail = "chosen-invalid", "this record does not lead to this save"
            return plan
        plan.mode, plan.sidecar = "return", c.path
        return plan
    sdir = os.path.dirname(os.path.abspath(source))
    look = [(sdir, 1), (os.path.dirname(sdir), 1)]            # the 2H rules: next to the save, one folder up,
    look += [(f, 2) for f in folders]                        # every output folder used, next to the destination save
    if dest:
        look.append((os.path.dirname(os.path.abspath(dest)), 1))
    found, sessions = [], set()
    for p in _record_files(look):
        c = _classify(p, source, direction, T)
        if c and c.status != "unrelated" and c.session not in sessions:   # copies of one conversion count once
            sessions.add(c.session)
            found.append(c)
    cands = found
    if cands:
        top = max(c.generation for c in cands)
        for c in cands:
            c.newest = c.generation == top
        newest = [c for c in cands if c.newest]
        exact = [c for c in newest if c.status == "exact"]
        pick = exact[0] if len(exact) == 1 else (newest[0] if len(newest) == 1 else None)
        if pick:
            plan.mode, plan.sidecar = "return", pick.path
            return plan
        plan.choices, plan.issue = cands, "choose"
        plan.detail = f"{len(cands)} matching conversion records"
        return plan
    plan.mode = "first"
    if start_fresh or not dest:
        return plan
    try:
        a, b = _image(source)[1], _image(dest)[1]
        plan.similarity = round(_xs.similarity(a, b), 3)
    except REFUSALS:
        return plan
    if plan.similarity >= _xs.SAME_PLAYTHROUGH:
        plan.mode, plan.issue = "blocked", "same-playthrough"      # find the record, or start fresh explicitly
    return plan


# ------------------------------------------------------------------------------------------------- slots / output
def suggest_slot(direction, dest=None):
    if TARGET.get(direction) != "3ds":
        if direction == "3ds_to_de":
            return _xs.suggest_slot("wii_to_de", dest)
        if direction == "3ds_to_wii":
            return _xs.suggest_slot("de_to_wii", dest)
        return _xs.suggest_slot(direction, dest)
    folder = os.path.dirname(os.path.abspath(dest)) if dest else None
    used = []
    for s in ("monado01", "monado02", "monado03"):
        p = os.path.join(folder, s) if folder else None
        if p and os.path.isfile(p) and detect(p)["kind"] == "3ds":
            used.append(s)
    for s in ("monado01", "monado02", "monado03"):
        if s not in used:
            return _xs.SlotSuggestion(s, True, used)
    own = os.path.basename(dest) if dest else "monado01"
    return _xs.SlotSuggestion(own if own in used else "monado01", False, used)


def new_output_name(direction, stamp):
    return f"{direction}_{stamp}" if is3(direction) else _xs.new_output_name(direction, stamp)


def plan_output(out_dir, direction, slot):
    if not is3(direction):
        return _xs.plan_output(out_dir, direction, slot)
    tgt = TARGET[direction]
    if tgt == "3ds":
        main = f"3ds/{s3._slot3(slot)}"
    elif tgt == "wii":
        main = _xs.wii_slot_name(slot)
    else:
        main = f"save_0/{_xs.de_slot_name(slot)}"
    rel = [main, RECORD_NAMES[direction], "manifest.json"]
    safeio.plan(out_dir, {k: b"" for k in rel})
    return rel


def convert_request(req, progress=None):
    if isinstance(req, ThreeDSRequest):
        return s3.convert3(req, progress)
    return _xs.convert_request(req, progress)
