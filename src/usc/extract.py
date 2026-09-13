"""Rebuild the source data in ``data/`` and ``assets/`` from a reference deck.

This is the provenance tool: it takes the published ``.apkg`` apart into the
structured source this repository builds from, and checks, note by note, that
the parse is lossless -- every field, tag string, sort field and checksum it
writes out must render back to exactly what the reference deck contains.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from . import collection as collection_module
from . import packaging, render
from .source import (
    ASSETS_DIR,
    FILE_SENTINEL,
    DeckSource,
    write_asset,
)

CSS_ASSET = "card.css"
FRONT_ASSET = "card_front.html"
BACK_ASSET = "card_back.html"

TENSE_TAGS = [
    "infinitivo",
    "gerundio",
    "participio",
    "presente",
    "imperfecto",
    "indefinido",
    "futuro",
    "condicional",
    "subjuntivo_presente",
    "subjuntivo_pasado",
    "subjuntivo_futuro",
    "imperativo",
]
PERSON_TAGS = ["yo", "tú", "vos", "tú_vos", "él_ella_usted", "nosotros", "vosotros",
               "ellos_ellas_ustedes"]
_ASCII = {"tú": "tu", "tú_vos": "tu_vos", "él_ella_usted": "el_ella_usted"}

_CARD_CONSTANTS = {
    "ord": 0, "type": 0, "queue": 0, "ivl": 0, "factor": 0, "reps": 0,
    "lapses": 0, "left": 0, "odue": 0, "odid": 0, "flags": 0, "data": "",
}


def extract(apkg_path: str) -> DeckSource:
    with tempfile.TemporaryDirectory() as workdir:
        collection_path = packaging.extract_entry(
            apkg_path, packaging.COLLECTION_ENTRY,
            os.path.join(workdir, packaging.COLLECTION_ENTRY),
        )
        connection = sqlite3.connect(collection_path)
        try:
            source = _extract_from_collection(connection, apkg_path)
        finally:
            connection.close()
    _check_round_trip(source, apkg_path)
    return source


# --------------------------------------------------------------------------
def _extract_from_collection(connection: sqlite3.Connection, apkg_path: str) -> DeckSource:
    col = connection.execute(
        "SELECT id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags "
        "FROM col"
    ).fetchall()
    if len(col) != 1:
        raise ValueError("expected exactly one col row, found %d" % len(col))
    (col_id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags) = col[0]

    models_obj = json.loads(models)
    if len(models_obj) != 1:
        raise ValueError("the deck is expected to define a single note type")
    model = next(iter(models_obj.values()))
    model_id = model["id"]

    # The card template and the stylesheet move to assets/, replaced in place
    # by sentinels so the JSON keeps the original key order.
    write_asset(CSS_ASSET, model["css"])
    model["css"] = FILE_SENTINEL + CSS_ASSET
    if len(model["tmpls"]) != 1:
        raise ValueError("the note type is expected to define a single card template")
    write_asset(FRONT_ASSET, model["tmpls"][0]["qfmt"])
    write_asset(BACK_ASSET, model["tmpls"][0]["afmt"])
    model["tmpls"][0]["qfmt"] = FILE_SENTINEL + FRONT_ASSET
    model["tmpls"][0]["afmt"] = FILE_SENTINEL + BACK_ASSET

    note_rows = connection.execute(
        "SELECT id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data "
        "FROM notes ORDER BY id"
    ).fetchall()
    card_rows = connection.execute(
        "SELECT id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, "
        "lapses, left, odue, odid, flags, data FROM cards ORDER BY id"
    ).fetchall()
    _check_regularity(note_rows, card_rows, model_id)

    deck_id = card_rows[0][2]
    collection: Dict[str, Any] = {
        "col": {
            "id": col_id, "crt": crt, "mod": mod, "scm": scm, "ver": ver,
            "dty": dty, "usn": usn, "ls": ls, "tags": json.loads(tags),
        },
        "ids": {
            "model_id": model_id,
            "deck_id": deck_id,
            "first_note_id": note_rows[0][0],
            "first_card_id": card_rows[0][0],
            "first_due": card_rows[0][8],
        },
        "package": _package_metadata(apkg_path),
        "conf": json.loads(conf),
        "models": models_obj,
        "decks": json.loads(decks),
        "dconf": json.loads(dconf),
    }

    verbs: Dict[str, Dict[str, Any]] = {}
    templates: Dict[str, str] = {}
    template_ids: Dict[str, str] = {}
    infinitives = _infinitives(note_rows)
    notes: List[Dict[str, Any]] = []
    for note_row, card_row in zip(note_rows, card_rows):
        notes.append(
            _extract_note(note_row, card_row, infinitives, verbs, templates, template_ids)
        )

    verb_list = [verbs[name] for name in infinitives if name in verbs]
    return DeckSource(
        collection=collection,
        verbs=verb_list,
        templates=dict(sorted(templates.items())),
        notes=notes,
    )


def _package_metadata(apkg_path: str) -> Dict[str, Any]:
    entries = packaging.describe(apkg_path)
    by_name = {entry["name"]: entry for entry in entries}
    if set(by_name) != {packaging.COLLECTION_ENTRY, packaging.MEDIA_ENTRY}:
        raise ValueError("unexpected package entries: %s" % sorted(by_name))
    import zipfile

    with zipfile.ZipFile(apkg_path) as archive:
        media = archive.read(packaging.MEDIA_ENTRY).decode("utf-8")
    timestamps = {tuple(entry["timestamp"]) for entry in entries}
    if len(timestamps) != 1:
        raise ValueError("entries carry different timestamps: %s" % timestamps)
    return {
        "timestamp": list(timestamps.pop()),
        "media": media,
        "entries": [
            {
                "name": entry["name"],
                "create_system": entry["create_system"],
                "create_version": entry["create_version"],
                "extract_version": entry["extract_version"],
                "external_attr": entry["external_attr"],
            }
            for entry in entries
        ],
    }


def _check_regularity(note_rows, card_rows, model_id: int) -> None:
    """Assert the structural invariants the builder relies on."""
    if len(note_rows) != len(card_rows):
        raise ValueError("the deck is expected to hold one card per note")
    first_note, first_card, first_due = note_rows[0][0], card_rows[0][0], card_rows[0][8]
    deck_id = card_rows[0][2]
    for position, (note, card) in enumerate(zip(note_rows, card_rows)):
        if note[0] != first_note + position:
            raise ValueError("note ids are not consecutive at position %d" % position)
        if note[2] != model_id:
            raise ValueError("note %d uses another note type" % note[0])
        if (note[9], note[10]) != (0, ""):
            raise ValueError("note %d carries flags/data" % note[0])
        if card[0] != first_card + position:
            raise ValueError("card ids are not consecutive at position %d" % position)
        if card[1] != note[0]:
            raise ValueError("card %d is not the card of note %d" % (card[0], note[0]))
        if card[2] != deck_id:
            raise ValueError("card %d lives in another deck" % card[0])
        if card[8] != first_due + position:
            raise ValueError("card %d is out of its new-card position" % card[0])
        values = dict(zip(
            ["id", "nid", "did", "ord", "mod", "usn", "type", "queue", "due", "ivl",
             "factor", "reps", "lapses", "left", "odue", "odid", "flags", "data"], card))
        for name, expected in _CARD_CONSTANTS.items():
            if values[name] != expected:
                raise ValueError("card %d has %s=%r, expected %r"
                                 % (card[0], name, values[name], expected))


def _infinitives(note_rows) -> List[str]:
    """The verbs of the deck, in the order their infinitive card appears."""
    verbs: List[str] = []
    for row in note_rows:
        tags = row[5].split()
        if "infinitivo" not in tags:
            continue
        prompt = row[6].split(render.FIELD_SEPARATOR)[1]
        match = re.search(r"\{\{c1::([^:}]+)\}\}", prompt)
        if match is None:
            raise ValueError("infinitive card without a plain cloze: %r" % prompt)
        verbs.append(match.group(1))
    return verbs


def _extract_note(note_row, card_row, infinitives, verbs, templates, template_ids):
    (note_id, guid, _mid, mod, usn, tags, flds, _sfld, _csum, _flags, _data) = note_row
    tag_list = tags.split()
    fields = flds.split(render.FIELD_SEPARATOR)
    if len(fields) != len(render.FIELD_NAMES):
        raise ValueError("note %d has %d fields" % (note_id, len(fields)))
    uuid, prompt, similar, notes_field = fields

    verb = _verb_of(tag_list, infinitives, note_id)
    parsed_prompt = render.parse_prompt(prompt)
    template = parsed_prompt.pop("template")
    parsed_prompt["template"] = _template_id(template, tag_list, templates, template_ids)

    return {
        "guid": guid,
        "uuid": uuid,
        "verb": verb,
        "tags": tag_list,
        "prompt": parsed_prompt,
        "similar": render.parse_similar(similar),
        "notes": _extract_notes_field(notes_field, verb, verbs, note_id),
        "mod": mod,
        "usn": usn,
        "card_mod": card_row[4],
        "card_usn": card_row[5],
    }


def _verb_of(tag_list, infinitives, note_id) -> Optional[str]:
    found = [tag for tag in tag_list if tag in set(infinitives)]
    if not found:
        return None
    if len(found) > 1:
        raise ValueError("note %d is tagged with several verbs: %s" % (note_id, found))
    return found[0]


def _template_id(template: str, tag_list, templates, template_ids) -> str:
    if template in template_ids:
        return template_ids[template]
    key = _template_key(tag_list)
    ordinal = 1 + sum(1 for name in template_ids.values() if name.startswith(key + "."))
    name = "{}.{:02d}".format(key, ordinal)
    template_ids[template] = name
    templates[name] = template
    return name


def _template_key(tag_list) -> str:
    tags = set(tag_list)
    if "negative_imperativo" in tags:
        tense = "imperativo_negativo"
    else:
        tense = next((tag for tag in TENSE_TAGS if tag in tags), None)
    if tense is None:
        return "orientation"
    person = next((tag for tag in PERSON_TAGS if tag in tags), None)
    if person is None:
        return tense
    return "{}.{}".format(tense, _ASCII.get(person, person))


def _extract_notes_field(field: str, verb, verbs, note_id) -> List[Any]:
    parts: List[Any] = []
    for part in render.parse_notes(field):
        if isinstance(part, tuple):  # the DLE verb line
            _, slug, text, summary = part
            if verb is None:
                raise ValueError("note %d has a verb line but no verb tag" % note_id)
            if text != verb:
                raise ValueError("note %d links to %r, tagged %r" % (note_id, text, verb))
            _record_verb(verbs, verb, {"dle_slug": slug, "summary": summary}, note_id)
            parts.append("verb_line")
        elif part["section"] == "family":
            if verb is None:
                raise ValueError("note %d has a family note but no verb tag" % note_id)
            _record_verb(verbs, verb, {"family": part["html"]}, note_id)
            parts.append("family")
        else:
            parts.append(part)
    return parts


def _record_verb(verbs, verb, values, note_id) -> None:
    entry = verbs.setdefault(verb, {"infinitive": verb})
    for key, value in values.items():
        if key in entry and entry[key] != value:
            raise ValueError("verb %r has two different %s (note %d)" % (verb, key, note_id))
        entry[key] = value


# --------------------------------------------------------------------------
def _check_round_trip(source: DeckSource, apkg_path: str) -> None:
    """Render every note again and compare it with the reference deck."""
    resolved = DeckSource(
        collection=_with_assets(source.collection),
        verbs=source.verbs,
        templates=source.templates,
        notes=source.notes,
    )
    notes, cards = collection_module.build_rows(resolved)
    with tempfile.TemporaryDirectory() as workdir:
        path = packaging.extract_entry(
            apkg_path, packaging.COLLECTION_ENTRY,
            os.path.join(workdir, packaging.COLLECTION_ENTRY),
        )
        connection = sqlite3.connect(path)
        try:
            reference_notes = connection.execute(
                "SELECT id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data "
                "FROM notes ORDER BY id").fetchall()
            reference_cards = connection.execute(
                "SELECT id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, "
                "reps, lapses, left, odue, odid, flags, data FROM cards ORDER BY id"
            ).fetchall()
        finally:
            connection.close()
    for rebuilt, reference in zip(notes, reference_notes):
        if rebuilt != tuple(reference):
            raise AssertionError(_first_difference("note", rebuilt, tuple(reference)))
    for rebuilt, reference in zip(cards, reference_cards):
        if rebuilt != tuple(reference):
            raise AssertionError(_first_difference("card", rebuilt, tuple(reference)))


def _with_assets(collection: Dict[str, Any]) -> Dict[str, Any]:
    from .source import resolve_sentinels

    return resolve_sentinels(collection)


def _first_difference(kind: str, rebuilt, reference) -> str:
    for index, (left, right) in enumerate(zip(rebuilt, reference)):
        if left != right:
            return "rebuilt %s differs in column %d:\n  built: %r\n  ref:   %r" % (
                kind, index, left, right)
    return "rebuilt %s differs: %r != %r" % (kind, rebuilt, reference)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Rebuild data/ and assets/ from a reference .apkg")
    parser.add_argument("apkg", help="the reference Ultimate Spanish Conjugation .apkg")
    args = parser.parse_args(argv)

    source = extract(args.apkg)
    source.save()
    print("notes: {}".format(len(source.notes)))
    print("verbs: {}".format(len(source.verbs)))
    print("prompt templates: {}".format(len(source.templates)))
    print("wrote data/ and {}/".format(os.path.relpath(ASSETS_DIR)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
