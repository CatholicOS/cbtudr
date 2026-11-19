"""Bring reviewed links from the review store back into an edition's map files.

Usage: BTU_REVIEW_TOKEN=... python3 scripts/import_reviewed.py --edition SLUG --api https://query.bibleget.io/dev

The token (a reviewer's Zitadel access token) is read from the environment, never from an argument. For each
book, the reviewed links replace the drafts of the same verses in data/maps/<slug>/, their confidences leave
drafts/<slug>/, and `absent` is recomputed. Links made by rule are never changed. The script prints what it did:
- splits that reviewers flagged (drafts with a note), which are not applied: a split adds units, by hand;
- verses reviewed as having no counterpart in the units, which may need units of their own (`+n`).
Then it runs the validator.
"""

import argparse
import copy
import json
import os
import sys
import urllib.request
from pathlib import Path

from seed_nova_vulgata import dump
from validate import _leaves, _run, _tree, validate


def apply_review(map_data, drafts, units, links):
    """The map and drafts file of one book with the review applied, and a report.

    `links` are the review store's links of the book (any status). Returns (map, drafts or None, report)."""
    m = copy.deepcopy(map_data)
    d = copy.deepcopy(drafts) if drafts else None
    report = {"applied": 0, "splits": [], "no_counterpart": []}
    by_ref = {v["ref"]: v for v in m["verses"]}
    for lk in links:
        v = by_ref.get(lk["ref"])
        if v is None or v.get("status") == "rule":
            continue
        if lk["status"] == "reviewed":
            v.clear()
            v.update({"ref": lk["ref"], "units": list(lk["units"]), "kind": lk["kind"], "status": "reviewed"})
            report["applied"] += 1
            if not lk["units"]:
                report["no_counterpart"].append(lk["ref"])
            if d:
                d["confidence"].pop(lk["ref"], None)
        elif lk.get("note"):
            report["splits"].append({"ref": lk["ref"], "note": lk["note"]})
    order, kids = _tree(units)
    primary = m.get("primary", "")
    covered = set()
    for v in m["verses"]:
        if _run(v["ref"]) == primary:
            for u in v.get("units", []):
                covered.update(_leaves(u, kids))
    absent = [u for u in order if u not in kids and u not in covered]
    if absent:
        m["absent"] = absent
    else:
        m.pop("absent", None)
    if d is not None and not d["confidence"]:
        d = None
    return m, d, report


def _get(api, path, token):
    req = urllib.request.Request(api.rstrip("/") + path, headers={"Accept": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--edition", required=True)
    ap.add_argument("--api", required=True)
    a = ap.parse_args()
    token = os.environ.get("BTU_REVIEW_TOKEN")
    if not token:
        sys.exit("Set BTU_REVIEW_TOKEN to a reviewer's access token.")
    root = Path(__file__).resolve().parent.parent
    sigla = a.edition.upper()
    books = {b["number"]: b for b in json.loads((root / "data/books.json").read_text())["books"]}
    chapters = {}
    for status in ("reviewed", "draft"):
        for c in _get(a.api, f"/review/editions/{sigla}/chapters?status={status}", token)["chapters"]:
            chapters.setdefault(c["book"], set()).add(c["chapter"])
    total = {"applied": 0, "splits": [], "no_counterpart": []}
    for number, chs in sorted(chapters.items()):
        b = books[number]
        name = f"{number:02d}-{b['segment']}.json"
        mpath, dpath = root / f"data/maps/{a.edition}/{name}", root / f"drafts/{a.edition}/{name}"
        links = [lk for c in sorted(chs) for lk in _get(a.api, f"/review/editions/{sigla}/books/{number}/chapters/{c}", token)["links"]]
        units = json.loads((root / f"data/units/{name}").read_text())
        m, d, report = apply_review(json.loads(mpath.read_text()), json.loads(dpath.read_text()) if dpath.exists() else None, units, links)
        mpath.write_text(dump(m, "verses"))
        if d is None:
            dpath.unlink(missing_ok=True)
        else:
            dpath.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        total["applied"] += report["applied"]
        total["splits"] += [{"book": b["segment"], **s} for s in report["splits"]]
        total["no_counterpart"] += [f"{b['segment']} {r}" for r in report["no_counterpart"]]
    print(f"{total['applied']} reviewed links applied")
    for s in total["splits"]:
        print(f"split flagged: {s['book']} {s['ref']}: {s['note']}")
    for r in total["no_counterpart"]:
        print(f"no counterpart: {r}")
    problems = validate(root)
    for p in problems:
        print(p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
