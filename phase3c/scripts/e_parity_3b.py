"""Part E: the 3C engine against the frozen 3B engine (phase3c/baseline_3B) on real inputs. For each case both engines
run on the same files; outputs are compared byte for byte and, where they differ, every differing byte is classified:
  de_item_only  - inside a DE item record, at a byte the canonical shared state does not read (DE-only per-item data)
  wii_item_only - inside a Wii item record (Wii-only per-item data: header low bits, crystal +0x16)
  other         - anything else (must not occur)
plus a canonical shared-state comparison. Writes phase3c/work/e_parity_3b.json.  python e_parity_3b.py"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P3C = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(P3C)
sys.path.insert(0, os.path.join(P3C, "tests"))
import p3cfix as F  # noqa: E402
from p3cfix import H, T, rd  # noqa: E402
import canon  # noqa: E402
import de_save  # noqa: E402
import wii_save  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcservice as xs  # noqa: E402

BASE = os.path.join(HERE, "baseline3b.py")
REAL = os.path.join(ROOT, "phase2f", "fixtures", "real")
W = os.path.join(P3C, "work", "parity")


def b3(*args):
    r = subprocess.run([sys.executable, BASE, *args], capture_output=True, text=True, timeout=900)
    if r.returncode:
        return None, r.stderr.strip().splitlines()[-1][:300]
    return rd(json.loads(r.stdout.strip().splitlines()[-1])["main_output"]), None


def classify(a, b, game):
    if len(a) != len(b):
        return {"other": ["size"]}
    out = {"de_item_only": 0, "wii_item_only": 0, "other": []}
    if game == "de":
        ranges = [(off, off + size * 500) for _, _, off, size, _ in de_save.BOXES]
    else:
        ranges = [(wii_save.ITEM + off, wii_save.ITEM + off + size * n) for _, _, off, size, n in wii_save.BOXES]
    for i in range(len(a)):
        if a[i] != b[i]:
            if any(lo <= i < hi for lo, hi in ranges):
                out["de_item_only" if game == "de" else "wii_item_only"] += 1
            else:
                out["other"].append(hex(i))
    out["other"] = out["other"][:20]
    return out


def shared(img, game):
    return canon.from_de(img, T)["shared"] if game == "de" else canon.from_wii(img, T)["shared"]


def case(name, game, new, old, err_old=None, err_new=None):
    rec = {"case": name, "game": game}
    if new is None or old is None:
        rec.update(identical=False, new_error=err_new, old_error=err_old)
        return rec
    rec["identical"] = new == old
    if not rec["identical"]:
        rec["diff"] = classify(new, old, game)
        rec["shared_equal"] = shared(new, game) == shared(old, game)
    return rec


def main():
    res = []
    d = F.fresh("parity")
    # 1. first conversions Wii -> DE
    for nm, w in (("W150", H.W150), ("W018", H.W018)):
        n = rd(xs.wii_to_de(xs.WiiToDeRequest(wii=w, out=os.path.join(d, nm + "_w2d"), template=H.DE_TPL)).main_output)
        o, eo = b3("wii_to_de_first", w, H.DE_TPL, os.path.join(d, nm + "_w2d_b3"))
        res.append(case(f"wii_to_de first {nm}", "de", n, o, eo))
    # 2. first DE -> Wii exports (real DE saves, user's Wii save as base, overflow kept in the sidecar)
    for f in sorted(os.listdir(REAL)):
        if not f.endswith(".sav"):
            continue
        p = os.path.join(REAL, f)
        try:
            n = rd(F.export(p, os.path.join(d, f + "_d2w")).main_output)
            en = None
        except Exception as e:  # noqa: BLE001
            n, en = None, str(e)[:200]
        o, eo = b3("de_to_wii", p, H.W150, "-", "-", os.path.join(d, f + "_d2w_b3"))
        res.append(case(f"de_to_wii first {f}", "wii", n, o, eo, en))
    # 3. re-imports after (synthetic) Wii play, real DE sources
    for f in ("s232_v10_monado.sav", "s269_v10_monado.sav", "s206_v10_monado.sav"):
        p = os.path.join(REAL, f)
        e = F.export(p, os.path.join(d, f + "_exp"))
        w = H.play_wii(rd(e.main_output), flags=4)
        wp = H.put(os.path.join(d, f + "_wplay", "monado01"), w)
        n = rd(xs.wii_to_de(xs.WiiToDeRequest(wii=wp, out=os.path.join(d, f + "_back"), sidecar=e.sidecar_path,
                                              current_de=p)).main_output)
        o, eo = b3("wii_to_de", wp, e.sidecar_path, p, os.path.join(d, f + "_back_b3"))
        res.append(case(f"wii_to_de return {f} (+4 flags)", "de", n, o, eo))
        # unchanged return
        try:
            n = rd(xs.wii_to_de(xs.WiiToDeRequest(wii=e.main_output, out=os.path.join(d, f + "_u"),
                                                  sidecar=e.sidecar_path, current_de=p)).main_output)
            en = None
        except Exception as ex:  # noqa: BLE001
            n, en = None, str(ex)[:200]
        o, eo = b3("wii_to_de", e.main_output, e.sidecar_path, p, os.path.join(d, f + "_u_b3"))
        rec = case(f"wii_to_de unchanged return {f}", "de", n, o, eo, en)
        rec["new_equals_source"] = n == rd(p) if n else None
        res.append(rec)
    # 4. 3DS: DE s232 -> 3DS, a5 game save (+ synthetic flags) -> DE
    r1 = s3.convert3(s3.ThreeDSRequest("de_to_3ds", source=H.DE_S232, out=os.path.join(d, "x_a"),
                                       template=H.X3_USER, overflow="sidecar"))
    o, eo = b3("convert3", json.dumps(dict(direction="de_to_3ds", source=H.DE_S232, out=os.path.join(d, "x_a_b3"),
                                           template=H.X3_USER, overflow="sidecar")))
    res.append(case("de_to_3ds s232", "3ds", rd(r1.main_output), o, eo))
    p = H.put(os.path.join(d, "x_in", "monado01"), H.x3_a5_played())
    r2 = s3.convert3(s3.ThreeDSRequest("3ds_to_de", source=p, out=os.path.join(d, "x_b"), record=r1.sidecar_path,
                                       current=H.DE_S232))
    o, eo = b3("convert3", json.dumps(dict(direction="3ds_to_de", source=p, out=os.path.join(d, "x_b_b3"),
                                           record=r1.sidecar_path, current=H.DE_S232)))
    res.append(case("3ds_to_de s232 via a5", "de", rd(r2.main_output), o, eo))
    # 5. Wii -> DE -> (DE play) -> Wii return
    r = xs.wii_to_de(xs.WiiToDeRequest(wii=H.W150, out=os.path.join(d, "u_w2d"), template=H.DE_TPL))
    dp = F.put_de(d, "u_play", H.play_de(rd(r.main_output), flags=5))
    n = rd(xs.de_to_wii_convert(xs.DeToWiiRequest(de=dp, out=os.path.join(d, "u_d2w"), sidecar=r.sidecar_path,
                                                  current_wii=H.W150)).main_output)
    o, eo = b3("de_to_wii", dp, "-", r.sidecar_path, H.W150, os.path.join(d, "u_d2w_b3"))
    res.append(case("de_to_wii return W150 (+5 DE flags)", "wii", n, o, eo))
    # 6. E1: the save the Wii game wrote after the 154 -> 156 event (EXP earned at the highest level) back to DE
    FX = os.path.join(P3C, "fixtures")
    w156 = os.path.join(FX, "wii_s156_dolphin_d1_game_save")
    sc = os.path.join(FX, "wii_s154_export_3c.de_to_wii.sidecar.json")
    de154 = os.path.join(FX, "de_s154_monado_autosave.sav")
    n = rd(xs.wii_to_de(xs.WiiToDeRequest(wii=w156, out=os.path.join(d, "e1_back"), sidecar=sc,
                                          current_de=de154)).main_output)
    o, eo = b3("wii_to_de", w156, sc, de154, os.path.join(d, "e1_back_b3"))
    rec = case("wii_to_de return of the Wii-played 156 save (E1)", "de", n, o, eo)
    if o is not None:
        CH = 0x152728
        rec["character_bytes_differing"] = sorted({hex((i - CH) % 0x138) for i in range(CH, CH + 0x138 * 16)
                                                  if n[i] != o[i]})
    res.append(rec)
    os.makedirs(os.path.join(P3C, "work"), exist_ok=True)
    json.dump(res, open(os.path.join(P3C, "work", "e_parity_3b.json"), "w"), indent=1)
    for x in res:
        print(json.dumps(x))


if __name__ == "__main__":
    main()
