"""xcservice - the conversion service layer shared by the xcconv CLI and the desktop GUI (Phase 2G).

Everything that reads, converts, checks, verifies or writes a save lives here (or in the engine modules it calls);
the CLI (xcconv.py) and the GUI (xcgui/) only turn user input into a request and present the result. Moving the
2F-rc1 command bodies here changed no behaviour: the CLI produces byte-identical output (tests/test_phase2g_*).

  detect(path) / preview(path)            what a file is, and a summary of a save from the verified decoders
  validate_bytes(b) / compatibility(...)  structural checks, DE -> Wii compatibility
  wii_to_de(req, progress) / de_to_wii(req, progress)
                                          one conversion; progress(stage) is called at each real stage boundary
  roundtrip(...), sidecar_info(path)      advanced checks
  find_sidecars(save, direction, folders) sidecar discovery with lineage classification (never picks silently)
  plan_output(out_dir, direction, slot)   output-folder validation without writing anything

Errors: every refusal is one of REFUSALS; nothing is written when one is raised.
"""
import hashlib
import json
import os
import re
import struct
from dataclasses import dataclass, field

import canon
import convert
import de_save
import de_to_wii
import paths
import reimport
import safeio
import sidecar as scmod
import wii_save

Refused = safeio.Refused
REFUSALS = (Refused, scmod.SidecarError, reimport.DivergenceError, de_to_wii.IncompatibleError, convert.ConvertError)
WII_SIZE = 0x28000
NICE = {"de_to_wii": "DE -> Wii", "wii_to_de": "Wii -> DE"}
TOLERATED = ("/achievements", "/quest_counters", "/clock", "/characters/1/palette2")   # documented lossy projections
SIDECAR_NAMES = {"wii_to_de": "wii_to_de.sidecar.json", "de_to_wii": "de_to_wii.sidecar.json"}
CHAR_NAMES = wii_save.CHAR_NAMES
_T = None
_MAP_NAMES = None

# real stage boundaries of a conversion, in the order they happen
STAGES = [("read", "Reading saves"), ("check", "Checking compatibility"), ("translate", "Translating gameplay state"),
          ("verify", "Verifying generated files"), ("write", "Writing output"),
          ("final", "Verifying written files")]


def tables():
    global _T
    if _T is None:
        try:
            _T = convert.load_tables()
        except FileNotFoundError as e:
            raise Refused(str(e))
    return _T


def reset_tables():
    """Forget loaded tables (after the data folder changed)."""
    global _T, _MAP_NAMES
    _T, _MAP_NAMES = None, None
    de_to_wii._WII_MAPS = None


def tables_available():
    try:
        paths.data_dir()
        return True
    except FileNotFoundError:
        return False


def sha(b):
    return hashlib.sha256(b).hexdigest()


def _noop(stage):
    pass


# ------------------------------------------------------------------------------------------------- inputs
def kind_of(b):
    if len(b) == WII_SIZE and b[:4] == b"USRD":
        return "wii"
    if b[:4] == b"DMMY":
        return "wii-empty"
    if len(b) in (de_save.V7, de_save.V10) and struct.unpack_from("<I", b, 0)[0] == (10 if len(b) == de_save.V10 else 7):
        return "de"
    return "unknown"


def load_wii(path, what):
    b = safeio.read_input(path, what)
    if b[:4] == b"DMMY":
        raise Refused(f"{what}: {path} is an empty Wii save slot")
    if len(b) != WII_SIZE or b[:4] != b"USRD":
        raise Refused(f"{what}: {path} is not a Xenoblade Chronicles Wii save (size {len(b)}, expected {WII_SIZE})")
    bad = wii_save.check_container(b)
    if bad:
        raise Refused(f"{what}: {path} is damaged or edited ({', '.join(bad)}); it is not repaired or converted")
    try:
        wii_save.decode_bytes(b, path)
    except Exception as e:
        raise Refused(f"{what}: {path} cannot be decoded ({type(e).__name__}: {e})")
    return b


def load_de(path, what, v10_only=False):
    b = safeio.read_input(path, what)
    if len(b) not in (de_save.V7, de_save.V10):
        raise Refused(f"{what}: {path} is not a Xenoblade Chronicles DE save (size {len(b)})")
    ver, want = struct.unpack_from("<I", b, 0)[0], (10 if len(b) == de_save.V10 else 7)
    if ver != want:
        raise Refused(f"{what}: {path} has header version {ver}, which does not match its size (format v{want})")
    if v10_only and ver != 10:
        raise Refused(f"{what}: {path} is a format-v{ver} save (game version 1.x). The return trip needs format v10: "
                      "load it and save once in DE 2.0 / Monado first")
    try:
        de_save.decode_bytes(b, path)
    except Exception as e:
        raise Refused(f"{what}: {path} cannot be decoded ({type(e).__name__}: {e})")
    return b


def read_sidecar_text(path, what="--sidecar"):
    text = safeio.read_input(path, what, limit=32 << 20)
    try:
        return text.decode("utf-8")
    except UnicodeDecodeError:
        raise scmod.SidecarError(f"{path} is not a text sidecar file")


