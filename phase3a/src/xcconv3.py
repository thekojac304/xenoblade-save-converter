"""xcconv 3A - Xenoblade Chronicles save converter: Wii, Definitive Edition and New 3DS (Xenoblade Chronicles 3D).

Wii <-> DE (unchanged 2H commands and options; xcconv <command> --help):
  wii-to-de, de-to-wii, roundtrip-check, compatibility-check, sidecar-info, cleanup-staging
New in 3A:
  inspect <save> / validate <save>     Wii, DE or 3DS save (3DS: monado01/02/03 from the save archive)
  wii-to-3ds --wii W --template X3 --out DIR [--slot 1|2|3] [--record R (--current-3ds X | --no-current-3ds)]
  3ds-to-wii --3ds X --out DIR [--slot monado01] [--record R (--current-wii W | --no-current-wii)]
  de-to-3ds  --de D --template X3 --out DIR [--slot 1|2|3] [--record R (--current-3ds X | --no-current-3ds)]
  3ds-to-de  --3ds X --out DIR (--template DE | --record R (--current-de D | --no-current-de)) [--slot 00]
  --keep-this-progress                 on a divergence (both games played), keep this save's progress and drop the
                                       destination game's later progress (2H --branch)
  record-info <file.record.json>       ancestry of a conversion record (also reads 2H sidecars)
  unpack-3ds <3ds save> <out.bin>      decompressed payload (diagnostics)
Outputs: one NEW folder DIR:  3DS -> DIR/3ds/monado0N (+ DIR/checkpoint/xcconv_<id>/ = the complete save archive
         with that slot replaced, when the template sits in a complete archive folder), Wii -> DIR/monado0N,
         DE -> DIR/save_0/bfsgameNN.sav; always DIR/<direction>.record.json and DIR/manifest.json.
Exit codes as in 2H: 0 done, 1 check failed, 2 refused (nothing written), 3 internal error (nothing written).
"""
import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "..", "tools"), os.path.join(HERE, "engine")):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, os.path.abspath(p))
import safeio  # noqa: E402
import xc3d  # noqa: E402
import xc3dservice as s3  # noqa: E402
import xcconv as x2  # noqa: E402
import xcservice as svc  # noqa: E402

OLD = ("wii-to-de", "de-to-wii", "roundtrip-check", "compatibility-check", "sidecar-info", "cleanup-staging")


def cmd_inspect(a):
    b = safeio.read_input(a.save, "save")
    if xc3d.is_3ds_file(b):
        fb, raw, wii = s3.load_3ds(a.save, "save")
        out = s3.summary3(wii)
        out["sha256"] = svc.sha(fb)
        out["unverified_fields_with_data"] = s3.unverified_nonzero(raw)
        print(json.dumps(out, indent=1))
        return 0
    return x2.cmd_inspect(a)


def cmd_validate(a):
    b = safeio.read_input(a.save, "save")
    if xc3d.is_3ds_file(b):
        res = {"kind": "3ds", "sha256": svc.sha(b), "problems": []}
        try:
            fb, raw, wii = s3.load_3ds(a.save, "save")
            res.update(svc.validate_bytes(wii))
            res["kind"] = "3ds"
            res["container_3ds"] = xc3d.check_container(raw)
        except s3.REFUSALS as e:
            res["problems"] = [str(e)]
            res["ok"] = False
        res.setdefault("ok", not res["problems"])
        res["file"] = a.save
        print(json.dumps(res, indent=1, default=str))
        return 0 if res["ok"] else 1
    return x2.cmd_validate(a)


