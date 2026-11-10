"""xc3dservice - Xenoblade Chronicles 3D (New 3DS) support on top of the unchanged Phase 2H service (Phase 3A).

Six directions, one canonical model:
  Wii -> DE, DE -> Wii      the 2H engine, unchanged (xcservice.wii_to_de / de_to_wii_convert)
  Wii -> 3DS, 3DS -> Wii    lossless layout transcode (xc3d.transcode): the 3DS payload is the Wii save's own layout
                            in little-endian; every byte is carried, nothing needs a template except the 3DS picture
  DE -> 3DS                 DE -> (2H engine) -> Wii layout -> 3DS.  The Wii structural base is the 3DS destination
                            save itself (transcoded), so no Wii save is needed
  3DS -> DE                 3DS -> Wii layout -> (2H engine) -> DE
The 2H engine runs on temporary Wii-layout files in a private temp folder; only the final files are committed (one
new output folder, all or nothing, safeio).  Conversion records ("*.record.json", schema xc1-record/3) give every
conversion an ancestry entry and carry a 2H sidecar forward when DE-only state is pending (Expert Mode, cosmetics,
DE-only items, ...), so  Wii -> DE -> 3DS -> Wii -> DE  keeps it.  See SIDECAR_V3_DESIGN.md.
"""
import base64
import hashlib
import json
import os
import shutil
import struct
import tempfile
import time
import zlib
from dataclasses import dataclass, field

import canon
import safeio
import sidecar as scmod
import wii_save
import xc3d
import xc3dstats
import xcservice as xs

Refused = safeio.Refused
REFUSALS = xs.REFUSALS + (xc3d.FormatError,)
CONVERTER_VERSION = "3F-rc1"   # 3E-rc1, 3D-rc1, 3C-rc1, 3A-rc1 until 3B
RECORD_SCHEMA = "xc1-record/3"
DIRECTIONS3 = {"wii_to_3ds": ("wii", "3ds"), "3ds_to_wii": ("3ds", "wii"), "de_to_3ds": ("de", "3ds"),
               "3ds_to_de": ("3ds", "de")}
NICE3 = {"wii_to_de": "Wii -> DE", "de_to_wii": "DE -> Wii", "wii_to_3ds": "Wii -> 3DS", "3ds_to_wii": "3DS -> Wii",
         "de_to_3ds": "DE -> 3DS", "3ds_to_de": "3DS -> DE"}
SLOT_RANGE = (1, 2, 3)

# ---- Phase 3A path guards: 3DS emulator and SD-card save locations are live data, never written
for _m in (os.path.join("nintendo 3ds"), os.path.join("title", "00040000", "0f700100"),
           os.path.join("3ds", "checkpoint", "saves"), os.path.join("azahar", "sdmc"), os.path.join("citra", "user")):
    if _m not in safeio.LIVE_MARKERS:
        safeio.LIVE_MARKERS.append(_m)
for _f in ("azahar.exe", "citra-qt.exe", "citra.exe", "Checkpoint.3dsx", "boot.firm"):
    if _f not in safeio.MARKER_FILES:
        safeio.MARKER_FILES.append(_f)


_WBDAT = None


def wii_bdat():
    global _WBDAT
    if _WBDAT is None:
        import paths
        with open(paths.data("bdat_wii.json"), encoding="utf-8") as f:
            _WBDAT = json.load(f)
    return _WBDAT


def to_3ds_image(wii, template_raw):
    """Wii-layout image -> 3DS payload.  The 3DS game uses each character's saved stat block and equipment caches as
    live values (the Wii recomputes them), so they are rebuilt first exactly as the game computes them (no change for
    a save the game itself wrote; see xc3dstats).  -> (payload, rebuilt Wii-layout image, changes)."""
    import canon
    import flagmap as fm
    # Phase 3D: from scenario 275 Fiora is character 8, whose caches the 3DS uses live as well
    fixed, changes = xc3dstats.rebuild(wii, wii_bdat(), chars=canon.main_chars(fm.wii_get(wii, 0x20)))
    fixed = xc3d.fix_wii_checksums(fixed) if changes else wii
    return xc3d.transcode(fixed, "3ds", template=template_raw), fixed, changes


