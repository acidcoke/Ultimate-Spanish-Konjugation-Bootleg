"""Loading and saving the deck source data.

The deck is fully described by four files:

``data/collection.json``
    Collection level metadata: the ``col`` row, the deck list, the deck
    options group, the collection configuration, the note type, and the
    id/timestamp bases used when numbering notes and cards.
``data/verbs.json``
    The 72 verbs of the deck, with the per-verb material that every note of
    that verb repeats (the DLE link line and the "same family" note).
``data/prompt_templates.json``
    The sentence templates of the front side, one per tense/person/variant.
``data/notes.jsonl``
    One record per note, in deck order.

Text that belongs to the note type rather than to the content (the card
template and the stylesheet) lives in ``assets/`` and is referenced from
``data/collection.json`` through ``@file:`` sentinels, so that the note type
JSON keeps the exact key order of the original deck.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterator, List

FILE_SENTINEL = "@file:"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")

COLLECTION_JSON = os.path.join(DATA_DIR, "collection.json")
VERBS_JSON = os.path.join(DATA_DIR, "verbs.json")
TEMPLATES_JSON = os.path.join(DATA_DIR, "prompt_templates.json")
NOTES_JSONL = os.path.join(DATA_DIR, "notes.jsonl")


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def read_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: str, records: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_asset(name: str) -> str:
    with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def write_asset(name: str, text: str) -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    with open(os.path.join(ASSETS_DIR, name), "w", encoding="utf-8") as fh:
        fh.write(text)


def resolve_sentinels(obj: Any) -> Any:
    """Replace every ``"@file:<name>"`` string by the content of that asset."""
    if isinstance(obj, dict):
        return {key: resolve_sentinels(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [resolve_sentinels(value) for value in obj]
    if isinstance(obj, str) and obj.startswith(FILE_SENTINEL):
        return read_asset(obj[len(FILE_SENTINEL):])
    return obj


class DeckSource:
    """The complete source of the deck, as loaded from ``data/``."""

    def __init__(
        self,
        collection: Dict[str, Any],
        verbs: List[Dict[str, Any]],
        templates: Dict[str, str],
        notes: List[Dict[str, Any]],
    ) -> None:
        self.collection = collection
        self.verbs = verbs
        self.templates = templates
        self.notes = notes
        self.verbs_by_name = {verb["infinitive"]: verb for verb in verbs}

    @classmethod
    def load(cls) -> "DeckSource":
        collection = resolve_sentinels(read_json(COLLECTION_JSON))
        return cls(
            collection=collection,
            verbs=read_json(VERBS_JSON),
            templates=read_json(TEMPLATES_JSON),
            notes=list(read_jsonl(NOTES_JSONL)),
        )

    def save(self) -> None:
        write_json(COLLECTION_JSON, self.collection)
        write_json(VERBS_JSON, self.verbs)
        write_json(TEMPLATES_JSON, self.templates)
        write_jsonl(NOTES_JSONL, self.notes)
