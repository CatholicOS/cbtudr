# CBTUDR

The home of the **Common Biblical Textual Unit Data Repository**, curated by the
**Catholic Engineering Task Force** of the
[Catholic Digital Commons Foundation](https://github.com/CatholicOS).

## What is CBTUDR?

Bible editions divide the same text differently:

- Chapters begin at different places: Genesis 31:55 in the Vulgate is Genesis 32:1 in the Hebrew numbering.
- One edition's verse is two in another: the Clementine Vulgate's Tobit 5:3-4 is the CEI 2008's Tobit 5:4.
- Some editions print verses out of order.
- Whole books follow different recensions.

So "Tobit 5:4" is not the same text in every Bible.

CBTUDR gives each **textual unit** a canonical, stable identifier, independent of any edition's numbering:

```text
btu:tb.5.4        the unit that is Nova Vulgata Tobit 5:4
btu:tb.5.4.1      its first part, once some edition divides it
btu:tb.5.4+1      text the Nova Vulgata lacks, placed after Tobit 5:4
```

For each edition, the registry then publishes which units each of its verses contains. With it, a Bible application can:

- line up two editions verse by verse, even across chapter boundaries;
- carry a reference from one edition to another;
- define a passage once for every edition.

The registry holds **identifiers and verse structure only, never Bible text**, so it can map copyrighted editions as freely as public-domain ones.

## Why the Nova Vulgata?

The units are seeded from the verses of the **Nova Vulgata**, which the Church names as the point of reference for translations used in the liturgy (*Liturgiam authenticam*, 2001). Its numbering, as published on [vatican.va](https://www.vatican.va/archive/bible/nova_vulgata/documents/nova-vulgata_index_lt.html), defines the first units; editions that divide the text more finely split them, and text the Nova Vulgata lacks gets units of its own.

The full design, the identifier grammar and the open questions for the committee are in [docs/schema-proposal.md](docs/schema-proposal.md). **All identifiers are drafts pending committee review** until release `v1.0.0`.

## Repository contents

- [`data/books.json`](data/books.json): the 73 books of the Catholic canon. Each has its number, identifier segment, OSIS code, and Latin and English names.
- [`data/units/`](data/units/): one file per book, listing the book's units in Nova Vulgata order.
- [`data/editions.json`](data/editions.json) and [`data/maps/<edition>/`](data/maps/): each mapped edition, and the units each of its verses contains.
- [`registry/books.md`](registry/books.md): the books as a human-readable table, with their unit counts.
- [`docs/schema-proposal.md`](docs/schema-proposal.md): the schema, the grammar, how the seed was made, and the open questions.
- [`scripts/`](scripts/):
  - `validate.py` checks the data against the schema's rules (`python3 scripts/validate.py`);
  - `generate_registry.py` regenerates the table;
  - `check_vatican.py` compares the units with vatican.va;
  - `seed_nova_vulgata.py` made the seed.

  Tests: `python3 -m unittest discover -s scripts`.

## Status

- `v0.1` (this seed): the units of all 73 books, and the Nova Vulgata's own mapping.
- Next:
  - the mappings of further editions, by rule where their numbering differs in a documented way (chapter boundaries, the Psalms, Esther, Daniel);
  - drafted and reviewed alignments where their text differs (Tobit, Job, Sirach, Greek Esther, Exodus 40).

## Relationship to other CDCF work

- **The [CDCF URI scheme](https://github.com/CatholicOS/cdcf-uri-scheme)** identifies Scripture references (`cdcf:verse/…`), and its open versification issue asks for a verse-level mapping between numberings. This registry is meant to provide it. Under [cdcf-uri-scheme#13](https://github.com/CatholicOS/cdcf-uri-scheme/issues/13), a unit's full identifier is `cdcf:btu:tb.5.4`.
- **[BibleGet I/O](https://github.com/BibleGet-I-O)** is the first consumer: it uses these units to line up editions in its comparison view.

## Licences

The licensing follows the proposal open in every CDCF registry (e.g. [CatholicOS/crpdr#2](https://github.com/CatholicOS/crpdr/issues/2)):

| Part | Licence |
|---|---|
| `data/`: identifiers, units and edition mappings | [CC0 1.0](LICENSE-CC0) |
| `docs/` and `registry/` | [CC BY-ND 4.0](LICENSE) |
| `scripts/` | [Apache 2.0](scripts/LICENSE) |
