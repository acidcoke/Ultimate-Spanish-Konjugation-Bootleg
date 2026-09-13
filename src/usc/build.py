"""Build the deck: source data -> ``.apkg``."""

from __future__ import annotations

import os
import tempfile

from . import collection as collection_module
from . import packaging, tts
from .source import DeckSource, REPO_ROOT

DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "dist", "Ultimate_Spanish_Conjugation.apkg")


def build(output_path: str = DEFAULT_OUTPUT, source: DeckSource = None) -> str:
    source = source or DeckSource.load()
    with tempfile.TemporaryDirectory() as workdir:
        collection_path = os.path.join(workdir, packaging.COLLECTION_ENTRY)
        collection_module.write_collection(source, collection_path)
        packaging.write_apkg(collection_path, source.collection["package"], output_path)
    return output_path


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build the Anki deck from data/")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="output .apkg path")
    parser.add_argument("--tts", action="store_true",
                        help="have the back of each card speak the Spanish form")
    parser.add_argument("--tts-lang", default=tts.DEFAULT_LANG,
                        help="TTS language (default: %(default)s)")
    parser.add_argument("--tts-voices", default=None,
                        help="comma separated Anki voice names, e.g. "
                             "Apple_M\u00f3nica,Microsoft_Helena")
    parser.add_argument("--tts-speed", type=float, default=None,
                        help="TTS speed, e.g. 0.8")
    args = parser.parse_args(argv)

    source = DeckSource.load()
    if args.tts:
        source = tts.with_tts(source, lang=args.tts_lang, voices=args.tts_voices,
                              speed=args.tts_speed)
        print("text-to-speech: {}".format(
            tts.tts_tag(args.tts_lang, args.tts_voices, args.tts_speed)))
    path = build(args.output, source)
    print("notes: {}  cards: {}".format(len(source.notes), len(source.notes)))
    print("wrote {} ({} bytes)".format(path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