def load_sidecar(path, direction):
    sc = scmod.load(read_sidecar_text(path))
    if sc["direction"] != direction:
        want = "a DE -> Wii export" if direction == "de_to_wii" else "a Wii -> DE export or re-import"
        raise Refused(f"--sidecar {path} was written by a {NICE[sc['direction']]} conversion; this command needs the "
                      f"sidecar of {want}")
    return sc


def de_slot_name(slot):
    if not re.fullmatch(r"\d\d", slot or ""):
        raise Refused(f"--slot {slot!r}: use a two-digit DE slot number such as 00 or 01")
    return f"bfsgame{slot}.sav"


def wii_slot_name(slot):
    if slot not in ("monado01", "monado02", "monado03"):
        raise Refused(f"--slot {slot!r}: use monado01, monado02 or monado03")
    return slot


# ------------------------------------------------------------------------------------------------- summaries
def summary(b):
    T = tables()
    k = kind_of(b)
    if k == "wii-empty":
        return {"game": "wii", "empty_slot": True}
    if k == "unknown":
        raise Refused("not an XC1 Wii or DE save")
    c = canon.from_wii(b, T) if k == "wii" else canon.from_de(b, T)
    s = c["shared"]
    return {"game": k, "format": c["source"]["format"], "sha256": sha(b), "story": s["story"],
            "map": "ma%02d%02d" % (s["map"] & 0xFFFF, s["map"] >> 16), "party": s["party"],
            "levels": {k_: ch["level"] for k_, ch in s["characters"].items() if k_ in s["party"]},
            "money": s["money"], "play_time": "%d:%02d:%02d" % (s["play_time_s"] // 3600, s["play_time_s"] // 60 % 60,
                                                                 s["play_time_s"] % 60),
            "clock": s["clock"], "items": {b_: len(r) for b_, r in s["inventory"].items()},
            "flags_set": len(s["flags"]), "fingerprint_shared": canon.fingerprint(c)}


def map_names():
    """{'ma0101': 'Colony 9', ...} from the user's Wii FLD_maplist (names stored inline in that table)."""
    global _MAP_NAMES
    if _MAP_NAMES is None:
        try:
            with open(paths.data("bdat_wii.json"), encoding="utf-8") as f:
                rows = json.load(f)["FLD_maplist"]["rows"]
            _MAP_NAMES = {r["resource"]: r["name"] for r in rows if isinstance(r.get("name"), str) and r["name"]}
        except (OSError, KeyError, ValueError, FileNotFoundError):
            _MAP_NAMES = {}
    return _MAP_NAMES


def detect(path):
    """-> {"kind": wii | wii-empty | de | sidecar | folder | unknown | missing, ...}. Reads at most one file; never
    decodes more than the header (cheap enough for drag-and-drop feedback)."""
    if not path or not os.path.exists(path):
        return {"kind": "missing", "path": path}
    if os.path.isdir(path):
        return {"kind": "folder", "path": path, "saves": saves_in_folder(path)}
    try:
        n = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(64)
    except OSError as e:
        return {"kind": "unknown", "path": path, "error": str(e)}
    if head.lstrip()[:1] == b"{" and n < (32 << 20):
        try:
            sc = scmod.load(read_sidecar_text(path))
            return {"kind": "sidecar", "path": path, "direction": sc["direction"]}
        except (scmod.SidecarError, Refused):
            return {"kind": "unknown", "path": path, "note": "JSON file that is not a valid sidecar"}
    if n == WII_SIZE and head[:4] == b"USRD":
        return {"kind": "wii", "path": path}
    if head[:4] == b"DMMY":
        return {"kind": "wii-empty", "path": path}
    if n in (de_save.V7, de_save.V10):
        ver = struct.unpack_from("<I", head, 0)[0]
        if ver == (10 if n == de_save.V10 else 7):
            return {"kind": "de", "path": path, "version": ver}
        return {"kind": "unknown", "path": path, "note": f"DE-sized file with header version {ver}"}
    return {"kind": "unknown", "path": path}


def saves_in_folder(folder):
    """Save files directly in folder (or its save_0 sub-folder): Wii monado01..03, DE bfsgameNN.sav."""
    out = []
    for d in (folder, os.path.join(folder, "save_0"), os.path.join(folder, "data")):
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if os.path.isfile(p) and (re.fullmatch(r"monado0[1-3]", n) or re.fullmatch(r"bfsgame\d\d\.sav", n)):
                k = detect(p)["kind"]
                if k in ("wii", "de"):
                    out.append(p)
    return out


def preview(path):
    """Display-ready summary from the verified decoders. Fields the decoders do not establish are not invented."""
    k = detect(path)["kind"]
    if k == "wii":
        b = load_wii(path, "save")
    elif k == "de":
        b = load_de(path, "save")
    elif k == "wii-empty":
        raise Refused(f"save: {path} is an empty Wii save slot")
    else:
        raise Refused(f"save: {path} is not a Xenoblade Chronicles Wii or DE save")
    s = summary(b)
    names = map_names()
    party = [{"id": cid, "name": CHAR_NAMES.get(cid, f"Character {cid}"), "level": s["levels"].get(cid)}
             for cid in s["party"]]
    ver = struct.unpack_from("<I", b, 0)[0] if k == "de" else None
    return {"game": k, "path": os.path.abspath(path), "format": s["format"], "de_version": ver,
            "story": s["story"], "map": s["map"], "map_name": names.get(s["map"]),
            "play_time": s["play_time"], "money": s["money"], "party": party,
            "items_total": sum(s["items"].values()), "clock": s["clock"], "sha256": s["sha256"],
            "unsupported_party": canon.unsupported_party({"party": s["party"], "story": s["story"]})}


