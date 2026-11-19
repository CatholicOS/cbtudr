"""Tests for validate.py: the identifier grammar, the unit tree and the edition mappings."""

import unittest

from validate import check_id, check_map, check_units, coverage_gaps

BOOK = "tb"


def units(*specs):
    """Units from ("id", parent-or-None, after-or-None) tuples."""
    out = []
    for spec in specs:
        uid, parent, after = (spec + (None, None))[:3]
        u = {"id": uid}
        if parent:
            u["parent"] = parent
        if after:
            u["after"] = after
        out.append(u)
    return {"book": BOOK, "units": out}


def verse(ref, *ids, kind="same", status="rule"):
    return {"ref": ref, "units": list(ids), "kind": kind, "status": status}


class Grammar(unittest.TestCase):
    def test_valid_ids(self):
        for uid in [
            "btu:tb.5.4",
            "btu:tb.5.4.1",
            "btu:tb.5.4.1.2",
            "btu:est.1.1a",
            "btu:est.4.17aa",
            "btu:tb.5.4+1",
            "btu:tb.5.4+1.2",
            "btu:1sm.20.42",
            "btu:bar.6.0",
        ]:
            self.assertEqual(check_id(uid), [], uid)

    def test_invalid_ids(self):
        for uid in [
            "tb.5.4",  # no prefix
            "btu:Tb.5.4",  # uppercase
            "btu:tb.5",  # no verse
            "btu:tb.5.4.a",  # a split is a number, not a letter
            "btu:tb.5.4.0",  # parts count from 1
            "btu:tb.05.4",  # leading zero
            "btu:tb.5.4+0",
            "btu:tb.5.4 ",
        ]:
            self.assertNotEqual(check_id(uid), [], uid)


class Units(unittest.TestCase):
    def test_a_well_formed_tree_passes(self):
        u = units(("btu:tb.5.4",), ("btu:tb.5.4.1", "btu:tb.5.4"), ("btu:tb.5.4.2", "btu:tb.5.4"), ("btu:tb.5.4+1", None, "btu:tb.5.4"))
        self.assertEqual(check_units(u, BOOK), [])

    def test_duplicates_and_wrong_book_are_errors(self):
        errs = check_units(units(("btu:tb.5.4",), ("btu:tb.5.4",), ("btu:gn.1.1",)), BOOK)
        self.assertTrue(any("duplicate" in e for e in errs))
        self.assertTrue(any("book" in e for e in errs))

    def test_a_child_names_its_parent_by_its_own_id(self):
        # btu:tb.5.4.1 must be a child of btu:tb.5.4, declared before it.
        errs = check_units(units(("btu:tb.5.4.1", "btu:tb.5.4"), ("btu:tb.5.4",)), BOOK)
        self.assertTrue(any("parent" in e for e in errs))
        errs = check_units(units(("btu:tb.5.4",), ("btu:tb.5.5",), ("btu:tb.5.5.1", "btu:tb.5.4")), BOOK)
        self.assertTrue(any("parent" in e for e in errs))

    def test_a_lone_child_is_an_error(self):
        # A split makes at least two parts.
        errs = check_units(units(("btu:tb.5.4",), ("btu:tb.5.4.1", "btu:tb.5.4")), BOOK)
        self.assertTrue(any("one child" in e for e in errs))

    def test_an_added_unit_follows_an_existing_one(self):
        errs = check_units(units(("btu:tb.5.4",), ("btu:tb.5.4+1",)), BOOK)
        self.assertTrue(any("after" in e for e in errs))
        errs = check_units(units(("btu:tb.5.4+1", None, "btu:tb.5.9"),), BOOK)
        self.assertTrue(any("after" in e for e in errs))


