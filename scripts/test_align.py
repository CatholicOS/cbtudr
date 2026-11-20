"""Tests for align.py: the rule pass, the stretches between rule anchors, and the alignment inside a stretch.

Vectors are synthetic one-hot vectors (no text): two items match exactly when they share a dimension.
"""

import unittest

from align import align_stretch, hebrew_psalm, rule_pass

DIM = 64


def onehot(*dims):
    v = [0.0] * DIM
    for d in dims:
        v[d] = 1.0
    return v


def verse(chapter, label, dim=None, book=1, tradition=""):
    return {"book": book, "chapter": chapter, "label": str(label), "tradition": tradition,
            "vec": onehot(dim) if dim is not None else None, "length": 10}


def unit(seg, chapter, label, dim=None, omitted=False):
    u = {"id": f"btu:{seg}.{chapter}.{label}", "chapter": chapter, "label": str(label),
         "vec": onehot(dim) if dim is not None else None}
    if omitted:
        u["nv_omitted"] = True
    return u


class Rules(unittest.TestCase):
    def test_identical_chapters_are_rule_links(self):
        vs = [verse(5, n) for n in (1, 2, 3)]
        us = [unit("gn", 5, n) for n in (1, 2, 3)]
        links, stretches = rule_pass(vs, us, psalms="hebrew")
        self.assertEqual(stretches, [])
        self.assertEqual(links[0], {"ref": "5:1", "units": ["btu:gn.5.1"], "kind": "same", "status": "rule"})
        self.assertEqual([lk["status"] for lk in links], ["rule"] * 3)

    def test_a_differing_chapter_becomes_one_stretch_between_anchors(self):
        vs = [verse(4, 1), verse(5, 1), verse(5, 2), verse(6, 1)]
        us = [unit("gn", 4, 1), unit("gn", 5, 1), unit("gn", 5, 2), unit("gn", 5, 3), unit("gn", 6, 1)]
        links, stretches = rule_pass(vs, us, psalms="hebrew")
        self.assertEqual(len(stretches), 1)
        self.assertEqual(stretches[0]["verses"], [1, 2])
        self.assertEqual(stretches[0]["units"], ["btu:gn.5.1", "btu:gn.5.2", "btu:gn.5.3"])
        self.assertEqual([lk["status"] for lk in links if lk["ref"] in ("4:1", "6:1")], ["rule", "rule"])

    def test_a_hebrew_run_matches_the_units_without_the_greek_additions(self):
        # Esther's Hebrew text has no lettered additions: its 1:1-3 are the units 1:1-3, by rule.
        vs = [verse(1, n, book=19, tradition="HEBREW") for n in (1, 2, 3)]
        us = [unit("est", 1, "1a"), unit("est", 1, "1b"), unit("est", 1, 1), unit("est", 1, 2), unit("est", 1, 3)]
        links, stretches = rule_pass(vs, us, psalms="hebrew")
        self.assertEqual(stretches, [])
        self.assertEqual([lk["units"] for lk in links], [["btu:est.1.1"], ["btu:est.1.2"], ["btu:est.1.3"]])

    def test_a_missing_nova_vulgata_omission_still_matches(self):
        # The Nova Vulgata prints Mt 17:21 in brackets; an edition without it matches the chapter by rule.
        vs = [verse(17, 20, book=47), verse(17, 22, book=47)]
        us = [unit("mt", 17, 20), unit("mt", 17, 21, omitted=True), unit("mt", 17, 22)]
        links, stretches = rule_pass(vs, us, psalms="hebrew")
        self.assertEqual(stretches, [])
        self.assertEqual([lk["units"] for lk in links], [["btu:mt.17.20"], ["btu:mt.17.22"]])


class Psalms(unittest.TestCase):
    def test_vulgate_psalms_are_compared_in_hebrew_numbering(self):
        self.assertEqual(hebrew_psalm(9, 22, "VGCL"), (10, 1))
        self.assertEqual(hebrew_psalm(113, 9, "VGCL"), (115, 1))
        self.assertEqual(hebrew_psalm(115, 1, "VGCL"), (116, 10))
        self.assertEqual(hebrew_psalm(115, 10, "DRB"), (116, 10))
        self.assertEqual(hebrew_psalm(147, 1, "VGCL"), (147, 12))
        self.assertEqual(hebrew_psalm(50, 3, "VGCL"), (51, 3))
        self.assertEqual(hebrew_psalm(50, 3, "NABRE"), (50, 3))
        # VGCL Ps 9 (39 verses) is Hebrew Ps 9 (21) and 10 (18): rule links to both.
        vs = [verse(9, n, book=23) for n in range(1, 40)]
        us = [unit("ps", 9, n) for n in range(1, 22)] + [unit("ps", 10, n) for n in range(1, 19)]
        links, stretches = rule_pass(vs, us, psalms="vulgate", edition="VGCL")
        self.assertEqual(stretches, [])
        self.assertEqual(links[21], {"ref": "9:22", "units": ["btu:ps.10.1"], "kind": "same", "status": "rule"})


