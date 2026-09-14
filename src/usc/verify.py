"""Compare a generated ``.apkg`` with the reference deck, 1:1.

Two packages are considered identical when

* the zip holds the same entries, in the same order, with the same
  compression, timestamps and permissions;
* the collections declare the same SQLite schema;
* every table holds exactly the same rows -- ``col`` (including the
  configuration, note type and deck JSON, compared as strings), ``notes``,
  ``cards``, ``revlog`` and ``graves``.

The raw bytes of ``collection.anki2`` are *not* compared: the reference file
was written by Anki's own SQLite build, so its page layout, free list and
"last written by" header field cannot be reproduced by another SQLite
version.  What the deck contains is compared exhaustively instead, which is
what Anki reads back when the deck is imported.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Tuple

from . import anki_schema, packaging
from . import collection as collection_module


def compare(generated_path: str, reference_path: str) -> List[str]:
    """Return a list of differences; empty means the decks are identical."""
    differences: List[str] = []
    differences += _compare_packages(generated_path, reference_path)
    with tempfile.TemporaryDirectory() as workdir:
        generated = packaging.extract_entry(
            generated_path, packaging.COLLECTION_ENTRY, os.path.join(workdir, "generated"))
        reference = packaging.extract_entry(
            reference_path, packaging.COLLECTION_ENTRY, os.path.join(workdir, "reference"))
        differences += _compare_schema(generated, reference)
        differences += _compare_tables(generated, reference)
    return differences


def _compare_packages(generated_path: str, reference_path: str) -> List[str]:
    generated = packaging.describe(generated_path)
    reference = packaging.describe(reference_path)
    if [entry["name"] for entry in generated] != [entry["name"] for entry in reference]:
        return ["package entries differ: %s vs %s"
                % ([e["name"] for e in generated], [e["name"] for e in reference])]
    differences = []
    for left, right in zip(generated, reference):
        for key in ("compress_type", "timestamp", "create_system", "create_version",
                    "extract_version", "external_attr"):
            if left[key] != right[key]:
                differences.append("zip entry %r: %s is %r, reference has %r"
                                   % (left["name"], key, left[key], right[key]))
    return differences


def _compare_schema(generated: str, reference: str) -> List[str]:
    left = [_normalise(sql) for sql in collection_module.dump_schema(generated)]
    right = [_normalise(sql) for sql in collection_module.dump_schema(reference)]
    if left != right:
        return ["SQLite schema differs:\n  built: %s\n  ref:   %s"
                % (_only_in(left, right), _only_in(right, left))]
    return []


def _compare_tables(generated: str, reference: str) -> List[str]:
    left = collection_module.dump_tables(generated)
    right = collection_module.dump_tables(reference)
    differences: List[str] = []
    for table in anki_schema.TABLES:
        rows_left, rows_right = left[table], right[table]
        if len(rows_left) != len(rows_right):
            differences.append("table %s: %d rows, reference has %d"
                               % (table, len(rows_left), len(rows_right)))
            continue
        mismatches = [(a, b) for a, b in zip(rows_left, rows_right) if a != b]
        if mismatches:
            differences.append("table %s: %d of %d rows differ; first difference: %s"
                               % (table, len(mismatches), len(rows_left),
                                  _describe_row_difference(mismatches[0])))
    return differences


def _describe_row_difference(pair: Tuple[Any, Any]) -> str:
    built, reference = pair
    for index, (left, right) in enumerate(zip(built, reference)):
        if left != right:
            return "column %d\n  built: %r\n  ref:   %r" % (index, left, right)
    return "%r != %r" % (built, reference)


def _normalise(sql: str) -> str:
    return " ".join(sql.split())


def _only_in(left: List[str], right: List[str]) -> str:
    return "; ".join(sorted(set(left) - set(right))) or "(nothing)"


def summary(generated_path: str, reference_path: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as workdir:
        generated = packaging.extract_entry(
            generated_path, packaging.COLLECTION_ENTRY, os.path.join(workdir, "generated"))
        reference = packaging.extract_entry(
            reference_path, packaging.COLLECTION_ENTRY, os.path.join(workdir, "reference"))
        return {
            "generated": collection_module.fingerprint(generated),
            "reference": collection_module.fingerprint(reference),
        }


def main(argv=None) -> int:
    import argparse

    from . import build as build_module

    parser = argparse.ArgumentParser(
        description="Check a generated .apkg against the reference deck")
    parser.add_argument("reference", help="the reference .apkg")
    parser.add_argument("-g", "--generated", default=None,
                        help="the .apkg to check (default: build one from data/ with "
                             "--reference, the deck as published)")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as workdir:
        generated = args.generated
        if generated is None:
            generated = build_module.build(os.path.join(workdir, "reference.apkg"),
                                           build_module.reference_source())
            print("built the reference deck from data/")
        differences = compare(generated, args.reference)
        fingerprints = summary(generated, args.reference)
        print("generated collection fingerprint: %s" % fingerprints["generated"])
        print("reference collection fingerprint: %s" % fingerprints["reference"])
    if differences:
        print("\nDIFFERENCES (%d):" % len(differences))
        for difference in differences:
            print("  - %s" % difference)
        return 1
    print("\nidentical: same schema, same rows, same package metadata")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