def validate_bytes(b):
    T = tables()
    k = kind_of(b)
    res = {"kind": k, "sha256": sha(b), "problems": []}
    P = res["problems"]
    if k == "wii":
        res["crc"] = wii_save.check_crcs(b)
        P += wii_save.check_container(b)
        if not P:
            ir = wii_save.decode_bytes(b)
            if not ir["party"]:
                P.append("empty party")
            for c in ir["characters"][1:8]:
                if not 1 <= c["level"] <= 99:
                    P.append(f"character {c['id']} level {c['level']}")
            inv = {n: {r["index"]: r for r in ir["items"][n]} for n in wii_save.EQUIP_SLOTS + ["gem"]}
            for k_ in ir["party"]:
                if not 1 <= k_ < wii_save.N_CHARS:
                    P.append(f"party id {k_}")
                    continue
                for s, e in ir["characters"][k_]["equipment"].items():
                    if e["box_index"] is not None and (e["box_index"] not in inv[s] or
                                                       inv[s][e["box_index"]]["header"]["gid"] != e["gid"]):
                        P.append(f"character {k_} {s} -> box index {e['box_index']} does not hold item {e['gid']}")
            for s in wii_save.EQUIP_SLOTS:
                for r in inv[s].values():
                    for so in r["sockets"]:
                        if so["gem_box_ref"] is not None and so["gem_box_ref"] not in inv["gem"]:
                            P.append(f"{s}[{r['index']}] gem reference {so['gem_box_ref']} -> empty gem slot")
    elif k == "de":
        d = de_save.decode_bytes(b)
        res["version"] = d["version"]
        if not d["party"]:
            P.append("empty party")
        boxes = {n: {r["slot"] for r in recs} for n, recs in d["boxes"].items()}
        for cid in d["party"]:
            if not 1 <= cid <= 16:
                P.append(f"party id {cid}")
                continue
            c = d["characters"][cid]
            if not 1 <= c["level"] <= 99:
                P.append(f"character {cid} level {c['level']}")
            for sl, e in c["equipment"].items():
                if (e["index"], e["type"]) != (0, 0) and e["index"] not in boxes[sl]:
                    P.append(f"char {cid} {sl} -> empty slot {e['index']}")
        for n in de_to_wii.EQUIP:
            for r in d["boxes"][n]:
                for s in r["sockets"]:
                    if s["normal"] >> 16 == 3 and (s["normal"] & 0xFFFF) not in boxes["gem"]:
                        P.append(f"{n}[{r['slot']}] gem reference {s['normal'] & 0xFFFF} -> empty gem slot")
    elif k == "wii-empty":
        P.append("empty Wii save slot")
    else:
        P.append("not an XC1 Wii or DE save (size / header)")
    res["ok"] = not P
    return res


def validate_file(path):
    b = safeio.read_input(path, "save")
    try:
        res = validate_bytes(b)
    except Exception as e:     # a structurally broken file is a validation failure, not a crash
        res = {"kind": kind_of(b), "ok": False, "problems": [f"cannot be decoded: {type(e).__name__}: {e}"]}
    res["file"] = path
    return res


def readback_diffs(src_canon_shared, out_canon_shared, drop_out_slots=()):
    """Shared-state differences an output must not have (documented lossy projections excluded)."""
    cd = out_canon_shared
    if drop_out_slots:
        for box, sl in drop_out_slots:
            cd["inventory"][box].pop(sl, None)
        for box in cd["inventory"]:
            cd["inventory"][box] = canon.rerank(cd["inventory"][box])
    return [d for d in canon.compare(src_canon_shared, cd) if not d[0].startswith(TOLERATED)]


def same_instances(exported_de, de):
    """Phase 3C: {box: DE slots holding the same item as the DE save a wii_to_de sidecar exported} - same slot, same
    item id, same DE acquisition serial (the per-type counter never hands out a serial twice, 0x9AB70..0x9AB88)."""
    out = {}
    if len(exported_de) != len(de):
        return {name: set() for name, *_ in de_save.BOXES}
    for name, typ, off, size, n in de_save.BOXES:
        keep = set()
        for i in range(n):
            o = off + size * i
            if de[o + 0x10] and exported_de[o + 0x10] and de[o + 4:o + 6] == exported_de[o + 4:o + 6] and \
                    de[o + 0xC:o + 0x10] == exported_de[o + 0xC:o + 0x10]:
                keep.add(i)
        out[name] = keep
    return out


def unchanged_return_diffs(wii, de_out, sc, T):
    """Read-back of an unchanged return trip: the returned DE save, projected through the export (deferred items
    removed, compaction map applied, references followed), must equal the Wii save's state."""
    import itemcorr
    maps, bad = itemcorr.export_map(canon.from_de(de_out, T)["shared"]["inventory"],
                                    canon.from_wii(wii, T)["shared"]["inventory"], sc.get("deferred", {}))
    if bad:
        return [("/inventory (export map)", bad, None)]
    deferred = {kind: {box: {int(sl): v for sl, v in slots.items()} for box, slots in boxes.items()}
                for kind, boxes in sc.get("deferred", {}).items() if kind in ("de_only_items", "overflow_items")}
    return [d for d in de_to_wii.verify(wii, de_out, T, deferred, maps) if not d[0].startswith(TOLERATED)]


