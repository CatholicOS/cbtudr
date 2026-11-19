"""Tests for check_cases.py: drafts checked against documented versification shifts."""

import unittest

from check_cases import expected_links, contradictions


class Cases(unittest.TestCase):
    SHIFT = {"book": "gn", "editions": ["vgcl"], "edition": "31:55", "nova_vulgata": "32:1"}
    RANGE = {"book": "ex", "editions": ["vgcl"], "edition": "8:1-4", "nova_vulgata": "7:26-29"}

    def test_a_shift_expands_to_verse_pairs(self):
        self.assertEqual(expected_links(self.SHIFT), [("31:55", "btu:gn.32.1")])
        self.assertEqual(expected_links(self.RANGE), [("8:1", "btu:ex.7.26"), ("8:2", "btu:ex.7.27"), ("8:3", "btu:ex.7.28"), ("8:4", "btu:ex.7.29")])

    def test_contradicting_link_is_reported(self):
        verses = [{"ref": "31:55", "units": ["btu:gn.31.54"], "kind": "same", "status": "draft"}]
        self.assertEqual(contradictions(self.SHIFT, verses), [("31:55", "btu:gn.32.1", ["btu:gn.31.54"])])
        ok = [{"ref": "31:55", "units": ["btu:gn.32.1"], "kind": "same", "status": "draft"}]
        self.assertEqual(contradictions(self.SHIFT, ok), [])


if __name__ == "__main__":
    unittest.main()