class Maps(unittest.TestCase):
    TREE = units(
        ("btu:tb.5.3",),
        ("btu:tb.5.4",),
        ("btu:tb.5.4.1", "btu:tb.5.4"),
        ("btu:tb.5.4.2", "btu:tb.5.4"),
        ("btu:tb.5.4+1", None, "btu:tb.5.4"),
    )

    def m(self, verses, **extra):
        return {"edition": "x", "book": BOOK, "verses": verses, **extra}

    def test_a_complete_mapping_passes(self):
        mp = self.m([verse("5:3", "btu:tb.5.3"), verse("5:4", "btu:tb.5.4.1"), verse("5:5", "btu:tb.5.4.2", "btu:tb.5.4+1")])
        self.assertEqual(check_map(mp, self.TREE, BOOK), [])

    def test_a_parent_covers_its_children(self):
        mp = self.m([verse("5:3", "btu:tb.5.3"), verse("5:4", "btu:tb.5.4"), verse("5:5", "btu:tb.5.4+1")])
        self.assertEqual(check_map(mp, self.TREE, BOOK), [])

    def test_repeated_refs_and_unknown_units_are_errors(self):
        mp = self.m([verse("5:3", "btu:tb.5.3"), verse("5:3", "btu:tb.5.99")])
        errs = check_map(mp, self.TREE, BOOK)
        self.assertTrue(any("repeated" in e for e in errs))
        self.assertTrue(any("unknown" in e for e in errs))

    def test_a_unit_and_its_ancestor_in_one_run_overlap(self):
        mp = self.m([verse("5:3", "btu:tb.5.3"), verse("5:4", "btu:tb.5.4"), verse("5:5", "btu:tb.5.4.2", "btu:tb.5.4+1")])
        self.assertTrue(any("more than once" in e for e in check_map(mp, self.TREE, BOOK)))

    def test_bad_kind_status_or_ref_are_errors(self):
        mp = self.m([{"ref": "5", "units": ["btu:tb.5.3"], "kind": "similar", "status": "guess"}])
        errs = check_map(mp, self.TREE, BOOK)
        for word in ["ref", "kind", "status"]:
            self.assertTrue(any(word in e for e in errs), word)

    def test_an_omitted_verse_has_no_units(self):
        mp = self.m([verse("5:3", "btu:tb.5.3"), {"ref": "5:3a", "units": [], "omitted": True}, verse("5:4", "btu:tb.5.4", "btu:tb.5.4+1")])
        self.assertEqual(check_map(mp, self.TREE, BOOK), [])
        mp = self.m([verse("5:3", "btu:tb.5.3"), {"ref": "5:4", "units": [], "kind": "same", "status": "rule"}])
        self.assertTrue(any("no units" in e for e in check_map(mp, self.TREE, BOOK)))

    def test_traditions_are_separate_runs(self):
        # Esther: the Hebrew run and the Greek run both cover the shared units.
        mp = self.m(
            [verse("5:3@GREEK", "btu:tb.5.3"), verse("5:4@GREEK", "btu:tb.5.4", "btu:tb.5.4+1"), verse("5:3@HEBREW", "btu:tb.5.3")],
            primary="GREEK",
        )
        self.assertEqual(check_map(mp, self.TREE, BOOK), [])


class Coverage(unittest.TestCase):
    def test_every_unit_is_covered_or_absent(self):
        tree = Maps.TREE
        mp = {"edition": "x", "book": BOOK, "verses": [verse("5:3", "btu:tb.5.3"), verse("5:4", "btu:tb.5.4.1")]}
        self.assertEqual(coverage_gaps(mp, tree), ["btu:tb.5.4.2", "btu:tb.5.4+1"])
        mp["absent"] = ["btu:tb.5.4.2", "btu:tb.5.4+1"]
        self.assertEqual(coverage_gaps(mp, tree), [])

    def test_only_the_primary_run_must_be_complete(self):
        tree = Maps.TREE
        mp = {
            "edition": "x",
            "book": BOOK,
            "primary": "GREEK",
            "verses": [verse("5:3@GREEK", "btu:tb.5.3"), verse("5:4@GREEK", "btu:tb.5.4", "btu:tb.5.4+1"), verse("5:3@HEBREW", "btu:tb.5.3")],
        }
        self.assertEqual(coverage_gaps(mp, tree), [])


if __name__ == "__main__":
    unittest.main()
