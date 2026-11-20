"""Tests for draft_alignment.py: the map and drafts files it writes."""

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from draft_alignment import draft_edition
from validate import validate

ROOT = Path(__file__).resolve().parent.parent


def cv(uid):
    """The chapter and verse of a unit id: "btu:tb.5.4" -> (5, 4)."""
    _, c, v = uid.split(":")[1].split(".")[:3]
    return int(c), int(v)


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class Fixture(unittest.TestCase):
    """A copy of the registry with a synthetic edition of Tobit 5 (book 17) and Genesis 1 (book 1)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for d in ["data", "scripts"]:
            shutil.copytree(ROOT / d, self.tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        units = json.loads((self.tmp / "data/units/17-tb.json").read_text())["units"]
        self.tb5 = [u["id"] for u in units if u["id"].startswith("btu:tb.5.")]
        # The edition: Genesis as the units have it, Tobit 5 with its first two verses joined.
        gn = json.loads((self.tmp / "data/units/01-gn.json").read_text())["units"]
        struct = [[1, *cv(u["id"]), "", "", "f", "f"] for u in gn if "+" not in u["id"]]
        tb = json.loads((self.tmp / "data/units/17-tb.json").read_text())["units"]
        for u in tb:
            c, v = cv(u["id"])
            if c == 5 and v == 2:
                continue
            struct.append([17, c, v if c != 5 or v == 1 else v - 1, "", "", "f", "f"])
        write_csv(self.tmp / "struct.csv", ["book", "chapter", "verse", "verse_segment", "text_tradition", "omitted", "empty"], struct)
        dim = len(self.tb5) + 2
        def onehot(*ks):
            return json.dumps([1.0 if k in ks else 0.0 for k in range(dim)])
        nv = [[17, 5, cv(u)[1], "", "", onehot(k)] for k, u in enumerate(self.tb5)]
        ed = [[17, 5, 1, "", "", onehot(0, 1)]] + [[17, 5, n - 1, "", "", onehot(k)] for k, u in enumerate(self.tb5) for n in [cv(u)[1]] if n > 2]
        head = ["book", "chapter", "verse", "verse_segment", "text_tradition", "labse"]
        write_csv(self.tmp / "nv.csv", head, nv)
        write_csv(self.tmp / "ed.csv", head, ed)
        eds = json.loads((self.tmp / "data/editions.json").read_text())
        eds["editions"].append({"slug": "test", "title": "Test", "language": "en", "year": 2000})
        (self.tmp / "data/editions.json").write_text(json.dumps(eds))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_draft(self, **kw):
        draft_edition(self.tmp, "test", self.tmp / "struct.csv", self.tmp / "ed.csv", self.tmp / "nv.csv", **kw)

    def test_cli_writes_maps_and_drafts(self):
        self.run_draft()
        mp = json.loads((self.tmp / "data/maps/test/17-tb.json").read_text())
        dr = json.loads((self.tmp / "drafts/test/17-tb.json").read_text())
        first = next(v for v in mp["verses"] if v["ref"] == "5:1")
        self.assertEqual(first["units"], ["btu:tb.5.1", "btu:tb.5.2"])
        self.assertEqual(first["status"], "draft")
        self.assertNotIn("confidence", first)
        self.assertGreater(dr["confidence"]["5:1"], 0.9)
        self.assertEqual(json.loads((self.tmp / "data/maps/test/01-gn.json").read_text())["verses"][0]["status"], "rule")
        self.assertEqual(validate(self.tmp), [])

    def test_a_verse_printed_in_two_unlettered_parts_gets_numbered_refs(self):
        with open(self.tmp / "struct.csv", "a", newline="") as f:
            csv.writer(f).writerow([17, 14, 15, "", "", "f", "f"])
        self.run_draft()
        refs = [v["ref"] for v in json.loads((self.tmp / "data/maps/test/17-tb.json").read_text())["verses"]]
        self.assertIn("14:15", refs)
        self.assertIn("14:15#2", refs)
        self.assertEqual(validate(self.tmp), [])

    def test_vectors_are_matched_by_sort_order_when_given(self):
        # The Vulgate's Greek additions to Esther are many rows numbered 1:1: only sort_order tells them apart.
        from draft_alignment import read_vectors
        path = self.tmp / "so.csv"
        write_csv(path, ["book", "chapter", "verse", "verse_segment", "text_tradition", "sort_order", "labse"],
                  [[19, 1, 1, "", "GREEK", 10, "[1.0, 0.0]"], [19, 1, 1, "", "GREEK", 11, "[0.0, 1.0]"]])
        vecs = read_vectors(path)
        self.assertEqual(vecs[("sort_order", "10")], [1.0, 0.0])
        self.assertEqual(vecs[("sort_order", "11")], [0.0, 1.0])

    def test_copies_placed_in_nova_vulgata_order_lend_their_links_to_the_rows_they_name(self):
        # The Vulgate prints Tobit's (here: synthetic) addition as 14:16, after the book; the source also stores a copy
        # in place, labelled 5:2a, whose alt_ref names 14:16. The copy is aligned; 14:16 gets its link; the copy is
        # not in the edition's map.
        from align import draft_links
        from draft_alignment import fold_copies
        rows = [
            {"chapter": "5", "verse": "1", "verse_segment": "", "alt_ref": ""},
            {"chapter": "5", "verse": "2", "verse_segment": "a", "alt_ref": "14:16"},
            {"chapter": "14", "verse": "16", "verse_segment": "", "alt_ref": "14:16"},
        ]
        aligned, copies = fold_copies(rows)
        self.assertEqual([f"{r['chapter']}:{r['verse']}{r['verse_segment']}" for r in aligned], ["5:1", "5:2a"])
        self.assertEqual(copies, {"5:2a": "14:16"})

    def test_esthers_greek_text_of_the_hebrew_verses_corresponds(self):
        # An edition printing both texts: its Greek run's unlettered verses are the Septuagint's version of the
        # Masoretic verses the units are; its lettered additions are the same text; its Hebrew run is the same text.
        from draft_alignment import kind_for
        self.assertEqual(kind_for("est", "GREEK", "1:1@GREEK", "same", both=True), "corresponding")
        self.assertEqual(kind_for("est", "GREEK", "1:1a@GREEK", "same", both=True), "same")
        self.assertEqual(kind_for("est", "HEBREW", "1:1@HEBREW", "same", both=True), "same")
        # Without a Hebrew run (the Vulgate's Esther), the book's own kind stands.
        self.assertEqual(kind_for("est", "GREEK", "11:2@GREEK", "corresponding", both=False), "corresponding")
        self.assertEqual(kind_for("tb", "", "5:1", "same", both=False), "same")

    def test_only_the_books_asked_for_are_redrafted(self):
        self.run_draft()
        gn = self.tmp / "data/maps/test/01-gn.json"
        gn.write_text(gn.read_text().replace('"status": "rule"', '"status": "reviewed"', 1))
        reviewed = gn.read_text()
        self.run_draft(only={"tb"})
        self.assertEqual(gn.read_text(), reviewed)

    def test_corresponding_books_are_drafted_as_corresponding(self):
        self.run_draft(corresponding={"tb"})
        mp = json.loads((self.tmp / "data/maps/test/17-tb.json").read_text())
        self.assertEqual({v["kind"] for v in mp["verses"] if v["status"] == "draft"}, {"corresponding"})

    def test_drafts_file_refs_match_map_refs(self):
        self.run_draft()
        mp = json.loads((self.tmp / "data/maps/test/17-tb.json").read_text())
        dr = json.loads((self.tmp / "drafts/test/17-tb.json").read_text())
        drafts = {v["ref"] for v in mp["verses"] if v["status"] == "draft"}
        self.assertEqual(set(dr["confidence"]), drafts)

    def test_validator_rejects_a_draft_ref_unknown_to_the_map(self):
        self.run_draft()
        p = self.tmp / "drafts/test/17-tb.json"
        dr = json.loads(p.read_text())
        dr["confidence"]["99:1"] = 0.5
        p.write_text(json.dumps(dr))
        self.assertTrue(any("99:1" in e for e in validate(self.tmp)))


if __name__ == "__main__":
    unittest.main()
