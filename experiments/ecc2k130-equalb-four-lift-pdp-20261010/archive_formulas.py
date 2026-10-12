#!/usr/bin/env python3
"""Archive exact XCNF streams with deterministic gzip and raw-hash replay."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import build_four_lift as gate


def decompressed_sha(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    for name in ("w24", "normal4"):
        stem = name + "_m6_four_lift"
        raw = args.run_dir / (stem + ".xcnf")
        archive = args.run_dir / (stem + ".xcnf.gz")
        receipt_path = args.run_dir / (stem + ".json")
        archive_receipt_path = args.run_dir / (stem + ".archive.json")
        receipt = json.loads(receipt_path.read_text())
        if receipt["formula_sha256"] != (
                gate.ref.sha(raw) if raw.exists() else receipt["formula_sha256"]):
            raise ValueError("raw formula differs from build receipt")
        if not args.verify:
            if not raw.exists() or archive.exists() or archive_receipt_path.exists():
                raise ValueError("archive inputs or outputs already changed")
            with raw.open("rb") as source, archive.open("xb") as destination:
                with gzip.GzipFile(filename="", mode="wb", fileobj=destination,
                                   mtime=0, compresslevel=9) as stream:
                    for block in iter(lambda: source.read(1 << 20), b""):
                        stream.write(block)
        if not archive.exists():
            raise FileNotFoundError(archive)
        replay_sha, replay_bytes = decompressed_sha(archive)
        if replay_sha != receipt["formula_sha256"]:
            raise ValueError("decompressed XCNF differs from built formula")
        result = {
            "schema": "ecc2k130-four-lift-xcnf-archive-v1",
            "policy": receipt["policy"],
            "raw_formula_sha256": replay_sha,
            "raw_formula_bytes": replay_bytes,
            "archive_sha256": gate.ref.sha(archive),
            "archive_bytes": archive.stat().st_size,
            "formula_receipt_sha256": gate.ref.sha(receipt_path),
            "archiver_sha256": gate.ref.sha(Path(__file__)),
        }
        if args.verify:
            if result != json.loads(archive_receipt_path.read_text()):
                raise ValueError("archive receipt changed")
        else:
            archive_receipt_path.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n")
            raw.unlink()
        print(json.dumps({key: result[key] for key in
                          ("policy", "raw_formula_sha256", "raw_formula_bytes",
                           "archive_bytes")}, sort_keys=True))


if __name__ == "__main__":
    main()
