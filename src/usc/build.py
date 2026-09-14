"""Build the deck: source data -> ``.apkg``.

The deck this repository builds by default is the customised one: the
hypothetical regular forms are dropped from the notes, and the back of each
conjugation card speaks the Spanish form through Anki's text to speech.

``data/`` still describes the deck as published, and ``--reference`` builds
exactly that, which is what ``usc.verify`` compares against.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from . import collection as collection_module
from . import packaging, tts, variants
from .source import DeckSource, REPO_ROOT

DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "dist", "Ultimate_Spanish_Conjugation.apkg")


def make_source(
    keep_hypothetical: bool = False,
    speech: bool = True,
    reference: bool = False,
    lang: str = tts.DEFAULT_LANG,
    voices: Optional[str] = None,
    speed: Optional[float] = None,
) -> DeckSource:
    """Load the source data and apply the requested variants.

    With ``reference=True`` nothing is applied and the published deck is
    rebuilt as it stands.
    """
    source = DeckSource.load()
    if reference:
        return source
    if not keep_hypothetical:
        source = variants.without_hypothetical_forms(source)
    if speech:
        source = tts.with_tts(source, lang=lang, voices=voices, speed=speed)
    return source


def reference_source() -> DeckSource:
    """The published deck, untouched -- what ``usc.verify`` expects."""
    return make_source(reference=True)


def build(output_path: str = DEFAULT_OUTPUT, source: Optional[DeckSource] = None) -> str:
    source = source if source is not None else make_source()
    with tempfile.TemporaryDirectory() as workdir:
        collection_path = os.path.join(workdir, packaging.COLLECTION_ENTRY)
        collection_module.write_collection(source, collection_path)
        packaging.write_apkg(collection_path, source.collection["package"], output_path)
    return output_path


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build the Anki deck from data/ (customised by default)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="output .apkg path")
    parser.add_argument("--keep-hypothetical", action="store_true",
                        help="keep the hypothetical regular forms in the notes")
    parser.add_argument("--no-tts", action="store_true",
                        help="do not have the cards speak the Spanish form")
    parser.add_argument("--reference", action="store_true",
                        help="build the deck as published, with no changes at all")
    parser.add_argument("--tts-lang", default=tts.DEFAULT_LANG,
                        help="TTS language (default: %(default)s)")
    parser.add_argument("--tts-voices", default=None,
                        help="comma separated Anki voice names, e.g. "
                             "Apple_Mónica,Microsoft_Helena; leave unset so that "
                             "every platform, AnkiDroid included, picks its own voice")
    parser.add_argument("--tts-speed", type=float, default=None,
                        help="TTS speed, e.g. 0.8")
    args = parser.parse_args(argv)

    speech = not args.no_tts
    source = make_source(
        keep_hypothetical=args.keep_hypothetical,
        speech=speech,
        reference=args.reference,
        lang=args.tts_lang,
        voices=args.tts_voices,
        speed=args.tts_speed,
    )
    if args.reference:
        print("the deck as published, unchanged")
    else:
        print("hypothetical regular forms: {}".format(
            "kept" if args.keep_hypothetical else "dropped"))
        print("text-to-speech: {}".format(
            tts.tts_tag(args.tts_lang, args.tts_voices, args.tts_speed)
            if speech else "off"))
    path = build(args.output, source)
    print("notes: {}  cards: {}".format(len(source.notes), len(source.notes)))
    print("wrote {} ({} bytes)".format(path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
