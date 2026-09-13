"""Optional text-to-speech for the Spanish verb form.

Anki reads a field aloud through a ``{{tts}}`` tag in the card template, using
the voices installed on the device (Anki 2.1.20+, AnkiDroid 2.16+, AnkiMobile).
This module turns the deck into a variant that speaks the answer -- the
conjugated Spanish form -- on the back of every conjugation card:

* a ``Speech`` field is added to the note type, holding just the form
  (``soy``, ``fuera, fuese``, ``nos endeudáramos``) with no markup;
* the back template gains ``{{tts es_ES:Speech}}``, wrapped in
  ``{{#Speech}}…{{/Speech}}`` so the seven orientation cards, whose text is
  English, stay silent;
* the front template is left alone: speaking the answer there would give it
  away.

The transformation happens in memory at build time, so ``data/`` keeps
describing the published deck and ``python -m usc build`` without ``--tts``
still reproduces it 1:1.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from .source import DeckSource

SPEECH_FIELD = "Speech"
DEFAULT_LANG = "es_ES"

#: Separator between the accepted variants of a form (``fuera | fuese``).
VARIANT_SEPARATOR = " | "

CSS_RULE = """
.tts {  /* the text-to-speech replay button on the back of the card */
  margin-top: 0.4em;
}
"""


def speech_text(record: Dict[str, Any]) -> str:
    """What the card should say: the Spanish form, or nothing.

    Orientation cards (no verb) are silent.  Where a form has several
    accepted variants the pipe becomes a comma, so the voice pauses between
    them instead of running them together.
    """
    if not record.get("verb"):
        return ""
    answer = record["prompt"]["answer"]
    return answer.replace(VARIANT_SEPARATOR, ", ")


def tts_tag(lang: str = DEFAULT_LANG, voices: Optional[str] = None,
            speed: Optional[float] = None) -> str:
    options = ""
    if voices:
        options += " voices=%s" % voices
    if speed:
        options += " speed=%s" % speed
    return "{{tts %s%s:%s}}" % (lang, options, SPEECH_FIELD)


def with_tts(source: DeckSource, lang: str = DEFAULT_LANG,
             voices: Optional[str] = None, speed: Optional[float] = None) -> DeckSource:
    """Return a copy of *source* whose cards speak the Spanish form."""
    collection = copy.deepcopy(source.collection)
    model = next(iter(collection["models"].values()))
    _add_speech_field(model["flds"])
    template = model["tmpls"][0]
    template["afmt"] = _add_tts_to_back(template["afmt"], lang, voices, speed)
    model["css"] = model["css"] + CSS_RULE

    variant = DeckSource(
        collection=collection,
        verbs=source.verbs,
        templates=source.templates,
        notes=source.notes,
    )
    variant.speech = True
    return variant


def _add_speech_field(fields: List[Dict[str, Any]]) -> None:
    if any(field["name"] == SPEECH_FIELD for field in fields):
        raise ValueError("the note type already has a %r field" % SPEECH_FIELD)
    last = fields[-1]
    fields.append({
        "name": SPEECH_FIELD,
        "ord": len(fields),
        "sticky": False,
        "rtl": False,
        "font": last["font"],
        "size": last["size"],
    })


def _add_tts_to_back(afmt: str, lang: str, voices: Optional[str],
                     speed: Optional[float]) -> str:
    """Put the replay button right under the answered sentence."""
    block = '{{#%s}}<div class="tts">%s</div>{{/%s}}' % (
        SPEECH_FIELD, tts_tag(lang, voices, speed), SPEECH_FIELD)
    marker = "{{cloze:Prompt}}"
    if not afmt.startswith(marker):
        raise ValueError("unexpected back template: it should open with %s" % marker)
    return afmt[: len(marker)] + "\n" + block + afmt[len(marker):]
