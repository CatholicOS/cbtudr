"""Draft an edition's mapping to the units: a rule pass, then an alignment of what the rules leave.

1. **Rule pass.** For each Nova Vulgata chapter, the edition's verses that fall in it are compared with the
   chapter's units. Where the labels are the same, in the same order, each verse is linked to its unit:
   status `rule`. Units the Nova Vulgata prints without text (`nv_omitted`) may be missing from the edition.
   Where an edition numbers the Psalms as the Vulgate does, its references are first converted to the Hebrew
   numbering the Nova Vulgata uses (`hebrew_psalm`).
2. **Stretches.** The verses and units the rule pass leaves between two consecutive rule anchors form a
   stretch. A stretch may cross a chapter boundary (the Vulgate's Gn 31:55 is the Nova Vulgata's Gn 32:1).
3. **Alignment.** Inside each stretch, verses and units are aligned in reading order on their vectors (any
   sentence-embedding model), allowing groupings of up to three to one and two to two, and verses or units
   with no counterpart. Each link is a `draft`, with a confidence: the cosine similarity of its group.

No text is read: only verse identities and vectors.
"""

import re

import numpy as np

# Hebrew psalms the Vulgate splits or joins, as spans of Hebrew verses:
# Hebrew chapter -> [(first Hebrew verse, last Hebrew verse, Vulgate chapter, verse offset)].
# As the Clementine Vulgate numbers them; DRB_SPANS overrides where the Douay-Rheims differs.
# Ported from BibleGet's PsalmNumbering (src/Pipeline/Transform/PsalmNumbering.php).
SPANS = {
    9: [(1, 21, 9, 0)],
    10: [(1, 18, 9, 21)],
    114: [(1, 8, 113, 0)],
    115: [(1, 18, 113, 8)],
    116: [(1, 9, 114, 0), (10, 19, 115, -9)],
    147: [(1, 11, 146, 0), (12, 20, 147, -11)],
}
DRB_SPANS = {
    116: [(1, 9, 114, 0), (10, 19, 115, 0)],
    147: [(1, 11, 146, 0), (12, 20, 147, 0)],
}
PSALMS = 23
MOVES = [(1, 1), (2, 1), (1, 2), (3, 1), (1, 3), (2, 2), (1, 0), (0, 1)]


def _vulgate_chapter(hebrew):
    return hebrew - 1 if 11 <= hebrew <= 113 or 117 <= hebrew <= 146 else hebrew


def hebrew_psalm(chapter, verse, edition):
    """The Hebrew (Nova Vulgata) chapter and verse of a psalm verse an edition stores under the Vulgate number."""
    if edition not in ("VGCL", "DRB"):
        return chapter, verse
    spans = {**SPANS, **DRB_SPANS} if edition == "DRB" else SPANS
    for hebrew, zone in spans.items():
        for first, last, vulgate, offset in zone:
            hv = verse - offset
            if vulgate == chapter and first <= hv <= last:
                return hebrew, hv
    nxt = chapter + 1
    if nxt not in spans and _vulgate_chapter(nxt) == chapter:
        return nxt, verse
    return chapter, verse


def ref_of(v):
    """The verse's ref: chapter:label, then #n for the n-th unlettered part of a verse printed in parts, then @TRADITION."""
    part = f"#{v['part']}" if v.get("part", 1) > 1 else ""
    return f"{v['chapter']}:{v['label']}{part}" + (f"@{v['tradition']}" if v.get("tradition") else "")


def _candidate(v, psalms, edition):
    """Where the verse would sit in the Nova Vulgata's numbering: (chapter, label)."""
    if v["book"] == PSALMS and psalms == "vulgate":
        m = re.match(r"(\d+)(.*)", v["label"])
        c, n = hebrew_psalm(v["chapter"], int(m[1]), edition)
        return c, f"{n}{m[2]}"
    return v["chapter"], v["label"]


def _anchors(verses, units, psalms, edition):
    """Verse index -> unit index, for the verses of chapters that match the units exactly."""
    by_chapter = {}
    for j, u in enumerate(units):
        by_chapter.setdefault(u["chapter"], []).append(j)
    cand = [_candidate(v, psalms, edition) for v in verses]
    in_chapter = {}
    for i, (c, _) in enumerate(cand):
        in_chapter.setdefault(c, []).append(i)
    match = {}
    for c, js in by_chapter.items():
        vs = in_chapter.get(c, [])
        labels = [cand[i][1] for i in vs]
        # The units as they are; without those the Nova Vulgata prints without text; and without the lettered
        # additions too, for a text that lacks them (Esther's Hebrew text: its 1:1 is the unit 1:1, not 1:1a).
        plain = [j for j in js if not re.search(r"[a-z]", units[j]["label"])]
        for pool in (js, [j for j in js if not units[j].get("nv_omitted")], plain, [j for j in plain if not units[j].get("nv_omitted")]):
            if labels and labels == [units[j]["label"] for j in pool]:
                match.update(zip(vs, pool))
                break
    # Anchors must follow the units' order: one that would go back is not an anchor.
    out, last = {}, -1
    for i in range(len(verses)):
        if i in match and match[i] > last:
            out[i] = last = match[i]
    return out