# ------------------------------------------------------------------------------------------------- reading
def kind_of(b):
    if xc3d.is_3ds_file(b):
        try:
            raw = xc3d.unpack(b)
        except xc3d.FormatError:
            return "3ds-damaged"
        k = xc3d.kind(raw)
        return {"save": "3ds", "empty": "3ds-empty"}.get(k, "3ds-damaged")
    return xs.kind_of(b)


def load_3ds(path, what):
    """-> (file bytes, payload, Wii-layout image).  Refuses empty slots, damaged or edited files."""
    b = safeio.read_input(path, what)
    if not xc3d.is_3ds_file(b):
        raise Refused(f"{what}: {path} is not a Xenoblade Chronicles 3D save")
    try:
        raw = xc3d.unpack(b)
    except xc3d.FormatError as e:
        raise Refused(f"{what}: {path} is damaged ({e}); it is not repaired or converted")
    k = xc3d.kind(raw)
    if k == "empty":
        raise Refused(f"{what}: {path} is an empty 3DS save slot")
    bad = xc3d.check_container(raw)
    if k != "save" or bad:
        raise Refused(f"{what}: {path} is damaged or edited ({', '.join(bad) or 'unknown header'}); it is not "
                      "repaired or converted")
    try:
        wii = xc3d.transcode(raw, "wii")
        wii_save.decode_bytes(wii, path)
    except Exception as e:
        raise Refused(f"{what}: {path} cannot be decoded ({type(e).__name__}: {e})")
    if wii_save.check_container(wii):
        raise Refused(f"{what}: {path} does not translate to a valid save layout")
    return b, raw, wii


def load_any_sx(path, what):
    """Wii or 3DS save -> (platform, file bytes, Wii-layout image)."""
    b = safeio.read_input(path, what)
    if xc3d.is_3ds_file(b):
        fb, raw, wii = load_3ds(path, what)
        return "3ds", fb, wii
    w = xs.load_wii(path, what)
    return "wii", w, w


def detect(path):
    """What a file is: {'kind': wii|de|3ds|..., 'platform', ...}.  Never raises for unreadable files."""
    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except OSError as e:
        return {"kind": "unreadable", "error": str(e)}
    if head == xc3d.MAGIC:
        b = open(path, "rb").read()
        k = kind_of(b)
        return {"kind": k, "platform": "3ds", "size": len(b)}
    if os.path.basename(path).lower().endswith(".record.json"):
        return {"kind": "record", "platform": None}
    d = xs.detect(path)
    d.setdefault("platform", {"wii": "wii", "de": "de"}.get(d.get("kind")))
    return d


def summary3(wii_image):
    s = xs.summary(wii_image)
    s["game"] = "3ds"
    s["format"] = "ctr-xc3d"
    return s


def preview(path):
    d = detect(path)
    if d.get("kind") == "3ds":
        fb, raw, wii = load_3ds(path, "save")
        s = summary3(wii)
        return {"platform": "3ds", "summary": s, "sha256": xs.sha(fb), "unverified_nonzero": unverified_nonzero(raw)}
    return xs.preview(path)


def unverified_nonzero(payload):
    """Unverified schema spans that hold data in this save (they are carried byte for byte, but their meaning on the
    other platform is inferred, not proven)."""
    out = []
    for s, e, note in xc3d.UNVERIFIED:
        if any(payload[s:e]) and payload[s:e] not in (bytes([0x01, 0, 0x01, 0]), bytes([0, 1, 0, 1])):
            out.append(note)
    return sorted(set(out))


# ------------------------------------------------------------------------------------------------- records (v3)
def _pack(b):
    return base64.b64encode(zlib.compress(b, 9)).decode()


def _unpack(s):
    return zlib.decompress(base64.b64decode(s))


