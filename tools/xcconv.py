"""xcconv - Xenoblade Chronicles save converter, Wii (SX4E monadoNN) <-> Definitive Edition (v10, Monado), 2G-rc1.

Commands (all paths explicit; nothing is ever written next to a game or into a live save folder):
  inspect <save>                       summary of a Wii or DE save (story, map, party, levels, items)
  validate <save>                      structural checks (size, version, CRCs, references); exit 1 if not valid
  wii-to-de --wii W --out DIR --template DE [--slot 00]
                                       first export of a Wii playthrough to DE (DE save used as a structure template)
  wii-to-de --wii W --out DIR --sidecar S (--current-de DE | --no-current-de) [--branch wii] [--slot 00]
                                       bring Wii progress back onto the DE save a DE->Wii export started from
  de-to-wii --de D --out DIR --base WII [--same-playthrough] [--slot monado01] [--overflow refuse|sidecar]
                                       DE -> Wii using a Wii save as the structure base
  de-to-wii --de D --out DIR --sidecar S (--current-wii W | --no-current-wii) [--branch de] [--slot monado01]
                                       DE progress back onto the Wii save a Wii->DE export started from
  roundtrip-check (--wii W --template DE | --de D --base WII)   static round trip, field-level report
  compatibility-check --de D [--base WII]   can this DE save become a Wii save? why not?
  sidecar-info <sidecar.json>
  cleanup-staging <folder>             remove ".xcconv-staging-*" folders left by an interrupted run
Common: --dry-run (convert and verify, write nothing), --report FILE (full JSON report, not with --dry-run),
        --json (print the full report), --debug (print a traceback on internal errors).
Outputs: a NEW folder DIR (it must not exist, or be empty) that appears complete or not at all:
         DE  -> DIR/save_0/bfsgameNN.sav (+ .tmb and bfssystem.sav copied from the template folder when present)
         Wii -> DIR/<slot> (+ banner.bin copied from the base folder when present)
         always DIR/<direction>.sidecar.json and DIR/manifest.json (SHA-256 of every input and output)
Exit codes: 0 done, 1 check failed (validate / roundtrip-check / compatibility-check), 2 refused (nothing written),
            3 internal error (nothing written).

Phase 2G: this file is the command-line front end only. Reading, conversion, checks, sidecar lineage, verification
and the transactional writer are in xcservice.py (shared with the desktop GUI).
"""
import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import safeio  # noqa: E402
import sidecar as scmod  # noqa: E402
import xcservice as svc  # noqa: E402

# 2F-rc1 names kept for callers and tests
Refused = safeio.Refused
guard_out = safeio.guard_out
LIVE_MARKERS = safeio.LIVE_MARKERS
WII_SIZE = svc.WII_SIZE
NICE = svc.NICE
TOLERATED = svc.TOLERATED
tables, sha, kind_of, load_wii, load_de = svc.tables, svc.sha, svc.kind_of, svc.load_wii, svc.load_de
load_sidecar, de_slot_name, wii_slot_name = svc.load_sidecar, svc.de_slot_name, svc.wii_slot_name
summary, validate_bytes, readback_diffs, manifest = svc.summary, svc.validate_bytes, svc.readback_diffs, svc.manifest


def atomic_write(path, data, dry):
    """Single new file (kept for the 2E API); refuses existing files and live locations."""
    guard_out(path)
    if os.path.lexists(path):
        raise Refused(f"refusing to overwrite existing file: {path}")
    if not dry:
        safeio.write_new(path, data)


def cmd_inspect(a):
    b = safeio.read_input(a.save, "save")
    if kind_of(b) == "wii":
        b = load_wii(a.save, "save")
    elif kind_of(b) == "de":
        b = load_de(a.save, "save")
    print(json.dumps(summary(b), indent=1))


def cmd_validate(a):
    res = svc.validate_file(a.save)
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


def cmd_wii_to_de(a):
    r = svc.wii_to_de(svc.WiiToDeRequest(wii=a.wii, out=a.out, template=a.template, sidecar=a.sidecar,
                                         current_de=a.current_de, no_current_de=a.no_current_de, branch=a.branch,
                                         slot=a.slot, dry_run=a.dry_run))
    finish(a, r.report, f"DE save {r.main_output}", "wii_to_de.sidecar.json")


def cmd_de_to_wii(a):
    r = svc.de_to_wii_convert(svc.DeToWiiRequest(de=a.de, out=a.out, base=a.base, sidecar=a.sidecar,
                                                 current_wii=a.current_wii, no_current_wii=a.no_current_wii,
                                                 branch=a.branch, slot=a.slot, overflow=a.overflow,
                                                 same_playthrough=a.same_playthrough, dry_run=a.dry_run))
    finish(a, r.report, f"Wii save {r.main_output}", "de_to_wii.sidecar.json")


