"""Sync All: one transaction that turns the chosen save into a complete, validated generation for every configured
platform, commits it with a single pointer update, and publishes it into the device ready folders.

The two families
  W  Wii and 3DS saves hold the same state in the same layout (3A: lossless transcode)
  D  the Definitive Edition, which holds more (Expert Mode, outfits, DE-only items/flags, ...)
Within a family nothing is converted beyond the 3A transcode. Between the families the unchanged 2H engine runs:
  W -> D   xcservice.wii_to_de: a re-import onto the DE "anchor" (the last DE save that was actually played, with the
           DE -> Wii sidecar made from it), or a first export onto the DE template
  D -> W   xcservice.de_to_wii_convert: a return onto the W anchor (the last Wii/3DS save actually played, with the
           Wii -> DE sidecar made from it), or a first conversion onto the Wii/3DS template
so DE-only state survives any number of Wii/3DS generations and Wii-only state survives DE generations, exactly as
the engine's own return trips (which the 2H/3A tests and emulator runs validated).

Anchors: generation N sourced from family F records anchors[F] = (N, the F -> other sidecar it produced) and
inherits anchors[other] from the generation its source continued (normally the previous one). Nothing is ever
merged: the source is converted as it is; the other family only contributes what the engine restores from its own
anchor (exclusive state), never progress.

Transaction (all inside the hub folder, one volume):
  staging/tx-<id>/            built, written, fsync'ed, re-read and validated
  -> os.rename to history/gen-NNNNNN   (one step; the folder is never modified again)
  -> metadata/sync-state.json replaced atomically (the commit point; the previous pointer is kept)
  -> publish: ready/<device>/ files replaced one by one from the immutable generation, READY.json last.
A crash before the pointer update leaves the old generation current (the prepared folder is set aside at the next
Sync); a crash during publication leaves READY.json at the old generation, so the scan reports the folder as
outdated and Finish publishing repeats it. Nothing here claims to know whether a file reached a device.
"""
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field

from . import paths3b  # noqa: F401
from . import GENERATION_SCHEMA, APP_VERSION
from .store import (Hub, HubError, FAMILY, SHORT, NICE, sha, sha_file, now_iso, atomic_write, write_json,
                    family_image, summarize_image)
from . import scan as scanmod

import canon
import safeio
import sidecar as scmod
import xc3d
import xc3dservice as s3
import xcservice as xs

STAGES = [("check", "Checking the selected save"), ("build", "Creating the saves"),
          ("validate", "Validating every save"), ("commit", "Saving the new generation"),
          ("publish", "Updating the device folders"), ("done", "Done")]
OTHER = {"wii": "de", "de": "wii"}
FAULT = None              # test hook: callable(point, detail) - may raise (failure injection)


class Cancelled(HubError):
    pass


class Blocked(HubError):
    """Some configured platform cannot be produced; nothing was committed."""

    def __init__(self, msg, blocked):
        super().__init__(msg)
        self.blocked = blocked


def _fault(point, detail=""):
    if FAULT is not None:
        FAULT(point, detail)


@dataclass
class SyncResult:
    generation: int
    kind: str
    gen_dir: str
    platforms: list
    published: dict = field(default_factory=dict)       # device id -> "ready" | "failed: ..." | "not-available"
    partial: bool = False
    blocked: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    message: str = ""
    complete: bool = False


# ------------------------------------------------------------------------------------------------- helpers
def _rd(p):
    with open(p, "rb") as f:
        return f.read()


def _put(root, rel, data):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return p


def _collect(folder):
    out = {}
    for dp, _, fs in os.walk(folder):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, folder).replace("\\", "/")] = _rd(p)
    return out


def _gen_files(gdir):
    out = {}
    for dp, _, fs in os.walk(gdir):
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, gdir).replace("\\", "/")
            if rel != "generation.json":
                out[rel] = sha_file(p)
    return out


def _engine_error(e):
    s = str(e)
    return s if len(s) < 400 else s[:397] + "..."


# ------------------------------------------------------------------------------------------------- recovery
def recover(hub):
    """Inside the lock: remove interrupted transactions (ours, never referenced) and set aside prepared but
    uncommitted generation folders. -> notes."""
    notes = []
    st = hub.p("staging")
    if os.path.isdir(st):
        for n in os.listdir(st):
            p = os.path.join(st, n)
            if os.path.isdir(p) and (n.startswith("tx-") or n.startswith("pub-")):
                shutil.rmtree(p)
                notes.append(f"removed an interrupted sync ({n})")
    committed = set(hub.committed())
    hd = hub.p("history")
    if os.path.isdir(hd):
        for n in sorted(os.listdir(hd)):
            m = re.fullmatch(r"gen-(\d{6})", n)
            if m and int(m.group(1)) not in committed:
                dst = hub.p("history", "interrupted", f"{n}-{time.strftime('%Y%m%d-%H%M%S')}")
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(os.path.join(hd, n), dst)
                notes.append(f"set aside the uncommitted {n} (interrupted before it became current)")
    return notes


# ------------------------------------------------------------------------------------------------- audit
def _item_identity(shared, box, idx):
    """What sits in inventory slot idx of box: the item itself (with its gems), independent of the slot number
    (a DE -> Wii conversion renumbers slots when DE-only / overflow items are set aside)."""
    if idx is None:
        return None
    rec = (shared["inventory"].get(box) or {}).get(idx)
    if rec is None:
        return ["missing", box, idx]
    socks = []
    for s in rec.get("sockets", []):
        if s and s[0] == "gem":
            g = shared["inventory"].get("gem", {}).get(s[1])
            socks.append(list(canon.item_key("gem", g)) if g else ["missing gem", s[1]])
        else:
            socks.append(s)
    return [box, rec.get("gid"), socks]


