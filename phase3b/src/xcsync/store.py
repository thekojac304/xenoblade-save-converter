"""Sync Hub storage: managed folder layout, device profiles, verified templates, the commit pointer and the lock.

Layout (inside the hub folder the user chose):

  xcsync-hub.json              marker: schema, hub id (a folder without it is never treated as a hub)
  metadata/devices.json        device profiles (stable ids; display names may change)
  metadata/sync-state.json     THE commit pointer: current generation number + SHA-256 of its generation.json
  metadata/sync-state.prev.json   the pointer before the last commit (recovery if the current one is damaged)
  metadata/hub.lock            present only while a Sync / publish runs
  templates/<wii|de|3ds>/      verified copies of the starting / template saves (originals never changed)
  incoming/<device folder>/    default place for a device's incoming saves (Syncthing share from the device)
  ready/<device folder>/       published output for a device (Syncthing share to the device) + READY.json
  history/gen-NNNNNN/          one immutable folder per committed generation
  staging/                     transactions in progress (never referenced by the pointer)

Every write here is atomic per file (temp file + fsync + os.replace) and guarded against live game folders.
"""
import ctypes
import hashlib
import json
import os
import re
import shutil
import time
import uuid

from . import paths3b  # noqa: F401
from . import HUB_SCHEMA, APP_VERSION

import safeio
import xc3d
import xc3dservice as s3
import xcservice as xs

Refused = safeio.Refused
MARKER = "xcsync-hub.json"
PLATFORMS = ("wii", "de", "3ds")
NICE = {"wii": "Wii (Dolphin)", "de": "Definitive Edition", "3ds": "Xenoblade 3D"}
SHORT = {"wii": "Wii", "de": "DE", "3ds": "3DS"}
FAMILY = {"wii": "wii", "3ds": "wii", "de": "de"}         # Wii and 3DS hold the same state (lossless transcode)
DEFAULT_SLOT = {"wii": "monado01", "de": "00", "3ds": "monado01"}
SUGGESTED_DEVICES = [("Windows desktop", "de"), ("GPD Win Mini", "de"), ("Android phone", "wii"),
                     ("Odin 2 Mini", "wii"), ("New Nintendo 3DS", "3ds")]


class HubError(Refused):
    """A refusal by the Sync Hub (nothing was changed)."""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return sha(f.read())


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------------------------------------------- atomic files
def atomic_write(path, data):
    """Replace path with data in one step (temp file in the same folder, fsync, os.replace)."""
    safeio.guard_out(path)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".xcsync-tmp-{uuid.uuid4().hex[:12]}")
    try:
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def write_json(path, obj):
    atomic_write(path, json.dumps(obj, indent=1, sort_keys=True).encode())


def read_json(path, what):
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, ValueError, UnicodeDecodeError) as e:
        raise HubError(f"{what} is damaged ({type(e).__name__}: {e})")


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return (s or "device")[:32]


