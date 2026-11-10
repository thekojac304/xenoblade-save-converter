"""Read-only startup scan.

scan(hub) enumerates every enabled device's incoming folder, keeps only complete, stable, valid Xenoblade saves,
compares each with the committed sync history and decides what Sync All may do. It never writes, converts, renames
or deletes anything (tested by hashing the whole hub and every incoming folder before and after).

Classification of one save (always against images of the SAME family: Wii and 3DS share the Wii layout; DE is
compared with DE):

  in-sync        byte-identical to a file of the current generation, or the same progress (re-saved: only save time,
                 thumbnail, play-time seconds or the in-game clock differ)
  older          a copy of an earlier generation, or progress the current generation already contains
  new-progress   continues the current generation AND contains the progress that generation added
  divergent      continues an earlier generation but not the current one (played on an old copy) - never picked
                 automatically
  unrelated      a different playthrough (ignored)
  unknown        ancestry cannot be proven (no history for this platform yet, or the checks disagree)
  start          there is no history yet: a possible starting save

Higher play time, story or level alone never decides anything: "continues" needs sidecar.descent (flags and items
kept) plus the delta check below, which is what stops an old copy that was played for a long time from passing as a
continuation of the newest generation.
"""
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict

from . import paths3b  # noqa: F401
from .store import Hub, HubError, FAMILY, SHORT, sha, family_image, summarize_image

import canon
import de_save
import safeio
import sidecar as scmod
import xc3d
import xc3dservice as s3
import xcservice as xs

WII_SIZE = 0x28000
MAX_READ = 2 << 20
SAVE_RE = re.compile(r"^(monado0[1-3]|bfsgame\d\d[a-z]?\.sav)$", re.I)
CONFLICT_RE = re.compile(r"^(?P<stem>monado0[1-3]|bfsgame\d\d[a-z]?)\.sync-conflict-\d{8}-\d{6}-[A-Z0-9]{7}"
                         r"(?P<ext>\.sav)?$", re.I)
TEMP_RE = re.compile(r"^(\.syncthing\.|~syncthing~)(?P<name>.+)\.tmp$", re.I)
SKIP_DIRS = {".stversions", ".stfolder", ".stignore", "$recycle.bin", "system volume information"}
MAX_DEPTH = 4
SETTLE_SECONDS = 5.0       # a file modified more recently than this may still be written
STABLE_DELAY = 0.4         # pause between the two reads of every candidate
CONTAINS_MIN = 0.8         # share of the generation's new facts a continuation must hold
SAME_PLAYTHROUGH = xs.SAME_PLAYTHROUGH
HISTORY_DEPTH = 40         # generations searched for divergence / older copies


# ------------------------------------------------------------------------------------------------- data
@dataclass
class Observed:
    device_id: str
    device_name: str
    device_platform: str
    path: str
    name: str
    size: int = 0
    mtime: float = 0.0
    sha256: str = ""
    platform: str = None           # detected from the content: wii | de | 3ds
    state: str = "ok"              # ok | pending | damaged | empty | ignored
    status: str = None             # classification (see module doc), only for state == ok
    gen_ref: int = None            # the generation this save matches / continues
    detail: str = ""
    note: str = ""
    conflict_copy: bool = False
    summary: dict = None
    progress_key: str = None
    family: str = None
    image: bytes = field(default=None, repr=False)
    data: bytes = field(default=None, repr=False)

    @property
    def key(self):
        return f"{self.device_id}:{self.path}"

    def public(self):
        d = asdict(self)
        d.pop("image", None)
        d.pop("data", None)
        d["key"] = self.key
        return d


@dataclass
class DeviceScan:
    device: dict
    available: bool = True
    status: str = "empty"          # missing | empty | pending | damaged | in-sync | older | new-progress | divergent |
    text: str = ""                 # unrelated | unknown | start
    saves: list = field(default_factory=list)
    syncthing_folder: bool = False
    syncthing_busy: bool = False
    ready_generation: int = None
    ready_state: str = None        # current | outdated | missing | damaged | not-needed