def _normalized(shared):
    out = {k: v for k, v in shared.items() if k != "inventory"}
    chars = {}
    for k, ch in shared["characters"].items():
        c = dict(ch)
        if ch.get("equipment"):
            c["equipment"] = {s: _item_identity(shared, s, i) for s, i in ch["equipment"].items()}
        chars[k] = c
    out["characters"] = chars
    return out


def _audit(a, b, what):
    """Independent gameplay comparison of two shared states (documented lossy projections excluded). Equipment is
    compared by the items worn (and their gems), not by inventory slot numbers.
    -> list of differences outside the inventory, and the inventory multiset difference (a - b, b - a)."""
    diffs = [d for d in canon.compare(_normalized(a), _normalized(b)) if not d[0].startswith(xs.TOLERATED)]
    ia, ib = scmod._items(a), scmod._items(b)
    lost = {k: n - ib.get(k, 0) for k, n in ia.items() if n > ib.get(k, 0)}
    extra = {k: n - ia.get(k, 0) for k, n in ib.items() if n > ia.get(k, 0)}
    return diffs, lost, extra


def _count(d):
    return sum(d.values())


# ------------------------------------------------------------------------------------------------- Wii junk
JUNK_SPANS = [(s, e) for s, e, k in xc3d.SCHEMA if k[0] in ("gap", "pad")]
CRC_FIELDS = [(h + 0xC, h + 0x10) for _, h, _, _ in xc3d.SECTIONS]


def clean_wii_junk(w, T):
    """A Wii save written by the game after play can hold leftover heap bytes in the gaps between sections and in
    struct padding (defect B1, found in Phase 3B: 9,269 such bytes in a Dolphin save of the user's playthrough).
    They are not game data, the 3DS layout stores fixed filler there, and the 3A engine's strict read-back check
    then refuses the 3DS conversion. -> the image with exactly those bytes zeroed (as a 3DS -> Wii transcode writes
    them) and the section checksums recomputed. Proven harmless per call: only schema gap/pad bytes and checksum
    fields may differ, and the canonical gameplay state must be identical."""
    b = bytearray(w)
    for s, e in JUNK_SPANS:
        b[s:e] = bytes(e - s)
    if bytes(b) == w:
        return w
    out = xc3d.fix_wii_checksums(bytes(b))
    allowed = JUNK_SPANS + CRC_FIELDS
    for i in range(len(w)):
        if out[i] != w[i] and not any(s <= i < e for s, e in allowed):
            raise HubError(f"internal: clearing unused Wii bytes changed offset {i:#x}")
    if canon.fingerprint(canon.from_wii(out, T)) != canon.fingerprint(canon.from_wii(w, T)):
        raise HubError("internal: clearing unused Wii bytes changed the gameplay state")
    return out