def manifest(inputs, outputs, extra):
    m = {"converter": scmod.CONVERTER_VERSION, "canon_schema": canon.SCHEMA,
         "inputs": {k: {"path": p, "sha256": sha(b)} for k, (p, b) in inputs.items() if p},
         "outputs": {k: {"sha256": sha(b), "size": len(b)} for k, b in outputs.items()}}
    m.update(extra)
    return json.dumps(m, indent=1, default=str).encode()


def require_current(cur, none, cur_opt, none_opt, game):
    if bool(cur) == bool(none):
        raise Refused(f"with --sidecar, give your current {game} save of this playthrough with "
                      f"--{cur_opt.replace('_', '-')} (it is only read), or --{none_opt.replace('_', '-')} to state "
                      f"that no {game} save is newer than the export. This protects progress made in {game} after "
                      "the export from being silently replaced.")


# ------------------------------------------------------------------------------------------------- conversions
@dataclass
class WiiToDeRequest:
    wii: str
    out: str
    template: str = None
    sidecar: str = None
    current_de: str = None
    no_current_de: bool = False
    branch: str = None
    slot: str = "00"
    dry_run: bool = False


@dataclass
class DeToWiiRequest:
    de: str
    out: str
    base: str = None
    sidecar: str = None
    current_wii: str = None
    no_current_wii: bool = False
    branch: str = None
    slot: str = "monado01"
    overflow: str = "refuse"
    same_playthrough: bool = False
    dry_run: bool = False


@dataclass
class ConversionResult:
    direction: str
    report: dict
    out_dir: str
    main_output: str          # path of the converted save inside out_dir
    sidecar_path: str
    written: dict = field(default_factory=dict)   # relative path -> sha256 (also filled in a dry run)
    dry_run: bool = False


def wii_to_de(r, progress=None):
    progress = progress or _noop
    progress("read")
    T = tables()
    slot = de_slot_name(r.slot)
    wii = load_wii(r.wii, "--wii")
    files, inputs, drop = {}, {"wii": (r.wii, wii)}, []
    if r.sidecar:
        if r.template:
            raise Refused("use either --template (first export) or --sidecar (re-import), not both")
        require_current(r.current_de, r.no_current_de, "current_de", "no_current_de", "DE")
        sc = load_sidecar(r.sidecar, "de_to_wii")
        cur_de = load_de(r.current_de, "--current-de") if r.current_de else None
        progress("check")
        progress("translate")
        out, log = reimport.wii_to_de_reimport(wii, sc, T, cur_de, r.branch, no_newer_de=r.no_current_de)
        drop = [(p[1], p[3]) for p in log.get("deferred_restored", [])]
        inputs.update(sidecar=(r.sidecar, scmod.dumps(sc).encode()), current_de=(r.current_de, cur_de or b""))
        parent, notes = sc, ["re-import onto the original DE save"]
    else:
        if not r.template:
            raise Refused("--template (a DE v10 save to start from) or --sidecar is required")
        if r.current_de or r.no_current_de or r.branch:
            raise Refused("--current-de / --no-current-de / --branch only apply to a re-import with --sidecar")
        tpl = load_de(r.template, "--template", v10_only=True)
        progress("check")
        progress("translate")
        out, log, fail = convert.build(wii, tpl, T, convert.FEATURES_2F, "clear", r.wii, r.template)
        if fail:
            raise Refused(f"read-back verification failed: {fail[:5]}")
        inputs["template"] = (r.template, tpl)
        tdir = os.path.dirname(os.path.abspath(r.template))
        for extra in (slot.replace(".sav", ".tmb"), "bfssystem.sav"):
            p = os.path.join(tdir, extra)
            if not os.path.exists(p):
                p = os.path.join(tdir, extra.replace(r.slot, "00"))
            if os.path.isfile(p):
                files[f"save_0/{extra}"] = safeio.read_input(p, "template companion file")
        parent, notes = None, ["first export Wii -> DE"]
    progress("verify")
    cw = canon.from_wii(wii, T)
    if r.sidecar and log.get("result", "").startswith("Wii unchanged"):
        # Phase 3C (3B finding B2): the DE save comes back unchanged, at its own slots; compare it with the Wii state
        # through the export's compaction map (items the export moved to other Wii slots), not slot by slot
        hard = unchanged_return_diffs(wii, out, sc, T)
    else:
        hard = readback_diffs(cw["shared"], canon.from_de(out, T)["shared"], drop)   # deferred DE-only items excluded
        # Phase 3E: stored gear the Wii session did not change keeps the DE's own entries (re-import 3-way)
        kept = tuple(f"/stored_gear/{k}" for k in (log.get("stored_gear") or {}).get("kept_from_de", ()))
        hard = [d for d in hard if not (kept and d[0].startswith(kept))]
    if hard:
        raise Refused(f"independent read-back differs from the Wii state: {hard[:5]}")
    co = canon.from_de(out, T)
    sc_new = scmod.make("wii_to_de", wii, out, cw, co, parent=parent, names=(os.path.basename(r.wii), slot), notes=notes)
    files[f"save_0/{slot}"] = out
    files["wii_to_de.sidecar.json"] = scmod.dumps(sc_new).encode()
    files["manifest.json"] = manifest(inputs, {k: v for k, v in files.items() if k != "manifest.json"},
                                      {"direction": "wii_to_de", "sidecar_session": sc_new["session_id"]})
    rep = {"direction": "wii_to_de", "summary_in": summary(wii), "summary_out": summary(out),
           "written": sorted(files), "log": log if r.sidecar else
           {k: v for k, v in log.items() if k not in ("flags", "minimap")}, "dry_run": r.dry_run,
           "deferred_restored": log.get("deferred_restored", []) if r.sidecar else [],
           "kept_in_sidecar": ["full snapshot of the Wii save (recovery)", "full snapshot of the DE output",
                               "Wii-only state: EXP-earned counters, Wii-only flags, Wii time words"]}
    if not r.dry_run:
        progress("write")
    digests = safeio.commit(r.out, files, r.dry_run)
    if not r.dry_run:
        progress("final")
    return ConversionResult("wii_to_de", rep, r.out, os.path.join(r.out, "save_0", slot),
                            os.path.join(r.out, SIDECAR_NAMES["wii_to_de"]), digests, r.dry_run)