@dataclass
class Decision:
    kind: str                      # no-devices | nothing | start | choose-start | in-sync | new-progress | conflict |
    message: str                   # waiting | error
    source: str = None             # key of the proposed source Observed (Sync All may proceed)
    options: list = field(default_factory=list)       # keys the user may choose from
    needs_choice: bool = False
    detail: str = ""


@dataclass
class ScanResult:
    hub_root: str
    scanned_at: str
    generation: int
    generation_info: dict
    devices: list
    decision: Decision
    issues: list = field(default_factory=list)       # recovery notes (interrupted syncs, outdated ready folders)
    platforms: list = field(default_factory=list)
    error: str = None

    def saves(self):
        return [s for d in self.devices for s in d.saves]

    def find(self, key):
        for s in self.saves():
            if s.key == key:
                return s
        return None


# ------------------------------------------------------------------------------------------------- reading
def _walk(folder):
    """(path, name) of every file that might be a save, Syncthing temp files flagged; dot/Syncthing folders skipped."""
    out, temps = [], []
    base_depth = folder.rstrip("\\/").count(os.sep)
    for dp, dns, fs in os.walk(folder):
        dns[:] = [d for d in dns if not d.startswith(".") and d.lower() not in SKIP_DIRS]
        if dp.count(os.sep) - base_depth >= MAX_DEPTH:
            dns[:] = []
        for n in fs:
            p = os.path.join(dp, n)
            m = TEMP_RE.match(n)
            if m:
                temps.append((p, m.group("name")))
            elif SAVE_RE.match(n) or CONFLICT_RE.match(n):
                out.append((p, n))
    return out, temps


def _read(p):
    st = os.stat(p)
    if st.st_size > MAX_READ:
        return st, None
    with open(p, "rb") as f:
        return st, f.read()


def _kind(b):
    """Content-based platform detection with the engine's own validators. -> (platform|None, state, note)."""
    if b is None:
        return None, "ignored", "too large to be a save"
    if xc3d.is_3ds_file(b):
        k = s3.kind_of(b)
        if k == "3ds-empty":
            return "3ds", "empty", "empty 3DS save slot"
        if k != "3ds":
            return "3ds", "damaged", "damaged or incomplete 3DS save"
        return "3ds", "ok", ""
    if b[:4] == b"DMMY":
        return "wii", "empty", "empty Wii save slot"
    if b[:4] == b"USRD":
        if len(b) != WII_SIZE:
            return "wii", "damaged", f"incomplete Wii save ({len(b)} of {WII_SIZE} bytes)"
        return "wii", "ok", ""
    if len(b) in (de_save.V7, de_save.V10):
        return "de", "ok", ""
    if len(b) < de_save.V10 and len(b) > 1_000_000 and b[:4] == b"\x0a\x00\x00\x00":
        return "de", "damaged", f"incomplete DE save ({len(b)} bytes)"
    return None, "ignored", "not a Xenoblade save"


def _validate(platform, path):
    """Full engine validation; -> image family + image, or raises Refused."""
    if platform == "3ds":
        fb, raw, wii = s3.load_3ds(path, "save")
        return "wii", wii
    if platform == "wii":
        return "wii", xs.load_wii(path, "save")
    b = xs.load_de(path, "save")
    if len(b) != de_save.V10:
        raise safeio.Refused("format-v7 DE save (game version 1.x): load and save it once in DE 2.0 / Monado first")
    return "de", b


# ------------------------------------------------------------------------------------------------- state keys
class Canon:
    """Per-scan cache of canonical states (decoding is the expensive part)."""

    def __init__(self):
        self.T = xs.tables()
        self.c = {}

    def get(self, family, img):
        k = (family, sha(img))
        if k not in self.c:
            self.c[k] = canon.from_wii(img, self.T) if family == "wii" else canon.from_de(img, self.T)
        return self.c[k]

    def shared(self, family, img):
        return self.get(family, img)["shared"]