def _body_hash(r):
    body = {k: v for k, v in r.items() if k != "integrity"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_record(direction, src_native, src_wii, out_native, out_wii, T, parent=None, de_sidecar=None, notes=None,
                names=("", ""), extra=None):
    sp, op = DIRECTIONS3[direction]
    s_sha, o_sha = xs.sha(src_native), xs.sha(out_native)
    session = hashlib.sha256((direction + s_sha + o_sha).encode()).hexdigest()[:32]
    if parent:
        pl = parent["lineage"]
        lineage = {"playthrough_id": pl["playthrough_id"], "generation": pl["generation"] + 1,
                   "parent_session": parent["session_id"],
                   "platforms": (pl.get("platforms") or [parent.get("source", {}).get("game") or
                                                          parent.get("source", {}).get("platform")]) + [op]}
    else:
        lineage = {"playthrough_id": s_sha[:32], "generation": 1, "parent_session": None, "platforms": [sp, op]}

    def side(platform, native, wii):
        if platform == "de":
            c = canon.from_de(native, T)
        else:
            c = canon.from_wii(wii, T)
        sh = c["shared"]
        return {"platform": platform, "sha256": xs.sha(native), "fingerprint_shared": canon.fingerprint(c),
                "story": sh["story"], "play_time_s": sh["play_time_s"]}

    r = {"record_schema": RECORD_SCHEMA, "converter_version": CONVERTER_VERSION, "canon_schema": canon.SCHEMA,
         "direction": direction, "session_id": session, "lineage": lineage,
         "source": dict(side(sp, src_native, src_wii), name=names[0]),
         "output": dict(side(op, out_native, out_wii), name=names[1]),
         "snapshots": {"source": _pack(src_native), "output": _pack(out_native)},
         "de_sidecar": de_sidecar, "notes": notes or [], "extra": extra or {}}
    r["integrity"] = {"sha256": _body_hash(r)}
    return r


def dumps_record(r):
    return json.dumps(r, indent=1, sort_keys=True)


def load_record_text(text):
    """A v3 record or a 2H sidecar -> ('record'|'sidecar', dict).  Integrity is checked; damaged files refused."""
    try:
        r = json.loads(text)
    except ValueError as e:
        raise Refused(f"conversion record is not valid JSON ({e})")
    if r.get("record_schema") == RECORD_SCHEMA:
        if r.get("integrity", {}).get("sha256") != _body_hash(r):
            raise Refused("conversion record has been edited or damaged (integrity check failed)")
        if r.get("direction") not in DIRECTIONS3:
            raise Refused("conversion record has an unknown direction")
        if r.get("de_sidecar"):
            scmod.load(scmod.dumps(r["de_sidecar"]))     # full 2H consistency check of the embedded sidecar
        return "record", r
    try:
        return "sidecar", scmod.load(text)
    except scmod.SidecarError as e:
        raise Refused(f"not a conversion record or sidecar: {e}")


def load_record(path):
    return load_record_text(xs.read_sidecar_text(path, "conversion record"))


def record_output_wii(r):
    """Wii-layout image of a record's output (for 3DS/Wii outputs)."""
    b = _unpack(r["snapshots"]["output"])
    if r["output"]["platform"] == "3ds":
        return xc3d.transcode(xc3d.unpack(b), "wii")
    return b


def record_source_wii(r):
    b = _unpack(r["snapshots"]["source"])
    if r["source"]["platform"] == "3ds":
        return xc3d.transcode(xc3d.unpack(b), "wii")
    return b if r["source"]["platform"] == "wii" else None


# ------------------------------------------------------------------------------------------------- lineage checks
def check_return(src_wii, exported_wii, current_dest_wii, exported_source_wii, branch, keep_word, T, dest_game):
    """Shared return-trip rules for the lossless family (Wii/3DS layout), mirroring 2H:
    the save being converted must continue the exported one; if the destination game was ALSO played after the
    export, refuse unless branch == keep_word (keep this save's progress, discard the destination's)."""
    ok, reasons, changed = scmod.descent(exported_wii, src_wii, T, "wii")
    if not ok:
        raise Refused("this save does not continue the one the conversion record exported (different playthrough "
                      "or older save): " + "; ".join(reasons))
    if current_dest_wii is None or exported_source_wii is None:
        return changed, []
    if current_dest_wii == exported_source_wii or \
            canon.fingerprint(canon.from_wii(current_dest_wii, T)) == canon.fingerprint(canon.from_wii(exported_source_wii, T)):
        return changed, []
    dok, _, dchanged = scmod.descent(exported_source_wii, current_dest_wii, T, "wii")
    if not dok:
        raise Refused(f"your current {dest_game} save is not from this playthrough's history (it does not continue the "
                      "save this conversion started from)")
    if dchanged and changed and branch != keep_word:
        raise Refused(f"both games were played after the last conversion: your current {dest_game} save changed and "
                      "this save progressed too. Choose explicitly to keep this save's progress (the "
                      f"{dest_game} progress made after the export will NOT be in the new file), or convert the "
                      "other way.")
    if dchanged and not changed and branch != keep_word:
        raise Refused(f"this save has no progress since the last conversion, but your {dest_game} save does: there "
                      "is nothing new to bring over (your {dest_game} save is the newer one)")
    return changed, (["branch: kept this save's progress, discarded the destination's later progress"]
                     if branch == keep_word else [])


# ------------------------------------------------------------------------------------------------- requests
@dataclass
class ThreeDSRequest:
    direction: str            # wii_to_3ds | 3ds_to_wii | de_to_3ds | 3ds_to_de
    source: str
    out: str
    template: str = None      # 3DS destination save (wii/de -> 3ds); DE template (3ds -> de, first time)
    record: str = None        # v3 record or 2H sidecar of the previous conversion
    current: str = None       # current save of the destination game (only read)
    no_current: bool = False
    branch: str = None        # "keep_source": keep this save's progress on a divergence
    slot: str = None          # 3DS slot 1-3, Wii monado0N, DE 00-..
    overflow: str = "refuse"
    dry_run: bool = False


def _slot3(slot):
    s = str(slot or "1").replace("monado0", "").strip()
    if s not in ("1", "2", "3"):
        raise Refused(f"3DS slot must be 1, 2 or 3 (got {slot!r})")
    return f"monado0{s}"


def _tmpdir():
    return tempfile.mkdtemp(prefix="xc3a-")


def _write(d, name, b):
    p = os.path.join(d, name)
    with open(p, "wb") as f:
        f.write(b)
    return p


def _require_current(r, game):
    if r.record and bool(r.current) == bool(r.no_current):
        raise Refused(f"with a conversion record, give your current {game} save of this playthrough (it is only read), "
                      f"or state that no {game} save is newer than the last conversion. This protects {game} progress "
                      "from being silently replaced.")


def _checkpoint_folder(template_path, slot_name, out_file):
    """Complete Checkpoint-style backup folder: every file of the template's save archive, with one slot replaced.
    Only produced when the template sits in a complete archive folder (monado01..03 present)."""
    tdir = os.path.dirname(os.path.abspath(template_path))
    names = sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []
    if not all(f"monado0{i}" in names for i in (1, 2, 3)):
        return None
    files = {}
    for n in names:
        p = os.path.join(tdir, n)
        if not os.path.isfile(p) or n.startswith(".") or n.endswith((".json", ".metadata")):
            continue
        if n in ("monado01", "monado02", "monado03", "specialmode"):
            files[n] = out_file if n == slot_name else safeio.read_input(p, "template archive file")
    return files


def convert3(r, progress=None):
    progress = progress or xs._noop
    if r.direction not in DIRECTIONS3:
        raise Refused(f"unknown direction {r.direction}")
    progress("read")
    T = xs.tables()
    fn = {"wii_to_3ds": _wii_to_3ds, "3ds_to_wii": _3ds_to_wii, "de_to_3ds": _de_to_3ds, "3ds_to_de": _3ds_to_de}
    return fn[r.direction](r, T, progress)


def _finish(r, direction, files, inputs, rep, main_rel, record_rel, progress):
    files["manifest.json"] = xs.manifest(inputs, {k: v for k, v in files.items() if k != "manifest.json"},
                                         {"direction": direction, "converter_version": CONVERTER_VERSION})
    rep["written"] = sorted(files)
    rep["dry_run"] = r.dry_run
    if not r.dry_run:
        progress("write")
    digests = safeio.commit(r.out, files, r.dry_run)
    if not r.dry_run:
        progress("final")
        for rel, dg in digests.items():          # final read-back of the committed files
            with open(os.path.join(r.out, rel), "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != dg:
                    raise Refused(f"written file {rel} does not read back identically")
    return xs.ConversionResult(direction, rep, r.out, os.path.join(r.out, main_rel), os.path.join(r.out, record_rel),
                               digests, r.dry_run)


def _verify_3ds_output(out_file, wii_expected):
    raw = xc3d.unpack(out_file)
    if xc3d.check_container(raw):
        raise Refused("generated 3DS save fails its own container check")
    back = xc3d.transcode(raw, "wii")
    if back[0x20:] != wii_expected[0x20:] and _mask_thum(back) != _mask_thum(wii_expected):
        raise Refused("generated 3DS save does not read back to the converted state")
    return back


def _mask_thum(w):
    b = bytearray(w)
    b[0xA0:0x9CA0] = bytes(0x9CA0 - 0xA0)
    b[0x1C:0x20] = bytes(4)
    return bytes(b)


def _parent_and_desidecar(rec):
    """(parent dict for lineage, pending 2H sidecar or None) from a loaded record/sidecar."""
    if rec is None:
        return None, None
    kind, d = rec
    if kind == "record":
        return d, d.get("de_sidecar")
    return d, d


def _wii_to_3ds(r, T, progress):
    slot = _slot3(r.slot)
    src_plat, src_fb, wii = "wii", xs.load_wii(r.source, "your Wii save"), None
    wii = src_fb
    if not r.template:
        raise Refused("a 3DS save is needed as the destination template (it supplies the save picture; it is not changed)")
    tfb, traw, twii = load_3ds(r.template, "3DS destination save")
    inputs = {"wii": (r.source, src_fb), "template_3ds": (r.template, tfb)}
    notes, parent, de_sc = ["Wii -> 3DS (lossless layout transcode)"], None, None
    progress("check")
    if r.record:
        _require_current(r, "3DS")
        rec = load_record(r.record)
        parent, de_sc = _parent_and_desidecar(rec)
        kind, d = rec
        if kind == "record" and d["direction"] == "3ds_to_wii":
            cur = load_3ds(r.current, "current 3DS save")[2] if r.current else None
            _, extra_notes = check_return(wii, record_output_wii(d), cur, record_source_wii(d), r.branch,
                                          "keep_source", T, "3DS")
            notes += extra_notes + ["return trip: continues the 3DS -> Wii conversion " + d["session_id"]]
        elif kind == "sidecar" and d["direction"] == "de_to_wii":
            ok, reasons, _ = scmod.descent(scmod.output_image(d), wii, T, "wii")
            if not ok:
                raise Refused("this Wii save does not continue the DE -> Wii export of the sidecar: " + "; ".join(reasons))
            notes.append("DE-only state from the DE -> Wii sidecar is carried in this record")
        elif kind == "record" and d.get("de_sidecar"):
            notes.append("pending DE-only state carried forward")
        inputs["record"] = (r.record, xs.read_sidecar_text(r.record).encode())
        if r.current:
            inputs["current_3ds"] = (r.current, safeio.read_input(r.current, "current 3DS save"))
    progress("translate")
    out_raw, fixed, rebuilt = to_3ds_image(wii, traw)
    out_file = xc3d.pack(out_raw)
    progress("verify")
    _verify_3ds_output(out_file, fixed)
    if rebuilt:
        notes.append(f"character stats/equipment caches rebuilt for the 3DS: {len(rebuilt)} block(s)")
    diffs = xs.readback_diffs(canon.from_wii(wii, T)["shared"], canon.from_wii(xc3d.transcode(out_raw, "wii"), T)["shared"])
    if diffs:
        raise Refused(f"independent read-back differs: {diffs[:5]}")
    rec_new = make_record("wii_to_3ds", src_fb, wii, out_file, wii, T, parent=parent, de_sidecar=de_sc, notes=notes,
                          names=(os.path.basename(r.source), slot), extra={"slot": slot, "template_sha256": xs.sha(tfb),
                                                                          "picture": "from the 3DS destination save"})
    files = {f"3ds/{slot}": out_file, "wii_to_3ds.record.json": dumps_record(rec_new).encode()}
    cp = _checkpoint_folder(r.template, slot, out_file)
    if cp:
        for n, b in cp.items():                       # deterministic folder name (same inputs, same output)
            files[f"checkpoint/xcconv_{rec_new['session_id'][:12]}/{n}"] = b
    rep = {"direction": "wii_to_3ds", "summary_in": xs.summary(wii), "summary_out": summary3(wii), "notes": notes,
           "inferred_fields_with_data": unverified_nonzero(out_raw),
           "checkpoint_backup": bool(cp)}
    return _finish(r, "wii_to_3ds", files, inputs, rep, f"3ds/{slot}", "wii_to_3ds.record.json", progress)


def _3ds_to_wii(r, T, progress):
    slot = xs.wii_slot_name(r.slot or "monado01")
    fb, raw, wii = load_3ds(r.source, "your 3DS save")
    inputs = {"3ds": (r.source, fb)}
    notes, parent, de_sc = ["3DS -> Wii (lossless layout transcode)"], None, None
    progress("check")
    if r.record:
        _require_current(r, "Wii")
        rec = load_record(r.record)
        parent, de_sc = _parent_and_desidecar(rec)
        kind, d = rec
        cur = xs.load_wii(r.current, "current Wii save") if r.current else None
        if kind == "record" and d["direction"] in ("wii_to_3ds", "de_to_3ds"):
            src_w = record_source_wii(d) if d["direction"] == "wii_to_3ds" else None
            _, extra_notes = check_return(wii, record_output_wii(d), cur, src_w, r.branch, "keep_source", T, "Wii")
            notes += extra_notes + ["continues the conversion " + d["session_id"]]
        inputs["record"] = (r.record, xs.read_sidecar_text(r.record).encode())
        if cur is not None:
            inputs["current_wii"] = (r.current, cur)
    progress("translate")
    out = wii
    if wii_save.check_container(out):
        raise Refused("translated Wii save fails the Wii container check")
    progress("verify")
    back = xc3d.transcode(out, "3ds", template=raw)
    if xc3d.transcode(back, "wii") != out:
        raise Refused("3DS -> Wii translation is not reversible for this save")
    rec_new = make_record("3ds_to_wii", fb, wii, out, out, T, parent=parent, de_sidecar=de_sc, notes=notes,
                          names=(os.path.basename(r.source), slot), extra={"slot": slot})
    files = {slot: out, "3ds_to_wii.record.json": dumps_record(rec_new).encode()}
    if r.current:
        bd = os.path.join(os.path.dirname(os.path.abspath(r.current)), "banner.bin")
        if os.path.isfile(bd):
            files["banner.bin"] = safeio.read_input(bd, "banner.bin")
    rep = {"direction": "3ds_to_wii", "summary_in": summary3(wii), "summary_out": xs.summary(out), "notes": notes,
           "inferred_fields_with_data": unverified_nonzero(raw)}
    return _finish(r, "3ds_to_wii", files, inputs, rep, slot, "3ds_to_wii.record.json", progress)


def _collect(folder):
    out = {}
    for dp, _, fs in os.walk(folder):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, folder).replace("\\", "/")] = open(p, "rb").read()
    return out