# ------------------------------------------------------------------------------------------------- build
class Builder:
    def __init__(self, hub, tx, src, base_gen, n, kind, progress):
        self.hub, self.tx, self.src, self.base, self.n, self.kind = hub, tx, src, base_gen, n, kind
        self.progress = progress
        self.work = os.path.join(tx, "engine")
        self.gfiles = {}           # rel -> bytes (generation folder content)
        self.outputs = {}          # platform -> {"main": rel, "files": {rel: sha}, "from": ..}
        self.family_images = {}    # family -> {"file": rel, "sha256"}
        self.images = {}           # family -> bytes
        self.conversions = []
        self.notes = []
        self.blocked = {}
        self.validation = []
        self.cross = None          # {"direction", "file"}
        self.T = xs.tables()
        self.deferred_n = 0

    # anchors of the base generation (absolute paths resolved inside the hub)
    def anchor(self, family):
        if not self.base:
            return None
        a = (self.base.get("anchors") or {}).get(family)
        if not a or not a.get("sidecar"):
            return None
        sc = self.hub.p(*a["sidecar"].split("/"))
        cur = self.hub.p(*a["current"].split("/"))
        for p, h in ((sc, a.get("sidecar_sha256")), (cur, a.get("current_sha256"))):
            if not os.path.isfile(p) or (h and sha_file(p) != h):
                raise HubError(f"the history file {p} needed for this sync is missing or changed")
        return {"gen": a["gen"], "sidecar": sc, "current": cur, "rel": a}

    def _in(self, name, data):
        p = os.path.join(self.tx, "in", name)
        if not os.path.exists(p):
            _put(os.path.join(self.tx, "in"), name, data)
        return p

    def template(self, platform):
        return self.hub.template_file(platform)

    # ---- the cross-family conversions
    def w_to_d(self, wpath):
        a = self.anchor("de")
        out = os.path.join(self.work, "wii_to_de")
        req = xs.WiiToDeRequest(wii=wpath, out=out, slot="00")
        if a:
            req.sidecar, req.current_de = a["sidecar"], a["current"]
            mode = f"return onto the DE save of generation {a['gen']}"
        else:
            t = self.template("de")
            if not t:
                raise Blocked("no DE template", {"de": "A DE save is needed once as a template: add one in Settings"})
            req.template = t
            mode = "first conversion onto the DE template"
        _fault("convert", "wii_to_de")
        res = xs.wii_to_de(req, None)
        got = _collect(res.out_dir)
        sc = got["wii_to_de.sidecar.json"]
        scmod.load(sc.decode())
        de_rel = [k for k in got if k.startswith("save_0/bfsgame") and k.endswith(".sav")][0]
        self.conversions.append({"direction": "wii_to_de", "mode": mode, "anchor": a["gen"] if a else None,
                                 "notes": res.report.get("notes", []) if isinstance(res.report, dict) else []})
        restored = res.report.get("deferred_restored", [])
        if restored:
            self.notes.append(f"{len(restored)} DE-only or overflow item(s) put back into the DE save")
        self.deferred_n = len(restored)
        tmb = got.get(de_rel[:-4] + ".tmb") or self._prev_tmb()     # a return trip writes no thumbnail
        return got[de_rel], tmb, sc, "wii_to_de.sidecar.json"

    def d_to_w(self, dpath):
        a = self.anchor("wii")
        out = os.path.join(self.work, "de_to_wii")
        req = xs.DeToWiiRequest(de=dpath, out=out, overflow="sidecar")
        if a:
            req.sidecar, req.current_wii = a["sidecar"], a["current"]
            mode = f"return onto the Wii/3DS save of generation {a['gen']}"
        else:
            t = self.template("wii")
            if t:
                req.base = t
                mode = "first conversion onto the Wii template"
            else:
                t3 = self.template("3ds")
                if not t3:
                    raise Blocked("no Wii/3DS template", {
                        "wii": "A Wii or 3DS save is needed once as a template: add one in Settings",
                        "3ds": "A Wii or 3DS save is needed once as a template: add one in Settings"})
                req.base = self._in("base/monado01", s3.load_3ds(t3, "3DS template")[2])
                mode = "first conversion onto the 3DS template (as Wii layout)"
        _fault("convert", "de_to_wii")
        res = xs.de_to_wii_convert(req, None)
        got = _collect(res.out_dir)
        sc = got["de_to_wii.sidecar.json"]
        scmod.load(sc.decode())
        dn = res.report.get("deferred_to_sidecar", {})
        self.deferred_n = sum(v for v in dn.values() if isinstance(v, int))
        if self.deferred_n:
            self.notes.append(f"{self.deferred_n} DE-only or overflow item(s) wait in the history for the next return "
                              "to DE (the Wii/3DS cannot hold them)")
        self.conversions.append({"direction": "de_to_wii", "mode": mode, "anchor": a["gen"] if a else None})
        return got["monado01"], got.get("banner.bin"), sc, "de_to_wii.sidecar.json"

    def w_to_3ds(self, wpath):
        tpl = self.picture_template()
        if not tpl:
            raise Blocked("no 3DS template", {"3ds": "A 3DS save is needed once as a template (it supplies the "
                                                     "save picture): add one in Settings"})
        w = _rd(wpath)
        clean = clean_wii_junk(w, self.T)
        if clean != w:
            wpath = self._in("w3/monado01", clean)
            self.notes.append("unused bytes between the save's sections (left over by the Wii game) were cleared "
                              "before the 3DS conversion; no game data is affected")
        out = os.path.join(self.work, "wii_to_3ds")
        _fault("convert", "wii_to_3ds")
        res = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=wpath, out=out, template=tpl, slot="1"))
        got = _collect(res.out_dir)
        self.conversions.append({"direction": "wii_to_3ds", "mode": "lossless transcode, character stats rebuilt",
                                 "picture": os.path.relpath(tpl, self.hub.root).replace("\\", "/")})
        return got["3ds/monado01"]

    def picture_template(self):
        """The newest 3DS output of the lineage (keeps the user's picture), else the 3DS template."""
        g = self.base
        while g:
            o = (g.get("outputs") or {}).get("3ds")
            if o:
                p = os.path.join(g["_dir"], *o["main"].split("/"))
                if os.path.isfile(p) and sha_file(p) == o["files"][o["main"]]:
                    return p
            par = g.get("parent")
            g = self.hub.load_generation(par) if par else None
        return self.template("3ds")

    # ---- the generation
    def build(self, targets):
        src = self.src
        fam = FAMILY[src["platform"]]
        b = src["bytes"]
        self.gfiles[f"source/{src['name']}"] = b
        if fam == "wii":
            wimg = src["image"]
            self.images["wii"] = wimg
            wpath = self._in("w/monado01", wimg)
        else:
            dpath = self._in("d/bfsgame00.sav", b)
            self.images["de"] = b
        need_w = any(p in targets for p in ("wii", "3ds"))
        need_d = "de" in targets
        sc_rel = None
        # cross-family
        if fam == "wii" and need_d:
            try:
                d_out, tmb, sc, scn = self.w_to_d(wpath)
                self.images["de"] = d_out
                sc_rel = f"sidecars/{scn}"
                self.gfiles[sc_rel] = sc
                self.cross = {"direction": "wii_to_de", "file": sc_rel}
                self._out("de", {"bfsgame.sav": d_out, **({"bfsgame.tmb": tmb} if tmb else {})},
                          "bfsgame.sav", "conversion wii_to_de")
            except Blocked as e:
                self.blocked.update(e.blocked)
            except xs.REFUSALS + (xc3d.FormatError,) as e:
                self.blocked["de"] = _engine_error(e)
        if fam == "de" and need_w:
            try:
                w_out, banner, sc, scn = self.d_to_w(dpath)
                self.images["wii"] = w_out
                wpath = self._in("w/monado01", w_out)
                sc_rel = f"sidecars/{scn}"
                self.gfiles[sc_rel] = sc
                self.cross = {"direction": "de_to_wii", "file": sc_rel}
                self._banner = banner
            except Blocked as e:
                self.blocked.update(e.blocked)
            except xs.REFUSALS + (xc3d.FormatError,) as e:
                self.blocked["wii"] = self.blocked["3ds"] = _engine_error(e)
        # same-family outputs
        if fam == "de":
            tmb = src.get("companions", {}).get("tmb") or self._prev_tmb()
            self._out("de", {"bfsgame.sav": b, **({"bfsgame.tmb": tmb} if tmb else {})}, "bfsgame.sav", "source")
        if "wii" in targets and "wii" in self.images and "wii" not in self.blocked:
            files = {"monado01": src["bytes"] if src["platform"] == "wii" else self.images["wii"]}
            banner = src.get("companions", {}).get("banner") or getattr(self, "_banner", None) or self._prev_banner()
            if banner:
                files["banner.bin"] = banner
            how = "source" if src["platform"] == "wii" else ("transcode 3ds_to_wii" if src["platform"] == "3ds"
                                                            else "conversion de_to_wii")
            if src["platform"] == "3ds":                   # the engine's own reversibility check
                s3.convert3(s3.ThreeDSRequest("3ds_to_wii", source=src["path_copy"],
                                              out=os.path.join(self.work, "3ds_to_wii"), slot="monado01"))
                if _rd(os.path.join(self.work, "3ds_to_wii", "monado01")) != files["monado01"]:
                    raise HubError("3DS -> Wii transcode is not reproducible for this save")
            self._out("wii", files, "monado01", how)
        if "3ds" in targets and "wii" in self.images and "3ds" not in self.blocked:
            try:
                if src["platform"] == "3ds":
                    x3 = src["bytes"]
                    how = "source"
                else:
                    x3 = self.w_to_3ds(wpath)
                    how = "transcode wii_to_3ds"
                files = {"monado01": x3}
                arch = self._archive()
                for n_, v in arch.items():
                    files[f"archive/{n_}"] = v
                self._out("3ds", files, "monado01", how)
            except Blocked as e:
                self.blocked.update(e.blocked)
            except xs.REFUSALS + (xc3d.FormatError,) as e:
                self.blocked["3ds"] = _engine_error(e)
        for f, img in self.images.items():
            rel = "family/wii.bin" if f == "wii" else "family/de.sav"
            self.gfiles[rel] = img
            self.family_images[f] = {"file": rel, "sha256": sha(img)}
        for k, v in _collect(self.work).items() if os.path.isdir(self.work) else []:
            self.gfiles[f"engine/{k}"] = v
        # anchors
        anchors = {}
        if self.base and self.kind != "restart":
            anchors = {k: v for k, v in (self.base.get("anchors") or {}).items()}
        gd = f"history/gen-{self.n:06d}"
        if sc_rel:
            cur_rel = self.family_images[fam]["file"]
            anchors[fam] = {"gen": self.n, "sidecar": f"{gd}/{sc_rel}", "sidecar_sha256": sha(self.gfiles[sc_rel]),
                            "current": f"{gd}/{cur_rel}", "current_sha256": self.family_images[fam]["sha256"]}
        else:
            anchors[fam] = {"gen": self.n, "sidecar": None}
        self.anchors = anchors

    def _out(self, plat, files, main, how):
        rels = {}
        for rel, data in files.items():
            r = f"outputs/{plat}/{rel}"
            self.gfiles[r] = data
            rels[r] = sha(data)
        self.outputs[plat] = {"main": f"outputs/{plat}/{main}", "files": rels, "from": how}

    def _prev_tmb(self):
        g = self.base
        if g and "de" in (g.get("outputs") or {}):
            p = os.path.join(g["_dir"], "outputs", "de", "bfsgame.tmb")
            if os.path.isfile(p):
                return _rd(p)
        t = self.hub.template_info("de")
        if t and "bfsgame00.tmb" in t.get("files", {}):
            return _rd(os.path.join(self.hub.template_dir("de"), "bfsgame00.tmb"))
        return None

    def _prev_banner(self):
        g = self.base
        if g and "wii" in (g.get("outputs") or {}):
            p = os.path.join(g["_dir"], "outputs", "wii", "banner.bin")
            if os.path.isfile(p):
                return _rd(p)
        t = self.hub.template_info("wii")
        if t and "banner.bin" in t.get("files", {}):
            return _rd(os.path.join(self.hub.template_dir("wii"), "banner.bin"))
        return None

    def _archive(self):
        """Other 3DS slots for a complete Checkpoint backup: from the source's own archive folder (3DS source),
        else the previous generation's archive, else the 3DS template's archive. {} when none is complete."""
        a = self.src.get("archive")
        if a:
            return a
        g = self.base
        if g and "3ds" in (g.get("outputs") or {}):
            arch = {k.split("/")[-1]: _rd(os.path.join(g["_dir"], *k.split("/")))
                    for k in g["outputs"]["3ds"]["files"] if k.startswith("outputs/3ds/archive/")}
            if arch:
                return arch
        t = self.hub.template_info("3ds")
        if t and t.get("archive"):
            return {n: _rd(os.path.join(self.hub.template_dir("3ds"), "archive", n)) for n in t["archive"]}
        return {}

    # ---- independent validation of the staged files
    def validate(self, gdir):
        T, V = self.T, self.validation
        src_fam = FAMILY[self.src["platform"]]
        states = {}
        for plat, o in self.outputs.items():
            p = os.path.join(gdir, *o["main"].split("/"))
            b = _rd(p)
            if sha(b) != o["files"][o["main"]]:
                raise HubError(f"{plat} output does not read back identically")
            if plat == "wii":
                img = xs.load_wii(p, "generated Wii save")
                r = xs.validate_bytes(img)
            elif plat == "3ds":
                fb, raw, img = s3.load_3ds(p, "generated 3DS save")
                r = xs.validate_bytes(img)
            else:
                img = xs.load_de(p, "generated DE save", v10_only=True)
                r = xs.validate_bytes(img)
            if not r["ok"]:
                raise HubError(f"generated {SHORT[plat]} save fails validation: {r['problems'][:3]}")
            fam = FAMILY[plat]
            states[plat] = (fam, img, canon.from_wii(img, T) if fam == "wii" else canon.from_de(img, T))
            V.append({"check": f"{plat}: structure, checksums, references", "ok": True})
        # the same state on every platform
        src_img = self.src["image"] if src_fam == "wii" else self.src["bytes"]
        src_c = canon.from_wii(src_img, T) if src_fam == "wii" else canon.from_de(src_img, T)
        for plat, (fam, img, c) in states.items():
            if fam == src_fam:
                if canon.fingerprint(c) != canon.fingerprint(src_c):
                    raise HubError(f"generated {SHORT[plat]} save does not hold exactly the source's gameplay state")
                if fam == "wii" and plat != "3ds" and img != src_img and self.src["platform"] != "de":
                    raise HubError("Wii output differs from the source image")
                V.append({"check": f"{plat}: same gameplay state as the source (same family)", "ok": True})
            else:
                diffs, lost, extra = _audit(src_c["shared"], c["shared"], plat)
                if diffs:
                    raise HubError(f"generated {SHORT[plat]} save differs from the source: {diffs[:5]}")
                # DE holds every Wii item; the Wii/3DS may lack DE-only / overflow items that wait in the history
                if fam == "de":                       # W source -> DE
                    if lost:
                        raise HubError(f"items lost in the DE save: {_count(lost)}")
                    if _count(extra) != self.deferred_n:
                        raise HubError(f"unexpected extra items in the DE save ({_count(extra)}; {self.deferred_n} "
                                       "were expected back from the history)")
                else:                                 # D source -> Wii/3DS
                    if extra:
                        raise HubError(f"items duplicated in the {SHORT[plat]} save: {_count(extra)}")
                    if _count(lost) != self.deferred_n:
                        raise HubError(f"{_count(lost)} item(s) missing from the {SHORT[plat]} save, but "
                                       f"{self.deferred_n} were kept in the history")
                V.append({"check": f"{plat}: story, flags, quests, money, party, levels, EXP, skills, arts and "
                                   f"inventory match the source ({self.deferred_n} item(s) kept for DE)", "ok": True})
        if "wii" in states and "3ds" in states:
            if canon.fingerprint(states["wii"][2]) != canon.fingerprint(states["3ds"][2]):
                raise HubError("the Wii and 3DS saves do not hold the same state")
            V.append({"check": "wii/3ds: identical gameplay state", "ok": True})
        return states


