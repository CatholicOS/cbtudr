"""Seed the units and the Nova Vulgata's own mapping from a verse-structure export (no text).

Usage: python3 scripts/seed_nova_vulgata.py STRUCTURE.csv

STRUCTURE.csv has one row per verse of the Nova Vulgata, in reading order, with the columns book (1-73),
chapter, verse, verse_segment (the Nova Vulgata's own verse letters) and text_tradition. It is the verse
structure of BibleGet's NVBSE edition, checked against vatican.va (docs/schema-proposal.md, §1).

Each verse becomes a unit, `btu:<book>.<chapter>.<verse><letters>`, and maps to itself with status `rule`.
Esther, which the source stores as a Greek run (the whole book, with the lettered additions) and a Hebrew run
(the same text without them), is seeded from the Greek run; the Hebrew run maps to the same units.

Where the source differs from the Nova Vulgata on vatican.va, scripts/nova_vulgata_corrections.json says how,
and the Nova Vulgata governs:
- `omitted`: verse numbers the Nova Vulgata prints in brackets, without text (Mt 17:21). Each becomes a unit
  marked `nv_omitted`, which the Nova Vulgata's own mapping lists as absent; other editions map their text to it.
- `missing`: Nova Vulgata verses the source lacks. Each becomes a unit in its place.
- `order`: a chapter's verses in the Nova Vulgata's printed order, where the source orders them differently.

This overwrites data/units/ and data/maps/nvbse/. It is meant to run once, to create the registry.
"""

import csv
import json
import re
import sys
from pathlib import Path


def _number(label):
    return int(re.match(r"\d+", label)[0])


def _apply(rows, fixes, primary):
    """The primary run's rows with the corrections applied, in the Nova Vulgata's order."""
    rows = [dict(r) for r in rows if r["text_tradition"] == primary]
    added = [(f, True) for f in fixes.get("omitted", [])] + [(f, False) for f in fixes.get("missing", [])]
    for f, omitted in sorted(added, key=lambda x: (x[0]["chapter"], _number(x[0]["verse"]))):
        new = {"chapter": str(f["chapter"]), "verse": f["verse"], "verse_segment": "", "text_tradition": primary, "_omitted": omitted}
        at = 0
        for i, r in enumerate(rows):
            if int(r["chapter"]) < f["chapter"] or (int(r["chapter"]) == f["chapter"] and int(r["verse"]) < _number(f["verse"])):
                at = i + 1
        rows.insert(at, new)
    for f in fixes.get("order", []):
        idx = [i for i, r in enumerate(rows) if int(r["chapter"]) == f["chapter"] and f"{r['verse']}{r['verse_segment']}" in f["verses"]]
        picked = {f"{rows[i]['verse']}{rows[i]['verse_segment']}": rows[i] for i in idx}
        for i, label in zip(idx, f["verses"]):
            rows[i] = picked[label]
    return rows


def seed_book(segment, rows, fixes=None):
    """The unit file and the Nova Vulgata mapping of one book, from its rows in reading order."""
    traditions = {r["text_tradition"] for r in rows}
    primary = "GREEK" if "GREEK" in traditions else ""
    others = [r for r in rows if r["text_tradition"] != primary]
    rows = _apply(rows, fixes or {}, primary) + others

    def label(r):
        return f"{r['verse']}{r['verse_segment']}"

    def uid(r):
        return f"btu:{segment}.{r['chapter']}.{label(r)}"

    units, verses, absent = [], [], []
    for r in rows:
        if r["text_tradition"] != primary:
            continue
        suffix = f"@{primary}" if primary else ""
        ref = f"{r['chapter']}:{label(r)}{suffix}"
        if r.get("_omitted"):
            units.append({"id": uid(r), "nv_omitted": True})
            verses.append({"ref": ref, "units": [], "omitted": True})
            absent.append(uid(r))
            continue
        units.append({"id": uid(r)})
        verses.append({"ref": ref, "units": [uid(r)], "kind": "same", "status": "rule"})
    known = {u["id"] for u in units}
    for r in rows:
        if r["text_tradition"] == primary:
            continue
        if uid(r) not in known:
            raise ValueError(f"{segment} {r['chapter']}:{label(r)} {r['text_tradition']}: no verse of the {primary} run")
        verses.append({"ref": f"{r['chapter']}:{label(r)}@{r['text_tradition']}", "units": [uid(r)], "kind": "same", "status": "rule"})
    mp = {"edition": "nvbse", "book": segment, "verses": verses}
    if primary:
        mp["primary"] = primary
    if absent:
        mp["absent"] = absent
    return {"book": segment, "units": units}, mp


def dump(data, key):
    """JSON with one record per line, so that a change to one unit or verse is a one-line diff."""
    head = {k: v for k, v in data.items() if k != key}
    lines = ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in data[key])
    opening = json.dumps(head, ensure_ascii=False)[:-1]
    return f"{opening}, \"{key}\": [\n{lines}\n]}}\n"


def main(structure):
    root = Path(__file__).resolve().parent.parent
    books = json.loads((root / "data/books.json").read_text())["books"]
    by_number = {b["number"]: b for b in books}
    corrections = json.loads((root / "scripts/nova_vulgata_corrections.json").read_text())["books"]
    rows = {}
    with open(structure, newline="") as f:
        for r in csv.DictReader(f):
            rows.setdefault(int(r["book"]), []).append(r)
    for number, b in by_number.items():
        units, mp = seed_book(b["segment"], rows.get(number, []), corrections.get(b["segment"]))
        name = f"{number:02d}-{b['segment']}.json"
        (root / "data/units" / name).write_text(dump(units, "units"))
        (root / "data/maps/nvbse" / name).write_text(dump(mp, "verses"))
        print(f"{name}: {len(units['units'])} units, {len(mp['verses'])} verses")


if __name__ == "__main__":
    main(sys.argv[1])
