"""Phase 2F data-level probes against a tools directory (default: frozen 2E source). Library API only; writes nothing
except phase2f/probe_out/probe_data.json."""
import json
import os
import struct
import sys

P2F = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.dirname(P2F)
TOOLS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P2F, "snapshot_2E", "source", "tools")
sys.path.insert(0, TOOLS)
os.environ.setdefault("XCCONV_DATA", os.path.join(ROOT, "data"))
import canon  # noqa: E402
import convert  # noqa: E402
import de_to_wii  # noqa: E402
import reimport  # noqa: E402
import sidecar as scmod  # noqa: E402
import wii_save  # noqa: E402

T = convert.load_tables()
O = os.path.join(ROOT, "work", "originals")
W1 = open(os.path.join(O, "monado01"), "rb").read()
TPL = open(os.path.join(ROOT, "work", "template", "bfsgame00.sav"), "rb").read()
S232 = open(os.path.join(ROOT, "public", "blobs", "s232_207aed635e_bfsgame00.sav"), "rb").read()
res = {}


def wii_progress(w, money=1000):
    img = de_to_wii.WiiImage(w)
    m = struct.unpack_from(">I", w, wii_save.ITEM + 0x120E8)[0]
    img.put(wii_save.ITEM + 0x120E8, "I", m + money)
    pt = struct.unpack_from(">I", w, 0x11EB0)[0]
    img.put(0x11EB0, "I", pt + (1 << 6))
    de_to_wii.fix_crcs(img)
    return bytes(img.b)


def add_de_only_collectable(de, gid=3956, serial=9999):
    b = bytearray(de)
    off, size = 0x31970, 0x14
    sl = next(i for i in range(500) if b[off + size * i + 0x10] == 0)
    struct.pack_into("<HHHHH", b, off + size * sl, sl, 10, gid, 10, 1)
    struct.pack_into("<I", b, off + size * sl + 0xC, serial)
    b[off + size * sl + 0x10] = 1
    return bytes(b), sl


def has_item(de, gid):
    c = canon.from_de(de, T)["shared"]["inventory"]["collectable"]
    return sum(1 for r in c.values() if r["gid"] == gid)


# H5 stale sidecar resurrects a sold DE-only item
de0, _, _ = convert.build(W1, TPL, T)
de0x, sl = add_de_only_collectable(de0)
w1, _, dfr = de_to_wii.build(de0x, W1, T, lineage=True)
s1 = scmod.make("de_to_wii", de0x, w1, canon.from_de(de0x, T), canon.from_wii(w1, T), deferred=dfr)
w1p = wii_progress(w1)
de2, _ = reimport.wii_to_de_reimport(w1p, s1, T)
s2 = scmod.make("wii_to_de", w1p, de2, canon.from_wii(w1p, T), canon.from_de(de2, T), parent=s1)
de2s = bytearray(de2)                        # the user sells the DE-only item in DE
off, size = 0x31970, 0x14
for i in range(500):
    o = off + size * i
    if de2s[o + 0x10] and struct.unpack_from("<H", de2s, o + 4)[0] == 3956:
        de2s[o:o + size] = de2[off + size * 499:off + size * 500]
de2s = bytes(de2s)
w3, _, dfr3 = de_to_wii.build(de2s, scmod.source_image(s2), T, lineage=True)
s3 = scmod.make("de_to_wii", de2s, w3, canon.from_de(de2s, T), canon.from_wii(w3, T), deferred=dfr3, parent=s2)
w3p = wii_progress(w3, 500)
try:
    stale, log = reimport.wii_to_de_reimport(w3p, s1, T)
    res["H5_stale_sidecar_no_current_de"] = {"accepted": True, "items_3956_after": has_item(stale, 3956),
                                             "items_3956_in_current_de": has_item(de2s, 3956)}
except Exception as e:
    res["H5_stale_sidecar_no_current_de"] = {"accepted": False, "error": f"{type(e).__name__}: {e}"[:200]}
try:
    reimport.wii_to_de_reimport(w3p, s1, T, current_de=de2s)
    res["H5_stale_sidecar_with_current_de"] = {"accepted": True}
except Exception as e:
    res["H5_stale_sidecar_with_current_de"] = {"accepted": False, "error": f"{type(e).__name__}: {e}"[:200]}
good, _ = reimport.wii_to_de_reimport(w3p, s3, T, current_de=de2s)
res["H5_correct_sidecar"] = {"items_3956_after": has_item(good, 3956)}

# H8 re-import read-back hard differences (the CLI skips the check when a sidecar is used)
tolerated = ("/achievements", "/quest_counters", "/clock", "/characters/1/palette2")
diffs = canon.compare(canon.from_wii(w3p, T)["shared"], canon.from_de(good, T)["shared"])
res["H8_reimport_hard_diffs"] = [list(map(str, d)) for d in diffs if not d[0].startswith(tolerated)][:10]

# H10 template leak: a template with Expert-Mode state from ANOTHER playthrough
tplx = bytearray(TPL)
for k in range(1, 8):
    o = 0x152728 + 0x138 * (k - 1)
    struct.pack_into("<I", tplx, o + 0xF4, 123456)        # reserve EXP of the template's playthrough
    struct.pack_into("<I", tplx, o + 0x30, 0x1234)        # cosmetic of the template's playthrough
out, _, fail = convert.build(W1, bytes(tplx), T)
cd = canon.from_de(out, T)["de_only"]["characters"]
res["H10_template_leak"] = {k: {"reserve_exp": v["reserve_exp"], "cosmetic0": v["cosmetic"][0]} for k, v in cd.items()}

# v7 DE (public s232, real Expert Mode) -> Wii -> (Wii progress) -> DE
try:
    base = W1
    w, _, dfr = de_to_wii.build(S232, base, T, lineage=False, overflow="sidecar")
    sc = scmod.make("de_to_wii", S232, w, canon.from_de(S232, T), canon.from_wii(w, T), deferred=dfr)
    try:
        back, _ = reimport.wii_to_de_reimport(wii_progress(w), sc, T)
        res["V7_return_trip"] = {"ok": True, "len": len(back)}
    except Exception as e:
        res["V7_return_trip"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
except Exception as e:
    res["V7_export"] = f"{type(e).__name__}: {e}"[:200]

# party containing character 8 (Fiora, second form): converted or refused?
de8 = bytearray(de0)
struct.pack_into("<H", de8, 0x1526D8 + 2 * len(canon.from_de(de0, T)["shared"]["party"]), 8)
n = struct.unpack_from("<I", de8, 0x1526D8 + 0x18)[0]
struct.pack_into("<I", de8, 0x1526D8 + 0x18, n + 1)
try:
    w8, log8, _ = de_to_wii.build(bytes(de8), W1, T, lineage=True)
    c8 = wii_save.decode_bytes(w8)["characters"][8]
    res["C8_party_de_to_wii"] = {"accepted": True, "wii_party": wii_save.decode_bytes(w8)["party"],
                                 "wii_char8_level": c8["level"], "de_char8_level": struct.unpack_from("<I", de8, 0x152728 + 0x138 * 7)[0]}
except Exception as e:
    res["C8_party_de_to_wii"] = {"accepted": False, "error": f"{type(e).__name__}: {e}"[:200]}

os.makedirs(os.path.join(P2F, "probe_out"), exist_ok=True)
json.dump(res, open(os.path.join(P2F, "probe_out", "probe_data.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