# ------------------------------------------------------------------------------------------------- sync
def _source_from(hub, o, settle, delay):
    """Re-read and re-validate the scanned file; it must be byte-identical to what the scan saw."""
    if not os.path.isfile(o.path):
        raise HubError(f"the selected save is no longer there ({o.path}). Scan Again.")
    b1 = _rd(o.path)
    if delay:
        time.sleep(delay)
    b2 = _rd(o.path)
    if b1 != b2 or sha(b1) != o.sha256:
        raise HubError("the selected save changed since the scan (a transfer may still be running). Scan Again.")
    plat, state, note = scanmod._kind(b1)
    if state != "ok":
        raise HubError(f"the selected save is not usable: {note}")
    fam, img = scanmod._validate(plat, o.path)
    if sha(_rd(o.path)) != o.sha256:
        raise HubError("the selected save changed during validation. Scan Again.")
    src = {"platform": plat, "bytes": b1, "image": img, "name": o.name, "path": o.path, "sha256": o.sha256,
           "device_id": o.device_id, "device_name": o.device_name, "companions": {}}
    d = os.path.dirname(o.path)
    if plat == "de":
        stem = o.name[:-4] if o.name.lower().endswith(".sav") else o.name
        t = os.path.join(d, re.sub(r"\.sync-conflict-.*$", "", stem) + ".tmb")
        if os.path.isfile(t) and os.path.getsize(t) < (1 << 20):
            src["companions"]["tmb"] = _rd(t)
    if plat == "wii":
        bn = os.path.join(d, "banner.bin")
        if os.path.isfile(bn) and os.path.getsize(bn) < (1 << 20):
            src["companions"]["banner"] = _rd(bn)
    if plat == "3ds":
        arch = {}
        for n in ("monado01", "monado02", "monado03", "specialmode"):
            q = os.path.join(d, n)
            if os.path.isfile(q) and os.path.getsize(q) < MAX3:
                arch[n] = _rd(q)
        if all(f"monado0{i}" in arch for i in (1, 2, 3)):
            ok = True
            for n, v in arch.items():
                if n.startswith("monado") and s3.kind_of(v) not in ("3ds", "3ds-empty"):
                    ok = False
            if ok:
                src["archive"] = arch
    return src


