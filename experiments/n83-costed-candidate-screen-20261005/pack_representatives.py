#!/usr/bin/env python3
"""Deterministically pack exact representative JSON without losing its digest."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    for geometry_path in sorted((HERE / "runs").glob("shifted_*/geometry.json")):
        folder = geometry_path.parent
        geometry = json.loads(geometry_path.read_text())
        if geometry["status"] != "EXACT_GEOMETRY_PASS":
            continue
        original = folder / "representatives.json"
        packed = folder / "representatives.json.gz"
        if original.is_file():
            if packed.exists():
                raise FileExistsError(packed)
            raw = original.read_bytes()
            assert sha(raw) == geometry["representatives_sha256"]
            with packed.open("wb") as sink:
                with gzip.GzipFile(fileobj=sink, mode="wb", filename="", mtime=0,
                                   compresslevel=9) as compressor:
                    compressor.write(raw)
            assert gzip.decompress(packed.read_bytes()) == raw
            original.unlink()
        else:
            assert packed.is_file()
            assert sha(gzip.decompress(packed.read_bytes())) == \
                geometry["representatives_sha256"]
        print(f"{folder.name}: {packed.stat().st_size} packed bytes; "
              "decompressed SHA-256 matches receipt")


if __name__ == "__main__":
    main()
