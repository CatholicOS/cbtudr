"""Draft an edition's mapping to the units: rule links where a chapter matches, drafts elsewhere.

Usage:
  python3 scripts/draft_alignment.py --edition SLUG --structure S.csv --vectors V.csv --nv-vectors N.csv
                                     [--psalms vulgate|hebrew] [--kind-corresponding tb,idt,...]

- S.csv: the edition's verses in reading order, columns book (1-73), chapter, verse, verse_segment,
  text_tradition, omitted, empty (t/f). A verse marked omitted or empty is printed without text.
- V.csv and N.csv: a sentence vector per verse, for the edition and for the Nova Vulgata, columns book,
  chapter, verse, verse_segment, text_tradition, labse (a JSON array). Only the verses of chapters the rules
  cannot decide need vectors.
- --psalms vulgate: the edition numbers the Psalms as the Vulgate does (the Clementine Vulgate, the Douay-Rheims).
- --kind-corresponding: books whose drafts link passages of a different recension (`corresponding`).

Writes data/maps/<slug>/NN-<book>.json and drafts/<slug>/NN-<book>.json (each draft's stretch and confidence).
No text is read. See align.py for the method.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from align import draft_links
from seed_nova_vulgata import dump

csv.field_size_limit(sys.maxsize)


def _key(book, chapter, verse, segment, tradition):
    return (int(book), int(chapter), f"{verse}{segment or ''}", tradition or "")


def read_vectors(path):
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out[_key(r["book"], r["chapter"], r["verse"], r["verse_segment"], r["text_tradition"])] = json.loads(r["labse"])
    return out


def _units(root, book):
    """The book's units as align.py takes them: leaves of the tree, in order, with chapter and label."""
    data = json.loads(next((root / "data/units").glob(f"{book['number']:02d}-*.json")).read_text())
    parents = {u["parent"] for u in data["units"] if "parent" in u}
    out = []
    for u in data["units"]:
        if u["id"] in parents:
            continue
        _, c, v = u["id"].split(":")[1].split(".")[:3]
        out.append({"id": u["id"], "chapter": int(c), "label": v.split("+")[0], "nv_omitted": u.get("nv_omitted", False)})
    return out


def draft_edition(root, slug, structure, vectors, nv_vectors, psalms="hebrew", corresponding=frozenset(), extra=0.15, gap=0.30):
    root = Path(root)
    books = json.loads((root / "data/books.json").read_text())["books"]
    ev, nv = read_vectors(vectors), read_vectors(nv_vectors)
    rows = {}
    with open(structure, newline="") as f:
        for r in csv.DictReader(f):
            rows.setdefault(int(r["book"]), []).append(r)
    edition = slug.upper()
    (root / f"data/maps/{slug}").mkdir(parents=True, exist_ok=True)
    (root / f"drafts/{slug}").mkdir(parents=True, exist_ok=True)
    for book in books:
        if book["number"] not in rows:
            continue
        units = _units(root, book)
        runs = {}
        for r in rows[book["number"]]:
            runs.setdefault(r["text_tradition"] or "", []).append(r)
        primary = "GREEK" if "GREEK" in runs else ""
        kind = "corresponding" if book["segment"] in corresponding else "same"
        verses_out, stretches_out, confidence = [], [], {}
        for tradition, run in runs.items():
            nvtrad = "GREEK" if book["segment"] == "est" else ""
            for u in units:
                u["vec"] = nv.get((book["number"], u["chapter"], u["label"], nvtrad))
            text, omitted = [], []
            for r in run:
                label = f"{r['verse']}{r['verse_segment'] or ''}"
                ref = f"{r['chapter']}:{label}" + (f"@{tradition}" if tradition else "")
                if r.get("omitted") == "t" or r.get("empty") == "t":
                    omitted.append(ref)
                    continue
                text.append({"book": book["number"], "chapter": int(r["chapter"]), "label": label, "tradition": tradition,
                             "vec": ev.get(_key(r["book"], r["chapter"], r["verse"], r["verse_segment"], tradition)), "length": 0})
            links, stretches = draft_links(text, units, psalms=psalms, kind=kind, edition=edition, extra=extra, gap=gap)
            for lk in links:
                if lk["status"] == "draft":
                    confidence[lk["ref"]] = lk.pop("confidence")
                    lk.pop("stretch")
            verses_out += links + [{"ref": ref, "units": [], "omitted": True} for ref in omitted]
            for st in stretches:
                st["id"] = f"{tradition or 'main'}-{st['id']}" if len(runs) > 1 else st["id"]
            stretches_out += stretches
        covered = {u for v in verses_out if (v["ref"].split("@")[1] if "@" in v["ref"] else "") == primary for u in v["units"]}
        mp = {"edition": slug, "book": book["segment"], "verses": verses_out}
        if primary:
            mp["primary"] = primary
        absent = [u["id"] for u in units if u["id"] not in covered]
        if absent:
            mp["absent"] = absent
        name = f"{book['number']:02d}-{book['segment']}.json"
        (root / f"data/maps/{slug}/{name}").write_text(dump(mp, "verses"))
        dpath = root / f"drafts/{slug}/{name}"
        if confidence:
            dpath.write_text(json.dumps({"edition": slug, "book": book["segment"], "stretches": stretches_out, "confidence": confidence},
                                        ensure_ascii=False, indent=1) + "\n")
        elif dpath.exists():
            dpath.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--edition", required=True)
    ap.add_argument("--structure", required=True)
    ap.add_argument("--vectors", required=True)
    ap.add_argument("--nv-vectors", required=True)
    ap.add_argument("--psalms", choices=["hebrew", "vulgate"], default="hebrew")
    ap.add_argument("--kind-corresponding", default="")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    corr = frozenset(x for x in a.kind_corresponding.split(",") if x)
    draft_edition(root, a.edition, a.structure, a.vectors, a.nv_vectors, a.psalms, corr)


if __name__ == "__main__":
    main()
