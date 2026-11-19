"""Tests for generate_registry.py."""

import unittest

from generate_registry import book_rows


class Registry(unittest.TestCase):
    def test_one_row_per_book_with_its_counts(self):
        books = [{"number": 1, "segment": "gn", "osis": "Gen", "label_la": "Liber Genesis", "label_en": "Genesis", "testament": "OT"}]
        units = {"gn": {"units": [{"id": "btu:gn.1.1"}, {"id": "btu:gn.1.2", "nv_omitted": True}, {"id": "btu:gn.1.1.1", "parent": "btu:gn.1.1"}]}}
        maps = {"gn": ["nvbse", "vgcl"]}
        rows = book_rows(books, units, maps)
        self.assertEqual(rows, ["| 1 | `gn` | `Gen` | Liber Genesis | Genesis | 2 | 1 | 1 | nvbse, vgcl |"])


if __name__ == "__main__":
    unittest.main()