def de_to_wii_convert(r, progress=None):
    progress = progress or _noop
    progress("read")
    T = tables()
    slot = wii_slot_name(r.slot)
    de = load_de(r.de, "--de", v10_only=True)
    files, inputs = {}, {"de": (r.de, de)}
    if r.sidecar:
        if r.base:
            raise Refused("use either --base or --sidecar, not both")
        require_current(r.current_wii, r.no_current_wii, "current_wii", "no_current_wii", "Wii")
        sc = load_sidecar(r.sidecar, "wii_to_de")
        progress("check")
        base = scmod.source_image(sc)
        ok, reasons, changed = scmod.descent(scmod.output_image(sc), de, T, "de")
        if not ok:
            raise Refused("the DE save does not continue the exported one: " + "; ".join(reasons))
        cur_wii = load_wii(r.current_wii, "--current-wii") if r.current_wii else None
        div, detail = scmod.divergence(sc, cur_wii, T)
        if div:
            ratio, nfacts = scmod.stale_evidence(sc, cur_wii, de, T)
            if changed and nfacts >= scmod.STALE_MIN_FACTS and ratio >= scmod.STALE_RATIO:
                raise Refused(f"this sidecar looks older than your latest Wii -> DE conversion: {ratio:.0%} of the "
                              "progress your current Wii save made since this sidecar's export is already in the DE "
                              "save. Use the sidecar written by your most recent Wii -> DE conversion.")
            if changed and r.branch != "de":
                raise Refused("your current Wii save is not the one this sidecar exported: it changed after the export, "
                              "and the DE save also progressed. Either you played on the Wii after exporting (choose "
                              "--branch de to keep the DE progress and DISCARD the Wii progress made after the export), "
                              "or this sidecar is older than your latest conversion (use the newest sidecar).")
            if not changed and r.branch != "de":
                raise Refused("the DE save has no progress since the export but the Wii save does: nothing to export "
                              "(your current Wii save is the newer one)")
        elif cur_wii is not None and cur_wii != base:
            base = cur_wii       # same shared state, newer Wii-exclusive state: keep it
        lineage, base_name, parent, base_dir = True, "sidecar original Wii", sc, None
        instances = same_instances(scmod.output_image(sc), de)
        inputs.update(sidecar=(r.sidecar, scmod.dumps(sc).encode()), current_wii=(r.current_wii, cur_wii or b""))
    else:
        if not r.base:
            raise Refused("--base (a valid Wii XC1 save used as the structural template) or --sidecar is required")
        if r.current_wii or r.no_current_wii or r.branch:
            raise Refused("--current-wii / --no-current-wii / --branch only apply with --sidecar")
        base = load_wii(r.base, "--base")
        progress("check")
        lineage, base_name, parent, instances = r.same_playthrough, r.base, None, None
        base_dir = os.path.dirname(os.path.abspath(r.base))
        inputs["base"] = (r.base, base)
    progress("translate")
    out, log, deferred = de_to_wii.build(de, base, T, lineage=lineage, de_name=r.de, base_name=base_name,
                                         overflow=r.overflow, instances=instances)
    progress("verify")
    diffs = de_to_wii.verify(out, de, T, deferred, log["remap"])
    if diffs:
        raise Refused(f"independent read-back differs from the DE state: {diffs[:5]}")
    sc_new = scmod.make("de_to_wii", de, out, canon.from_de(de, T), canon.from_wii(out, T), deferred=deferred,
                        parent=parent, names=(os.path.basename(r.de), slot),
                        notes=[f"base: {'lineage' if lineage else 'foreign structural template'}"])
    files[slot] = out
    if base_dir and os.path.isfile(os.path.join(base_dir, "banner.bin")):
        files["banner.bin"] = safeio.read_input(os.path.join(base_dir, "banner.bin"), "banner.bin")
    files["de_to_wii.sidecar.json"] = scmod.dumps(sc_new).encode()
    files["manifest.json"] = manifest(inputs, {k: v for k, v in files.items() if k != "manifest.json"},
                                      {"direction": "de_to_wii", "sidecar_session": sc_new["session_id"]})
    deferred_n = {k: (sum(len(x) for x in v.values()) if isinstance(v, dict) and v and
                      isinstance(next(iter(v.values())), dict) else len(v)) for k, v in deferred.items()}
    rep = {"direction": "de_to_wii", "summary_in": summary(de), "summary_out": summary(out), "written": sorted(files),
           "deferred_to_sidecar": deferred_n, "log": {k: v for k, v in log.items() if k != "remap"},
           "dry_run": r.dry_run,
           "kept_in_sidecar": ["full snapshot of the DE save (recovery + re-import template): Expert Mode, cosmetics, "
                               "DE-only flags, Future Connected, Time Attack, options", "full snapshot of the Wii output"]}
    if not r.dry_run:
        progress("write")
    digests = safeio.commit(r.out, files, r.dry_run)
    if not r.dry_run:
        progress("final")
    return ConversionResult("de_to_wii", rep, r.out, os.path.join(r.out, slot),
                            os.path.join(r.out, SIDECAR_NAMES["de_to_wii"]), digests, r.dry_run)


