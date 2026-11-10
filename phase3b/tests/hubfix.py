"""Fixtures for the Phase 3B Sync Hub tests: game-written saves from earlier phases, simulated Syncthing device
folders, and SYNTHETIC gameplay progress (flags, money, EXP, items, play time edited on a Wii-layout image with the
checksums recomputed). Synthetic progress is only used where no game-written continuation exists; the emulator
acceptance runs (phase3b/runs) cover real play.
"""
import hashlib
import os
import shutil
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P3B = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3B)
for p in (os.path.join(P3B, "src"), os.path.join(ROOT, "phase3a", "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import canon  # noqa: E402
import flagmap as fm  # noqa: E402
import wii_save  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402
from xcsync import store, scan, sync  # noqa: E402

FIX3 = os.path.join(ROOT, "phase3a", "fixtures")
W150 = os.path.join(FIX3, "wii_user_s150.bin")                     # the user's 22 h Wii save (game-written)
W018 = os.path.join(FIX3, "wii_user_s018.bin")                     # the user's earlier save (story 18)
W006 = os.path.join(FIX3, "wii_d7_s006.bin")                       # a different playthrough (story 6)
W150_LATER = os.path.join(ROOT, "work", "phase2e", "dolphin", "d6_travel", "user", "Wii", "title", "00010000",
                          "53583445", "data", "monado01")         # the s150 playthrough played on in Dolphin
X3_USER = os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001", "monado01")   # 3DS story 8
X3_ARCH = os.path.join(ROOT, "phase3a", "originals", "azahar_live", "00000001")
X3_A2 = os.path.join(ROOT, "phase3a", "runs", "azahar", "a2_s150_gameplay", "save_after", "00000001", "monado02")
X3_A1 = os.path.join(ROOT, "phase3a", "runs", "azahar", "a1_wii_s150_to_3ds", "save_after", "00000001", "monado03")
X3_A5 = os.path.join(ROOT, "phase3a", "runs", "azahar", "a5_de_s232_to_3ds_fixed", "save_after", "00000001",
                     "monado02")                                    # DE s232 converted to 3DS, played and saved
DE_TPL = os.path.join(ROOT, "work", "template", "bfsgame00.sav")
DE_S232 = os.path.join(ROOT, "phase2f", "fixtures", "real", "s232_v10_monado.sav")
DE_S269 = os.path.join(ROOT, "phase2f", "fixtures", "real", "s269_v10_monado.sav")
WORK = os.path.join(P3B, "work", "tests")
T = xs.tables()


def rd(p):
    with open(p, "rb") as f:
        return f.read()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def put(path, data, age=60):
    """Write a file as a device would (via a temp file), with an mtime `age` seconds in the past."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    t = time.time() - age
    os.utime(path, (t, t))
    return path


def fresh(name):
    p = os.path.join(WORK, name)
    if os.path.exists(p):
        shutil.rmtree(p)
    os.makedirs(p)
    return p


def tree_hashes(*roots):
    out = {}
    for r in roots:
        for dp, _, fs in os.walk(r):
            for f in fs:
                p = os.path.join(dp, f)
                st = os.stat(p)
                out[p] = (sha(rd(p)), st.st_size, st.st_mtime_ns)
        out[r + "<dirs>"] = sorted(os.path.relpath(dp, r) for dp, _, _ in os.walk(r))
    return out


# ------------------------------------------------------------------------------------------------- hub fixture
class HubFx:
    """A hub with simulated Syncthing device folders (outside the hub, like real shares)."""

    def __init__(self, name, devices=(("Windows desktop", "de"), ("Odin 2 Mini", "wii"), ("New 3DS", "3ds")),
                 templates=("de", "3ds"), syncthing=True):
        self.base = fresh(name)
        self.hub = store.Hub.create(os.path.join(self.base, "Xenoblade Sync"))
        self.dev = {}
        for n, plat in devices:
            inc = os.path.join(self.base, "syncthing", n.replace(" ", "_"))
            os.makedirs(inc)
            if syncthing:
                os.makedirs(os.path.join(inc, ".stfolder"))
            self.dev[n] = self.hub.add_device(n, plat, incoming=inc)
        for t in templates:
            self.hub.add_template(t, {"de": DE_TPL, "3ds": X3_USER, "wii": W006}[t])

    def drop(self, device, name, data, age=60):
        return put(os.path.join(self.dev[device]["incoming"], name), data, age)

    def scan(self, **kw):
        kw.setdefault("delay", 0)
        kw.setdefault("settle", 0.5)
        return scan.scan(self.hub, **kw)

    def sync(self, res=None, **kw):
        res = res or self.scan()
        kw.setdefault("delay", 0)
        return sync.sync(self.hub, res, **kw)

    def gen(self, n=None):
        if n is None:
            return self.hub.current_generation()[1]
        return self.hub.load_generation(n)

    def out(self, plat, n=None):
        g = self.gen(n)
        return rd(os.path.join(g["_dir"], *g["outputs"][plat]["main"].split("/")))

    def image(self, fam, n=None):
        g = self.gen(n)
        return rd(os.path.join(g["_dir"], *g["family_images"][fam]["file"].split("/")))

    def ready(self, device):
        return self.hub.ready_dir(self.dev[device])

    def status(self, res, device):
        return next(d for d in res.devices if d.device["name"] == device)


# ------------------------------------------------------------------------------------------------- synthetic play
def _shared_1bit_unset(img, n, skip=0):
    gids = sorted(g for g in canon.shared_flag_map().values() if fm.kind(g) == 1 and not fm.wii_get(img, g))
    return gids[skip:skip + n]


def _set_bit(b, gid):
    k = gid - 0xA20
    off = fm.WII_P + 4 * (0x320 + (k >> 5))
    w = struct.unpack_from(">I", b, off)[0] | (1 << (k & 31))
    struct.pack_into(">I", b, off, w)


def play_wii(img, flags=8, skip=0, money=0, minutes=20, exp=0, char=1, add_items=0, remove_items=0, story=0):
    """Synthetic Wii-layout progress: set `flags` shared 1-bit flags (from index `skip`), money, play time, EXP,
    material records added/removed, story counter. Checksums recomputed."""
    b = bytearray(img)
    for g in _shared_1bit_unset(img, flags, skip):
        _set_bit(b, g)
    mo = wii_save.ITEM + 0x120E8
    struct.pack_into(">I", b, mo, struct.unpack_from(">I", b, mo)[0] + money)
    pt = struct.unpack_from(">I", b, 0x11EB0)[0]
    s = (pt >> 12) * 3600 + (pt >> 6 & 63) * 60 + (pt & 63) + minutes * 60
    struct.pack_into(">I", b, 0x11EB0, (s // 3600) << 12 | (s // 60 % 60) << 6 | s % 60)
    if exp:
        o = wii_save.CHAR_BASE + wii_save.CHAR_SIZE * char + 0x2A4
        struct.pack_into(">I", b, o, struct.unpack_from(">I", b, o)[0] + exp)
    if add_items or remove_items:
        ir = wii_save.decode_bytes(bytes(b))
        mats = ir["items"]["material"]
        used = {r["index"] for r in mats}
        base = wii_save.ITEM + 0x10B18
        for r in mats[:remove_items]:
            b[base + 8 * r["index"]:base + 8 * r["index"] + 8] = bytes(8)
        tpl = bytes(b[base + 8 * mats[-1]["index"]:base + 8 * mats[-1]["index"] + 8])
        free = [i for i in range(300) if i not in used]
        for i in free[:add_items]:
            b[base + 8 * i:base + 8 * i + 8] = tpl
    if story:
        o = fm.WII_P + 4 * 0x20
        w = struct.unpack_from(">I", b, o)[0]
        struct.pack_into(">I", b, o, (w & 0xFFFF0000) | ((w & 0xFFFF) + story))
    return xc3d.fix_wii_checksums(bytes(b))


def resave_wii(img, seconds=7):
    """What a load-and-save without play changes: play time seconds (and the clock)."""
    b = bytearray(img)
    pt = struct.unpack_from(">I", b, 0x11EB0)[0]
    s = (pt >> 12) * 3600 + (pt >> 6 & 63) * 60 + (pt & 63) + seconds
    struct.pack_into(">I", b, 0x11EB0, (s // 3600) << 12 | (s // 60 % 60) << 6 | s % 60)
    t = struct.unpack_from(">f", b, 0x11EB4)[0]
    struct.pack_into(">f", b, 0x11EB4, t + seconds)
    return xc3d.fix_wii_checksums(bytes(b))


def to_3ds(img, template=X3_USER):
    return xc3d.pack(s3.to_3ds_image(img, s3.load_3ds(template, "t")[1])[0])


def x3_a5_played():
    """Run a5 (the 3DS game's own save of DE s232 converted to 3DS - a load and re-save, 0.9 units moved) plus
    SYNTHETIC progress (6 shared flags, 25 minutes), written as a 3DS file with a5's own container."""
    img = s3.load_3ds(X3_A5, "a5")[2]
    return to_3ds(play_wii(img, flags=6, skip=40, minutes=25), template=X3_A5)


def play_de(de_bytes, flags=8, skip=0, money=0, minutes=20):
    """Synthetic DE progress, edited directly on the DE save (DE saves carry no checksum): shared 1-bit flags,
    money, play time."""
    import de_save
    b = bytearray(de_bytes)
    gids = sorted(t for t, g in canon.shared_flag_map().items() if fm.kind(t) == 1 and not fm.de_get(de_bytes, t))
    for t in gids[skip:skip + flags]:
        n = t - 0xA20
        off = 0x50 + 4 * (n >> 5)
        struct.pack_into("<I", b, off, struct.unpack_from("<I", b, off)[0] | 1 << (n & 31))
    struct.pack_into("<I", b, de_save.MONEY, struct.unpack_from("<I", b, de_save.MONEY)[0] + money)
    struct.pack_into("<I", b, 4, struct.unpack_from("<I", b, 4)[0] + minutes * 60)
    return bytes(b)


def play_de_via_engine(fx, de_bytes, **kw):
    """Synthetic DE progress: the DE state's Wii projection advanced with play_wii, converted back onto the same DE
    save by the engine (first-export onto that DE save as template): a DE save that continues de_bytes."""
    d = fresh(os.path.join(os.path.basename(fx.base), "play_de_" + sha(de_bytes)[:8] + "_" + str(sorted(kw.items()))
                           .replace(" ", "")[:40].translate(str.maketrans("[](),':", "_______"))))
    dp = put(os.path.join(d, "in", "bfsgame00.sav"), de_bytes)
    r = xs.de_to_wii_convert(xs.DeToWiiRequest(de=dp, out=os.path.join(d, "w"), base=W150, overflow="sidecar"))
    w2 = play_wii(rd(os.path.join(r.out_dir, "monado01")), **kw)
    wp = put(os.path.join(d, "w2", "monado01"), w2)
    r2 = xs.wii_to_de(xs.WiiToDeRequest(wii=wp, out=os.path.join(d, "d"), template=dp))
    return rd(r2.main_output)
