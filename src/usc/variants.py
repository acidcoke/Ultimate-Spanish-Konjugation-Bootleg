"""Optional content variants of the deck.

Like ``usc.tts``, these are build-time transformations: they rewrite the note
records in memory, leaving ``data/`` describing the published deck, so a plain
``python -m usc build`` still reproduces it 1:1.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .source import DeckSource

#: "Irregular form: the hypothetical regular form *so* is incorrect." and
#: "The forms *fuera* and *fuese* are both irregular. The hypothetical regular
#: forms *seiera* and *seiese* are both incorrect." -- the clause names a form
#: that does not exist, so the whole sentence goes, keeping the sentence stop.
HYPOTHETICAL_RE = re.compile(
    r"[:.] [Tt]he hypothetical regular forms? .*?(?:is|are both|are all) incorrect\.")


def without_hypothetical_forms(source: DeckSource) -> DeckSource:
    """Return a copy of *source* with the hypothetical regular forms dropped.

    The regularity note keeps what it says about the real form -- "Irregular
    form.", "The forms *yerga* and *irga* are both irregular." -- and loses the
    invented form that follows it.  The orientation card that shows off the
    note format carries the same sentence as an example, so it is trimmed too:
    afterwards no card in the deck displays a form that does not exist.
    """
    notes = [_strip_record(record) for record in source.notes]
    variant = DeckSource(
        collection=source.collection,
        verbs=source.verbs,
        templates=source.templates,
        notes=notes,
    )
    variant.speech = source.speech
    return variant


def _strip_record(record: Dict[str, Any]) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    if any(_has_hypothetical(part) for part in record["notes"]):
        stripped: List[Any] = []
        for part in record["notes"]:
            if _has_hypothetical(part):
                part = dict(part, html=_strip(part["html"]))
            stripped.append(part)
        changes["notes"] = stripped
    answer = record["prompt"]["answer"]
    if "hypothetical" in answer:
        changes["prompt"] = dict(record["prompt"], answer=_strip(answer))
    return dict(record, **changes) if changes else record


def _strip(html: str) -> str:
    return HYPOTHETICAL_RE.sub(".", html)


def _has_hypothetical(part: Any) -> bool:
    return isinstance(part, dict) and "hypothetical" in part["html"]