def _3ds_to_de(r, T, progress):
    fb, raw, wii = load_3ds(r.source, "your 3DS save")
    tmp = _tmpdir()
    try:
        wpath = _write(tmp, "monado01", wii)
        req = xs.WiiToDeRequest(wii=wpath, out=os.path.join(tmp, "out"), slot=r.slot or "00")
        parent, notes, rec = None, ["3DS -> Wii layout -> DE (2H engine)"], None
        if r.record:
            rec = load_record(r.record)
            kind, d = rec
            parent = d
            sc = d.get("de_sidecar") if kind == "record" else d
            if not sc or sc.get("direction") != "de_to_wii":
                raise Refused("this conversion record has no pending DE save to return to; convert as a first "
                              "conversion with a DE template instead")
            req.sidecar = _write(tmp, "de_to_wii.sidecar.json", scmod.dumps(sc).encode())
            if r.current:
                req.current_de = r.current
            else:
                req.no_current_de = r.no_current
            req.branch = "wii" if r.branch == "keep_source" else None
            notes.append("return trip onto the DE save of the conversion " + sc["session_id"])
        else:
            if not r.template:
                raise Refused("a DE save is needed as the destination template (it is not changed)")
            req.template = r.template
        progress("check")
        progress("translate")
        res = xs.wii_to_de(req, None)
        got = _collect(res.out_dir)
        sc_new = scmod.load(got["wii_to_de.sidecar.json"].decode())
        de_rel = [k for k in got if k.startswith("save_0/") and k.endswith(".sav") and "bfssystem" not in k][0]
        de_out = got[de_rel]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    progress("verify")
    rec_new = make_record("3ds_to_de", fb, wii, de_out, None, T, parent=parent, de_sidecar=sc_new, notes=notes,
                          names=(os.path.basename(r.source), os.path.basename(de_rel)))
    files = {k: v for k, v in got.items() if k.startswith("save_0/")}
    files["wii_to_de.sidecar.json"] = got["wii_to_de.sidecar.json"]
    files["3ds_to_de.record.json"] = dumps_record(rec_new).encode()
    inputs = {"3ds": (r.source, fb)}
    if r.template:
        inputs["template_de"] = (r.template, safeio.read_input(r.template, "DE template"))
    if r.record:
        inputs["record"] = (r.record, xs.read_sidecar_text(r.record).encode())
    if r.current:
        inputs["current_de"] = (r.current, safeio.read_input(r.current, "current DE save"))
    rep = dict(res.report, direction="3ds_to_de", summary_in=summary3(wii), notes=notes,
               inferred_fields_with_data=unverified_nonzero(raw))
    return _finish(r, "3ds_to_de", files, inputs, rep, de_rel, "3ds_to_de.record.json", progress)