def convert_request(req, progress=None):
    if isinstance(req, WiiToDeRequest):
        return wii_to_de(req, progress)
    if isinstance(req, DeToWiiRequest):
        return de_to_wii_convert(req, progress)
    raise TypeError(f"unknown request {type(req).__name__}")


# ------------------------------------------------------------------------------------------------- advanced checks
def roundtrip(wii=None, template=None, de=None, base=None):
    T = tables()
    if wii:
        wb = load_wii(wii, "--wii")
        tpl = load_de(template, "--template", v10_only=True)
        deb, log, fail = convert.build(wb, tpl, T)
        if fail:
            raise Refused(f"read-back verification failed: {fail[:5]}")
        back, blog, deferred = de_to_wii.build(deb, wb, T, lineage=True)
        return {"route": "wii -> de -> wii", "byte_identical": back == wb,
                "bytes_differing": sum(1 for x, y in zip(back, wb) if x != y),
                "shared_differences": [list(map(str, d)) for d in canon.compare(canon.from_wii(wb, T)["shared"],
                                                                                 canon.from_wii(back, T)["shared"])]}
    deb = load_de(de, "--de", v10_only=True)
    bb = load_wii(base, "--base")
    w, log, deferred = de_to_wii.build(deb, bb, T, lineage=False)
    sc = scmod.make("de_to_wii", deb, w, canon.from_de(deb, T), canon.from_wii(w, T), deferred=deferred)
    back, rlog = reimport.wii_to_de_reimport(w, sc, T, no_newer_de=True)
    return {"route": "de -> wii -> de (sidecar)", "byte_identical": back == deb,
            "bytes_differing": sum(1 for x, y in zip(back, deb) if x != y), "reimport": rlog}


def compatibility(de, base=None):
    T = tables()
    deb = load_de(de, "--de")
    bb = load_wii(base, "--base") if base else None
    cd = canon.from_de(deb, T)
    problems, deferred = de_to_wii.compatibility(cd, deb, T)
    if struct.unpack_from("<I", deb, 0)[0] != 10:
        problems.append("format v7 (game 1.x): load and save it once in DE 2.0 / Monado so it becomes v10")
    rep = {"compatible": not problems, "problems": problems,
           "deferred_to_sidecar": {k: (len(v) if hasattr(v, "__len__") else v) for k, v in deferred.items()}}
    if bb:
        caps = de_to_wii.wii_capacity(bb)
        rep["capacity_check"] = {b: {"items": len(r), "wii_capacity": caps[b], "fits": len(r) <= caps[b]}
                                 for b, r in cd["shared"]["inventory"].items()}
        over = [b for b, v in rep["capacity_check"].items() if not v["fits"]]
        if over:
            rep["note"] = f"boxes over the Wii capacity: {over} - de-to-wii needs --overflow sidecar for them"
    return rep


def wii_compatibility(wii):
    """Wii -> DE pre-check (the engine refuses these too; this lets the GUI warn before the user fills in the rest)."""
    T = tables()
    wb = load_wii(wii, "--wii")
    ir = wii_save.decode_bytes(wb)
    problems = []
    import flagmap as fm
    story = fm.wii_get(wb, 0x20)
    bad = convert.unsupported_wii_party(ir, story)
    if bad:
        problems.append(f"party member(s) {bad} cannot be in the party at scenario {story} (9-13 are prologue guests; "
                        "Fiora is character 3 before scenario 275 and character 8 from 275)")
    return {"compatible": not problems, "problems": problems, "summary": summary(wb)}


def sidecar_info(path):
    return scmod.info(scmod.load(read_sidecar_text(path, "sidecar")))


# ------------------------------------------------------------------------------------------------- sidecar discovery
# The sidecar a conversion needs is the one the LAST conversion of the other direction wrote:
#   DE save  -> Wii  re-import needs  wii_to_de.sidecar.json  (whose DE output this DE save continues)
#   Wii save -> DE   re-import needs  de_to_wii.sidecar.json  (whose Wii output this Wii save continues)
NEEDED = {"de_to_wii": "wii_to_de", "wii_to_de": "de_to_wii"}


