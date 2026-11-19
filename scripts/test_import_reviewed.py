"""Tests for import_reviewed.py: reviewed links from the review store, applied to a map and its drafts file."""

import unittest

from import_reviewed import apply_review

UNITS = {"book": "tb", "units": [{"id": f"btu:tb.5.{n}"} for n in (1, 2, 3, 4)]}


def mp():
    return {"edition": "x", "book": "tb", "verses": [
        {"ref": "5:1", "units": ["btu:tb.5.1"], "kind": "same", "status": "rule"},
        {"ref": "5:2", "units": ["btu:tb.5.2", "btu:tb.5.3"], "kind": "corresponding", "status": "draft"},
        {"ref": "5:3", "units": ["btu:tb.5.4"], "kind": "corresponding", "status": "draft"},
    ]}


def drafts():
    return {"edition": "x", "book": "tb", "stretches": [{"id": 1, "verses": ["5:2", "5:3"], "units": ["btu:tb.5.2", "btu:tb.5.3", "btu:tb.5.4"], "uncovered": []}],
            "confidence": {"5:2": 0.5, "5:3": 0.4}}


class Apply(unittest.TestCase):
    def test_reviewed_links_replace_drafts(self):
        m, d, report = apply_review(mp(), drafts(), UNITS, [{"ref": "5:2", "units": ["btu:tb.5.2"], "kind": "same", "status": "reviewed"}])
        v = next(v for v in m["verses"] if v["ref"] == "5:2")
        self.assertEqual(v, {"ref": "5:2", "units": ["btu:tb.5.2"], "kind": "same", "status": "reviewed"})
        self.assertEqual(d["confidence"], {"5:3": 0.4})
        self.assertEqual(report["applied"], 1)

    def test_none_becomes_absent(self):
        reviewed = [{"ref": "5:3", "units": [], "kind": "corresponding", "status": "reviewed"}]
        m, _, report = apply_review(mp(), drafts(), UNITS, reviewed)
        v = next(v for v in m["verses"] if v["ref"] == "5:3")
        self.assertEqual(v["units"], [])
        self.assertIn("btu:tb.5.4", m["absent"])
        self.assertEqual(report["no_counterpart"], ["5:3"])

    def test_split_flags_are_reported_not_applied(self):
        flagged = [{"ref": "5:2", "units": ["btu:tb.5.2", "btu:tb.5.3"], "kind": "corresponding", "status": "draft", "note": "two parts"}]
        m, d, report = apply_review(mp(), drafts(), UNITS, flagged)
        self.assertEqual(next(v for v in m["verses"] if v["ref"] == "5:2")["status"], "draft")
        self.assertEqual(report["splits"], [{"ref": "5:2", "note": "two parts"}])
        self.assertEqual(d["confidence"]["5:2"], 0.5)

    def test_rule_links_are_untouched(self):
        m, _, report = apply_review(mp(), drafts(), UNITS, [{"ref": "5:1", "units": ["btu:tb.5.2"], "kind": "same", "status": "rule"}])
        self.assertEqual(next(v for v in m["verses"] if v["ref"] == "5:1")["units"], ["btu:tb.5.1"])
        self.assertEqual(report["applied"], 0)

    def test_all_reviewed_drops_the_drafts_file(self):
        reviewed = [{"ref": r, "units": u, "kind": "corresponding", "status": "reviewed"} for r, u in [("5:2", ["btu:tb.5.2", "btu:tb.5.3"]), ("5:3", ["btu:tb.5.4"])]]
        _, d, _ = apply_review(mp(), drafts(), UNITS, reviewed)
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