# ------------------------------------------------------------------------------------------------- hub
class Hub:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    # paths
    def p(self, *parts):
        return os.path.join(self.root, *parts)

    @property
    def meta(self):
        return self.p("metadata")

    @property
    def pointer_path(self):
        return self.p("metadata", "sync-state.json")

    @property
    def prev_pointer_path(self):
        return self.p("metadata", "sync-state.prev.json")

    def gen_dir(self, n):
        return self.p("history", "gen-%06d" % n)

    def ready_dir(self, dev):
        return self.p("ready", dev["folder"])

    def incoming_default(self, folder):
        return self.p("incoming", folder)

    # ---- creation / opening
    @classmethod
    def create(cls, root):
        root = os.path.abspath(root)
        safeio.guard_out(root)
        if os.path.exists(os.path.join(root, MARKER)):
            return cls.open(root)
        if os.path.isdir(root) and os.listdir(root):
            raise HubError(f"{root} is not empty. Choose an empty folder (or an existing Sync Hub folder) so the hub "
                           "never mixes with other files.")
        h = cls(root)
        for d in ("metadata", "templates", "incoming", "ready", "history", "staging"):
            os.makedirs(h.p(d), exist_ok=True)
        write_json(h.p(MARKER), {"schema": HUB_SCHEMA, "hub_id": uuid.uuid4().hex, "created": now_iso(),
                                 "created_by": APP_VERSION})
        write_json(h.p("metadata", "devices.json"), {"schema": HUB_SCHEMA, "devices": []})
        return h

    @classmethod
    def open(cls, root):
        root = os.path.abspath(root)
        m = os.path.join(root, MARKER)
        if not os.path.isfile(m):
            raise HubError(f"{root} is not a Sync Hub folder (no {MARKER})")
        info = read_json(m, "hub marker")
        if info.get("schema") != HUB_SCHEMA:
            raise HubError(f"{root} was made by an unsupported Sync Hub version ({info.get('schema')})")
        h = cls(root)
        h.info = info
        return h

    @property
    def hub_id(self):
        return read_json(self.p(MARKER), "hub marker")["hub_id"]

    # ---- devices
    def devices(self):
        try:
            d = read_json(self.p("metadata", "devices.json"), "device list")
        except FileNotFoundError:
            return []
        devs = d.get("devices")
        if not isinstance(devs, list):
            raise HubError("device list is damaged")
        return devs

    def device(self, dev_id):
        for d in self.devices():
            if d["id"] == dev_id:
                return d
        raise HubError(f"unknown device {dev_id}")

    def _save_devices(self, devs):
        write_json(self.p("metadata", "devices.json"), {"schema": HUB_SCHEMA, "devices": devs})

    def add_device(self, name, platform, incoming=None, slot=None, enabled=True):
        if platform not in PLATFORMS:
            raise HubError(f"unknown platform {platform!r}")
        name = (name or "").strip()
        if not name:
            raise HubError("give the device a name")
        devs = self.devices()
        folders = {d["folder"] for d in devs}
        base, folder, i = slug(name), slug(name), 2
        while folder in folders:
            folder, i = f"{base}-{i}", i + 1
        dev = {"id": uuid.uuid4().hex[:16], "name": name, "platform": platform, "folder": folder,
               "incoming": os.path.abspath(incoming) if incoming else self.incoming_default(folder),
               "slot": self._check_slot(platform, slot or DEFAULT_SLOT[platform]), "enabled": bool(enabled),
               "created": now_iso()}
        if not incoming:
            os.makedirs(dev["incoming"], exist_ok=True)
        self._check_ready_location(dev)
        devs.append(dev)
        self._save_devices(devs)
        return dev

    def update_device(self, dev_id, **changes):
        devs = self.devices()
        for d in devs:
            if d["id"] == dev_id:
                for k, v in changes.items():
                    if k == "name":
                        v = (v or "").strip()
                        if not v:
                            raise HubError("give the device a name")
                    elif k == "incoming":
                        v = os.path.abspath(v) if v else self.incoming_default(d["folder"])
                    elif k == "slot":
                        v = self._check_slot(d["platform"], v)
                    elif k == "enabled":
                        v = bool(v)
                    elif k == "platform":
                        if v not in PLATFORMS:
                            raise HubError(f"unknown platform {v!r}")
                    else:
                        raise HubError(f"device setting {k!r} cannot be changed")
                    d[k] = v
                self._save_devices(devs)
                return d
        raise HubError(f"unknown device {dev_id}")

    def remove_device(self, dev_id):
        """Removes the profile only. Its incoming/ready folders and every generation stay on disk."""
        devs = [d for d in self.devices() if d["id"] != dev_id]
        if len(devs) == len(self.devices()):
            raise HubError(f"unknown device {dev_id}")
        self._save_devices(devs)

    @staticmethod
    def _check_slot(platform, slot):
        s = str(slot).strip()
        if platform == "de":
            if not re.fullmatch(r"\d\d", s):
                raise HubError("DE slot must be two digits (00, 01, ...)")
            return s
        s = s if s.startswith("monado0") else f"monado0{s}"
        if s not in ("monado01", "monado02", "monado03"):
            raise HubError("slot must be monado01, monado02 or monado03")
        return s

    def _check_ready_location(self, dev):
        safeio.guard_out(self.ready_dir(dev))

    def configured_platforms(self):
        return sorted({d["platform"] for d in self.devices() if d.get("enabled", True)}, key=PLATFORMS.index)

    # ---- templates
    def template_dir(self, platform):
        return self.p("templates", platform)

    def template_info(self, platform):
        try:
            return read_json(os.path.join(self.template_dir(platform), "template.json"), f"{platform} template info")
        except FileNotFoundError:
            return None

    def template_file(self, platform):
        """Path of the verified template copy (re-checked against its recorded hash), or None."""
        info = self.template_info(platform)
        if not info:
            return None
        p = os.path.join(self.template_dir(platform), info["file"])
        if not os.path.isfile(p) or sha_file(p) != info["sha256"]:
            raise HubError(f"the stored {SHORT[platform]} template was changed or damaged; add it again in Settings")
        return p

    def add_template(self, platform, path):
        """Validate a starting/template save and store a copy (the original is only read)."""
        if platform not in PLATFORMS:
            raise HubError(f"unknown platform {platform!r}")
        files, extra = {}, {}
        if platform == "wii":
            b = xs.load_wii(path, f"{SHORT[platform]} template")
            files["monado01"] = b
            bn = os.path.join(os.path.dirname(os.path.abspath(path)), "banner.bin")
            if os.path.isfile(bn):
                files["banner.bin"] = safeio.read_input(bn, "banner.bin")
            main = "monado01"
        elif platform == "de":
            b = xs.load_de(path, "DE template", v10_only=True)
            files["bfsgame00.sav"] = b
            d = os.path.dirname(os.path.abspath(path))
            stem = os.path.basename(path)[:-4]
            for comp, name in ((stem + ".tmb", "bfsgame00.tmb"), ("bfssystem.sav", "bfssystem.sav")):
                cp = os.path.join(d, comp)
                if os.path.isfile(cp):
                    files[name] = safeio.read_input(cp, "template companion file")
            main = "bfsgame00.sav"
        else:
            fb, raw, wii = s3.load_3ds(path, "3DS template")
            files["monado01"] = fb
            d = os.path.dirname(os.path.abspath(path))
            arch = {}
            for n in ("monado01", "monado02", "monado03", "specialmode"):
                q = os.path.join(d, n)
                if os.path.isfile(q):
                    arch[n] = safeio.read_input(q, "3DS archive file")
            if all(f"monado0{i}" in arch for i in (1, 2, 3)):
                for n, v in arch.items():
                    files[f"archive/{n}"] = v
                extra["archive"] = sorted(arch)
            main = "monado01"
        tdir = self.template_dir(platform)
        old = tdir + ".old"
        if os.path.isdir(old):
            shutil.rmtree(old)
        tmp = self.p("staging", f"template-{platform}-{uuid.uuid4().hex[:8]}")
        for rel, data in files.items():
            atomic_write(os.path.join(tmp, *rel.split("/")), data)
        info = {"platform": platform, "file": main, "sha256": sha(files[main]), "source_path": os.path.abspath(path),
                "added": now_iso(), "files": {k: sha(v) for k, v in files.items()}}
        info.update(extra)
        info["summary"] = summarize_bytes(platform, files[main])
        write_json(os.path.join(tmp, "template.json"), info)
        if os.path.isdir(tdir):
            os.rename(tdir, old)
        os.rename(tmp, tdir)
        if os.path.isdir(old):
            shutil.rmtree(old)
        return info

    # ---- pointer
    def pointer(self):
        """-> dict or None (no generation yet). A damaged pointer raises HubError."""
        try:
            ptr = read_json(self.pointer_path, "sync state")
        except FileNotFoundError:
            return None
        if not isinstance(ptr, dict) or not isinstance(ptr.get("current"), int):
            raise HubError("sync state is damaged")
        return ptr

    def current_generation(self):
        """-> (number, generation dict) of the committed generation, verified against the pointer; (0, None) when
        there is none yet."""
        ptr = self.pointer()
        if not ptr:
            return 0, None
        n = ptr["current"]
        g = self.load_generation(n, ptr.get("generation_sha256"))
        return n, g

    def load_generation(self, n, want_sha=None):
        p = os.path.join(self.gen_dir(n), "generation.json")
        try:
            with open(p, "rb") as f:
                raw = f.read()
        except OSError:
            raise HubError(f"generation {n} is missing from the history folder")
        if want_sha and sha(raw) != want_sha:
            raise HubError(f"generation {n} does not match the sync state (changed or damaged)")
        try:
            g = json.loads(raw.decode())
        except ValueError as e:
            raise HubError(f"generation {n} is damaged ({e})")
        g["_dir"] = self.gen_dir(n)
        return g

    def committed(self):
        """Committed generation numbers (from the pointer's history list), oldest first."""
        ptr = self.pointer()
        return [h["number"] for h in ptr.get("history", [])] if ptr else []

    def generations(self):
        ptr = self.pointer()
        out = []
        if not ptr:
            return out
        for h in ptr.get("history", []):
            try:
                out.append(self.load_generation(h["number"], h.get("sha256")))
            except HubError as e:
                out.append({"number": h["number"], "damaged": str(e)})
        return out

    def set_pointer(self, n, gen_sha, kind):
        old = self.pointer()
        hist = list(old.get("history", [])) if old else []
        hist.append({"number": n, "sha256": gen_sha, "kind": kind, "committed": now_iso()})
        ptr = {"schema": HUB_SCHEMA, "hub_id": self.hub_id, "current": n, "generation_sha256": gen_sha,
               "previous": old["current"] if old else None, "history": hist, "updated": now_iso()}
        if old:
            write_json(self.prev_pointer_path, old)
        write_json(self.pointer_path, ptr)
        return ptr

    # ---- lock
    def lock(self):
        return HubLock(self.p("metadata", "hub.lock"))


