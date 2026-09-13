"""Writing ``collection.anki2``, the SQLite database inside an ``.apkg``."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Sequence, Tuple

from . import anki_schema, render, tts
from .source import DeckSource

# Anki's ``stripHTMLMedia`` (anki/utils.py), used to fill the ``sfld`` column
# and to compute the note checksum.
_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
_STYLE_RE = re.compile(r"(?si)<style.*?>.*?</style>")
_SCRIPT_RE = re.compile(r"(?si)<script.*?>.*?</script>")
_TAG_RE = re.compile(r"(?s)<.*?>")
_ENTITY_RE = re.compile(r"&#?\w+;")
_MEDIA_RE = re.compile(r"(?i)<img[^>]+src=[\"']?([^\"'>]+)[\"']?[^>]*>")


def strip_html_media(text: str) -> str:
    """Plain text of a field, exactly as Anki computes it."""
    text = _MEDIA_RE.sub(" \\1 ", text)
    text = _COMMENT_RE.sub("", text)
    text = _STYLE_RE.sub("", text)
    text = _SCRIPT_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    return _ENTITY_RE.sub(lambda match: html.unescape(match.group()), text)


def field_checksum(text: str) -> int:
    """Anki's note checksum: the first 8 hex digits of the sha1 of field 0."""
    return int(hashlib.sha1(strip_html_media(text).encode("utf-8")).hexdigest()[:8], 16)


def build_rows(source: DeckSource) -> Tuple[List[Tuple[Any, ...]], List[Tuple[Any, ...]]]:
    """Build the ``notes`` and ``cards`` rows, in deck order.

    Note and card ids, and the ``due`` position of every card, are consecutive
    in the original deck: they are derived from the bases stored in
    ``data/collection.json`` plus the position of the note in the deck.
    """
    ids = source.collection["ids"]
    model_id = ids["model_id"]
    deck_id = ids["deck_id"]
    note_base = ids["first_note_id"]
    card_base = ids["first_card_id"]
    due_base = ids["first_due"]

    notes: List[Tuple[Any, ...]] = []
    cards: List[Tuple[Any, ...]] = []
    for position, record in enumerate(source.notes):
        fields = render.render_fields(record, source.templates, source.verbs_by_name)
        if source.speech:
            fields.append(tts.speech_text(record))
        note_id = note_base + position
        notes.append(
            (
                note_id,                                  # id
                record["guid"],                           # guid
                model_id,                                 # mid
                record["mod"],                            # mod
                record["usn"],                            # usn
                render.format_tags(record["tags"]),       # tags
                render.join_fields(fields),               # flds
                strip_html_media(fields[1]),              # sfld (sort field: Prompt)
                field_checksum(fields[0]),                # csum (over field 0: UUID)
                0,                                        # flags
                "",                                       # data
            )
        )
        cards.append(
            (
                card_base + position,                     # id
                note_id,                                  # nid
                deck_id,                                  # did
                0,                                        # ord (single cloze card)
                record["card_mod"],                       # mod
                record["card_usn"],                       # usn
                0,                                        # type   (new)
                0,                                        # queue  (new)
                due_base + position,                      # due    (new-card position)
                0, 0, 0, 0, 0, 0, 0, 0, "",               # ivl..data (untouched card)
            )
        )
    return notes, cards


def col_row(source: DeckSource) -> Tuple[Any, ...]:
    """The single row of the ``col`` table.

    The JSON blobs are written with ``json.dumps`` defaults, which is what
    Anki itself uses, so the stored strings match the original byte for byte.
    """
    col = source.collection["col"]
    return (
        col["id"],
        col["crt"],
        col["mod"],
        col["scm"],
        col["ver"],
        col["dty"],
        col["usn"],
        col["ls"],
        json.dumps(source.collection["conf"]),
        json.dumps(source.collection["models"]),
        json.dumps(source.collection["decks"]),
        json.dumps(source.collection["dconf"]),
        json.dumps(col["tags"]),
    )


def write_collection(source: DeckSource, path: str) -> None:
    """Create ``collection.anki2`` at *path* (an existing file is replaced)."""
    if os.path.exists(path):
        os.remove(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    notes, cards = build_rows(source)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA page_size = 4096")
        connection.execute("PRAGMA legacy_file_format = ON")
        for statement in anki_schema.DDL:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO col VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", col_row(source)
        )
        connection.executemany(
            "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)", notes
        )
        connection.executemany(
            "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cards
        )
        connection.commit()
    finally:
        connection.close()


def dump_tables(path: str) -> Dict[str, List[Tuple[Any, ...]]]:
    """Every row of every table, ordered, for comparing two collections."""
    connection = sqlite3.connect(path)
    try:
        tables: Dict[str, List[Tuple[Any, ...]]] = {}
        for table in anki_schema.TABLES:
            rows = connection.execute("SELECT * FROM %s" % table).fetchall()
            tables[table] = sorted(rows)
        return tables
    finally:
        connection.close()


def dump_schema(path: str) -> List[str]:
    connection = sqlite3.connect(path)
    try:
        return [
            row[0]
            for row in connection.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            )
        ]
    finally:
        connection.close()


def fingerprint(path: str) -> str:
    """A sha256 over the logical content of a collection.

    Independent of SQLite page layout, so two collections with the same
    schema and the same rows have the same fingerprint.
    """
    digest = hashlib.sha256()
    for statement in dump_schema(path):
        digest.update(_normalise_sql(statement).encode("utf-8"))
        digest.update(b"\x00")
    for table, rows in dump_tables(path).items():
        digest.update(table.encode("utf-8"))
        for row in rows:
            digest.update(repr(row).encode("utf-8"))
            digest.update(b"\x00")
    return digest.hexdigest()


def _normalise_sql(statement: str) -> str:
    return " ".join(statement.split())


def field_list(flds: str) -> Sequence[str]:
    return flds.split(render.FIELD_SEPARATOR)