def _dumps(o):
    return json.dumps(canon.jsonable(o), sort_keys=True, separators=(",", ":"), default=str)


IGNORED_SHARED = ("play_time_s", "clock",            # change on every re-save without play
                  "position", "angle_rad")           # compared with a tolerance (same_place)
DE_ONLY_KEYS = ("characters", "items", "flags", "quest_counters_fc")   # DE-only progress (no header/time words)
POS_EPS = 5.0          # world units; Monado's load + save without moving shifted the height by 0.001 (run m2)


def progress_key(cc, family, img):
    """Hash of the gameplay state, ignoring what a load-and-save without play changes (save time, thumbnail,
    play-time seconds, in-game clock, the exact standing position - see same_place). DE-only progress (Expert Mode,
    outfits, DE-only items/flags) counts for DE."""
    c = cc.get(family, img)
    sh = {k: v for k, v in c["shared"].items() if k not in IGNORED_SHARED}
    parts = [_dumps(sh)]
    if family == "de":
        parts.append(_dumps({k: c["de_only"].get(k) for k in DE_ONLY_KEYS}))
    return sha("|".join(parts).encode())


def same_place(cc, family, a, b):
    """Same map (part of progress_key) and within POS_EPS: a re-save, not a walk."""
    pa, pb = cc.shared(family, a)["position"], cc.shared(family, b)["position"]
    return sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5 <= POS_EPS


def same_progress(cc, family, a, b):
    return progress_key(cc, family, a) == progress_key(cc, family, b) and same_place(cc, family, a, b)


def delta_facts(a, b):
    """Progress made from shared state a to shared state b: story, flag values, level-ups, items gained.
    Monotone counters (EXP, play time, money) are deliberately NOT facts: a branch that simply played longer has
    more of them without containing the other branch's progress (3B finding, W150_LATER vs the 3DS battle save)."""
    F = []
    if b["story"] > a["story"]:
        F.append(("story", b["story"]))
    for f, v in b["flags"].items():
        if a["flags"].get(f) != v:
            F.append(("flag", f, v))
    for k, ch in b["characters"].items():
        ca = a["characters"][k]
        if ch["level"] > ca["level"]:
            F.append(("level", k, ch["level"]))
    ia, ib = scmod._items(a), scmod._items(b)
    for k, n in ib.items():
        if n > ia.get(k, 0):
            F.append(("item", k, n))
    return F


def contains(c, facts):
    """-> (ok, ratio, n). ok: c holds the progress described by facts (story and levels strictly; flags/items by
    ratio, since items are used up and counters move on)."""
    if not facts:
        return True, 1.0, 0
    have, hard = 0, True
    ic = scmod._items(c)
    for f in facts:
        if f[0] == "story":
            ok = c["story"] >= f[1]
            hard &= ok
        elif f[0] == "level":
            ok = c["characters"][f[1]]["level"] >= f[2]
            hard &= ok
        elif f[0] == "flag":
            v = c["flags"].get(f[1])
            ok = v == f[2] or (isinstance(v, int) and isinstance(f[2], int) and f[2] > 0 and v >= f[2])
        else:
            ok = ic.get(f[1], 0) >= f[2]
        have += ok
    r = have / len(facts)
    return hard and r >= CONTAINS_MIN, r, len(facts)