class Alignment(unittest.TestCase):
    def test_a_stretch_crosses_the_chapter_boundary(self):
        # VGCL Gn 31 has 55 verses where the Hebrew numbering has 54: 31:55 is Gn 32:1.
        vs = [verse(31, n, dim=n) for n in (53, 54, 55)] + [verse(32, 1, dim=56)]
        us = [unit("gn", 31, 53, dim=53), unit("gn", 31, 54, dim=54), unit("gn", 32, 1, dim=55), unit("gn", 32, 2, dim=56)]
        groups = align_stretch(vs, us)
        self.assertIn(([2], [2], 1.0), [(g, h, round(s, 6)) for g, h, s in groups])
        self.assertIn(([3], [3], 1.0), [(g, h, round(s, 6)) for g, h, s in groups])

    def test_two_verses_to_one_unit(self):
        vs = [verse(5, 3, dim=None), verse(5, 4, dim=None)]
        vs[0]["vec"], vs[1]["vec"] = onehot(1), onehot(2)
        us = [unit("tb", 5, 4)]
        us[0]["vec"] = onehot(1, 2)
        groups = align_stretch(vs, us)
        self.assertEqual([(g, h) for g, h, _ in groups], [([0, 1], [0])])

    def test_unmatched_verse_has_no_units(self):
        vs = [verse(5, 1, dim=1), verse(5, 2, dim=40), verse(5, 3, dim=3)]
        us = [unit("tb", 5, 1, dim=1), unit("tb", 5, 3, dim=3)]
        groups = align_stretch(vs, us)
        self.assertIn(([1], [], 0.0), groups)

    def test_rule_pass_and_alignment_give_draft_links_with_confidence(self):
        vs = [verse(4, 1, dim=1), verse(5, 1, dim=2), verse(5, 2, dim=3), verse(6, 1, dim=9)]
        us = [unit("gn", 4, 1, dim=1), unit("gn", 5, 1, dim=2), unit("gn", 5, 2, dim=3), unit("gn", 5, 3, dim=4), unit("gn", 6, 1, dim=9)]
        from align import draft_links
        links, stretches = draft_links(vs, us, psalms="hebrew", kind="same")
        by_ref = {lk["ref"]: lk for lk in links}
        self.assertEqual(by_ref["5:1"]["status"], "draft")
        self.assertEqual(by_ref["5:1"]["units"], ["btu:gn.5.1"])
        self.assertEqual(by_ref["5:1"]["stretch"], 1)
        self.assertEqual(by_ref["5:1"]["confidence"], 1.0)
        self.assertEqual(stretches[0]["id"], 1)
        # btu:gn.5.3 has no counterpart in the edition: it is reported, not linked.
        self.assertEqual(stretches[0]["uncovered"], ["btu:gn.5.3"])


class MissingVectors(unittest.TestCase):
    def test_a_verse_without_a_vector_is_no_evidence(self):
        vs = [verse(5, 1, dim=1), verse(5, 2), verse(5, 3, dim=3)]
        us = [unit("tb", 5, 1, dim=1), unit("tb", 5, 2), unit("tb", 5, 3, dim=3)]
        groups = align_stretch(vs, us)
        self.assertIn(([0], [0], 1.0), groups)
        self.assertIn(([2], [2], 1.0), groups)


class Band(unittest.TestCase):
    def test_a_long_stretch_is_aligned_within_a_band(self):
        import random, time
        random.seed(1)
        dim = 400
        def rv():
            return [random.gauss(0, 1) for _ in range(dim)]
        us = [{"id": f"btu:eccli.1.{n}", "chapter": 1, "label": str(n), "vec": rv()} for n in range(1, 401)]
        # The edition joins units 100-101 into one verse: every other verse matches its unit.
        vs = []
        for n, u in enumerate(us, start=1):
            if n == 101:
                vs[-1]["vec"] = [a + b for a, b in zip(vs[-1]["vec"], u["vec"])]
                continue
            vs.append({"book": 28, "chapter": 1, "label": str(len(vs) + 1), "tradition": "", "vec": list(u["vec"]), "length": 10})
        t = time.time()
        groups = align_stretch(vs, us)
        self.assertLess(time.time() - t, 20)
        self.assertIn(([99], [99, 100]), [(g, h) for g, h, _ in groups])
        self.assertEqual(sum(len(h) for _, h, _ in groups), 400)


if __name__ == "__main__":
    unittest.main()
