"""Tests for seed_nova_vulgata.py: units and the Nova Vulgata's own mapping from a verse-structure export."""

import unittest

from seed_nova_vulgata import seed_book


def row(chapter, verse, segment="", tradition=""):
    return {"chapter": str(chapter), "verse": str(verse), "verse_segment": segment, "text_tradition": tradition}


class Seed(unittest.TestCase):
    def test_each_verse_is_a_unit_mapped_to_itself(self):
        units, mp = seed_book("tb", [row(1, 1), row(1, 2), row(2, 1)])
        self.assertEqual([u["id"] for u in units["units"]], ["btu:tb.1.1", "btu:tb.1.2", "btu:tb.2.1"])
        self.assertEqual(mp["verses"][0], {"ref": "1:1", "units": ["btu:tb.1.1"], "kind": "same", "status": "rule"})
        self.assertNotIn("primary", mp)

    def test_lettered_verses_keep_their_letters(self):
        units, mp = seed_book("1par", [row(4, 18, "a"), row(4, 18, "b")])
        self.assertEqual([u["id"] for u in units["units"]], ["btu:1par.4.18a", "btu:1par.4.18b"])
        self.assertEqual([v["ref"] for v in mp["verses"]], ["4:18a", "4:18b"])

    def test_esther_is_seeded_from_the_greek_run_and_the_hebrew_maps_to_the_same_units(self):
        rows = [
            row(1, 1, "", "HEBREW"), row(1, 2, "", "HEBREW"),
            row(1, 1, "a", "GREEK"), row(1, 1, "", "GREEK"), row(1, 2, "", "GREEK"),
        ]
        units, mp = seed_book("est", rows)
        self.assertEqual([u["id"] for u in units["units"]], ["btu:est.1.1a", "btu:est.1.1", "btu:est.1.2"])
        self.assertEqual(mp["primary"], "GREEK")
        by_ref = {v["ref"]: v["units"] for v in mp["verses"]}
        self.assertEqual(by_ref["1:1@HEBREW"], ["btu:est.1.1"])
        self.assertEqual(by_ref["1:1a@GREEK"], ["btu:est.1.1a"])
        self.assertEqual([v["ref"] for v in mp["verses"]][:3], ["1:1a@GREEK", "1:1@GREEK", "1:2@GREEK"])

    def test_a_hebrew_verse_without_a_greek_twin_is_an_error(self):
        with self.assertRaises(ValueError):
            seed_book("est", [row(1, 1, "", "HEBREW"), row(1, 2, "", "GREEK")])


class Corrections(unittest.TestCase):
    """Where the source differs from the Nova Vulgata on vatican.va, the Nova Vulgata governs."""

    def test_a_bracketed_verse_is_a_unit_without_text_in_the_nova_vulgata(self):
        fixes = {"omitted": [{"chapter": 17, "verse": "21"}]}
        units, mp = seed_book("mt", [row(17, 20), row(17, 22)], fixes)
        self.assertEqual(units["units"][1], {"id": "btu:mt.17.21", "nv_omitted": True})
        self.assertEqual(mp["verses"][1], {"ref": "17:21", "units": [], "omitted": True})
        self.assertEqual(mp["absent"], ["btu:mt.17.21"])

    def test_a_verse_the_source_lacks_is_added_in_place(self):
        fixes = {"missing": [{"chapter": 24, "verse": "8"}], "omitted": [{"chapter": 24, "verse": "7"}]}
        units, mp = seed_book("act", [row(24, 6), row(24, 9)], fixes)
        self.assertEqual([u["id"] for u in units["units"]], ["btu:act.24.6", "btu:act.24.7", "btu:act.24.8", "btu:act.24.9"])
        self.assertEqual(mp["verses"][2], {"ref": "24:8", "units": ["btu:act.24.8"], "kind": "same", "status": "rule"})

    def test_a_chapter_is_reordered_as_the_nova_vulgata_prints_it(self):
        fixes = {"order": [{"chapter": 40, "verses": ["42a", "43a", "42b", "43b"]}]}
        rows = [row(40, 41), row(40, 42, "a"), row(40, 42, "b"), row(40, 43, "a"), row(40, 43, "b"), row(40, 44)]
        units, _ = seed_book("ez", rows, fixes)
        self.assertEqual([u["id"].split(".", 2)[2] for u in units["units"]], ["41", "42a", "43a", "42b", "43b", "44"])


if __name__ == "__main__":
    unittest.main()
