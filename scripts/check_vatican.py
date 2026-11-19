"""Compare the units with the Nova Vulgata on vatican.va, chapter by chapter.

Usage: python3 scripts/check_vatican.py PAGES_DIR [--download]

PAGES_DIR holds the Nova Vulgata's book pages from vatican.va (with --download, they are fetched there first,
one request a second). For each chapter it reports:
- our verse numbers not found, in order, among the page's numbers;
- numbers our chapter skips that the page has.

Expected differences, which are not errors:
- the numbers the Nova Vulgata prints in brackets without text (our `nv_omitted` units): the check skips
  numbers after a bracket;
- Bar 6:0, the unnumbered prescript of the Letter of Jeremiah;
- the one-chapter books, which have no chapter anchor on the page.
A few reports come from the page's markup (a number run into the next word, "1Cum"; a typo, "0" for 40 in
1 Par 11) and need reading against the page.
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


def chapters(path):
    s = html.unescape(path.read_text(encoding="latin-1")).replace("\xa0", " ").replace("\xad", " ")
    parts = re.split(r'<a name="(?:PSALMUS )?(\d+)"\s*>', s)
    out = {}
    for i in range(1, len(parts), 2):
        body = re.sub(r"<[^>]+>", " ", parts[i + 1])
        out[int(parts[i])] = re.findall(r"(?<![\w,.:;(])(\d+[a-z]*)(?=\s)", body)
    return out


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


def main(d, download):
    root = Path(__file__).resolve().parent.parent
    titles = pages(d, download)
    total = differ = 0
    for b in json.loads((root / "data/books.json").read_text())["books"]:
        page = titles.get(norm(b["label_la"]))
        if not page:
            print(f"{b['segment']}: no vatican.va page titled {b['label_la']}")
            continue
        vch = chapters(d / page)
        ours = {}
        for u in json.loads((root / f"data/units/{b['number']:02d}-{b['segment']}.json").read_text())["units"]:
            if "parent" in u or "+" in u["id"]:
                continue
            _, ch, v = u["id"].split(":")[1].split(".")[:3]
            ours.setdefault(int(ch), []).append(v)
        for ch, labels in sorted(ours.items()):
            total += 1
            toks = vch.get(ch)
            if toks is None:
                differ += 1
                print(f"{b['segment']} {ch}: no such chapter on the page")
                continue
            miss, extra = in_order(labels, toks), skipped(labels, toks)
            if miss or extra:
                differ += 1
                print(f"{b['segment']} {ch}: not found in order {miss}; skipped by us, on the page {extra}")
    print(f"{total} chapters, {differ} with differences")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--download" in sys.argv)