@dataclass
class SidecarCandidate:
    path: str
    status: str            # "exact" (save unchanged since that export) | "continues" | "unrelated" | "invalid" | "wrong-direction"
    detail: str
    generation: int = 0
    playthrough: str = ""
    session: str = ""
    newest: bool = False   # highest generation among the matching candidates of its playthrough


@dataclass
class SidecarDiscovery:
    candidates: list
    chosen: SidecarCandidate = None    # set only when the choice is unambiguous
    reason: str = ""


MAX_SIDECARS = 60


def _sidecar_files(folders):
    """folders: [(folder, depth)]; depth 0 = the folder's own files, 1 = also its sub-folders, ... Newest first."""
    seen, out = set(), []
    for top, depth in folders:
        if not top or not os.path.isdir(top):
            continue
        for root, dirs, files in os.walk(top):
            rel = os.path.relpath(root, top)
            level = 0 if rel == "." else rel.count(os.sep) + 1
            dirs[:] = [] if level >= depth else [x for x in dirs if not x.startswith(safeio.STAGING_PREFIX)]
            for n in files:
                if n.endswith(".sidecar.json"):
                    p = os.path.abspath(os.path.join(root, n))
                    if os.path.normcase(p) not in seen:
                        seen.add(os.path.normcase(p))
                        out.append(p)
    out.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return out[:MAX_SIDECARS]


def classify_sidecar(path, save_bytes, direction):
    """How does the sidecar at path relate to save_bytes (the save being converted in `direction`)?"""
    T = tables()
    need = NEEDED[direction]
    try:
        sc = scmod.load(read_sidecar_text(path))
    except (scmod.SidecarError, Refused) as e:
        return SidecarCandidate(path, "invalid", str(e))
    lin = sc["lineage"]
    base = dict(generation=lin["generation"], playthrough=lin["playthrough_id"], session=sc["session_id"])
    if sc["direction"] != need:
        return SidecarCandidate(path, "wrong-direction", f"written by a {NICE[sc['direction']]} conversion", **base)
    game = "de" if need == "wii_to_de" else "wii"
    out_img = scmod.output_image(sc)
    if out_img == save_bytes:
        return SidecarCandidate(path, "exact", "this save is exactly the file that conversion produced", **base)
    try:
        ok, reasons, changed = scmod.descent(out_img, save_bytes, T, game)
    except Exception as e:
        return SidecarCandidate(path, "invalid", f"cannot compare ({type(e).__name__})", **base)
    if ok:
        return SidecarCandidate(path, "continues", "; ".join(reasons), **base)
    return SidecarCandidate(path, "unrelated", "; ".join(reasons), **base)


def find_sidecars(save_path, direction, folders=()):
    """Look for sidecars next to the save (and one folder down), in its parent folder, and up to two folders down in
    each of `folders` (e.g. the GUI's output folder). The choice is made only when exactly one candidate matches the
    save and no sidecar of the same playthrough is newer (higher generation); otherwise the caller must ask the user.
    A stale sidecar is never chosen."""
    save_bytes = safeio.read_input(save_path, "save")
    here = os.path.dirname(os.path.abspath(save_path))
    look = [(here, 1), (os.path.dirname(here), 0), *((f, 2) if isinstance(f, str) else f for f in folders)]
    cands = [classify_sidecar(p, save_bytes, direction) for p in _sidecar_files(look)]
    match = [c for c in cands if c.status in ("exact", "continues")]
    for c in match:   # newest = no valid sidecar of the same history (either direction) has a higher generation
        c.newest = c.generation >= max(m.generation for m in cands
                                       if m.playthrough == c.playthrough and m.status != "invalid")
    disc = SidecarDiscovery(cands)
    if not match:
        disc.reason = "none of the preservation files found belongs to this save" if cands else "no preservation file found"
        return disc
    if len({c.playthrough for c in match}) > 1:
        disc.reason = "preservation files of different save histories match this save; choose one deliberately"
        return disc
    best = [c for c in match if c.newest]
    if not best:
        disc.reason = ("a later conversion of this save history wrote a newer preservation file that does not match "
                       "this save; choose deliberately")
        return disc
    if len({c.session for c in best}) > 1:
        disc.reason = "several preservation files match this save; choose one"
        return disc
    c = sorted(best, key=lambda m: m.status != "exact")[0]     # copies of one sidecar: any will do
    disc.chosen, disc.reason = c, ("the save is exactly the output of this conversion" if c.status == "exact"
                                   else "the save continues the output of this conversion")
    return disc


# ------------------------------------------------------------------------------------------------- history plan (2H)
# The GUI asks for one "destination game save" in every case. resolve_history() decides what it is:
#   first conversion  -> the structural starting save (--template / --base)
#   return conversion -> the current save of that game (--current-de / --current-wii), with the sidecar found here
# It never chooses a stale or ambiguous sidecar, and it never falls back to a first conversion when the save has a
# matching history or when the two saves look like one playthrough without a history (the user must decide).
SAME_PLAYTHROUGH = 0.8   # flag-set Jaccard similarity; measured: one playthrough >= 0.93, different ones <= 0.49


