# Generating the deck

From the repository root:

```sh
PYTHONPATH=src python -m usc build
```

It writes `dist/Ultimate_Spanish_Conjugation.apkg` — 4246 notes, no
hypothetical regular forms, the Spanish form read aloud on the back — ready
to import into Anki or AnkiDroid.

Variations:

```sh
PYTHONPATH=src python -m usc build -o /tmp/deck.apkg   # somewhere else
PYTHONPATH=src python -m usc build --no-tts            # silent cards
PYTHONPATH=src python -m usc build --keep-hypothetical # keep "the hypothetical regular form X is incorrect"
PYTHONPATH=src python -m usc build --reference         # the deck exactly as published
```

Check the generator against the published deck:

```sh
PYTHONPATH=src python -m usc verify path/to/Ultimate_Spanish_Conjugation.apkg
```

[README.md](README.md) explains the source data and what "1:1" covers.