MAX3 = 1 << 20


def _check_choice(res, key, allow):
    dec = res.decision
    if dec.kind in ("error", "waiting", "no-devices", "nothing") and key not in allow:
        raise HubError(dec.message or "nothing to sync")
    if dec.kind == "in-sync" and not allow:
        raise HubError("All available saves match the last sync: there is nothing new to sync.")
    if key is None:
        if dec.needs_choice or not dec.source:
            raise HubError("choose which save to continue first")
        key = dec.source
    if key not in dec.options and key not in allow:
        raise HubError("this save cannot be used as the sync source (see its status)")
    o = res.find(key)
    if o is None or o.state != "ok":
        raise HubError("the chosen save is not available. Scan Again.")
    return o


def sync(hub, res, source_key=None, allow_partial=False, progress=None, cancel=None, delay=None,
         restart=False):
    """Run Sync All for the save chosen from scan result `res`. -> SyncResult. Raises HubError (nothing committed)
    or Blocked (a configured platform cannot be produced; nothing committed unless allow_partial)."""
    progress = progress or (lambda stage: None)
    cancel = cancel or (lambda: False)
    delay = scanmod.STABLE_DELAY if delay is None else delay
    with hub.lock():
        cur_n, cur = hub.current_generation()
        if cur_n != res.generation:
            raise HubError("the sync history changed since the scan (another Sync ran). Scan Again.")
        allow = [source_key] if restart and source_key else []
        o = _check_choice(res, source_key, allow)
        if restart and o.status not in ("unknown", "unrelated", "divergent", "new-progress", "start"):
            raise HubError("only a save with its own progress can start a new line")
        progress("check")
        _fault("read", o.path)
        src = _source_from(hub, o, None, delay)
        notes = recover(hub)
        n = (max(hub.committed()) if hub.committed() else 0) + 1
        if restart:
            base, kind = None, "restart"
        elif not cur:
            base, kind = None, "start"
        else:
            base = hub.load_generation(o.gen_ref) if o.gen_ref else cur
            kind = "sync" if o.gen_ref == cur_n else "branch"
        tx = hub.p("staging", f"tx-{uuid.uuid4().hex[:12]}")
        os.makedirs(tx)
        try:
            targets = sorted(set(hub.configured_platforms()) | {src["platform"]}, key=("wii", "de", "3ds").index)
            # 3DS source: a copy of the exact file for the engine's own 3DS -> Wii check
            if src["platform"] == "3ds":
                src["path_copy"] = os.path.join(tx, "in", "x", "monado01")
                _put(os.path.join(tx, "in", "x"), "monado01", src["bytes"])
            if cancel():
                raise Cancelled("Sync cancelled; nothing changed")
            progress("build")
            B = Builder(hub, tx, src, base, n, kind, progress)
            B.build(targets)
            B.notes[:0] = notes
            if B.blocked and not allow_partial:
                raise Blocked(_blocked_text(B.blocked), B.blocked)
            if not B.outputs:
                raise HubError("nothing could be produced")
            _fault("sidecar")
            if cancel():
                raise Cancelled("Sync cancelled; nothing changed")
            gdir = os.path.join(tx, "gen")
            for rel, data in B.gfiles.items():
                _put(gdir, rel, data)
            _fault("stage")
            progress("validate")
            _fault("validate")
            B.validate(gdir)
            snaps = _snapshots(hub, res, o, gdir)
            gen = _generation_doc(hub, n, kind, src, o, base, cur_n, B, targets, snaps, restart)
            gen["files"] = _gen_files(gdir)
            for rel, h in gen["files"].items():           # everything in the folder is what was validated
                if rel in B.gfiles and sha(B.gfiles[rel]) != h:
                    raise HubError(f"staged file {rel} does not read back identically")
            _fault("manifest")
            raw = json.dumps(gen, indent=1, sort_keys=True).encode()
            _put(gdir, "generation.json", raw)
            if cancel():
                raise Cancelled("Sync cancelled; nothing changed")
            progress("commit")
            _fault("commit")
            final = hub.gen_dir(n)
            if os.path.exists(final):
                raise HubError(f"history folder gen-{n:06d} already exists")
            os.rename(gdir, final)
            _fault("pointer")
            hub.set_pointer(n, sha(raw), kind)
        except BaseException:
            shutil.rmtree(tx, ignore_errors=True)
            raise
        shutil.rmtree(tx, ignore_errors=True)
        _fault("after-commit")
        r = SyncResult(n, kind, hub.gen_dir(n), sorted(B.outputs), partial=bool(B.blocked), blocked=B.blocked,
                       notes=B.notes)
        progress("publish")
        r.published = publish(hub, locked=True)
        r.complete = (not r.partial and all(v == "ready" for v in r.published.values()))
        r.message = _result_text(r)
        progress("done")
        return r


