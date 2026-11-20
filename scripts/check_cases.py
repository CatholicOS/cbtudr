"""Check drafted maps against documented chapter-boundary shifts (scripts/documented_shifts.json).

Usage: python3 scripts/check_cases.py [--lower]

Each shift says which Nova Vulgata verses an edition's verses are (the Clementine Vulgate's Gn 31:55 is the
Nova Vulgata's Gn 32:1). A link that does not contain the expected unit is reported; a rule link that does not is
an error of the rule pass. With --lower, the confidence of each contradicting draft is set to 0 in its drafts
file, so that the review takes it first.
"""

import json
import sys
from pathlib import Path


def _range(spec):
    """"8:1-4" -> (8, [1, 2, 3, 4])."""
    c, vs = spec.split(":")
    a, _, b = vs.partition("-")
    return int(c), list(range(int(a), int(b or a) + 1))


def expected_links(shift):
    """[(edition ref, expected unit id)] for one shift."""
    ec, evs = _range(shift["edition"])
    nc, nvs = _range(shift["nova_vulgata"])
    if len(evs) != len(nvs):
        raise ValueError(f"{shift}: ranges of different lengths")
    return [(f"{ec}:{e}", f"btu:{shift['book']}.{nc}.{n}") for e, n in zip(evs, nvs)]


def contradictions(shift, verses):
    """[(ref, expected unit, the link's units)] for the links that lack their expected unit."""
    by_ref = {v["ref"]: v for v in verses}
    out = []
    for ref, uid in expected_links(shift):
        v = by_ref.get(ref)
        if v is not None and not any(u == uid or u.startswith(uid + ".") for u in v.get("units", [])):
            out.append((ref, uid, v.get("units", [])))
    return out


def main(lower):
    root = Path(__file__).resolve().parent.parent
    books = {b["segment"]: b["number"] for b in json.loads((root / "data/books.json").read_text())["books"]}
    shifts = json.loads((root / "scripts/documented_shifts.json").read_text())["shifts"]
    found = rule_errors = 0
    for s in shifts:
        name = f"{books[s['book']]:02d}-{s['book']}.json"
        for ed in s["editions"]:
            mpath = root / f"data/maps/{ed}/{name}"
            if not mpath.exists():
                continue
            verses = json.loads(mpath.read_text())["verses"]
            status = {v["ref"]: v.get("status") for v in verses}
            bad = contradictions(s, verses)
            dpath = root / f"drafts/{ed}/{name}"
            drafts = json.loads(dpath.read_text()) if dpath.exists() else None
            for ref, uid, units in bad:
                found += 1
                rule_errors += status.get(ref) == "rule"
                print(f"{ed} {s['book']} {ref}: expected {uid}, linked to {units or 'nothing'} ({status.get(ref)})")
                if lower and drafts and ref in drafts["confidence"]:
                    drafts["confidence"][ref] = 0.0
            if lower and drafts:
                dpath.write_text(json.dumps(drafts, ensure_ascii=False, indent=1) + "\n")
    print(f"{found} contradictions, {rule_errors} of them rule links")
    sys.exit(1 if rule_errors else 0)


if __name__ == "__main__":
    main("--lower" in sys.argv)
