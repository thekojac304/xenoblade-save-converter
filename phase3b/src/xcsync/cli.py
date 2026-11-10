"""xcsync - Sync Hub command line (Phase 3B). The same functions as the Sync Hub view.

  xcsync init HUB
  xcsync device-add HUB --name NAME --platform wii|de|3ds [--incoming DIR] [--slot S]
  xcsync devices HUB
  xcsync template HUB wii|de|3ds FILE
  xcsync scan HUB [--json OUT]                     read-only
  xcsync sync HUB [--choose TEXT] [--allow-partial] [--json OUT]
  xcsync publish HUB                               finish an interrupted publication
  xcsync history HUB
  xcsync rollback HUB N

Exit codes: 0 done / in sync, 1 refused or blocked (nothing changed), 2 a choice is needed, 3 waiting for files.
"""
import argparse
import json
import os
import sys

from . import paths3b  # noqa: F401
from . import APP_VERSION
from .store import Hub, HubError, SHORT
from . import scan as scanmod, sync as syncmod

import xcservice as xs


def _scan_json(r):
    return {"generation": r.generation, "decision": vars(r.decision), "issues": r.issues, "error": r.error,
            "devices": [{"name": d.device["name"], "id": d.device["id"], "platform": d.device["platform"],
                         "status": d.status, "text": d.text, "ready": d.ready_state,
                         "saves": [o.public() for o in d.saves]} for d in r.devices]}


def _print_scan(r):
    print(r.decision.message)
    if r.decision.detail:
        print("  " + r.decision.detail)
    for d in r.devices:
        print(f"- {d.device['name']} ({SHORT[d.device['platform']]}): {d.text}"
              + (f"  [ready folder: {d.ready_state}]" if d.ready_state not in (None, "not-needed") else ""))
        for o in d.saves:
            s = o.summary or {}
            what = o.status if o.state == "ok" else o.state
            print(f"    {o.name}: {what}  {s.get('location', '')} story {s.get('story', '')} {s.get('play_time', '')}"
                  f"  {o.detail or o.note}")
    for i in r.issues:
        print("note: " + i["text"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="xcsync", description=f"Xenoblade Sync Hub {APP_VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("hub")
    p = sub.add_parser("device-add")
    p.add_argument("hub")
    p.add_argument("--name", required=True)
    p.add_argument("--platform", required=True, choices=["wii", "de", "3ds"])
    p.add_argument("--incoming")
    p.add_argument("--slot")
    p = sub.add_parser("devices")
    p.add_argument("hub")
    p = sub.add_parser("template")
    p.add_argument("hub")
    p.add_argument("platform", choices=["wii", "de", "3ds"])
    p.add_argument("file")
    for c in ("scan", "sync"):
        p = sub.add_parser(c)
        p.add_argument("hub")
        p.add_argument("--json")
        if c == "sync":
            p.add_argument("--choose", help="part of the path or device name of the save to continue")
            p.add_argument("--allow-partial", action="store_true")
    p = sub.add_parser("publish")
    p.add_argument("hub")
    p = sub.add_parser("history")
    p.add_argument("hub")
    p = sub.add_parser("rollback")
    p.add_argument("hub")
    p.add_argument("n", type=int)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "init":
            h = Hub.create(a.hub)
            print(f"Sync Hub ready: {h.root}")
            return 0
        h = Hub.open(a.hub)
        if a.cmd == "device-add":
            d = h.add_device(a.name, a.platform, incoming=a.incoming, slot=a.slot)
            print(json.dumps(d, indent=1))
            return 0
        if a.cmd == "devices":
            for d in h.devices():
                print(f"{d['id']}  {d['name']} ({SHORT[d['platform']]}, slot {d['slot']})\n    incoming: "
                      f"{d['incoming']}\n    ready:    {h.ready_dir(d)}")
            return 0
        if a.cmd == "template":
            info = h.add_template(a.platform, a.file)
            print(f"{SHORT[a.platform]} template stored: {info['summary']}")
            return 0
        if a.cmd in ("scan", "sync"):
            r = scanmod.scan(h)
            if a.cmd == "scan":
                _print_scan(r)
                if a.json:
                    with open(a.json, "w", encoding="utf-8") as f:
                        json.dump(_scan_json(r), f, indent=1)
                return {"waiting": 3, "conflict": 2, "choose-start": 2, "error": 1}.get(r.decision.kind, 0)
            key = None
            if a.choose:
                m = [k for k in r.decision.options if a.choose.lower() in k.lower() or
                     a.choose.lower() in r.find(k).device_name.lower()]
                if len(m) != 1:
                    _print_scan(r)
                    print(f"--choose {a.choose!r} matches {len(m)} of the possible saves", file=sys.stderr)
                    return 2
                key = m[0]
            res = syncmod.sync(h, r, key, allow_partial=a.allow_partial,
                               progress=lambda s: print(f"  {dict(syncmod.STAGES).get(s, s)}..."))
            print(res.message)
            for k, v in res.published.items():
                print(f"  {h.device(k)['name']}: {v}")
            for n in res.notes:
                print("  note: " + n)
            if a.json:
                with open(a.json, "w", encoding="utf-8") as f:
                    json.dump(vars(res), f, indent=1, default=str)
            return 0
        if a.cmd == "publish":
            out = syncmod.publish(h)
            for k, v in out.items():
                print(f"{h.device(k)['name']}: {v}")
            return 0 if all(not v.startswith("failed") for v in out.values()) else 1
        if a.cmd == "history":
            cur = h.pointer()["current"] if h.pointer() else None
            for g in h.generations():
                if g.get("damaged"):
                    print(f"{g['number']}: DAMAGED - {g['damaged']}")
                    continue
                s = g["source"]
                print(f"{g['number']}{' *' if g['number'] == cur else ''}  {g['created']}  {g['kind']:8} from "
                      f"{s['device_name']} ({SHORT[s['platform']]})  story {s['summary']['story']} "
                      f"{s['summary']['play_time']}  -> {', '.join(SHORT[p] for p in sorted(g['outputs']))}"
                      + ("  PARTIAL" if g.get("partial") else ""))
            return 0
        if a.cmd == "rollback":
            r = syncmod.rollback(h, a.n)
            print(r.message)
            return 0
    except syncmod.Blocked as e:
        print(f"blocked: {e}", file=sys.stderr)
        return 1
    except xs.REFUSALS as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