def cmd_convert(a):
    d = a.cmd.replace("-", "_")
    src = getattr(a, "wii", None) or getattr(a, "de", None) or getattr(a, "x3ds", None)
    cur = getattr(a, "current_3ds", None) or getattr(a, "current_wii", None) or getattr(a, "current_de", None)
    no_cur = bool(getattr(a, "no_current_3ds", False) or getattr(a, "no_current_wii", False)
                  or getattr(a, "no_current_de", False))
    r = s3.convert3(s3.ThreeDSRequest(direction=d, source=src, out=a.out, template=a.template, record=a.record,
                                      current=cur, no_current=no_cur,
                                      branch="keep_source" if a.keep_this_progress else None, slot=a.slot,
                                      overflow=getattr(a, "overflow", "refuse"), dry_run=a.dry_run))
    rep = r.report
    print(f"xcconv {s3.CONVERTER_VERSION}: {s3.NICE3[d]} {'checked (dry run, nothing written)' if a.dry_run else 'done'}")
    si, so = rep.get("summary_in", {}), rep.get("summary_out", {})
    for lab, s in (("from", si), ("to  ", so)):
        if s:
            print(f"  {lab} : {s.get('format')} story {s.get('story')} {s.get('map')} play time {s.get('play_time')} "
                  f"party {s.get('party')}")
    if not a.dry_run:
        print(f"  wrote: {r.main_output}")
        print(f"         {r.sidecar_path}  <- keep this conversion record with your saves")
        if rep.get("checkpoint_backup"):
            print(f"         {os.path.join(a.out, 'checkpoint')}  <- complete save archive for Checkpoint (untested on hardware)")
    for w in rep.get("warnings", []) + rep.get("log", {}).get("warnings", []):
        print(f"  WARNING: {w}")
    if a.report and not a.dry_run:
        safeio.write_new(a.report, json.dumps(rep, indent=1, default=str).encode())
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    return 0


def cmd_record_info(a):
    kind, d = s3.load_record(a.record)
    if kind == "sidecar":
        print(json.dumps(svc.sidecar_info(a.record), indent=1, default=str))
        return 0
    out = {k: d[k] for k in ("record_schema", "converter_version", "direction", "session_id", "lineage", "source",
                             "output", "notes")}
    out["carries_de_state"] = bool(d.get("de_sidecar"))
    print(json.dumps(out, indent=1))
    return 0


def cmd_unpack(a):
    raw = xc3d.unpack(safeio.read_input(a.save, "3DS save"))
    safeio.write_new(a.out_file, raw)
    print(json.dumps({"payload": a.out_file, "container_problems": xc3d.check_container(raw)}, indent=1))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in OLD:
        return x2.main(argv)
    ap = argparse.ArgumentParser(prog="xcconv", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect"); p.add_argument("save"); p.set_defaults(f=cmd_inspect)
    p = sub.add_parser("validate"); p.add_argument("save"); p.set_defaults(f=cmd_validate)
    for name, src, cur in (("wii-to-3ds", "--wii", "3ds"), ("3ds-to-wii", "--3ds", "wii"), ("de-to-3ds", "--de", "3ds"),
                           ("3ds-to-de", "--3ds", "de")):
        p = sub.add_parser(name)
        p.add_argument(src, required=True, dest={"--wii": "wii", "--de": "de", "--3ds": "x3ds"}[src])
        p.add_argument("--out", required=True); p.add_argument("--template"); p.add_argument("--record")
        p.add_argument(f"--current-{cur}"); p.add_argument(f"--no-current-{cur}", action="store_true")
        p.add_argument("--keep-this-progress", action="store_true"); p.add_argument("--slot")
        if name == "de-to-3ds":
            p.add_argument("--overflow", choices=["refuse", "sidecar"], default="refuse")
        p.set_defaults(f=cmd_convert)
    p = sub.add_parser("record-info"); p.add_argument("record"); p.set_defaults(f=cmd_record_info)
    p = sub.add_parser("unpack-3ds"); p.add_argument("save"); p.add_argument("out_file"); p.set_defaults(f=cmd_unpack)
    for sp in sub.choices.values():
        sp.add_argument("--dry-run", action="store_true"); sp.add_argument("--report")
        sp.add_argument("--json", action="store_true"); sp.add_argument("--debug", action="store_true")
    a = ap.parse_args(argv)
    try:
        return a.f(a) or 0
    except s3.REFUSALS as e:
        print(f"xcconv: refused ({type(e).__name__}): {e}\nxcconv: nothing was written.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"xcconv: internal error ({type(e).__name__}: {e}).\nxcconv: nothing was written. Re-run with --debug "
              "and keep the message if you report it.", file=sys.stderr)
        if a.debug:
            traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
