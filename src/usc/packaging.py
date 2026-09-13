"""Writing the ``.apkg`` container.

An ``.apkg`` is a zip file holding ``collection.anki2`` plus a ``media`` map
(empty here: the deck ships no media).  The zip metadata of the original deck
-- entry order, compression method, timestamps and unix permissions -- is
reproduced from ``data/collection.json``.
"""

from __future__ import annotations

import os
import zipfile
from typing import Any, Dict, List

MEDIA_ENTRY = "media"
COLLECTION_ENTRY = "collection.anki2"


def write_apkg(collection_path: str, package: Dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    timestamp = tuple(package["timestamp"])
    with open(collection_path, "rb") as fh:
        collection_bytes = fh.read()
    payloads = {
        COLLECTION_ENTRY: collection_bytes,
        MEDIA_ENTRY: package["media"].encode("utf-8"),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in package["entries"]:
            info = zipfile.ZipInfo(entry["name"], timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = entry["create_system"]
            info.create_version = entry["create_version"]
            info.extract_version = entry["extract_version"]
            info.external_attr = entry["external_attr"]
            archive.writestr(info, payloads[entry["name"]])


def describe(path: str) -> List[Dict[str, Any]]:
    """The zip metadata of an ``.apkg``, for comparing two packages."""
    with zipfile.ZipFile(path) as archive:
        return [
            {
                "name": info.filename,
                "compress_type": info.compress_type,
                "timestamp": list(info.date_time),
                "create_system": info.create_system,
                "create_version": info.create_version,
                "extract_version": info.extract_version,
                "external_attr": info.external_attr,
                "size": info.file_size,
            }
            for info in archive.infolist()
        ]


def extract_entry(path: str, name: str, destination: str) -> str:
    with zipfile.ZipFile(path) as archive:
        data = archive.read(name)
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    with open(destination, "wb") as fh:
        fh.write(data)
    return destination