def _pid_alive(pid):
    if os.name == "nt":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))         # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259               # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


class HubLock:
    """Exclusive lock file: two windows (or two PCs sharing the hub folder) cannot run Sync at the same time.
    A lock left by a crashed run (its process is gone) is taken over."""

    def __init__(self, path):
        self.path = path
        self.held = False

    def holder(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def stale(self):
        h = self.holder()
        if not h:
            return True
        if h.get("host") != os.environ.get("COMPUTERNAME", ""):
            return time.time() - h.get("t", 0) > 6 * 3600      # another PC: trust it for 6 hours
        return not _pid_alive(h.get("pid", 0))

    def __enter__(self):
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"pid": os.getpid(), "host": os.environ.get("COMPUTERNAME", ""), "t": time.time(),
                               "at": now_iso()}, f)
                self.held = True
                return self
            except FileExistsError:
                if self.stale():
                    try:
                        os.remove(self.path)
                    except OSError:
                        pass
                    continue
                h = self.holder() or {}
                raise HubError(f"another Sync is running (started {h.get('at', '?')} on {h.get('host', '?')}); "
                               "wait for it to finish")
        raise HubError("could not take the Sync Hub lock")

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(self.path)
            except OSError:
                pass
            self.held = False
        return False


# ------------------------------------------------------------------------------------------------- summaries
def family_image(platform, b):
    """Native file bytes -> (family, image): Wii-layout image for Wii/3DS, the DE bytes for DE."""
    if platform == "3ds":
        raw = xc3d.unpack(b)
        return "wii", xc3d.transcode(raw, "wii")
    return FAMILY[platform], b


def summarize_image(family, img):
    s = xs.summary(img)
    names = xs.map_names()
    party = s.get("party") or []
    lead = party[0] if party else None
    return {"story": s["story"], "map": s["map"], "location": names.get(s["map"]) or s["map"],
            "play_time": s["play_time"], "money": s["money"],
            "level": s["levels"].get(lead) if lead is not None else None,
            "leader": xs.CHAR_NAMES.get(lead, f"Character {lead}") if lead is not None else None,
            "party": [{"id": c, "name": xs.CHAR_NAMES.get(c, f"Character {c}"), "level": s["levels"].get(c)}
                      for c in party]}


def summarize_bytes(platform, b):
    fam, img = family_image(platform, b)
    return summarize_image(fam, img)