def cmd_roundtrip(a):
    rep = svc.roundtrip(wii=a.wii, template=a.template, de=a.de, base=a.base)
    a.dry_run = True
    finish(a, rep, None, None)
    return 0 if rep["byte_identical"] else 1


def cmd_compat(a):
    rep = svc.compatibility(a.de, a.base)
    a.dry_run = True
    finish(a, rep, None, None)
    return 0 if rep["compatible"] else 1


def cmd_sidecar_info(a):
    print(json.dumps(svc.sidecar_info(a.sidecar), indent=1, default=str))


def cmd_cleanup(a):
    found = safeio.leftovers(a.folder)
    if a.dry_run:
        print(json.dumps({"would_remove": found}, indent=1))
        return 0
    print(json.dumps({"removed": safeio.cleanup(a.folder)}, indent=1))
    return 0


def finish(a, rep, main_out, sc_name):
    txt = json.dumps(rep, indent=1, default=str)
    if main_out:
        print(f"xcconv {scmod.CONVERTER_VERSION}: {NICE[rep['direction']]} "
              f"{'checked (dry run, nothing written)' if a.dry_run else 'done'}")
        si, so = rep["summary_in"], rep["summary_out"]
        print(f"  from : {si['format']} story {si['story']} {si['map']} play time {si['play_time']} party {si['party']}")
        print(f"  to   : {so['format']} story {so['story']} {so['map']} play time {so['play_time']} party {so['party']}")
        if not a.dry_run:
            print(f"  wrote: {main_out}")
            print(f"         {os.path.join(a.out, sc_name)}  <- keep this sidecar with your saves")
        dfr = {k: v for k, v in rep.get("deferred_to_sidecar", {}).items() if v}
        if dfr:
            print(f"  kept in the sidecar (not in the Wii file): {dfr}")
        if rep.get("deferred_restored"):
            print(f"  restored from the sidecar: {len(rep['deferred_restored'])} deferred item(s)")
        for w in rep.get("log", {}).get("warnings", []):
            print(f"  WARNING: {w}")
    if a.report:
        if a.dry_run and main_out:
            print("  (--report not written: --dry-run writes nothing)")
        else:
            safeio.write_new(a.report, txt.encode())
    if a.json or not main_out:
        print(txt)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="xcconv", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect"); p.add_argument("save"); p.set_defaults(f=cmd_inspect)
    p = sub.add_parser("validate"); p.add_argument("save"); p.set_defaults(f=cmd_validate)
    p = sub.add_parser("wii-to-de")
    p.add_argument("--wii", required=True); p.add_argument("--out", required=True); p.add_argument("--template")
    p.add_argument("--sidecar"); p.add_argument("--current-de"); p.add_argument("--no-current-de", action="store_true")
    p.add_argument("--branch", choices=["wii"]); p.add_argument("--slot", default="00"); p.set_defaults(f=cmd_wii_to_de)
    p = sub.add_parser("de-to-wii")
    p.add_argument("--de", required=True); p.add_argument("--out", required=True); p.add_argument("--base")
    p.add_argument("--sidecar"); p.add_argument("--current-wii"); p.add_argument("--no-current-wii", action="store_true")
    p.add_argument("--branch", choices=["de"])
    p.add_argument("--slot", default="monado01"); p.add_argument("--overflow", choices=["refuse", "sidecar"], default="refuse")
    p.add_argument("--same-playthrough", action="store_true",
                   help="the --base Wii save is this playthrough's own earlier Wii save (keep its exact bytes where unchanged)")
    p.set_defaults(f=cmd_de_to_wii)
    p = sub.add_parser("roundtrip-check")
    p.add_argument("--wii"); p.add_argument("--template"); p.add_argument("--de"); p.add_argument("--base")
    p.set_defaults(f=cmd_roundtrip)
    p = sub.add_parser("compatibility-check"); p.add_argument("--de", required=True); p.add_argument("--base")
    p.set_defaults(f=cmd_compat)
    p = sub.add_parser("sidecar-info"); p.add_argument("sidecar"); p.set_defaults(f=cmd_sidecar_info)
    p = sub.add_parser("cleanup-staging"); p.add_argument("folder"); p.set_defaults(f=cmd_cleanup)
    for sp in sub.choices.values():
        sp.add_argument("--dry-run", action="store_true")
        sp.add_argument("--report")
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--debug", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "roundtrip-check" and not ((a.wii and a.template) or (a.de and a.base)):
        ap.error("roundtrip-check needs --wii and --template, or --de and --base")
    try:
        return a.f(a) or 0
    except svc.REFUSALS as e:
        print(f"xcconv: refused ({type(e).__name__}): {e}\nxcconv: nothing was written.", file=sys.stderr)
        return 2
    except Exception as e:   # never a raw traceback for the user; nothing is committed before the final step
        print(f"xcconv: internal error ({type(e).__name__}: {e}).\nxcconv: nothing was written. Re-run with --debug "
              "and keep the message if you report it.", file=sys.stderr)
        if a.debug:
            traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
