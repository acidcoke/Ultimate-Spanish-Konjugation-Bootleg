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
| `python -m usc build --tts` | same deck, with the Spanish form read aloud |
| `python -m usc build --no-hypothetical` | same deck, without the hypothetical regular forms |
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

## Text to speech

`--tts` builds a variant whose cards say the answer -- the conjugated Spanish
form -- through Anki's built-in text to speech (Anki 2.1.20+, AnkiDroid
2.16+, AnkiMobile; it uses the voices installed on the device, so nothing is
downloaded and the deck still ships no media):

```sh
PYTHONPATH=src python -m usc build --tts -o dist/Ultimate_Spanish_Conjugation_TTS.apkg
PYTHONPATH=src python -m usc build --tts --tts-voices Apple_Mónica,Microsoft_Helena
PYTHONPATH=src python -m usc build --tts --tts-lang es_MX --tts-speed 0.8
```

The variant adds a `Speech` field holding the bare form, and puts
`{{#Speech}}<div class="tts">{{tts es_ES:Speech}}</div>{{/Speech}}` under the
answered sentence on the back:

* the front is left untouched -- speaking the answer there would give it away;
* a form with several accepted variants is spoken as a list, `fuera | fuese`
  becoming `fuera, fuese`, so the voice pauses between them;
* the seven orientation cards, whose text is English, stay silent: their
  `Speech` field is empty and the `{{#Speech}}` conditional drops the tag.

### Voices, and AnkiDroid

The `{{tts}}` tag needs Anki 2.1.20+, AnkiMobile 2.0.56+ or **AnkiDroid
2.17+**, and it speaks through the voices installed on the device -- on
Android, a TTS engine with Spanish data (Settings › Accessibility ›
Text-to-speech output). No voice for the language means a silent card and a
"no voice found" error, not a fallback.

`--tts-voices` names are platform specific (`Apple_Mónica` on macOS/iOS,
`Microsoft_Helena` on Windows); Anki picks the first one in the list that
exists on the device. Build **without** `--tts-voices` for a deck that also
works on Android: the language alone (`es_ES`) lets each platform pick its
own Spanish voice. If you do pin voices, list one per platform you use.

Nothing else changes: the `UUID`, `Prompt`, `Similar` and `Notes` fields, the
note guids, the ids, the sort fields and the checksums are the same as in the
published deck, so the variant updates an existing collection rather than
duplicating it. Because it adds a field to the note type, importing it on top
of the original deck asks Anki to update that note type; on Anki versions old
enough to refuse a changed note type (pre-2.1.50), remove the old deck and
its note type first.

`--tts` is a build option, not a change to the source data: `python -m usc
build` without it still reproduces the published deck 1:1, and the test suite
checks both.

## Dropping the hypothetical regular forms

1296 of the notes explain an irregularity by naming the form the verb *would*
have if it were regular:

> **Irregular form**: the hypothetical regular form *so* is incorrect.

`--no-hypothetical` removes that clause and keeps the verdict:

> **Irregular form**.

> The forms *fuera* and *fuese* are both **irregular**.

The orientation card that shows off the note format carries the same sentence
as an example, so it is trimmed too — afterwards no card in the deck displays
a form that does not exist. Everything else is untouched: guids, ids, tags,
timestamps and the other fields are the same as in the published deck, so the
variant updates an existing collection instead of duplicating it.

The options compose, and both are build options rather than edits to `data/`:

```sh
PYTHONPATH=src python -m usc build --no-hypothetical --tts -o dist/deck.apkg
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
  tts.py           the optional text-to-speech variant
  variants.py      optional content variants (--no-hypothetical)
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