@dataclass
class HistoryPlan:
    mode: str                     # "first" | "return" | "blocked"
    issue: str = ""               # "" | "choose" | "older" | "chosen-invalid" | "dest-unrelated" | "same-playthrough"
    sidecar: str = None           # path of the sidecar a return conversion uses
    candidate: SidecarCandidate = None
    choices: list = field(default_factory=list)    # usable candidates when the user must choose
    dest_relation: str = ""       # return: "exact" | "continues" | "unrelated" | "" (no destination save)
    similarity: float = None      # first: flag similarity of source and destination save
    detail: str = ""


def _shared(b):
    T = tables()
    return (canon.from_wii(b, T) if kind_of(b) == "wii" else canon.from_de(b, T))["shared"]


def similarity(a_bytes, b_bytes):
    """Share of story/quest flags the two saves have in common (game-neutral canonical flags, 0..1)."""
    fa, fb = set(_shared(a_bytes)["flags"].items()), set(_shared(b_bytes)["flags"].items())
    return len(fa & fb) / max(len(fa | fb), 1)


def destination_relation(sidecar_path, dest_bytes):
    """Return trip: is dest the save the last conversion started from, or a continuation of it?"""
    sc = scmod.load(read_sidecar_text(sidecar_path))
    src = scmod.source_image(sc)
    if dest_bytes == src:
        return "exact"
    ok, _, _ = scmod.descent(src, dest_bytes, tables(), sc["source"]["game"])
    return "continues" if ok else "unrelated"


def resolve_history(source, direction, dest=None, folders=(), chosen=None, start_fresh=False):
    """Decide first vs return conversion for the GUI. Reads only; raises REFUSALS for unreadable inputs."""
    src_bytes = safeio.read_input(source, "save")
    dest_bytes = safeio.read_input(dest, "destination save") if dest else None
    plan = HistoryPlan("blocked")
    if chosen:
        c = classify_sidecar(chosen, src_bytes, direction)
        if c.status not in ("exact", "continues"):
            plan.issue, plan.candidate, plan.detail = "chosen-invalid", c, c.detail
            return plan
        plan.mode, plan.sidecar, plan.candidate = "return", c.path, c
    else:
        extra = [(os.path.dirname(os.path.abspath(dest)), 1)] if dest else []
        disc = find_sidecars(source, direction, [*folders, *extra])
        usable = [c for c in disc.candidates if c.status in ("exact", "continues")]
        if disc.chosen:
            plan.mode, plan.sidecar, plan.candidate = "return", disc.chosen.path, disc.chosen
        elif usable:
            plan.choices, plan.detail = usable, disc.reason
            plan.issue = "older" if not any(c.newest for c in usable) else "choose"
            return plan
        elif start_fresh:
            plan.mode = "first"
            return plan
        else:
            plan.mode = "first"
            if dest_bytes is not None and kind_of(dest_bytes) in ("wii", "de"):
                plan.similarity = round(similarity(src_bytes, dest_bytes), 3)
                if plan.similarity >= SAME_PLAYTHROUGH:
                    plan.mode, plan.issue = "blocked", "same-playthrough"
            return plan
    if dest_bytes is not None:
        plan.dest_relation = destination_relation(plan.sidecar, dest_bytes)
        if plan.dest_relation == "unrelated":
            plan.mode, plan.issue = "blocked", "dest-unrelated"
    return plan


@dataclass
class SlotSuggestion:
    slot: str
    free: bool        # no save with this name next to the destination save
    used: list = field(default_factory=list)


def suggest_slot(direction, dest=None):
    """A slot name not used next to the destination save (so copying the result back cannot replace a save there)."""
    folder = os.path.dirname(os.path.abspath(dest)) if dest else None
    names = set(os.listdir(folder)) if folder and os.path.isdir(folder) else set()
    if direction == "wii_to_de":
        used = sorted(int(m.group(1)) for n in names if (m := re.fullmatch(r"bfsgame(\d\d)\.sav", n)))
        for n in [*range(1, 100), 0]:
            if n not in used:
                return SlotSuggestion(f"{n:02d}", True, [f"{u:02d}" for u in used])
        return SlotSuggestion("01", False, [f"{u:02d}" for u in used])
    used = []
    for s in ("monado01", "monado02", "monado03"):
        p = os.path.join(folder, s) if folder else None
        if p and os.path.isfile(p) and detect(p)["kind"] == "wii":
            used.append(s)
    for s in ("monado01", "monado02", "monado03"):
        if s not in used:
            return SlotSuggestion(s, True, used)
    own = os.path.basename(dest) if dest else "monado01"
    return SlotSuggestion(own if own in used else "monado01", False, used)


# ------------------------------------------------------------------------------------------------- output folders
def new_output_name(direction, stamp):
    return f"{'wii_to_de' if direction == 'wii_to_de' else 'de_to_wii'}_{stamp}"


def plan_output(out_dir, direction, slot):
    """Check an output folder without writing (the same rules as the commit). -> list of relative output files."""
    if direction == "wii_to_de":
        rel = [f"save_0/{de_slot_name(slot)}", SIDECAR_NAMES[direction], "manifest.json"]
    else:
        rel = [wii_slot_name(slot), SIDECAR_NAMES[direction], "manifest.json"]
    safeio.plan(out_dir, {k: b"" for k in rel})
    return rel
