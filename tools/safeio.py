"""Output and input safety for xcconv (Phase 2F). Nothing here knows about save formats.

  guard_out(path)          refuse paths that are, or resolve (junctions, symlinks, case aliases) into, a game install,
                           an emulator folder or a Wii NAND title folder
  check_name(name, kind)   validated output file names (no separators, no traversal)
  commit(out_dir, files)   all-or-nothing install of several files: everything is written and verified in a hidden
                           staging folder next to out_dir, then the staging folder is renamed to out_dir in one step.
                           out_dir must not exist (or be an empty folder). A failure at any point leaves no out_dir
                           and no partial files; a crash can only leave a ".xcconv-staging-*" folder, which never
                           looks like an output and is listed / removed by leftovers() / cleanup()
  write_new(path, data)    single new file (reports), same guards, never overwrites
  read_input(path, limit)  bounded read of an input file with clear errors
"""
import hashlib
import json
import os
import re
import shutil
import tempfile


class Refused(Exception):
    pass


LIVE_MARKERS = [  # lower-case path fragments that identify live game data folders
    os.path.join("quiver launcher", "apps"),
    os.path.join("dolphin", "user", "wii"),
    os.path.join("dolphin emulator", "wii"),
    os.path.join("game saves & memory cards", "wii", "title"),
    os.path.join("my files", "video game stuff"),
    os.path.join("wii", "title", "00010000"),
    os.path.join("title", "00010000", "53583445"),
]
MARKER_FILES = [  # a folder holding one of these (or any of its sub-folders) is a game / emulator installation
    "xcde.exe", os.path.join("build", "xcde.exe"), "xcde.ini", "Dolphin.exe", "portable.txt", "Play Monado.bat",
]
STAGING_PREFIX = ".xcconv-staging-"
STAGING_MARK = ".xcconv-staging.json"
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
_FAULT = None   # test hook: callable(stage, detail) that may raise, for failure injection


def _fault(stage, detail=""):
    if _FAULT is not None:
        _FAULT(stage, detail)


def resolve(path):
    """Absolute path with every existing component resolved (junctions and symlinks included)."""
    return os.path.realpath(os.path.abspath(path))


def _ancestors(p):
    out = []
    while True:
        out.append(p)
        q = os.path.dirname(p)
        if q == p:
            return out
        p = q


def guard_out(path):
    cands = {os.path.normcase(os.path.abspath(path)), os.path.normcase(resolve(path))}
    for c in cands:
        low = c.lower() + os.sep
        for m in LIVE_MARKERS:
            if m + os.sep in low or low.endswith(m + os.sep):
                raise Refused(f"refusing to write into a live game/save location: {path}")
        for a in _ancestors(c):
            for f in MARKER_FILES:
                if os.path.isfile(os.path.join(a, f)):
                    raise Refused(f"refusing to write inside a game or emulator installation ({a}): {path}")


def check_name(name, what="file name"):
    if not NAME_RE.match(name or "") or ".." in name:
        raise Refused(f"invalid {what} {name!r}: use letters, digits, '_', '-', '.' only (no folders)")
    return name


def _check_rel(rel):
    parts = rel.replace("\\", "/").split("/")
    if not parts or any(not NAME_RE.match(p) or p in (".", "..") for p in parts) or os.path.isabs(rel):
        raise Refused(f"invalid output path {rel!r}")
    return os.path.join(*parts)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def plan(out_dir, files):
    """Validate a commit without writing: returns the resolved target folder."""
    if not files:
        raise Refused("nothing to write")
    target = resolve(out_dir)
    guard_out(out_dir)
    for rel in files:
        guard_out(os.path.join(target, _check_rel(rel)))
    if os.path.lexists(out_dir):
        if not os.path.isdir(out_dir) or os.listdir(out_dir):
            raise Refused(f"output folder already exists and is not empty: {out_dir} (choose a new folder; existing "
                          "files are never overwritten)")
        if os.path.islink(out_dir) or getattr(os.path, "isjunction", lambda _: False)(out_dir):
            raise Refused(f"output folder is a link/junction: {out_dir} (choose a plain new folder)")
    return target


def commit(out_dir, files, dry=False):
    """files: {relative path: bytes}. -> {relative path: sha256}. All or nothing."""
    target = plan(out_dir, files)
    digests = {rel: sha(b) for rel, b in files.items()}
    if dry:
        return digests
    parent = os.path.dirname(target)
    os.makedirs(parent, exist_ok=True)
    guard_out(parent)
    staging = tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=parent)
    try:
        with open(os.path.join(staging, STAGING_MARK), "w", encoding="utf-8") as f:
            json.dump({"target": target, "files": digests}, f)
        for rel, data in files.items():
            p = os.path.join(staging, _check_rel(rel))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            _fault("write", rel)
            with open(p, "xb") as f:
                f.write(data)
                f.flush()
                _fault("flush", rel)
                os.fsync(f.fileno())
        for rel, d in digests.items():          # read-back before anything becomes visible
            with open(os.path.join(staging, _check_rel(rel)), "rb") as f:
                if sha(f.read()) != d:
                    raise Refused(f"staged file {rel} does not read back identically")
            _fault("verify", rel)
        os.remove(os.path.join(staging, STAGING_MARK))
        _fault("rename", target)
        if os.path.isdir(target) and not os.listdir(target):
            os.rmdir(target)
        os.rename(staging, target)              # one step: the whole output appears or nothing does
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    for rel, d in digests.items():              # final check of the installed files
        with open(os.path.join(target, _check_rel(rel)), "rb") as f:
            if sha(f.read()) != d:
                raise Refused(f"installed file {rel} does not match what was written")
    return digests


def write_new(path, data):
    guard_out(path)
    if os.path.lexists(path):
        raise Refused(f"refusing to overwrite existing file: {path}")
    d = os.path.dirname(resolve(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=STAGING_PREFIX)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if os.path.lexists(path):
            raise Refused(f"refusing to overwrite existing file: {path}")
        os.rename(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def leftovers(folder):
    """Staging folders left by an interrupted run (they never contain a committed output)."""
    out = []
    if os.path.isdir(folder):
        for n in os.listdir(folder):
            p = os.path.join(folder, n)
            if n.startswith(STAGING_PREFIX) and os.path.isdir(p):
                out.append(p)
    return out


def cleanup(folder):
    removed = []
    for p in leftovers(folder):
        guard_out(p)
        shutil.rmtree(p)
        removed.append(p)
    return removed


def read_input(path, what, limit=4 << 20):
    if not path:
        raise Refused(f"{what}: no file given")
    if not os.path.isfile(path):
        raise Refused(f"{what}: file not found: {path}")
    n = os.path.getsize(path)
    if n > limit:
        raise Refused(f"{what}: {path} is {n} bytes, too large to be a save or sidecar")
    with open(path, "rb") as f:
        return f.read()
