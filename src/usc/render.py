"""Rebuilding the four note fields from the structured source records.

Every function here has a matching ``parse_*`` counterpart used by
``usc.extract``; the two are exact inverses and the extractor asserts the
round trip for all 4246 notes of the deck.

Field layout of the note type (``Ultimate Spanish Conjugation [Ankiweb]``)::

    0  UUID     a stable per-note uuid4, used by Anki for the note checksum
    1  Prompt   the cloze sentence shown on the front (the sort field)
    2  Similar  the conjugation of the same form in verbs of the same family
    3  Notes    regularity / spelling / family / idiom commentary
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

FIELD_SEPARATOR = "\x1f"
FIELD_NAMES = ("UUID", "Prompt", "Similar", "Notes")

#: Placeholders used inside the sentence templates of ``prompt_templates.json``.
CLOZE_SLOT = "⟪cloze⟫"
HINT_SLOT = "⟪hint⟫"

DLE_URL = "https://dle.rae.es/{slug}?m=form#conjugacion"

_CLOZE_RE = re.compile(r"\{\{c1::(.*?)\}\}", re.S)
_HINT_RE = re.compile(r"<span class=([\"'])sp_hint\1>(.*?)</span>", re.S)
_SIMILAR_ITEM_RE = re.compile(
    r'<br><span class="alt_to_inf"><a href="https://dle\.rae\.es/(?P<inf_slug>[^"]+?)'
    r'\?m=form#conjugacion">(?P<inf_text>[^<]*)</a></span>'
    r'|<br><span class="alt_conj">(?P<form>[^<]*)</span>←'
    r'<span class="alt_inf"><a href="https://dle\.rae\.es/(?P<conj_slug>[^"]+?)'
    r'\?m=form#conjugacion">(?P<conj_text>[^<]*)</a></span>'
    r'|<br><span class="alt_tu_vos">(?P<tu_vos>[^<]*)</span>'
)
_SECTION_OPEN_RE = re.compile(r'<span class="SECTION_(?P<name>[a-z_]+)">')
_SPAN_RE = re.compile(r"<span\b[^>]*>|</span>")
_VERB_LINE_RE = re.compile(
    r'<br><span class="dle_conj"><a href="https://dle\.rae\.es/(?P<slug>[^"]+?)'
    r'\?m=form#conjugacion">(?P<text>[^<]*)</a></span>(?P<summary>[^<]*)',
    re.S,
)


# --------------------------------------------------------------------------
# Prompt (front side)
# --------------------------------------------------------------------------
def render_prompt(prompt: Dict[str, Any], templates: Dict[str, str]) -> str:
    """Fill a sentence template with the answer and the parenthetical hint."""
    text = templates[prompt["template"]]
    cloze = prompt["answer"]
    if prompt.get("cloze_hint"):
        cloze = "{}::{}".format(cloze, prompt["cloze_hint"])
    text = text.replace(CLOZE_SLOT, "{{c1::%s}}" % cloze)
    if HINT_SLOT in text:
        quote = prompt.get("hint_quote", '"')
        hint = "<span class={q}sp_hint{q}>{text}</span>".format(q=quote, text=prompt["hint"])
        text = text.replace(HINT_SLOT, hint)
    return text


def parse_prompt(prompt: str) -> Dict[str, Any]:
    """Split a rendered prompt into its template and its variable parts."""
    cloze = _CLOZE_RE.search(prompt)
    if cloze is None:
        raise ValueError("prompt without a c1 cloze: %r" % prompt)
    inner = cloze.group(1)
    answer, _, cloze_hint = inner.partition("::")
    parsed: Dict[str, Any] = {
        "answer": answer,
        "cloze_hint": cloze_hint,
        "hint": "",
        "hint_quote": "",
    }
    template = prompt[: cloze.start()] + CLOZE_SLOT + prompt[cloze.end():]
    hint = _HINT_RE.search(template)
    if hint is not None:
        parsed["hint_quote"] = hint.group(1)
        parsed["hint"] = hint.group(2)
        template = template[: hint.start()] + HINT_SLOT + template[hint.end():]
    parsed["template"] = template
    return parsed


# --------------------------------------------------------------------------
# Similar (verbs of the same family, conjugated in the same form)
# --------------------------------------------------------------------------
def render_similar(items: Sequence[Sequence[str]]) -> str:
    out: List[str] = []
    for item in items:
        kind = item[0]
        if kind == "inf":
            slug = item[1]
            out.append(
                '<br><span class="alt_to_inf"><a href="{url}">{slug}</a></span>'.format(
                    url=DLE_URL.format(slug=slug), slug=slug
                )
            )
        elif kind == "conj":
            form, infinitive = item[1], item[2]
            out.append(
                '<br><span class="alt_conj">{form}</span>←'
                '<span class="alt_inf"><a href="{url}">{inf}</a></span>'.format(
                    form=form, url=DLE_URL.format(slug=infinitive), inf=infinitive
                )
            )
        elif kind == "tu_vos":
            out.append('<br><span class="alt_tu_vos">{}</span>'.format(item[1]))
        else:  # pragma: no cover - guarded by the extractor
            raise ValueError("unknown 'Similar' item: %r" % (item,))
    return "".join(out)


def parse_similar(field: str) -> List[List[str]]:
    items: List[List[str]] = []
    position = 0
    for match in _SIMILAR_ITEM_RE.finditer(field):
        if match.start() != position:
            raise ValueError("unparsed text in 'Similar': %r" % field[position:match.start()])
        position = match.end()
        if match.group("inf_slug") is not None:
            if match.group("inf_slug") != match.group("inf_text"):
                raise ValueError("link text differs from slug: %r" % match.group(0))
            items.append(["inf", match.group("inf_text")])
        elif match.group("conj_slug") is not None:
            if match.group("conj_slug") != match.group("conj_text"):
                raise ValueError("link text differs from slug: %r" % match.group(0))
            items.append(["conj", match.group("form"), match.group("conj_text")])
        else:
            items.append(["tu_vos", match.group("tu_vos")])
    if position != len(field):
        raise ValueError("unparsed text in 'Similar': %r" % field[position:])
    return items


# --------------------------------------------------------------------------
# Notes (back side commentary)
# --------------------------------------------------------------------------
def render_notes(parts: Sequence[Any], verb: Optional[Dict[str, Any]]) -> str:
    """Assemble the commentary from its per-note and per-verb pieces."""
    out: List[str] = []
    for part in parts:
        if part == "verb_line":
            out.append(
                '<br><span class="dle_conj"><a href="{url}">{text}</a></span>{summary}'.format(
                    url=DLE_URL.format(slug=verb["dle_slug"]),
                    text=verb["infinitive"],
                    summary=verb["summary"],
                )
            )
        elif part == "family":
            out.append('<span class="SECTION_family">{}</span>'.format(verb["family"]))
        else:
            out.append(
                '<span class="SECTION_{name}">{html}</span>'.format(
                    name=part["section"], html=part["html"]
                )
            )
    return "".join(out)


def parse_notes(field: str) -> List[Any]:
    """Split the commentary into ``SECTION_*`` spans and the DLE verb line."""
    parts: List[Any] = []
    position = 0
    while position < len(field):
        section = _SECTION_OPEN_RE.match(field, position)
        if section is not None:
            end = _matching_span_end(field, position)
            inner = field[section.end(): end - len("</span>")]
            parts.append({"section": section.group("name"), "html": inner})
            position = end
            continue
        verb_line = _VERB_LINE_RE.match(field, position)
        if verb_line is None:
            raise ValueError("unparsed text in 'Notes': %r" % field[position:])
        parts.append(("verb_line", verb_line.group("slug"), verb_line.group("text"),
                      verb_line.group("summary")))
        position = verb_line.end()
    return parts


def _matching_span_end(text: str, start: int) -> int:
    """Index just past the ``</span>`` matching the ``<span>`` at *start*."""
    depth = 0
    for match in _SPAN_RE.finditer(text, start):
        depth += -1 if match.group(0) == "</span>" else 1
        if depth == 0:
            return match.end()
    raise ValueError("unbalanced <span> at offset %d" % start)


# --------------------------------------------------------------------------
# The note as a whole
# --------------------------------------------------------------------------
def render_fields(
    record: Dict[str, Any],
    templates: Dict[str, str],
    verbs: Dict[str, Dict[str, Any]],
) -> List[str]:
    verb = verbs.get(record["verb"]) if record.get("verb") else None
    return [
        record["uuid"],
        render_prompt(record["prompt"], templates),
        render_similar(record["similar"]),
        render_notes(record["notes"], verb),
    ]


def join_fields(fields: Sequence[str]) -> str:
    return FIELD_SEPARATOR.join(fields)


def format_tags(tags: Sequence[str]) -> str:
    """Anki stores tags space separated, with a leading and trailing space."""
    return " {} ".format(" ".join(tags)) if tags else ""
