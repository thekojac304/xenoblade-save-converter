"""Row-by-row Wii vs DE comparison of the ID spaces a save references (read-only).

Reads data/bdat_wii.json and data/bdat_de.json (from dump_bdat.py) and writes tables/idmap_<space>.tsv plus a
summary to stdout. For each ID: English name in both games, the shared numeric columns that differ, and a status:
  same          name and every shared numeric column identical
  same_name     name identical, some numeric columns changed (balance edit; the ID still denotes the same thing)
  renamed       name differs (text revision), numeric columns identical
  changed       name and numbers differ -> treat as a different entity, needs a manual decision
  wii_only / de_only
DE text: name columns hold message IDs into gb:<table>_ms.

  python id_compare.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
COSMETIC = {"icon", "icon_base"}  # menu icon indices; recorded but do not change an entity's identity
TEXT_COLS = {"name", "help", "comment", "rvs_caption", "cylinder_name", "resource", "caption", "title"}


def load():
    w = json.load(open(os.path.join(ROOT, "data", "bdat_wii.json"), encoding="utf-8"))
    d = json.load(open(os.path.join(ROOT, "data", "bdat_de.json"), encoding="utf-8"))
    return w, d


def de_text(d, table, col="name"):
    ms = d.get(f"gb:{table}_ms")
    if not ms:
        return {}
    return {r["id"]: r.get(col, "") for r in ms["rows"]}


def norm(s):
    s = re.sub(r"\[[^\]]*\]", "", str(s))  # DE markup tags
    return re.sub(r"\s+", " ", s).strip().lower()


def flat(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, list):
            for i, x in enumerate(v):
                out[f"{k}{i + 1}"] = x
        else:
            out[k] = v
    return out


def compare(w, d, table, name_of_de=None, text_cols=TEXT_COLS, w_rows=None, d_rows=None):
    wr = {r["id"]: flat(r) for r in (w_rows or w[table]["rows"])}
    dr = {r["id"]: flat(r) for r in (d_rows or d[table]["rows"])}
    names = name_of_de if name_of_de is not None else de_text(d, table)
    res = []
    for i in sorted(set(wr) | set(dr)):
        a, b = wr.get(i), dr.get(i)
        if a is None:
            res.append((i, "", names.get(b.get("name"), ""), "de_only", ""))
            continue
        if b is None:
            res.append((i, a.get("name", ""), "", "wii_only", ""))
            continue
        wn = a.get("name", "")
        dn = names.get(b.get("name"), "") if b.get("name") else ""
        shared = [k for k in a if k in b and k not in text_cols and k != "id"]
        diff = [f"{k}:{a[k]}->{b[k]}" for k in shared if a[k] != b[k] and k not in COSMETIC]
        diff += [f"(cosmetic){k}:{a[k]}->{b[k]}" for k in shared if a[k] != b[k] and k in COSMETIC]
        same_name = norm(wn) == norm(dn)
        real = [x for x in diff if not x.startswith("(cosmetic)")]
        st = ("same" if not real else "same_name") if same_name else ("renamed" if not real else "changed")
        res.append((i, wn, dn, st, ";".join(diff)))
    return res


def item_names(w, d):
    """Global item ID -> (wii name, de name) through itemType/itemID."""
    wt = {2: "ITM_wpnlist", 3: "BTL_skilllist", 4: "ITM_equiplist", 5: "ITM_equiplist", 6: "ITM_equiplist",
          7: "ITM_equiplist", 8: "ITM_equiplist", 9: "ITM_crystallist", 10: "ITM_collectlist",
          11: "ITM_materiallist", 12: "ITM_valuablelist", 13: "ITM_artslist"}
    wname = {}
    for r in w["ITM_itemlist"]["rows"]:
        tab = wt.get(r["itemType"])
        rows = {x["id"]: x for x in w[tab]["rows"]} if tab else {}
        x = rows.get(r["itemID"], {})
        wname[r["id"]] = x.get("name", f"crystal#{r['itemID']}" if r["itemType"] == 9 else "")
    dname = {}
    for r in d["ITM_itemlist"]["rows"]:
        tab = wt.get(r["itemType"])
        rows = {x["id"]: x for x in d[tab]["rows"]} if tab else {}
        x = rows.get(r["itemID"], {})
        txt = de_text(d, tab) if tab else {}
        dname[r["id"]] = txt.get(x.get("name"), "") if x.get("name") else (
            f"crystal#{r['itemID']}" if r["itemType"] == 9 else "")
    return wname, dname


def compare_items(w, d):
    wname, dname = item_names(w, d)
    wr = {r["id"]: r for r in w["ITM_itemlist"]["rows"]}
    dr = {r["id"]: r for r in d["ITM_itemlist"]["rows"]}
    res = []
    for i in sorted(set(wr) | set(dr)):
        a, b = wr.get(i), dr.get(i)
        if a is None:
            res.append((i, "", f"{b['itemType']}/{b['itemID']}", "", dname.get(i, ""), "de_only", ""))
            continue
        if b is None:
            res.append((i, f"{a['itemType']}/{a['itemID']}", "", wname.get(i, ""), "", "wii_only", ""))
            continue
        diff = [f"{k}:{a[k]}->{b[k]}" for k in a if k in b and k not in ("id", "comment") and a[k] != b[k]
                and k not in COSMETIC]
        cos = [f"(cosmetic){k}:{a[k]}->{b[k]}" for k in COSMETIC if k in a and k in b and a[k] != b[k]]
        key_same = (a["itemType"], a["itemID"]) == (b["itemType"], b["itemID"])
        nm_same = norm(wname[i]) == norm(dname[i])
        if not key_same:
            st = "retargeted"
        elif nm_same:
            st = "same" if not diff else "same_name"
        else:
            st = "renamed"
        res.append((i, f"{a['itemType']}/{a['itemID']}", f"{b['itemType']}/{b['itemID']}", wname[i], dname[i], st,
                    ";".join(diff + cos)))
    return res


def write(name, header, rows):
    p = os.path.join(ROOT, "tables", f"idmap_{name}.tsv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(header) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    stat = {}
    for r in rows:
        stat[r[-2]] = stat.get(r[-2], 0) + 1
    print(f"{name:14s} {len(rows):5d} rows  {stat}")


def main():
    w, d = load()
    write("items", ["global_id", "wii_type/row", "de_type/row", "wii_name", "de_name", "status", "diff"],
          compare_items(w, d))
    hdr = ["id", "wii_name", "de_name", "status", "diff"]
    for space, table in [("arts", "pc_arts"), ("skills", "BTL_PSVskill"), ("skilllink", "BTL_PSVlink"),
                         ("weapons", "ITM_wpnlist"), ("armor", "ITM_equiplist"), ("gem_effects", "BTL_skilllist"),
                         ("crystals", "ITM_crystallist"), ("collectables", "ITM_collectlist"),
                         ("materials", "ITM_materiallist"), ("keyitems", "ITM_valuablelist"),
                         ("artmanuals", "ITM_artslist"), ("pclist", "BTL_pclist"), ("growlist", "BTL_growlist")]:
        write(space, hdr, compare(w, d, table))
    # menu-side table for skill-link slot shapes (Wii menu pkb vs DE bdat_menu_psv)
    write("psset", hdr, compare(w, d, "MNU_PSset", name_of_de={}, w_rows=w["menu:MNU_PSset"]["rows"],
                                d_rows=d["MNU_PSset"]["rows"]))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(__doc__)
    main()