# ------------------------------------------------------------------------------------------------- history view
class HistoryView:
    """The committed generations as the scanner needs them: file hashes, family images, lineage chain."""

    def __init__(self, hub):
        self.hub = hub
        self.number, self.current = hub.current_generation()
        self.gens = {}
        self.hashes = {}         # sha -> (gen, role)
        if not self.current:
            return
        for g in hub.generations()[-HISTORY_DEPTH:]:
            if g.get("damaged"):
                continue
            self.gens[g["number"]] = g
            for plat, o in g.get("outputs", {}).items():       # newest generation wins (a rollback copies files)
                for rel, h in o.get("files", {}).items():
                    self.hashes[h] = (g["number"], f"{plat} output")
            src = g.get("source") or {}
            if src.get("sha256"):
                self.hashes[src["sha256"]] = (g["number"], "source")
        cur = self.current
        for plat, o in (cur.get("outputs") or {}).items():         # the current generation always wins
            for rel, h in o.get("files", {}).items():
                self.hashes[h] = (self.number, f"{plat} output")

    def image(self, n, family):
        g = self.gens.get(n)
        if not g:
            return None
        fi = (g.get("family_images") or {}).get(family)
        if not fi:
            return None
        p = os.path.join(g["_dir"], *fi["file"].split("/"))
        try:
            with open(p, "rb") as f:
                b = f.read()
        except OSError:
            return None
        return b if sha(b) == fi["sha256"] else None

    def chain(self):
        """Current generation, then its parents (the lineage, skipping rolled-back generations)."""
        out, n, seen = [], self.number, set()
        while n and n in self.gens and n not in seen:
            seen.add(n)
            out.append(n)
            n = self.gens[n].get("parent")
        return out

    def latest_with(self, family):
        for n in self.chain():
            if self.image(n, family) is not None:
                return n
        return None

    def parent_with(self, n, family):
        """The nearest ancestor of generation n that has an image of family."""
        g = self.gens.get(n)
        p = g.get("parent") if g else None
        while p and p in self.gens:
            if self.image(p, family) is not None:
                return p
            p = self.gens[p].get("parent")
        return None


# ------------------------------------------------------------------------------------------------- classification
def classify(o, hv, cc):
    """Fills o.status / o.gen_ref / o.detail for a valid save (o.state == 'ok')."""
    fam, img = o.family, o.image
    if not hv.current:
        o.status, o.detail = "start", "possible starting save (no sync history yet)"
        return
    hit = hv.hashes.get(o.sha256)
    if hit:
        n, role = hit
        if n == hv.number:
            o.status, o.gen_ref, o.detail = "in-sync", n, f"identical to generation {n} ({role})"
        else:
            o.status, o.gen_ref, o.detail = "older", n, f"copy of generation {n} ({role})"
        return
    chain = [n for n in hv.chain() if hv.image(n, fam) is not None]
    if chain and _continues_abandoned(o, hv, cc, chain):
        return
    if not chain:
        o.status, o.detail = "unknown", f"no {SHORT[o.platform]} save has been synced yet; its history is unknown"
        return
    cur_n = chain[0]
    cur_img = hv.image(cur_n, fam)
    cur_sh = cc.shared(fam, cur_img)
    c_sh = cc.shared(fam, img)
    for n in chain:
        g_img = hv.image(n, fam)
        if same_progress(cc, fam, img, g_img):
            if n == hv.number:
                o.status, o.gen_ref, o.detail = "in-sync", n, f"same progress as generation {n} (re-saved)"
            else:
                o.status, o.gen_ref, o.detail = "older", n, f"same progress as generation {n}"
            return
        ok, reasons, changed = scmod.descent(g_img, img, cc.T, fam)
        if not ok:
            continue
        p = hv.parent_with(n, fam)
        facts = delta_facts(cc.shared(fam, hv.image(p, fam)), cc.shared(fam, g_img)) if p else []
        has, ratio, nf = contains(c_sh, facts)
        if not has:
            continue                       # continues an ancestor of n, not n itself
        if n == hv.number:
            o.status, o.gen_ref = "new-progress", n
            o.detail = f"continues generation {n}"
            return
        # continues an older generation: is it simply behind the newest one?
        own = delta_facts(cc.shared(fam, g_img), c_sh)
        behind, r2, n2 = contains(cur_sh, own)
        if behind and c_sh["play_time_s"] <= cur_sh["play_time_s"]:
            o.status, o.gen_ref, o.detail = "older", cur_n, f"older than generation {cur_n} (its progress is included)"
            return
        if cur_n != hv.number:
            o.detail = (f"continues generation {n}; the newest generation has no {SHORT[o.platform]} output, and "
                        "the source of that generation progressed separately")
        else:
            o.detail = f"continues generation {n}, not the newest generation {hv.number}: played on an older copy"
        o.status, o.gen_ref = "divergent", n
        return
    # nothing continues: an ancestor of the newest state, a different playthrough, or unprovable
    ok, _, _ = scmod.descent(img, cur_img, cc.T, fam)
    if ok and contains(cur_sh, delta_facts(c_sh, cur_sh))[0] and c_sh["play_time_s"] <= cur_sh["play_time_s"]:
        o.status, o.gen_ref, o.detail = "older", cur_n, f"older than generation {cur_n}"
        return
    sim = xs.similarity(cur_img, img) if fam == "wii" else _sim_de(cc, cur_img, img)
    if sim < SAME_PLAYTHROUGH:
        o.status, o.detail = "unrelated", f"a different playthrough (flag similarity {sim:.0%})"
    else:
        o.status, o.detail = "unknown", ("looks like this playthrough, but how it relates to the sync history "
                                         "cannot be proven")


