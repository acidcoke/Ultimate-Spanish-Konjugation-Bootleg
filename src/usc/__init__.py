"""Generator for the *Ultimate Spanish Conjugation* Anki deck.

The package rebuilds the shared deck (AnkiWeb id 638411848) from the plain
source data in ``data/`` and ``assets/`` so that the resulting ``.apkg`` is
identical to the reference deck: same note type, same deck configuration,
same note/card ids, timestamps, guids and field HTML.

Modules
-------
``anki_schema``  the Anki 2.1 (schema 11) SQLite DDL
``source``       loading/saving the deck source data
``render``       rebuilding note fields from the structured source records
``collection``   writing ``collection.anki2``
``packaging``    writing the ``.apkg`` zip container
``build``        source data -> ``.apkg``
``extract``      reference ``.apkg`` -> source data (provenance tool)
``verify``       1:1 comparison of two ``.apkg`` files
"""

__all__ = ["build", "extract", "verify"]
__version__ = "1.0.0"