def _de_to_3ds(r, T, progress):
    slot = _slot3(r.slot)
    if not r.template:
        raise Refused("a 3DS save is needed as the destination template (it is not changed)")
    tfb, traw, twii = load_3ds(r.template, "3DS destination save")
    de = xs.load_de(r.source, "your DE save", v10_only=True)
    tmp = _tmpdir()
    notes, parent = ["DE -> (2H engine) -> Wii layout -> 3DS"], None
    try:
        req = xs.DeToWiiRequest(de=r.source, out=os.path.join(tmp, "out"), overflow=r.overflow)
        if r.record:
            rec = load_record(r.record)
            kind, d = rec
            parent = d
            sc = d.get("de_sidecar") if kind == "record" else d
            if not sc or sc.get("direction") != "wii_to_de":
                raise Refused("this conversion record does not lead to this DE save (no Wii/3DS -> DE conversion in it)")
            req.sidecar = _write(tmp, "wii_to_de.sidecar.json", scmod.dumps(sc).encode())
            if r.current:
                c_fb, c_raw, c_wii = load_3ds(r.current, "current 3DS save")
                req.current_wii = _write(tmp, "current_monado01", c_wii)
            else:
                req.no_current_wii = r.no_current
            req.branch = "de" if r.branch == "keep_source" else None
            notes.append("return trip: continues the conversion " + sc["session_id"])
        else:
            req.base = _write(tmp, "base_monado01", twii)    # the 3DS destination save is the structural template
            notes.append("structural template: the 3DS destination save")
        progress("check")
        progress("translate")
        res = xs.de_to_wii_convert(req, None)
        got = _collect(res.out_dir)
        wii_out = got["monado01"]
        sc_new = scmod.load(got["de_to_wii.sidecar.json"].decode())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out_raw, fixed, rebuilt = to_3ds_image(wii_out, traw)
    out_file = xc3d.pack(out_raw)
    progress("verify")
    _verify_3ds_output(out_file, fixed)
    if rebuilt:
        notes.append(f"character stats/equipment caches rebuilt for the 3DS: {len(rebuilt)} block(s)")
    diffs = xs.readback_diffs(canon.from_wii(wii_out, T)["shared"], canon.from_wii(xc3d.transcode(out_raw, "wii"), T)["shared"])
    if diffs:
        raise Refused(f"independent read-back differs: {diffs[:5]}")
    rec_new = make_record("de_to_3ds", de, None, out_file, wii_out, T, parent=parent, de_sidecar=sc_new, notes=notes,
                          names=(os.path.basename(r.source), slot), extra={"slot": slot, "template_sha256": xs.sha(tfb)})
    files = {f"3ds/{slot}": out_file, "de_to_3ds.record.json": dumps_record(rec_new).encode(),
             "de_to_wii.sidecar.json": got["de_to_wii.sidecar.json"]}
    cp = _checkpoint_folder(r.template, slot, out_file)
    if cp:
        for n, b in cp.items():                       # deterministic folder name (same inputs, same output)
            files[f"checkpoint/xcconv_{rec_new['session_id'][:12]}/{n}"] = b
    inputs = {"de": (r.source, de), "template_3ds": (r.template, tfb)}
    if r.record:
        inputs["record"] = (r.record, xs.read_sidecar_text(r.record).encode())
    if r.current:
        inputs["current_3ds"] = (r.current, safeio.read_input(r.current, "current 3DS save"))
    rep = dict(res.report, direction="de_to_3ds", summary_out=summary3(wii_out), notes=notes, checkpoint_backup=bool(cp),
               inferred_fields_with_data=unverified_nonzero(out_raw))
    return _finish(r, "de_to_3ds", files, inputs, rep, f"3ds/{slot}", "de_to_3ds.record.json", progress)