def _continues_abandoned(o, hv, cc, chain):
    """A save that continues a generation which is no longer in the current line (replaced by a rollback or by an
    explicit branch choice) and holds that generation's own progress is divergent, never new progress."""
    fam, img = o.family, o.image
    cur_sh = cc.shared(fam, hv.image(chain[0], fam))
    c_sh = cc.shared(fam, img)
    in_chain = set(hv.chain())
    chain_imgs = {sha(hv.image(n, fam)) for n in chain}
    for n in sorted(hv.gens, reverse=True):
        if n in in_chain:
            continue
        g_img = hv.image(n, fam)
        if g_img is None or sha(g_img) in chain_imgs:
            continue
        p = hv.parent_with(n, fam)
        if not p:
            continue
        facts = delta_facts(cc.shared(fam, hv.image(p, fam)), cc.shared(fam, g_img))
        if not facts or contains(cur_sh, facts)[0]:
            continue                                   # its progress is part of the current line anyway
        ok, _, _ = scmod.descent(g_img, img, cc.T, fam)
        if ok and contains(c_sh, facts)[0]:
            o.status, o.gen_ref = "divergent", n
            o.detail = f"continues generation {n}, which is no longer part of the current sync line"
            return True
    return False


def _sim_de(cc, a, b):
    fa, fb = set(cc.shared("de", a)["flags"]), set(cc.shared("de", b)["flags"])
    return len(fa & fb) / max(len(fa | fb), 1)


# ------------------------------------------------------------------------------------------------- ready folders
def ready_state(hub, dev, gen_n, gen):
    """(state, generation in READY.json). Read-only."""
    p = os.path.join(hub.ready_dir(dev), "READY.json")
    if not gen:
        return "not-needed", None
    want = (gen.get("outputs") or {}).get(dev["platform"])
    if not want:
        return "not-available", None
    try:
        with open(p, "rb") as f:
            r = json.loads(f.read().decode())
    except FileNotFoundError:
        return "missing", None
    except (OSError, ValueError, UnicodeDecodeError):
        return "damaged", None
    if r.get("generation") != gen_n:
        return "outdated", r.get("generation")
    for rel, h in (r.get("files") or {}).items():
        q = os.path.join(hub.ready_dir(dev), *rel.split("/"))
        try:
            with open(q, "rb") as f:
                if sha(f.read()) != h:
                    return "damaged", gen_n
        except OSError:
            return "damaged", gen_n
    return "current", gen_n


def recovery_issues(hub, hv):
    out = []
    st = hub.p("staging")
    if os.path.isdir(st):
        for n in sorted(os.listdir(st)):
            if n.startswith("tx-") or n.startswith("pub-"):
                out.append({"kind": "interrupted", "path": os.path.join(st, n),
                            "text": "An earlier sync was interrupted before it finished. It was not used; nothing "
                                    "changed. It is cleaned up at the next Sync."})
    hd = hub.p("history")
    committed = set(hub.committed()) if hv.current else set()
    if os.path.isdir(hd):
        for n in sorted(os.listdir(hd)):
            m = re.fullmatch(r"gen-(\d{6})", n)
            if m and int(m.group(1)) not in committed:
                out.append({"kind": "uncommitted", "path": os.path.join(hd, n),
                            "text": f"Generation {int(m.group(1))} was prepared but never committed (interrupted). "
                                    "It is set aside at the next Sync; the current generation is unchanged."})
    return out


