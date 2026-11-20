"""Compare the units with the Nova Vulgata on vatican.va, chapter by chapter.

Usage: python3 scripts/check_vatican.py PAGES_DIR [--download]

PAGES_DIR holds the Nova Vulgata's book pages from vatican.va (with --download, they are fetched there first,
one request a second). For each chapter it reports:
- our verse numbers not found, in order, among the page's numbers;
- numbers our chapter skips that the page has;
- the numbers the Nova Vulgata prints in brackets without text ("(21)", "(10. 11)", "(16 17)", "( 6 )") that are
  not our `nv_omitted` units, and our `nv_omitted` units it does not print in brackets. (The Greek numbers in the
  Psalms' titles, "PSALMUS 51 (50)", are not such numbers.)

Expected differences, which are not errors:
- Bar 6:0, the unnumbered prescript of the Letter of Jeremiah;
- the one-chapter books, which have no chapter anchor on the page.
A few reports come from the page's markup (a number run into the next word, "1Cum", "2“ Fili"; typos: "0" for 40
in 1 Par 11, "(20 Plenitudo" for "20 Plenitudo" in Sir 1) and need reading against the page.
"""

import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://www.vatican.va/archive/bible/nova_vulgata/documents/"
INDEXES = ["nova-vulgata_vetus-testamentum_lt.html", "nova-vulgata_novum-testamentum_lt.html"]


def norm(t):
    return re.sub(r"[^a-z]", "", t.lower())


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CBTUDR check)"})
    path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    time.sleep(1)


def pages(d, download):
    """Book page file names by normalized Latin title."""
    titles = {}
    for f in INDEXES:
        if download and not (d / f).exists():
            fetch(BASE + f, d / f)
        s = (d / f).read_text(encoding="latin-1")
        for h, t in re.findall(r'href="(nova-vulgata_[nv]t_[^"]+)"[^>]*>(.*?)</a>', s, re.S | re.I):
            titles[norm(html.unescape(re.sub(r"<[^>]+>", "", t)))] = h
            if download and not (d / h).exists():
                fetch(BASE + h, d / h)
    # vatican.va titles Philemon "Epistulam ad Philemonem".
    titles.setdefault(norm("Epistula ad Philemonem"), titles.get(norm("Epistulam ad Philemonem")))
    return titles


BRACKETED = re.compile(r"\(\s*(\d+(?:[.\s]+\d+)*)\s*\)")
PSALM_TITLE = re.compile(r"PSALMUS\s+\d+\s*\(\s*\d+\s*\)")


def bracketed(body):
    """The verse numbers printed in brackets without text: "(10. 11)" gives ["10", "11"]."""
    body = PSALM_TITLE.sub(" ", body)
    return [n for m in BRACKETED.finditer(body) for n in re.split(r"[.\s]+", m[1])]


def chapter_bodies(path):
    """Each chapter's text on the page, markup removed, by chapter number."""
    s = html.unescape(path.read_text(encoding="latin-1")).replace("\xa0", " ").replace("\xad", " ")
    parts = re.split(r'<a name="(?:PSALMUS )?(\d+)"\s*>', s)
    return {int(parts[i]): re.sub(r"<[^>]+>", " ", parts[i + 1]) for i in range(1, len(parts), 2)}


def tokens(body):
    """The verse numbers printed in a chapter, in order; bracketed numbers, "( 6 )" included, are not among them."""
    return re.findall(r"(?<![\w,.:;(])(\d+[a-z]*)(?=\s)", BRACKETED.sub(" ", body))


def in_order(labels, tokens):
    missing, k = [], 0
    for lab in labels:
        try:
            k = tokens.index(lab, k) + 1
        except ValueError:
            missing.append(lab)
    return missing


def skipped(labels, tokens):
    nums = [int(re.match(r"\d+", lab)[0]) for lab in labels]
    return [str(n) for a, b in zip(nums, nums[1:]) for n in range(a + 1, b) if str(n) in tokens]


def omitted_differences(ours, printed):
    """The bracketed numbers that are not nv_omitted units, and the nv_omitted units not printed in brackets."""
    return [n for n in printed if n not in ours], [v for v in ours if v not in printed]


def main(d, download):
    root = Path(__file__).resolve().parent.parent
    titles = pages(d, download)
    total = differ = 0
    for b in json.loads((root / "data/books.json").read_text())["books"]:
        page = titles.get(norm(b["label_la"]))
        if not page:
            print(f"{b['segment']}: no vatican.va page titled {b['label_la']}")
            continue
        bodies = chapter_bodies(d / page)
        vch = {ch: tokens(body) for ch, body in bodies.items()}
        ours, omitted = {}, {}
        for u in json.loads((root / f"data/units/{b['number']:02d}-{b['segment']}.json").read_text())["units"]:
            if "parent" in u or "+" in u["id"]:
                continue
            _, ch, v = u["id"].split(":")[1].split(".")[:3]
            # An nv_omitted unit is checked against the bracketed numbers, not among the verse numbers.
            if u.get("nv_omitted"):
                omitted.setdefault(int(ch), []).append(v)
            else:
                ours.setdefault(int(ch), []).append(v)
        for ch, labels in sorted(ours.items()):
            total += 1
            toks = vch.get(ch)
            if toks is None:
                differ += 1
                print(f"{b['segment']} {ch}: no such chapter on the page")
                continue
            miss, extra = in_order(labels, toks), skipped(labels, toks)
            unmarked, unprinted = omitted_differences(omitted.get(ch, []), bracketed(bodies[ch]))
            differ += bool(miss or extra or unmarked or unprinted)
            if miss or extra:
                print(f"{b['segment']} {ch}: not found in order {miss}; skipped by us, on the page {extra}")
            if unmarked or unprinted:
                print(f"{b['segment']} {ch}: in brackets on the page, not nv_omitted {unmarked}; "
                      f"nv_omitted, not in brackets on the page {unprinted}")
    print(f"{total} chapters, {differ} with differences")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--download" in sys.argv)
