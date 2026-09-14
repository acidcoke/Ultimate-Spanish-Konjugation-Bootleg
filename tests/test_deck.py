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

from usc import build, collection, packaging, render, tts, variants, verify  # noqa: E402
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


class TtsTest(unittest.TestCase):
    """The optional --tts variant: it speaks the form, and only that."""

    @classmethod
    def setUpClass(cls):
        cls.source = tts.with_tts(DeckSource.load())
        cls.workdir = tempfile.TemporaryDirectory()
        apkg = build.build(os.path.join(cls.workdir.name, "tts.apkg"), cls.source)
        cls.collection = packaging.extract_entry(
            apkg, packaging.COLLECTION_ENTRY,
            os.path.join(cls.workdir.name, packaging.COLLECTION_ENTRY))
        cls.notes = collection.dump_tables(cls.collection)["notes"]

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()

    def _model(self):
        import json
        import sqlite3

        connection = sqlite3.connect(self.collection)
        try:
            models = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
        finally:
            connection.close()
        return next(iter(models.values()))

    def test_note_type_gains_a_speech_field(self):
        fields = [field["name"] for field in self._model()["flds"]]
        self.assertEqual(fields, ["UUID", "Prompt", "Similar", "Notes", tts.SPEECH_FIELD])

    def test_back_template_speaks_and_front_stays_silent(self):
        template = self._model()["tmpls"][0]
        self.assertIn("{{tts es_ES:Speech}}", template["afmt"])
        self.assertIn("{{#Speech}}", template["afmt"])
        self.assertNotIn("tts", template["qfmt"])

    def test_every_conjugation_card_speaks_its_form(self):
        silent = 0
        for row, record in zip(self.notes, self.source.notes):
            speech = row[6].split(render.FIELD_SEPARATOR)[4]
            if record["verb"] is None:
                silent += 1
                self.assertEqual(speech, "")
            else:
                self.assertTrue(speech)
                self.assertNotIn("<", speech)
                self.assertNotIn("|", speech)
        self.assertEqual(silent, 7)  # the orientation cards

    def test_variants_are_spoken_as_a_list(self):
        self.assertEqual(tts.speech_text(
            {"verb": "ser", "prompt": {"answer": "fuera | fuese"}}), "fuera, fuese")

    def test_content_fields_are_untouched(self):
        for row, record in zip(self.notes, self.source.notes):
            fields = row[6].split(render.FIELD_SEPARATOR)
            self.assertEqual(fields[0], record["uuid"])
            self.assertEqual(len(fields), 5)

    def test_base_build_is_unaffected(self):
        source = DeckSource.load()
        self.assertFalse(source.speech)
        with tempfile.TemporaryDirectory() as workdir:
            apkg = build.build(os.path.join(workdir, "deck.apkg"), source)
            path = packaging.extract_entry(
                apkg, packaging.COLLECTION_ENTRY, os.path.join(workdir, "collection.anki2"))
            self.assertEqual(collection.fingerprint(path), REFERENCE_FINGERPRINT)


class HypotheticalFormsTest(unittest.TestCase):
    """--no-hypothetical: the invented forms go, the real ones stay."""

    @classmethod
    def setUpClass(cls):
        cls.base = DeckSource.load()
        cls.source = variants.without_hypothetical_forms(cls.base)
        cls.workdir = tempfile.TemporaryDirectory()
        apkg = build.build(os.path.join(cls.workdir.name, "trimmed.apkg"), cls.source)
        cls.collection = packaging.extract_entry(
            apkg, packaging.COLLECTION_ENTRY,
            os.path.join(cls.workdir.name, packaging.COLLECTION_ENTRY))
        cls.notes = collection.dump_tables(cls.collection)["notes"]

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()

    def test_no_card_shows_an_invented_form(self):
        for row in self.notes:
            self.assertNotIn("hypothetical", row[6])
            self.assertNotIn("wrong_conj", row[6])

    def test_the_regularity_note_keeps_its_verdict(self):
        trimmed = [row for row in self.notes if "SECTION_regularity" in row[6]]
        self.assertTrue(trimmed)
        for row in trimmed:
            notes_field = row[6].split(render.FIELD_SEPARATOR)[3]
            self.assertNotIn("incorrect", notes_field)
        self.assertIn('<span class="note_feature">Irregular form</span>.',
                      "".join(row[6] for row in self.notes[:200]))

    def test_only_the_affected_notes_change(self):
        changed = [index for index, (record, original)
                   in enumerate(zip(self.source.notes, self.base.notes))
                   if record != original]
        self.assertEqual(len(changed), 1297)  # 1296 regularity notes + orientation card 5

    def test_ids_guids_and_tags_are_untouched(self):
        for record, original in zip(self.source.notes, self.base.notes):
            self.assertEqual(record["guid"], original["guid"])
            self.assertEqual(record["uuid"], original["uuid"])
            self.assertEqual(record["tags"], original["tags"])
            self.assertEqual(record["mod"], original["mod"])

    def test_composes_with_tts(self):
        both = tts.with_tts(variants.without_hypothetical_forms(DeckSource.load()))
        self.assertTrue(both.speech)
        with tempfile.TemporaryDirectory() as workdir:
            apkg = build.build(os.path.join(workdir, "both.apkg"), both)
            path = packaging.extract_entry(
                apkg, packaging.COLLECTION_ENTRY, os.path.join(workdir, "collection.anki2"))
            rows = collection.dump_tables(path)["notes"]
        for row in rows:
            fields = row[6].split(render.FIELD_SEPARATOR)
            self.assertEqual(len(fields), 5)
            self.assertNotIn("hypothetical", row[6])

    def test_source_data_is_not_modified(self):
        self.assertTrue(any("hypothetical" in part["html"]
                            for record in DeckSource.load().notes
                            for part in record["notes"] if isinstance(part, dict)))


@unittest.skipUnless(REFERENCE_APKG, "set USC_REFERENCE_APKG to the published deck")
class ReferenceDeckTest(unittest.TestCase):
    def test_matches_reference_deck(self):
        with tempfile.TemporaryDirectory() as workdir:
            apkg = build.build(os.path.join(workdir, "deck.apkg"))
            differences = verify.compare(apkg, REFERENCE_APKG)
        self.assertEqual(differences, [])


if __name__ == "__main__":
    unittest.main()