# ------------------------------------------------------------------------------------------------- scan
DEVICE_TEXT = {
    "missing": "Folder not available (offline or not connected)",
    "empty": "No save yet",
    "pending": "Receiving files...",
    "damaged": "Only a damaged or incomplete save",
    "in-sync": "Up to date",
    "older": "Has an older save",
    "new-progress": "New progress",
    "divergent": "Different progress (from an older sync)",
    "unrelated": "Different playthrough (ignored)",
    "unknown": "History unknown",
    "start": "Save found",
}
PRIORITY = ["pending", "new-progress", "divergent", "start", "unknown", "in-sync", "older", "unrelated", "damaged",
            "empty", "missing"]


def scan(hub, settle=None, delay=None, now=None):
    """Read-only. -> ScanResult."""
    settle = SETTLE_SECONDS if settle is None else settle
    delay = STABLE_DELAY if delay is None else delay
    now = time.time() if now is None else now
    res = ScanResult(hub.root, time.strftime("%Y-%m-%dT%H:%M:%S"), 0, None, [], Decision("nothing", ""))
    try:
        hv = HistoryView(hub)
    except HubError as e:
        res.error = str(e)
        res.decision = Decision("error", "The sync history could not be read: " + str(e))
        return res
    res.generation = hv.number
    res.platforms = hub.configured_platforms()
    if hv.current:
        g = hv.current
        res.generation_info = {"number": hv.number, "kind": g.get("kind"), "created": g.get("created"),
                               "source": {k: (g.get("source") or {}).get(k) for k in
                                          ("device_name", "platform", "summary")},
                               "platforms": sorted((g.get("outputs") or {}).keys()),
                               "partial": g.get("partial", False), "blocked": g.get("blocked", {})}
    res.issues = recovery_issues(hub, hv)
    devs = [d for d in hub.devices() if d.get("enabled", True)]
    cc = Canon()
    reads = []
    for dev in devs:
        ds = DeviceScan(dev)
        res.devices.append(ds)
        folder = dev["incoming"]
        if not os.path.isdir(folder):
            ds.available, ds.status = False, "missing"
            continue
        ds.syncthing_folder = os.path.exists(os.path.join(folder, ".stfolder"))
        try:
            files, temps = _walk(folder)
        except OSError:
            ds.available, ds.status = False, "missing"
            continue
        temp_targets = {os.path.normcase(os.path.join(os.path.dirname(p), n)) for p, n in temps}
        ds.syncthing_busy = bool(temps)
        for p, n in files:
            o = Observed(dev["id"], dev["name"], dev["platform"], p, n, conflict_copy=bool(CONFLICT_RE.match(n)))
            try:
                st, b = _read(p)
            except OSError as e:
                o.state, o.note = "pending", f"cannot be read yet ({e.strerror or e})"
                ds.saves.append(o)
                continue
            o.size, o.mtime, o.data = st.st_size, st.st_mtime, b
            o.sha256 = sha(b) if b is not None else ""
            if os.path.normcase(p) in temp_targets:
                o.state, o.note = "pending", "Syncthing is still transferring a newer version"
            elif now - st.st_mtime < settle:
                o.state, o.note = "pending", "changed a moment ago - may still be written"
            ds.saves.append(o)
            reads.append(o)
        for p, n in temps:
            tgt = os.path.join(os.path.dirname(p), n)
            if not os.path.exists(tgt) and SAVE_RE.match(n):
                ds.saves.append(Observed(dev["id"], dev["name"], dev["platform"], tgt, n, state="pending",
                                         note="Syncthing is transferring this save"))
    if reads and delay:
        time.sleep(delay)
    for o in reads:                                        # second read: size and content must be unchanged
        try:
            st, b = _read(o.path)
        except OSError:
            o.state, o.note = "pending", "disappeared or became unreadable during the scan"
            continue
        if st.st_size != o.size or (b is not None and sha(b) != o.sha256) or st.st_mtime != o.mtime:
            o.state, o.note = "pending", "changed during the scan - still being written"
    for ds in res.devices:
        for o in ds.saves:
            if o.state != "ok":
                if o.state == "pending":
                    pass
                continue
            plat, state, note = _kind(o.data)
            o.platform = plat
            if state != "ok":
                o.state, o.note = state, note
                continue
            try:
                o.family, o.image = _validate(plat, o.path)
            except xs.REFUSALS + (Exception,) as e:     # damaged file: never a candidate
                o.state, o.note = "damaged", _short(e)
                continue
            if sha(o.data) != o.sha256 or (o.image is not None and plat != "3ds" and sha(o.image) != o.sha256):
                o.state, o.note = "pending", "changed during validation"
                continue
            if plat != ds.device["platform"]:
                o.note = f"{SHORT[plat]} save in a {SHORT[ds.device['platform']]} device folder"
            try:
                o.summary = summarize_image(o.family, o.image)
                o.progress_key = progress_key(cc, o.family, o.image)
                classify(o, hv, cc)
            except Exception as e:                       # decoding problem: treat as damaged, never as progress
                o.state, o.note, o.status = "damaged", _short(e), None
        _device_status(hub, ds, hv)
    res.decision = decide(res, hv, cc)
    _ready_issues(res)
    for o in res.saves():
        o.data = None                                    # keep the result small; Sync re-reads the file
    return res


