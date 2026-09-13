# Ultimate Spanish Conjugation — deck generator

Python that generates the *Ultimate Spanish Conjugation* Anki deck
([AnkiWeb 638411848](https://ankiweb.net/shared/info/638411848)) from plain
source data, and proves the result matches the published deck 1:1.

```
$ PYTHONPATH=src python -m usc build
notes: 4246  cards: 4246
wrote dist/Ultimate_Spanish_Conjugation.apkg (779822 bytes)

$ PYTHONPATH=src python -m usc verify Ultimate_Spanish_Conjugation.apkg
generated collection fingerprint: 1d3dfce93b3381116a46abdba424e15db1d6c43247aa404b0df290829af9fa34
reference collection fingerprint: 1d3dfce93b3381116a46abdba424e15db1d6c43247aa404b0df290829af9fa34

identical: same schema, same rows, same package metadata
```

Standard library only — no Anki, no `genanki`, no third-party packages.

## What "1:1" means here

`python -m usc verify` compares the generated `.apkg` with the reference one
and reports every difference:

* **the package** — same zip entries in the same order (`collection.anki2`,
  `media`), same compression method, same timestamps, same unix permissions;
* **the schema** — the `sqlite_master` of both collections is identical;
* **the content** — every row of `col`, `notes`, `cards`, `revlog` and
  `graves` is identical, column by column. That covers the note type, deck,
  deck options and collection configuration JSON (compared as stored
  strings), and, for all 4246 notes, the guid, note id, modification time,
  usn, tag string, the four field values, the sort field and the checksum —
  plus each note's card with its id, deck, due position and flags.

The one thing that is *not* byte-identical is the physical layout of
`collection.anki2` inside the zip. The reference file was written by Anki's
own SQLite build (3.31.0): its page ordering, its two free pages left over
from the deck's editing history, and the "last written by" field in the file
header belong to that build and cannot be reproduced by another SQLite
version. The generated database holds the same 2069 content pages and the
same rows — which is all Anki reads back on import — so both files produce
exactly the same collection. The fingerprint printed by `verify` is a sha256
over the schema and every row, and is independent of that page layout.

## Commands

| command | what it does |
| --- | --- |
| `python -m usc build [-o OUT]` | build the `.apkg` from `data/` and `assets/` |
| `python -m usc verify REF [-g GEN]` | compare a generated `.apkg` with a reference one |
| `python -m usc extract REF` | rebuild `data/` and `assets/` from a reference `.apkg` |

Run them from the repository root with `src/` on the path:

```sh
PYTHONPATH=src python -m usc build
PYTHONPATH=src python -m usc verify path/to/Ultimate_Spanish_Conjugation.apkg
```

Tests:

```sh
PYTHONPATH=src python -m unittest discover -s tests
# and, against the published deck:
USC_REFERENCE_APKG=path/to/Ultimate_Spanish_Conjugation.apkg \
    PYTHONPATH=src python -m unittest discover -s tests
```

## Layout

```
src/usc/
  anki_schema.py   the Anki 2.1 (schema 11) DDL, verbatim
  source.py        loading/saving the source data
  render.py        note fields <-> structured records (exact inverses)
  collection.py    writing collection.anki2, sort fields, checksums
  packaging.py     writing the .apkg zip
  build.py         source data -> .apkg
  extract.py       reference .apkg -> source data, with a per-note round-trip check
  verify.py        1:1 comparison of two .apkg files
data/
  collection.json      col row, ids, note type, deck, deck options, zip metadata
  verbs.json           the 72 verbs and the material every note of a verb repeats
  prompt_templates.json  343 sentence templates, one per tense/person/variant
  notes.jsonl          4246 note records, in deck order
assets/
  card.css, card_front.html, card_back.html   the note type's styling and template
```

## How the deck is put together

**The note type** (`Ultimate Spanish Conjugation [Ankiweb]`) is a cloze type
with four fields — `UUID`, `Prompt`, `Similar`, `Notes` — sorting on
`Prompt`. Its stylesheet and card template live in `assets/`; `collection.json`
refers to them through `@file:` sentinels, so the note type JSON keeps the
exact key order of the original and is written back byte for byte.

**A note record** in `data/notes.jsonl` carries only what is specific to that
note:

```json
{"guid": "m05T}gc0C;", "uuid": "610fe216-7c31-414b-91fb-19192740ded1", "verb": "ser",
 "tags": ["ends_in_er", "extreme_irregularity", "irregular_form", "irregular_verb",
          "presente", "ser", "yo"],
 "prompt": {"answer": "soy", "cloze_hint": "…ser…", "hint": "(consciente de ello)",
            "hint_quote": "'", "template": "presente.yo.01"},
 "similar": [],
 "notes": [{"section": "regularity", "html": "<br><span class=\"note_feature\">Irregular form</span>: …"},
           "verb_line", "family"],
 "mod": 1599309962, "usn": 0, "card_mod": 1600165204, "card_usn": 7310}
```

* `prompt.template` names a sentence in `prompt_templates.json`, where the
  answer and the parenthetical hint are `⟪cloze⟫` and `⟪hint⟫` slots — for
  instance `⊙ Ahora mismo, ⊙<br><br><span class="cloze_pronoun">yo</span>
  <span class="sp_verb">⟪cloze⟫</span> ⟪hint⟫`. Templates are named
  `tense.person.NN`, the variants covering the idioms, proverbs and
  in-the-wild sentences that some verbs use instead of the stock sentence.
* `similar` is the list of same-family verbs shown on the back, as
  `["conj", form, infinitive]`, `["inf", infinitive]` or `["tu_vos", header]`
  items; the DLE links are rebuilt from the infinitive.
* `notes` is the ordered commentary: per-note `SECTION_*` spans plus the two
  pieces that repeat across all 59 notes of a verb — `verb_line` (the DLE
  link and the irregularity summary) and `family` — which are stored once per
  verb in `verbs.json`.

**Derived at build time**, never stored per note:

* note id, card id and the card's `due` position — consecutive in the deck,
  so they come from the bases in `collection.json` plus the note's position;
* the sort field `sfld` — the `Prompt` field with its HTML stripped, using
  Anki's own `stripHTMLMedia` rules;
* the checksum `csum` — the first 8 hex digits of the sha1 of field 0;
* the tag string — Anki's space-separated form, `" tag1 tag2 "`;
* the card row — one new card per note, `ord`/`type`/`queue`/`ivl`/`factor`
  all zero, in deck `1596992405271`.

## Regenerating the source data

`data/` and `assets/` were produced from the published deck by the extractor:

```sh
PYTHONPATH=src python -m usc extract path/to/Ultimate_Spanish_Conjugation.apkg
```

The extractor is the inverse of the builder and checks itself: it asserts the
structural invariants (one card per note, consecutive ids and due positions,
a single note type, untouched scheduling columns), then re-renders every note
from what it just wrote and compares the resulting `notes` and `cards` rows
with the reference — so a parse that loses anything fails there rather than
in the built deck.

## Credits

The deck itself — its sentences, verb analysis and commentary — is the work
of its author; see the
[deck manual](http://www.asiteaboutnothing.net/w_ultimate_spanish_conjugation.html).
This repository is only the generator that rebuilds the published package
from that content.