def _blocked_text(blocked):
    parts = [f"{SHORT[p]}: {why}" for p, why in sorted(blocked.items())]
    return "Not every configured platform can be updated, so nothing was changed. " + " | ".join(parts)


def _result_text(r):
    if r.complete:
        return "All configured platforms updated."
    if r.partial:
        return (f"Generation {r.generation} was saved for {', '.join(SHORT[p] for p in r.platforms)} only; "
                f"{', '.join(SHORT[p] for p in r.blocked)} could not be updated and keep their previous files.")
    bad = [d for d, v in r.published.items() if v != "ready" and v != "not-available"]
    return f"Generation {r.generation} was saved, but {len(bad)} device folder(s) could not be updated yet."


def _snapshots(hub, res, chosen, gdir):
    """Recoverable copies of every save with its own progress seen at sync time (the unselected branches)."""
    out = []
    for o in res.saves():
        if o.state != "ok" or o.status not in ("new-progress", "divergent", "unknown", "start"):
            continue
        if not os.path.isfile(o.path):
            continue
        b = _rd(o.path)
        if sha(b) != o.sha256:
            continue
        dev = next((d for d in hub.devices() if d["id"] == o.device_id), None)
        folder = dev["folder"] if dev else o.device_id
        rel = f"snapshots/{folder}/{o.sha256[:12]}/{o.name}"
        p = os.path.join(gdir, *rel.split("/"))
        if not os.path.exists(p):
            _put(gdir, rel, b)
        out.append({"device_id": o.device_id, "device_name": o.device_name, "platform": o.platform, "file": rel,
                    "sha256": o.sha256, "status": o.status, "chosen": o.key == chosen.key,
                    "original_path": o.path, "summary": o.summary})
    return out


