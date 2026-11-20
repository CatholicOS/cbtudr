"""Tests for check_vatican.py: the numbers vatican.va prints in brackets, against the nv_omitted units."""

import unittest

from check_vatican import bracketed, omitted_differences, tokens


class Bracketed(unittest.TestCase):
    def test_every_form_the_nova_vulgata_prints(self):
        self.assertEqual(bracketed("vobis ”. (21) 22 Conversantibus"), ["21"])
        self.assertEqual(bracketed("gaudium dabit.(19) (20 Plenitudo"), ["19"])
        self.assertEqual(bracketed("ignis exardescit. (10. 11) 12 Cum alterius"), ["10", "11"])
        self.assertEqual(bracketed("ab omni malo. (16 17) 18 Super scutum"), ["16", "17"])
        self.assertEqual(bracketed("Uriae Hetthaei. ( 6 ) 7 Reliqua"), ["6"])

    def test_the_greek_number_in_a_psalm_title_is_not_one(self):
        self.assertEqual(bracketed("PSALMUS 51 (50) 1 Magistro chori."), [])

    def test_bracketed_numbers_are_not_verse_tokens(self):
        self.assertEqual(tokens(" 9 Propter speciem exardescit. (10. 11) 12 Cum alterius "), ["9", "12"])
        self.assertEqual(tokens(" 5 eo quod Uriae Hetthaei. ( 6 ) 7 Reliqua "), ["5", "7"])


class OmittedDifferences(unittest.TestCase):
    def test_both_directions(self):
        self.assertEqual(omitted_differences(["16", "17"], ["16", "17"]), ([], []))
        # Sir 9 before the fix: the page brackets 10 and 11, the registry had no such units.
        self.assertEqual(omitted_differences([], ["10", "11"]), (["10", "11"], []))
        self.assertEqual(omitted_differences(["21"], []), ([], ["21"]))


if __name__ == "__main__":
    unittest.main()
