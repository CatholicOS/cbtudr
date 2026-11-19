"""Validate the CBTUDR data: the identifier grammar, the unit trees and the edition mappings.

Run from the repository root: python3 scripts/validate.py
It prints every problem found and exits 1 if there is any. The rules are those of docs/schema-proposal.md.
"""

import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(
    r"^btu:(?P<book>[a-z0-9]+)\.(?P<chapter>[1-9]\d*)\.(?P<verse>(?:0|[1-9]\d*)[a-z]*)"
    r"(?P<parts>(?:\.[1-9]\d*)*)(?:\+(?P<extra>[1-9]\d*)(?P<xparts>(?:\.[1-9]\d*)*))?$"
)
REF_RE = re.compile(r"^[1-9]\d*:(?:0|[1-9]\d*)[a-z]*(?:@[A-Z]+)?$")
KINDS = {"same", "corresponding"}
STATUSES = {"rule", "draft", "reviewed"}


def check_id(uid):
    """Problems with one identifier's form (an empty list when it is well formed)."""
    return [] if isinstance(uid, str) and ID_RE.match(uid) else [f"{uid!r}: not a btu: identifier"]


def _split_parent(uid):
    """The identifier a split part must name as its parent ("btu:tb.5.4.2" -> "btu:tb.5.4"), or None."""
    m = ID_RE.match(uid)
    if not m:
        return None
    if m["extra"]:
        return uid.rsplit(".", 1)[0] if m["xparts"] else None
    return uid.rsplit(".", 1)[0] if m["parts"] else None


def _added_base(uid):
    """The unit an added unit must follow ("btu:tb.5.4+1" -> "btu:tb.5.4"), or None."""
    m = ID_RE.match(uid)
    return uid.split("+", 1)[0] if m and m["extra"] and not m["xparts"] else None


def check_units(data, book):
    """Problems with one book's unit file."""
    errs = []
    seen = set()
    children = {}
    for u in data.get("units", []):
        uid = u.get("id")
        errs += check_id(uid)
        m = ID_RE.match(uid) if isinstance(uid, str) else None
        if not m:
            continue
        if uid in seen:
            errs.append(f"{uid}: duplicate")
        if m["book"] != book:
            errs.append(f"{uid}: not of book {book}")
        want_parent = _split_parent(uid)
        if want_parent:
            if u.get("parent") != want_parent or want_parent not in seen:
                errs.append(f"{uid}: parent must be {want_parent}, declared before it")
            children.setdefault(want_parent, []).append(uid)
        elif "parent" in u:
            errs.append(f"{uid}: only a split part has a parent")
        base = _added_base(uid)
        if base:
            if u.get("after") != base or base not in seen:
                errs.append(f"{uid}: after must be {base}, declared before it")
        elif "after" in u:
            errs.append(f"{uid}: only an added unit has 'after'")
        seen.add(uid)
    for parent, kids in children.items():
        if len(kids) == 1:
            errs.append(f"{parent}: split into only one child")
    return errs


def _tree(data):
    """Unit ids in order and each unit's children."""
    order = [u["id"] for u in data.get("units", [])]
    kids = {}
    for u in data.get("units", []):
        if "parent" in u:
            kids.setdefault(u["parent"], []).append(u["id"])
    return order, kids


def _leaves(uid, kids):
    if uid not in kids:
        return [uid]
    return [leaf for k in kids[uid] for leaf in _leaves(k, kids)]


def _run(ref):
    return ref.split("@", 1)[1] if "@" in ref else ""


def check_map(data, units, book):
    """Problems with one edition's mapping of one book (coverage is checked separately)."""
    errs = []
    order, kids = _tree(units)
    known = set(order)
    if data.get("book") != book:
        errs.append(f"map: book is {data.get('book')!r}, not {book}")
    refs = set()
    covered = {}
    for v in data.get("verses", []):
        ref = v.get("ref")
        good_ref = isinstance(ref, str) and bool(REF_RE.match(ref))
        if not good_ref:
            errs.append(f"{ref!r}: not a verse ref (chapter:verse[segment][@TRADITION])")
        elif ref in refs:
            errs.append(f"{ref}: repeated")
        refs.add(ref)
        ids = v.get("units", [])
        if v.get("omitted"):
            if ids:
                errs.append(f"{ref}: an omitted verse has no units")
            continue
        if not ids:
            errs.append(f"{ref}: no units (mark it omitted if the edition prints no text)")
        if v.get("kind") not in KINDS:
            errs.append(f"{ref}: kind must be one of {sorted(KINDS)}")
        if v.get("status") not in STATUSES:
            errs.append(f"{ref}: status must be one of {sorted(STATUSES)}")
        run = covered.setdefault(_run(ref) if good_ref else "?", {})
        for uid in ids:
            if uid not in known:
                errs.append(f"{ref}: unknown unit {uid}")
                continue
            for leaf in _leaves(uid, kids):
                if leaf in run:
                    errs.append(f"{ref}: {leaf} covered more than once (also by {run[leaf]})")
                run[leaf] = ref
    return errs


def coverage_gaps(data, units):
    """The leaf units the edition's primary run neither covers nor lists as absent, in unit order."""
    order, kids = _tree(units)
    primary = data.get("primary", "")
    done = set()
    for v in data.get("verses", []):
        if _run(v.get("ref", "")) == primary:
            for uid in v.get("units", []):
                done.update(_leaves(uid, kids))
    for uid in data.get("absent", []):
        done.update(_leaves(uid, kids))
    return [u for u in order if u not in kids and u not in done]


def validate(root):
    errs = []
    books = json.loads((root / "data/books.json").read_text())["books"]
    numbers = [b["number"] for b in books]
    if numbers != list(range(1, 74)):
        errs.append("books.json: books must be numbered 1-73 in order")
    segments = [b["segment"] for b in books]
    if len(set(segments)) != len(segments):
        errs.append("books.json: repeated segment")
    trees = {}
    for b in books:
        path = root / f"data/units/{b['number']:02d}-{b['segment']}.json"
        if not path.exists():
            errs.append(f"{path.relative_to(root)}: missing")
            continue
        trees[b["segment"]] = json.loads(path.read_text())
        errs += [f"{path.name}: {e}" for e in check_units(trees[b["segment"]], b["segment"])]
    editions = json.loads((root / "data/editions.json").read_text())["editions"]
    for ed in editions:
        for path in sorted((root / f"data/maps/{ed['slug']}").glob("*.json")):
            data = json.loads(path.read_text())
            seg = data.get("book")
            if seg not in trees:
                errs.append(f"{ed['slug']}/{path.name}: unknown book {seg!r}")
                continue
            errs += [f"{ed['slug']}/{path.name}: {e}" for e in check_map(data, trees[seg], seg)]
            gaps = coverage_gaps(data, trees[seg])
            if gaps:
                more = f" and {len(gaps) - 5} more" if len(gaps) > 5 else ""
                errs.append(f"{ed['slug']}/{path.name}: units neither covered nor absent: {', '.join(gaps[:5])}{more}")
    return errs


if __name__ == "__main__":
    problems = validate(Path(__file__).resolve().parent.parent)
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