def _generation_doc(hub, n, kind, src, o, base, prev_n, B, targets, snaps, restart):
    fam = FAMILY[src["platform"]]
    summaries = {}
    for plat, out in B.outputs.items():
        f = FAMILY[plat]
        summaries[plat] = summarize_image(f, B.images[f])
    return {
        "schema": GENERATION_SCHEMA, "number": n, "kind": kind, "created": now_iso(), "app_version": APP_VERSION,
        "engine": {"converter_3a": s3.CONVERTER_VERSION, "sidecar_2h": scmod.CONVERTER_VERSION,
                   "canon": canon.SCHEMA},
        "hub_id": hub.hub_id, "parent": base["number"] if base else None, "previous": prev_n or None,
        "source": {"device_id": src["device_id"], "device_name": src["device_name"], "platform": src["platform"],
                   "family": fam, "file": f"source/{src['name']}", "original_path": src["path"],
                   "sha256": src["sha256"], "status": o.status, "progress_key": o.progress_key,
                   "summary": o.summary},
        "targets": targets, "outputs": {p: dict(v, summary=summaries[p]) for p, v in B.outputs.items()},
        "family_images": B.family_images, "anchors": B.anchors, "cross_sidecar": B.cross,
        "conversions": B.conversions, "validation": B.validation, "notes": B.notes,
        "partial": bool(B.blocked), "blocked": B.blocked, "snapshots": snaps,
        "branch": ({"chosen": o.key, "unselected": [s["file"] for s in snaps if not s["chosen"]]}
                   if any(not s["chosen"] for s in snaps) else None),
        "restart": bool(restart),
    }


# ------------------------------------------------------------------------------------------------- publication
INSTALL = {
    "wii": "Wii (Dolphin): copy {slot} (and banner.bin) into Dolphin's save folder for Xenoblade Chronicles\n"
           "  (...\\Wii\\title\\00010000\\53583445\\data\\) after backing up the save that is there.\n"
           "  On Android, use Dolphin's own file access (see the Sync Hub user guide).\n",
    "de": "Definitive Edition (Monado): copy bfsgame{slot}.sav (and .tmb) into Monado's save\\save_0 folder after\n"
          "  backing up the save that is there.\n",
    "3ds": "Xenoblade 3D: Azahar - copy {slot} into the game's save folder (right-click the game, Open Save Data\n"
           "  Location) after a backup. New 3DS - copy the folder in Checkpoint\\ into\n"
           "  sdmc:/3ds/Checkpoint/saves/<Xenoblade folder>/ and restore it with Checkpoint. Arriving on the SD card\n"
           "  is not the same as restored: the game only sees it after the Checkpoint restore.\n",
}


def device_files(hub, gen, dev):
    """{relative path in the ready folder: bytes} for one device, or None if its platform has no output."""
    plat = dev["platform"]
    o = (gen.get("outputs") or {}).get(plat)
    if not o:
        return None
    gd = gen["_dir"]

    def get(rel):
        p = os.path.join(gd, *rel.split("/"))
        b = _rd(p)
        if sha(b) != o["files"][rel]:
            raise HubError(f"generation {gen['number']} file {rel} was changed or damaged")
        return b
    files = {}
    if plat == "wii":
        files[dev["slot"]] = get("outputs/wii/monado01")
        if "outputs/wii/banner.bin" in o["files"]:
            files["banner.bin"] = get("outputs/wii/banner.bin")
    elif plat == "de":
        files[f"bfsgame{dev['slot']}.sav"] = get("outputs/de/bfsgame.sav")
        if "outputs/de/bfsgame.tmb" in o["files"]:
            files[f"bfsgame{dev['slot']}.tmb"] = get("outputs/de/bfsgame.tmb")
    else:
        main = get("outputs/3ds/monado01")
        files[dev["slot"]] = main
        arch = {k.split("/")[-1]: get(k) for k in o["files"] if k.startswith("outputs/3ds/archive/")}
        if arch:
            arch[dev["slot"]] = main
            for n_, v in arch.items():
                files[f"Checkpoint/XenobladeSync-gen{gen['number']:06d}/{n_}"] = v
    return files


def publish(hub, devices=None, locked=False):
    """Copy the current generation into each device's ready folder. Idempotent; READY.json is written last.
    -> {device id: 'ready' | 'not-available' | 'failed: ...'}"""
    if not locked:
        with hub.lock():
            return publish(hub, devices, locked=True)
    n, gen = hub.current_generation()
    if not gen:
        raise HubError("nothing has been synced yet")
    out = {}
    for dev in hub.devices():
        if not dev.get("enabled", True) or (devices and dev["id"] not in devices):
            continue
        try:
            files = device_files(hub, gen, dev)
            if files is None:
                out[dev["id"]] = "not-available"
                continue
            _publish_one(hub, gen, dev, files)
            out[dev["id"]] = "ready"
        except (HubError, OSError) as e:
            out[dev["id"]] = f"failed: {e}"
    return out


