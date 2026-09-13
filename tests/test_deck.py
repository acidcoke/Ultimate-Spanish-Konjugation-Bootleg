"""Tests for the deck generator.

``test_matches_reference_deck`` is the 1:1 check; it needs the published deck
and runs only when ``USC_REFERENCE_APKG`` points at it::

    USC_REFERENCE_APKG=~/Downloads/Ultimate_Spanish_Conjugation.apkg \
        python -m unittest discover -s tests

The other tests run everywhere: they rebuild the deck from ``data/`` and
compare its content fingerprint with the value recorded from the reference
deck, so a change to the source data or to the renderer that would alter the
published deck fails the suite.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from usc import build, collection, packaging, render, verify  # noqa: E402
from usc.source import DeckSource  # noqa: E402

#: sha256 over the schema and every row of the reference collection.
REFERENCE_FINGERPRINT = "1d3dfce93b3381116a46abdba424e15db1d6c43247aa404b0df290829af9fa34"

NOTE_COUNT = 4246
VERB_COUNT = 72
REFERENCE_APKG = os.environ.get("USC_REFERENCE_APKG")


class SourceDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DeckSource.load()

    def test_deck_size(self):
        self.assertEqual(len(self.source.notes), NOTE_COUNT)
        self.assertEqual(len(self.source.verbs), VERB_COUNT)

    def test_every_note_renders_four_fields(self):
        for record in self.source.notes:
            fields = render.render_fields(record, self.source.templates,
                                          self.source.verbs_by_name)
            self.assertEqual(len(fields), len(render.FIELD_NAMES))
            self.assertIn("{{c1::", fields[1])

    def test_every_template_is_used_and_defined(self):
        used = {record["prompt"]["template"] for record in self.source.notes}
        self.assertEqual(used, set(self.source.templates))

    def test_every_verb_note_refers_to_a_known_verb(self):
        for record in self.source.notes:
            if record["verb"] is not None:
                self.assertIn(record["verb"], self.source.verbs_by_name)

    def test_guids_and_uuids_are_unique(self):
        guids = {record["guid"] for record in self.source.notes}
        uuids = {record["uuid"] for record in self.source.notes}
        self.assertEqual(len(guids), NOTE_COUNT)
        self.assertEqual(len(uuids), NOTE_COUNT)


class ParserTest(unittest.TestCase):
    def test_prompt_round_trip(self):
        prompt = ('⊙ Ahora mismo, ⊙<br><br><span class="cloze_pronoun">yo</span> '
                  '<span class="sp_verb">{{c1::soy::…ser…}}</span> '
                  "<span class='sp_hint'>(consciente de ello)</span>")
        parsed = render.parse_prompt(prompt)
        templates = {"t": parsed.pop("template")}
        parsed["template"] = "t"
        self.assertEqual(parsed["answer"], "soy")
        self.assertEqual(parsed["cloze_hint"], "…ser…")
        self.assertEqual(parsed["hint_quote"], "'")
        self.assertEqual(render.render_prompt(parsed, templates), prompt)

    def test_similar_round_trip(self):
        field = ('<br><span class="alt_conj">busque</span>←<span class="alt_inf">'
                 '<a href="https://dle.rae.es/buscar?m=form#conjugacion">buscar</a>'
                 '</span><br><span class="alt_tu_vos">tú</span>')
        self.assertEqual(render.render_similar(render.parse_similar(field)), field)

    def test_checksum_matches_anki(self):
        # The checksum Anki stored for the first note of the reference deck.
        self.assertEqual(
            collection.field_checksum("1a04e75e-3113-4086-904e-a9832154f9cf"), 1025347023)

    def test_sort_field_is_plain_text(self):
        self.assertEqual(collection.strip_html_media("a<br>b&amp;c"), "ab&c")


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.TemporaryDirectory()
        cls.apkg = build.build(os.path.join(cls.workdir.name, "deck.apkg"))
        cls.collection = packaging.extract_entry(
            cls.apkg, packaging.COLLECTION_ENTRY,
            os.path.join(cls.workdir.name, packaging.COLLECTION_ENTRY))

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()

    def test_fingerprint_matches_reference(self):
        self.assertEqual(collection.fingerprint(self.collection), REFERENCE_FINGERPRINT)

    def test_one_card_per_note(self):
        tables = collection.dump_tables(self.collection)
        self.assertEqual(len(tables["notes"]), NOTE_COUNT)
        self.assertEqual(len(tables["cards"]), NOTE_COUNT)
        self.assertEqual(len(tables["revlog"]), 0)

    def test_package_entries(self):
        self.assertEqual([entry["name"] for entry in packaging.describe(self.apkg)],
                         [packaging.COLLECTION_ENTRY, packaging.MEDIA_ENTRY])

    def test_build_is_deterministic(self):
        second = build.build(os.path.join(self.workdir.name, "deck2.apkg"))
        with open(self.apkg, "rb") as first_file, open(second, "rb") as second_file:
            self.assertEqual(first_file.read(), second_file.read())


@unittest.skipUnless(REFERENCE_APKG, "set USC_REFERENCE_APKG to the published deck")
class ReferenceDeckTest(unittest.TestCase):
    def test_matches_reference_deck(self):
        with tempfile.TemporaryDirectory() as workdir:
            apkg = build.build(os.path.join(workdir, "deck.apkg"))
            differences = verify.compare(apkg, REFERENCE_APKG)
        self.assertEqual(differences, [])


if __name__ == "__main__":
    unittest.main()