def _short(e):
    s = str(e)
    return s if len(s) < 200 else s[:197] + "..."


def _device_status(hub, ds, hv):
    if not ds.available:
        ds.status = "missing"
    else:
        sts = [o.status if o.state == "ok" else o.state for o in ds.saves if o.state != "ignored"]
        sts = [s for s in sts if s != "empty"] or sts
        ds.status = min(sts, key=PRIORITY.index) if sts else "empty"
    ds.text = DEVICE_TEXT.get(ds.status, ds.status)
    if ds.status == "in-sync" and hv.number:
        ds.text = f"Up to date (generation {hv.number})"
    ds.ready_state, ds.ready_generation = ready_state(hub, ds.device, hv.number, hv.current)
    if ds.status == "older" and ds.ready_state == "current":
        ds.text = "Older save - update waiting in its ready folder"


def _ready_issues(res):
    for ds in res.devices:
        if ds.ready_state in ("missing", "outdated", "damaged") and res.generation:
            res.issues.append({"kind": "publish", "device": ds.device["id"],
                               "text": f"The ready folder of {ds.device['name']} does not hold generation "
                                       f"{res.generation} yet. Use Finish publishing."})


def _names(obs):
    seen = []
    for o in obs:
        if o.device_name not in seen:
            seen.append(o.device_name)
    return seen


def _join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _distinct(obs, cc):
    """One representative per distinct progress (same progress copied to several devices counts once; two saves of
    the same progress in different places are different). The representative is the one on a device of its own
    platform, else the most recent."""
    groups = []
    for o in obs:
        for g in groups:
            r = g[0]
            if (r.family, r.progress_key) == (o.family, o.progress_key) and same_place(cc, o.family, r.image, o.image):
                g.append(o)
                break
        else:
            groups.append([o])
    out = []
    for g in groups:
        g.sort(key=lambda o: (o.platform != o.device_platform, o.conflict_copy, -o.mtime))
        out.append((g[0], g))
    return out


