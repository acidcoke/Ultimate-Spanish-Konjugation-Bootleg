"""``python -m usc <command>`` -- build, extract or verify the deck."""

from __future__ import annotations

import sys

COMMANDS = {"build": "usc.build", "extract": "usc.extract", "verify": "usc.verify"}

USAGE = """usage: python -m usc <command> [options]

commands:
  build     build dist/Ultimate_Spanish_Conjugation.apkg from data/ and assets/
  extract   rebuild data/ and assets/ from a reference .apkg
  verify    compare a generated .apkg with a reference .apkg
"""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        sys.stderr.write(USAGE)
        return 2
    import importlib

    module = importlib.import_module(COMMANDS[argv[0]])
    return module.main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