def _publish_one(hub, gen, dev, files):
    rd = hub.ready_dir(dev)
    safeio.guard_out(rd)
    os.makedirs(rd, exist_ok=True)
    old = {}
    try:
        with open(os.path.join(rd, "READY.json"), "rb") as f:
            old = json.loads(f.read().decode()).get("files", {})
    except (OSError, ValueError, UnicodeDecodeError):
        old = {}
    stage = hub.p("staging", f"pub-{uuid.uuid4().hex[:10]}")
    try:
        for rel, b in files.items():
            _put(stage, rel, b)
        for rel, b in files.items():                    # replace one file at a time (each step atomic)
            _fault("publish", f"{dev['folder']}/{rel}")
            dst = os.path.join(rd, *rel.split("/"))
            safeio.guard_out(dst)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(os.path.join(stage, *rel.split("/")), dst)
        for rel in old:                                 # files of the previous publication that are gone now
            if rel not in files:
                p = os.path.join(rd, *rel.split("/"))
                if os.path.isfile(p):
                    os.remove(p)
                d = os.path.dirname(p)
                while os.path.normcase(d) != os.path.normcase(rd) and os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
                    d = os.path.dirname(d)
        src = gen.get("source") or {}
        slot = dev["slot"]
        ready = {"schema": "xc1-ready/1", "generation": gen["number"], "hub_id": gen.get("hub_id"),
                 "committed": gen.get("created"), "device": {"id": dev["id"], "name": dev["name"]},
                 "platform": dev["platform"], "files": {rel: sha(b) for rel, b in files.items()},
                 "source": {"device": src.get("device_name"), "platform": src.get("platform"),
                            "summary": src.get("summary")},
                 "partial": gen.get("partial", False),
                 "note": "These files are ready for this device. They are not installed: copy them into the game "
                         "yourself after a backup (HOW_TO_INSTALL.txt)."}
        text = (f"Xenoblade Sync Hub - generation {gen['number']} for {dev['name']} ({NICE[dev['platform']]})\n\n"
                + INSTALL[dev["platform"]].format(slot=slot) +
                "\nKeep the Sync Hub's copy: after you play, the save comes back through the device's incoming "
                "folder and the next Sync continues from it.\n")
        atomic_write(os.path.join(rd, "HOW_TO_INSTALL.txt"), text.encode())
        _fault("publish-ready", dev["folder"])
        atomic_write(os.path.join(rd, "READY.json"), json.dumps(ready, indent=1, sort_keys=True).encode())
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# ------------------------------------------------------------------------------------------------- rollback
def rollback(hub, target, progress=None):
    """Make generation `target` current again as a NEW generation (history stays append-only; every later
    generation remains recoverable). -> SyncResult."""
    progress = progress or (lambda s: None)
    with hub.lock():
        recover(hub)
        cur_n, cur = hub.current_generation()
        if target not in hub.committed():
            raise HubError(f"generation {target} is not in the history")
        if target == cur_n:
            raise HubError(f"generation {target} is already the current one")
        tg = hub.load_generation(target, next(h["sha256"] for h in hub.pointer()["history"]
                                              if h["number"] == target))
        n = max(hub.committed()) + 1
        tx = hub.p("staging", f"tx-{uuid.uuid4().hex[:12]}")
        gdir = os.path.join(tx, "gen")
        try:
            progress("build")
            keep = [k for k in tg.get("files", {}) if not k.startswith("snapshots/")]
            for rel in keep:
                b = _rd(os.path.join(tg["_dir"], *rel.split("/")))
                if sha(b) != tg["files"][rel]:
                    raise HubError(f"generation {target} file {rel} was changed or damaged")
                _put(gdir, rel, b)
            gd_old, gd_new = f"history/gen-{target:06d}", f"history/gen-{n:06d}"
            anchors = json.loads(json.dumps(tg.get("anchors") or {}))
            for fam, a in anchors.items():
                if a.get("gen") == target and a.get("sidecar"):
                    a["sidecar"] = a["sidecar"].replace(gd_old, gd_new)
                    a["current"] = a["current"].replace(gd_old, gd_new)
                    a["gen"] = n
            gen = {k: v for k, v in tg.items() if k not in ("_dir", "files", "snapshots", "branch")}
            gen.update(number=n, kind="rollback", created=now_iso(), app_version=APP_VERSION, rollback_of=target,
                       previous=cur_n, anchors=anchors, snapshots=[], branch=None,
                       notes=[f"rollback to generation {target}; generations {target + 1}-{cur_n} stay in the history"])
            gen["files"] = _gen_files(gdir)
            progress("validate")
            for plat, o in gen["outputs"].items():
                for rel, h in o["files"].items():
                    if gen["files"].get(rel) != h:
                        raise HubError("rollback copy is incomplete")
            raw = json.dumps(gen, indent=1, sort_keys=True).encode()
            _put(gdir, "generation.json", raw)
            progress("commit")
            os.rename(gdir, hub.gen_dir(n))
            hub.set_pointer(n, sha(raw), "rollback")
        except BaseException:
            shutil.rmtree(tx, ignore_errors=True)
            raise
        shutil.rmtree(tx, ignore_errors=True)
        r = SyncResult(n, "rollback", hub.gen_dir(n), sorted(gen["outputs"]), partial=gen.get("partial", False),
                       blocked=gen.get("blocked", {}), notes=gen["notes"])
        progress("publish")
        r.published = publish(hub, locked=True)
        r.complete = not r.partial and all(v == "ready" for v in r.published.values() if v != "not-available")
        r.message = (f"Generation {target} is current again (as generation {n})." if r.complete else _result_text(r))
        progress("done")
        return r


def restore_snapshot(hub, gen_n, rel, dest_dir):
    """Copy a recovery snapshot (e.g. an unselected branch) out of the history into a NEW folder the user chose."""
    g = hub.load_generation(gen_n)
    h = g.get("files", {}).get(rel)
    if not h:
        raise HubError("no such snapshot")
    b = _rd(os.path.join(g["_dir"], *rel.split("/")))
    if sha(b) != h:
        raise HubError("the snapshot was changed or damaged")
    name = rel.split("/")[-1]
    safeio.commit(dest_dir, {re.sub(r"\.sync-conflict-.*?(\.sav)?$", r"\1", name): b})
    return os.path.join(dest_dir, name)