def _chain_tip(cands, cc, hv=None):
    """Same-family candidates where one continues every other one -> that one; else None. With a base generation
    (all candidates continue it), "continues b" means: descent(b, a), at least b's play time, and a holds all the
    progress b made since the base (otherwise both progressed separately: a conflict)."""
    if len(cands) < 2 or len({o.family for o in cands}) != 1:
        return None
    fam = cands[0].family
    base = None
    if hv is not None and len({o.gen_ref for o in cands}) == 1 and cands[0].gen_ref:
        base = hv.image(cands[0].gen_ref, fam)
    for a in cands:
        ok_all = True
        sa = cc.shared(fam, a.image)
        for b in cands:
            if a is b:
                continue
            sb = cc.shared(fam, b.image)
            ok, _, _ = scmod.descent(b.image, a.image, cc.T, fam)
            if not ok or sa["play_time_s"] < sb["play_time_s"]:
                ok_all = False
                break
            if base is not None and not contains(sa, delta_facts(cc.shared(fam, base), sb))[0]:
                ok_all = False
                break
        if ok_all:
            return a
    return None


def decide(res, hv, cc):
    devs = res.devices
    if not devs:
        return Decision("no-devices", "Add your devices in Settings to start.")
    pending = [o for o in res.saves() if o.state == "pending"]
    if pending:
        names = _join(_names(pending))
        return Decision("waiting", f"Waiting for a complete save from {names}.",
                        detail="A save is still being transferred or written. Scan Again when Syncthing has "
                               "finished.")
    ok = [o for o in res.saves() if o.state == "ok"]
    if not hv.current:
        starts = _distinct([o for o in ok if o.status == "start"], cc)
        if not starts:
            return Decision("nothing", "No saves found yet. Put a save in a device folder, then Scan Again.")
        if len(starts) == 1:
            o = starts[0][0]
            return Decision("start", f"Ready to start syncing from {o.device_name}.", source=o.key,
                            options=[o.key])
        tip = _chain_tip([g[0] for g in starts], cc)
        keys = [g[0].key for g in starts]
        return Decision("choose-start", "Saves were found on " + _join(_names([g[0] for g in starts])) +
                        ". Choose the save to start syncing from.", options=keys, needs_choice=True,
                        detail=(f"Suggestion: {tip.device_name} (it contains the others' progress)" if tip else ""))
    new = _distinct([o for o in ok if o.status == "new-progress"], cc)
    div = _distinct([o for o in ok if o.status == "divergent"], cc)
    if len(new) > 1:                                    # successive saves of ONE device count once; progress on
        by_dev = {}                                     # two devices is always a choice (independent play)
        for g in new:
            by_dev.setdefault(g[0].device_id, []).append(g)
        keep = []
        for groups in by_dev.values():
            tip = _chain_tip([g[0] for g in groups], cc, hv) if len(groups) > 1 else groups[0][0]
            if tip is None:
                keep += groups
                continue
            for o, grp in groups:
                if o is not tip:
                    for x in grp:
                        x.status, x.detail = "older", f"an earlier save than {tip.name} on {tip.device_name}"
            keep += [g for g in groups if g[0] is tip]
        new = keep
    if len(new) == 1 and not div:
        o = new[0][0]
        return Decision("new-progress", f"New progress found on {o.device_name}.", source=o.key, options=[o.key])
    if not new and not div:
        return Decision("in-sync", "All available saves match the last sync.")
    cands = [g[0] for g in new + div]
    names = _names(cands)
    if len(names) == 2:
        msg = f"Progress was found on both the {_join(names)}. Choose which playthrough to continue."
    elif len(names) > 2:
        msg = f"Progress was found on the {_join(names)}. Choose which playthrough to continue."
    elif len(cands) >= 2:
        msg = f"{names[0]} has two different saves with new progress. Choose which playthrough to continue."
    elif div:
        msg = (f"{names[0]} has progress that started from an older sync (generation {cands[0].gen_ref}). Choose "
               "whether to continue it.")
    else:
        msg = "Choose which playthrough to continue."
    return Decision("conflict", msg, options=[o.key for o in cands], needs_choice=True,
                    detail="Every save found now is kept in the history and can be recovered; nothing is merged.")
