# Ultimate Spanish Conjugation — deck generator

Python that generates the *Ultimate Spanish Conjugation* Anki deck
([AnkiWeb 638411848](https://ankiweb.net/shared/info/638411848)) from plain
source data. One command builds it ([GENERATE.md](GENERATE.md)):

```
$ PYTHONPATH=src python -m usc build
hypothetical regular forms: dropped
text-to-speech: {{tts es_ES:Speech}}
notes: 4246  cards: 4246
wrote dist/Ultimate_Spanish_Conjugation.apkg (783785 bytes)
```

That is the customised deck: no hypothetical regular forms in the notes, and
the Spanish form read aloud on the back of every conjugation card. Pass
`--reference` for the deck exactly as published, which is what `verify`
checks, rebuilding it from `data/`:

```
$ PYTHONPATH=src python -m usc verify Ultimate_Spanish_Conjugation.apkg
built the reference deck from data/
generated collection fingerprint: 1d3dfce93b3381116a46abdba424e15db1d6c43247aa404b0df290829af9fa34
reference collection fingerprint: 1d3dfce93b3381116a46abdba424e15db1d6c43247aa404b0df290829af9fa34

identical: same schema, same rows, same package metadata
```

Standard library only — no Anki, no `genanki`, no third-party packages.

## What "1:1" means here

`python -m usc verify` builds the deck from `data/` with `--reference`,
compares it with the published `.apkg`, and reports every difference (pass
`-g` to check a deck you built yourself instead):

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
| `python -m usc build [-o OUT]` | build the customised `.apkg` from `data/` and `assets/` |
| `python -m usc build --reference` | build the deck exactly as published |
| `python -m usc build --keep-hypothetical` | keep the hypothetical regular forms |
| `python -m usc build --no-tts` | leave the cards silent |
| `python -m usc verify REF [-g GEN]` | compare the deck built from `data/` with a reference one |
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

The cards say the answer -- the conjugated Spanish form -- through
Anki's built-in text to speech. It uses the voices installed on the device,
so nothing is downloaded and the deck still ships no media:

```sh
PYTHONPATH=src python -m usc build                              # spoken (default)
PYTHONPATH=src python -m usc build --no-tts                     # silent
PYTHONPATH=src python -m usc build --tts-lang es_MX --tts-speed 0.8
PYTHONPATH=src python -m usc build --tts-voices Apple_Mónica,Microsoft_Helena
```

The deck adds a `Speech` field holding the bare form, and puts
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

Text to speech is applied at build time, not stored in `data/`: `python -m usc
build --reference` still reproduces the published deck 1:1, and the test suite
checks both.

## Dropping the hypothetical regular forms

1296 of the notes explain an irregularity by naming the form the verb *would*
have if it were regular:

> **Irregular form**: the hypothetical regular form *so* is incorrect.

The deck removes that clause and keeps the verdict (`--keep-hypothetical`
leaves the notes as published):

> **Irregular form**.

> The forms *fuera* and *fuese* are both **irregular**.

The orientation card that shows off the note format carries the same sentence
as an example, so it is trimmed too — afterwards no card in the deck displays
a form that does not exist. Everything else is untouched: guids, ids, tags,
timestamps and the other fields are the same as in the published deck, so the
variant updates an existing collection instead of duplicating it.

Both changes are build options rather than edits to `data/`, and each can be
turned off on its own:

```sh
PYTHONPATH=src python -m usc build --keep-hypothetical   # only the speech
PYTHONPATH=src python -m usc build --no-tts              # only the trimming
PYTHONPATH=src python -m usc build --reference           # neither: the deck as published
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
  tts.py           the text-to-speech variant
  variants.py      content variants (dropping the hypothetical forms)
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
