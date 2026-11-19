# CBTUDR Schema Proposal

**Status:** Draft, pending CETF review. Every identifier is a draft until release `v1.0.0`; from then on, a published identifier never changes.
**Registry:** Common Biblical Textual Unit Data Repository (`CatholicOS/cbtudr`).

## 0. Purpose

Bible editions divide the same text differently:

- Chapters begin and end at different places (Gn 31:55 in the Vulgate is Gn 32:1 in the Hebrew numbering).
- A verse of one edition is two in another (VGCL Tb 5:3-4 is CEI 2008 Tb 5:4).
- Verses are printed out of order (CEI 2008 Is 10: 17, 18a, 19, 18b).
- Whole recensions differ (the Vulgate's Tobit is longer than the Greek text modern editions follow).

A reference such as "Tb 5:4" therefore means different text in different editions.

CBTUDR gives each **textual unit** a canonical identifier, `btu:`, independent of any edition's numbering. It also publishes, for each edition, which units each of its verses contains. With this, any application can:

- line up two editions verse by verse, even across chapter boundaries;
- carry a reference from one edition to another;
- define a passage, such as a lectionary reading, once, for every edition.

The registry holds identifiers and verse structure only, **never Bible text**. Mapping a copyrighted edition records how it is numbered, not what it says.

### 0.1 Relation to the CDCF URI scheme

[`cdcf-uri-scheme`](https://github.com/CatholicOS/cdcf-uri-scheme) identifies Scripture **references**, `cdcf:verse/<osis>/<chapter>/<verse>`: a citation, read in some versification. Its open issue on versification asks for a verse-level mapping between numberings, sourced from a dataset; CBTUDR is meant to be that dataset.

A `btu:` identifier names a piece of **text**, whatever an edition calls it. Resolving a `cdcf:verse/` reference in a given edition therefore goes through that edition's mapping (§4). `data/books.json` carries each book's OSIS code for the crosswalk.

Following [cdcf-uri-scheme#13](https://github.com/CatholicOS/cdcf-uri-scheme/issues/13), the full identifier is `cdcf:btu:tb.5.4`: the scheme holds the grammar, this registry the vocabulary.

## 1. The reference: the Nova Vulgata

The units are seeded from the verses of the **Nova Vulgata** (*Nova Vulgata Bibliorum Sacrorum Editio*, 1979; 2nd ed. 1986). The Church names it as the point of reference for translations used in the liturgy (*Liturgiam authenticam*, 2001). The numbering is the one published on [vatican.va](https://www.vatican.va/archive/bible/nova_vulgata/documents/nova-vulgata_index_lt.html), and where a source differs from it, vatican.va governs.

Each Nova Vulgata verse is one unit to begin with. Units are then:

- **split** where an edition divides a Nova Vulgata verse;
- **added** for text the Nova Vulgata does not have.

### 1.1 How the seed was made

The seed is the verse structure (numbers only, no text) of BibleGet's NVBSE edition, compared chapter by chapter with vatican.va (`scripts/check_vatican.py`). Where the two differ, `scripts/nova_vulgata_corrections.json` records how, and the seed follows vatican.va:

- **Verses printed in brackets, without text.** The Nova Vulgata keeps the number of a verse the critical text omits and prints it in brackets: "… ab omni malo. (16 17) 18 Super scutum …" (Sir 29). There are 31 such numbers, for example 1 Reg 15:6, Mt 17:21, Act 8:37, and twelve in Sirach.
  - Each is a unit marked `"nv_omitted": true`.
  - The Nova Vulgata's own mapping lists it as absent.
  - Editions that print text there (the Clementine Vulgate, the Douay-Rheims) map that text to it.
- **Verses the source lacked:** Ez 40:15, Act 24:8, Sir 1:20. Each is a unit in its place.
- **Printed order:** the Nova Vulgata prints Ez 40:42a, 43a, 42b, 43b, and the units follow that order.

Other features of the Nova Vulgata the seed keeps:

- **The Psalms** are numbered as the Nova Vulgata numbers them: the Hebrew number first, with the Greek number in brackets ("PSALMUS 51 (50)"), and the superscription counted as verse 1.
- **Esther** is one book: the Hebrew-based text with the Greek additions as lettered verses (`btu:est.1.1a`…). The units follow the book's reading order.
- **Daniel 3:24-90** (the Greek additions) are numbered within chapter 3, as in the Nova Vulgata.
- **Baruch 6:0** is the unnumbered prescript of the Letter of Jeremiah ("Exemplum epistulae …"), printed before 6:1.

## 2. Identifier grammar

```abnf
unit-id   = "btu:" book "." chapter "." verse *( "." part ) [ "+" extra *( "." part ) ]
book      = 1*( lowercase / digit )          ; §2.1
chapter   = nonzero *digit
verse     = ( "0" / nonzero *digit ) *lowercase   ; the Nova Vulgata's own lettered verses (Est 1:1a, 4:17aa)
part      = nonzero *digit                   ; a split, numbered 1, 2, … in reading order
extra     = nonzero *digit                   ; text the Nova Vulgata lacks, after the preceding unit
nonzero   = %x31-39
```

`^btu:[a-z0-9]+\.[1-9]\d*\.(0|[1-9]\d*)[a-z]*(\.[1-9]\d*)*(\+[1-9]\d*(\.[1-9]\d*)*)?$`

Examples:

| id | what it is |
|---|---|
| `btu:tb.5.4` | Nova Vulgata Tobit 5:4 |
| `btu:tb.5.4.1`, `btu:tb.5.4.2` | its two parts, once an edition divides it |
| `btu:tb.5.4.1.2` | the second part of its first part |
| `btu:est.1.1a` | Nova Vulgata Esther 1:1a (a lettered verse of the Greek additions, not a split) |
| `btu:mt.17.21` | the verse number the Nova Vulgata prints in brackets, without text (`nv_omitted`) |
| `btu:tb.5.4+1` | text the Nova Vulgata lacks, placed after Tobit 5:4 (the Vulgate's longer Tobit) |
| `btu:tb.5.4+1.2` | the second part of that unit |

Splits are numbered, not lettered, so that a split (`btu:tb.5.4.1`) can never be mistaken for one of the Nova Vulgata's lettered verses (`btu:est.1.1a`).

The identifier records **where the unit was first created**, for readability. It is not a reference and must not be parsed as one:

- `btu:tb.5.4` is "the unit that began as Nova Vulgata Tb 5:4", not "Tb 5:4 in your edition".
- Translating between numberings is the job of the mapping files (§4).

### 2.1 Books

`data/books.json` lists the 73 books of the Catholic canon. Each record carries:

- its **number**, 1-73, in the order of the printed Nova Vulgata, with 1-2 Maccabees after Esther (vatican.va lists them at the end of the Old Testament);
- **`abbr_la`**: the book's Latin abbreviation as the Holy See prints it (`1 Sam`, `Eccli`, `Apc`), and **`segment`**, the same lowercased with no spaces (`1sam`, `eccli`, `apc`), which is the book's part of every identifier;
- its **OSIS** 2.1.1 and **USFM** 3 codes;
- its **Latin title**, as on vatican.va;
- its **English name**.

**Source of the abbreviations.** The printed Nova Vulgata's own list is not online. The abbreviations are taken from the list the Holy See publishes for the Latin *Catechismus Catholicae Ecclesiae*, [*Abbreviationes pro Sacra Scriptura*](https://www.vatican.va/archive/catechism_lt/abbrev_lt.htm), which gives the same Latin book titles as the Nova Vulgata. The Nova Vulgata's own *Praenotanda* cite books with the same abbreviations ("cfr. Eccli 12, 15", "Dt 32, 41", "Gn 19, 28").

The list abbreviates some names by contraction, keeping their first and last letters: `Il` (I*oe*l), `Apc` (Ap*o*c*alypsis*), `Ids` (I*u*d*a*s, Jude). The registry follows it as printed.

The list also has misprints, which are being reported to the Dicastery for Communication; the registry does not follow them:

- `3 Io` is glossed *Epistula II Ioannis* (for III).
- Some titles are misspelt (*Deutoronomii*, *Nahemiae*, *Liher Iudith*). The registry's titles are those of the Nova Vulgata on vatican.va.

**USFM and OSIS divide some books differently.** The codes are the Catholic book's; consumers converting to or from USFM or OSIS need to know four differences:

- **Baruch 6**, the Letter of Jeremiah, is a book of its own in both: USFM `LJE`, OSIS `EpJer`.
- **The Greek parts of Esther** are USFM `ESG` and OSIS `AddEsth`.
- **The Greek parts of Daniel:**
  - OSIS has separate books: `PrAzar` (Dn 3:24-90), `Sus` (Dn 13) and `Bel` (Dn 14);
  - USFM has `DAG` (Greek Daniel), `S3Y`, `SUS` and `BEL`.
- **The Psalms** have the same code, but different versifications.

## 3. Units

`data/units/NN-<book>.json`, one file per book, lists the units in Nova Vulgata reading order:

```json
{"book": "tb", "units": [
  {"id": "btu:tb.5.4"},
  {"id": "btu:tb.5.4.1", "parent": "btu:tb.5.4"},
  {"id": "btu:tb.5.4.2", "parent": "btu:tb.5.4"},
  {"id": "btu:tb.5.4+1", "after": "btu:tb.5.4"}
]}
```

Rules:

1. **A parent is exactly its children, in order.**
   - A link to a parent stays valid when the parent is split, so nothing that already links to it needs remapping.
   - A child's identifier is its parent's plus a part number.
   - A parent has at least two children.
2. **A split is made only when an edition needs it.** The commit that makes the split says which edition and verse required it.
3. **An added unit** (`+n`) is placed after an existing unit, named in `after`, which fixes its place in the Nova Vulgata order.
4. **`nv_omitted: true`** marks a unit whose number the Nova Vulgata prints without text (§1.1).

## 4. Edition mappings

`data/editions.json` lists the mapped editions. Each has:

- a slug (`nvbse`, `cei2008`, `vgcl`…), local to this registry until a Bible editions registry exists;
- its title, language and year.

`data/maps/<edition>/NN-<book>.json` maps each of that edition's verses, in the edition's reading order, to the units it contains:

```json
{"edition": "vgcl", "book": "tb", "verses": [
  {"ref": "5:3", "units": ["btu:tb.5.4.1"], "kind": "corresponding", "status": "reviewed"},
  {"ref": "5:4", "units": ["btu:tb.5.4.2"], "kind": "corresponding", "status": "reviewed"}
]}
```

### 4.1 Fields

- **`ref`** is the edition's own verse reference, `chapter ":" verse [segment] ["@" tradition]`. For example `10:18a`, or `1:1a@GREEK` in an edition that prints both texts of Esther.
- **`units`** is an ordered list of units. A verse may cover several units, and may cross a Nova Vulgata verse or chapter boundary.
- **`kind`:**
  - `same` means the same text, re-divided or renumbered.
  - `corresponding` means a different recension or translation base: the passage corresponds but is not the same text.
- **`status`:**
  - `rule` means generated by a documented rule (§5).
  - `draft` means proposed by a tool, not yet reviewed.
  - `reviewed` means checked by a reviewer. Who reviewed it, and when, is in the git history.
- **`omitted: true`** marks a verse number the edition prints without text. Such a verse has no units.
- **`primary`** names the tradition whose run must cover the whole book, when the edition prints more than one (Esther: `GREEK`).
- **`absent`** lists the units the edition does not have.

### 4.1.1 Drafts

`drafts/<edition>/NN-<book>.json` accompanies a map that has drafts:

```json
{"edition": "vgcl", "book": "tb",
 "stretches": [{"id": 3, "verses": ["5:1", "5:2"], "units": ["btu:tb.5.1", "btu:tb.5.2"], "uncovered": []}],
 "confidence": {"5:1": 0.88, "5:2": 0.76}}
```

- A **stretch** is a run of the edition's verses, and of units, between two links made by rule. A reviewer may relink a draft only to units of its own stretch.
- The **confidence** (0-1) is the similarity on which the link was proposed.
- **`uncovered`** lists the stretch's units that no verse was linked to.

Drafts files are working material for review. They leave the registry as links are reviewed.

### 4.2 Invariants

These are checked by `scripts/validate.py`:

1. Every `ref` appears once.
2. **A verse covers whole units only.** A boundary that falls inside a unit splits that unit first (§3, rule 2).
3. Within one tradition's run, no unit is covered twice by links of the same text (`kind: same`) with status `rule` or `reviewed`, whether directly or through an ancestor.
   - A **draft** may share a unit with another verse: it is not decided yet. The reviewer either accepts the grouping, which makes a split necessary, or relinks.
   - **Corresponding** passages may share a unit for good. A different recension (the Vulgate's Tobit) has no common text to split: the Clementine Vulgate's Tb 5:3 and 5:4 both correspond to the Nova Vulgata's Tb 5:4.
4. Every unit of the book is covered by the edition's primary run, or listed in `absent`.
5. An edition's own order is the order of its `verses`; units carry only the Nova Vulgata's order.

## 5. How links are made

1. **Same reference.** For most of the Bible, edition verse `c:v` covers `btu:<book>.c.v`. Status `rule`.
2. **Documented versification differences**, status `rule`, each listed with the editions it applies to:
   - the chapter-boundary cases between the Hebrew and Vulgate numberings (Gn 31:55 = Gn 32:1, Joel in 3 or 4 chapters…);
   - the Psalms;
   - the Greek parts of Esther and Daniel.
3. **Drafted alignments** for books whose text differs (Tobit, Job, Sirach, Greek Esther, Exodus 40).
   - A tool proposes links by aligning verses in reading order on multilingual sentence embeddings, and gives each link a confidence.
   - Each edition is aligned against the Nova Vulgata.
   - A link stays `draft` until a reviewer accepts or corrects it; it is then `reviewed`.

## 6. Using the registry

- **Two verses correspond** when their units overlap, a parent counting as all of its descendants. A comparison view joins each group of overlapping verses into one row.
- **An edition's chapter or pericope** is the set of units its verses cover. Chapters and pericopes are not units and get no identifiers (§7).
- A verse whose units are split across two of another edition's chapters belongs to both.

## 7. Not in this version

- **Named passages** (the Beatitudes, lectionary readings): spans over units with identifiers of their own. They will be added when the lectionary work begins.
- **Identifiers for editions** beyond the local slugs.

## 8. Releases and licences

- The registry is released as tagged versions (`v0.1.0`…). Consumers load a tag, never a branch.
- From `v1.0.0`, a release never removes or renumbers a unit; a unit may only gain children.

The licences follow the proposal open in every CDCF registry (e.g. [CatholicOS/crpdr#2](https://github.com/CatholicOS/crpdr/issues/2)):

| Part | Licence |
|---|---|
| `data/`: the identifiers, the units and the edition mappings | CC0 1.0 (`LICENSE-CC0`) |
| `docs/` and `registry/` | CC BY-ND 4.0 (`LICENSE`) |
| `scripts/` | Apache 2.0 (`scripts/LICENSE`) |

## 9. Open questions

The questions for the committee are tracked as issues:

- [#2](https://github.com/CatholicOS/cbtudr/issues/2): check the book abbreviations (§2.1) against the printed Nova Vulgata, and decide whether to keep its contractions (`Il`, `Ids`, `Apc`).
- [#3](https://github.com/CatholicOS/cbtudr/issues/3): edition identifiers, through a Common Bible Edition Data Repository (CBEDR) with cross-references to the identifiers already in use.
- [#4](https://github.com/CatholicOS/cbtudr/issues/4): how to identify unnumbered text, such as Bar 6:0 and the Psalm superscriptions.