def rule_pass(verses, units, psalms="hebrew", edition=""):
    """The rule links, and the stretches between rule anchors: {verses: [verse index], units: [unit id]}."""
    anchors = _anchors(verses, units, psalms, edition)
    links = [{"ref": ref_of(verses[i]), "units": [units[j]["id"]], "kind": "same", "status": "rule"} for i, j in anchors.items()]
    stretches, pending, last = [], [], -1

    def close(upto):
        between = [j for j in range(last + 1, upto) if j not in anchors.values()]
        # Units with no edition verse beside them carry no draft: the map's `absent` lists them.
        if pending:
            between = [units[j]["id"] for j in between]
            stretches.append({"verses": list(pending), "units": between})

    for i in range(len(verses)):
        if i in anchors:
            close(anchors[i])
            pending, last = [], anchors[i]
        else:
            pending.append(i)
    close(len(units))
    return links, stretches


def _unit(vectors):
    """The normalized sum of a group's vectors; verses or units without a vector add nothing (no evidence)."""
    present = [v for v in vectors if v is not None]
    if not present:
        return None
    s = np.sum(present, axis=0)
    n = np.linalg.norm(s)
    return s / n if n else None


def _cos(a, b):
    return float(a @ b) if a is not None and b is not None else 0.0


def align_stretch(verses, units, extra=0.15, gap=0.30, band=None):
    """[(verse indexes, unit indexes, similarity)] in reading order, maximizing the total score.

    Only cells within `band` of the diagonal are considered (by default, the difference in length plus 12),
    so a long stretch (a whole book of Sirach) is aligned in seconds."""
    def vec(x):
        if x.get("vec") is None:
            return None
        v = np.asarray(x["vec"], dtype=np.float64)
        n = np.linalg.norm(v)
        return v / n if n else None

    A = [vec(v) for v in verses]
    B = [vec(u) for u in units]
    n, m = len(A), len(B)
    width = band if band is not None else abs(n - m) + 12
    best = {(0, 0): (0.0, None, None)}
    for i in range(n + 1):
        centre = i * m / n if n else 0
        for j in range(max(0, int(centre - width)), min(m, int(centre + width)) + 1):
            if (i, j) == (0, 0):
                continue
            options = []
            for di, dj in MOVES:
                p = (i - di, j - dj)
                if p not in best:
                    continue
                if di and dj:
                    a, b = _unit(A[p[0]:i]), _unit(B[p[1]:j])
                    s = _cos(a, b) if a is not None and b is not None and a.shape == b.shape else 0.0
                    score = s - extra * (di + dj - 2)
                else:
                    s, score = 0.0, -gap
                options.append((best[p][0] + score, p, s))
            if options:
                best[(i, j)] = max(options, key=lambda o: o[0])
    groups, k = [], (n, m)
    while best[k][1] is not None:
        p, s = best[k][1], best[k][2]
        groups.append((list(range(p[0], k[0])), list(range(p[1], k[1])), max(0.0, min(1.0, s))))
        k = p
    return groups[::-1]


def draft_links(verses, units, psalms="hebrew", kind="same", edition="", extra=0.15, gap=0.30):
    """Rule links plus draft links for every stretch; stretches get ids and their uncovered units."""
    links, stretches = rule_pass(verses, units, psalms, edition)
    index = {u["id"]: j for j, u in enumerate(units)}
    for sid, st in enumerate(stretches, start=1):
        st["id"] = sid
        sv = [verses[i] for i in st["verses"]]
        su = [units[index[u]] for u in st["units"]]
        covered = set()
        for gi, hi, s in align_stretch(sv, su, extra, gap):
            ids = [su[h]["id"] for h in hi]
            if gi:
                covered.update(ids)
            for g in gi:
                links.append({"ref": ref_of(sv[g]), "units": ids, "kind": kind, "status": "draft",
                              "confidence": round(s, 4), "stretch": sid})
        st["uncovered"] = [u for u in st["units"] if u not in covered]
        st["verses"] = [ref_of(verses[i]) for i in st["verses"]]
    order = {ref_of(v): i for i, v in enumerate(verses)}
    links.sort(key=lambda lk: order[lk["ref"]])
    return links, stretches
