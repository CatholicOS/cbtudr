"""Draft an edition's mapping to the units: rule links where a chapter matches, drafts elsewhere.

Usage:
  python3 scripts/draft_alignment.py --edition SLUG --structure S.csv --vectors V.csv --nv-vectors N.csv
                                     [--psalms vulgate|hebrew] [--kind-corresponding tb,idt,...]

- S.csv: the edition's verses in reading order, columns book (1-73), chapter, verse, verse_segment,
  text_tradition, omitted, empty (t/f). A verse marked omitted or empty is printed without text.
- V.csv and N.csv: a sentence vector per verse, for the edition and for the Nova Vulgata, columns book,
  chapter, verse, verse_segment, text_tradition, labse (a JSON array), and optionally sort_order, which then
  matches the vectors to the structure's rows one by one. Only the verses of chapters the rules cannot decide
  need vectors.
- --psalms vulgate: the edition numbers the Psalms as the Vulgate does (the Clementine Vulgate, the Douay-Rheims).
- --kind-corresponding: books whose drafts link passages of a different recension (`corresponding`).

Writes data/maps/<slug>/NN-<book>.json and drafts/<slug>/NN-<book>.json (each draft's stretch and confidence).
No text is read. See align.py for the method.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from align import draft_links
from seed_nova_vulgata import dump

csv.field_size_limit(sys.maxsize)


def _key(book, chapter, verse, segment, tradition):
    return (int(book), int(chapter), f"{verse}{segment or ''}", tradition or "")


def read_vectors(path):
    """Vectors by verse identity, and by ("sort_order", n) when the file has a sort_order column: rows that share an
    identity (the Vulgate's Greek additions to Esther, all numbered 1:1) are told apart only by it."""
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            vec = json.loads(r["labse"])
            out.setdefault(_key(r["book"], r["chapter"], r["verse"], r["verse_segment"], r["text_tradition"]), vec)
            if r.get("sort_order"):
                out[("sort_order", r["sort_order"])] = vec
    return out


def fold_copies(rows):
    """Rows the source stores twice: an original where the edition prints it, and a copy placed in the Nova
    Vulgata's order whose alt_ref names the original (BibleGet stores the Vulgate's Greek additions to Esther both
    in its chapters 10:4-16:24 and as lettered verses in place, 1:1a with alt_ref 11:2).

    Returns the rows to align (the copies, not the originals they name) and {copy's c:v[letters]: original's c:v}.
    The copies are aligned, and their links then go to the originals: the edition prints the originals."""
    own = lambda r: f"{r['chapter']}:{r['verse']}"
    copies = {f"{own(r)}{r.get('verse_segment') or ''}": r["alt_ref"] for r in rows
              if r.get("alt_ref") and r["alt_ref"] != own(r) and re.fullmatch(r"\d+:\d+", r["alt_ref"])}
    targets = set(copies.values())
    aligned = [r for r in rows if not (own(r) in targets and not r.get("verse_segment") and r.get("alt_ref", "") in ("", own(r)))]
    return aligned, copies


def _nova_vulgata_order(rows, units):
    """Rows sorted as the Nova Vulgata orders them: by chapter and verse, a verse's lettered parts before it where the
    units put them before it (Est 1:1a-1k precede 1:1), after it elsewhere (3:13a follows 3:13)."""
    first = {}
    for i, u in enumerate(units):
        first.setdefault((u["chapter"], u["label"]), i)
    def key(r):
        c, v, seg = int(r["chapter"]), int(r["verse"]), r.get("verse_segment") or ""
        if not seg:
            return (c, v, 0)
        before = first.get((c, f"{v}a"), 1e9) < first.get((c, str(v)), -1)
        return (c, v, -1 if before else 1)
    return sorted(rows, key=key)


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


def _to_originals(links, stretches, copies, tradition):
    """Links of the copies given to the originals they name; links in the originals' (the edition's) order."""
    suffix = f"@{tradition}" if tradition else ""
    rename = {f"{c}{suffix}": f"{o}{suffix}" for c, o in copies.items()}
    for lk in links:
        lk["ref"] = rename.get(lk["ref"], lk["ref"])
    for st in stretches:
        st["verses"] = [rename.get(r, r) for r in st["verses"]]
    def order(ref):
        c, v = ref.split("@")[0].split("#")[0].split(":")
        m = re.match(r"(\d+)(.*)", v)
        return (int(c), int(m[1]), m[2])
    return sorted(links, key=lambda lk: order(lk["ref"])), stretches


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
            aligned, copies = fold_copies(run)
            if copies:
                run = _nova_vulgata_order(aligned, units)
            text, omitted, seen = [], [], {}
            for r in run:
                label = f"{r['verse']}{r['verse_segment'] or ''}"
                # A verse printed in unlettered parts (NABRE Job 10:1): its second part is 10:1#2.
                key = (r["chapter"], label)
                seen[key] = part = seen.get(key, 0) + 1
                ref = f"{r['chapter']}:{label}" + (f"#{part}" if part > 1 else "") + (f"@{tradition}" if tradition else "")
                if r.get("omitted") == "t" or r.get("empty") == "t":
                    omitted.append(ref)
                    continue
                # By row (sort_order) when both files have it; otherwise by verse identity, where only a verse's
                # first part has a vector (its other parts carry no evidence).
                vec = ev.get(("sort_order", r.get("sort_order", "")))
                if vec is None and part == 1:
                    vec = ev.get(_key(r["book"], r["chapter"], r["verse"], r["verse_segment"], tradition))
                text.append({"book": book["number"], "chapter": int(r["chapter"]), "label": label, "tradition": tradition,
                             "vec": vec, "length": 0, "part": part})
            links, stretches = draft_links(text, units, psalms=psalms, kind=kind, edition=edition, extra=extra, gap=gap)
            if copies:
                links, stretches = _to_originals(links, stretches, copies, tradition)
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
