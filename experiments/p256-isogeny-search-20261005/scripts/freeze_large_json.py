#!/usr/bin/env python3
"""Freeze, verify, or materialize a large JSON artifact as deterministic gzip."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import BinaryIO

CHUNK_BYTES = 1024 * 1024
COMPRESSION_LEVEL = 9


def sha256_stream(handle: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: handle.read(CHUNK_BYTES), b""):
        digest.update(block)
        size += len(block)
    return digest.hexdigest(), size


def sha256(path: Path) -> tuple[str, int]:
    with path.open("rb") as handle:
        return sha256_stream(handle)


def pack(source: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=archive.name + ".", suffix=".tmp", dir=archive.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as raw_output:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=COMPRESSION_LEVEL,
                fileobj=raw_output,
                mtime=0,
            ) as compressed:
                with source.open("rb") as raw_input:
                    for block in iter(lambda: raw_input.read(CHUNK_BYTES), b""):
                        compressed.write(block)
        Path(temporary_name).replace(archive)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_archive(archive: Path, manifest: dict) -> dict[str, int | str]:
    archive_hash, archive_bytes = sha256(archive)
    assert archive_hash == manifest["archive"]["sha256"]
    assert archive_bytes == manifest["archive"]["bytes"]
    with gzip.open(archive, "rb") as decompressed:
        source_hash, source_bytes = sha256_stream(decompressed)
    assert source_hash == manifest["uncompressed"]["sha256"]
    assert source_bytes == manifest["uncompressed"]["bytes"]
    return {
        "archive_sha256": archive_hash,
        "archive_bytes": archive_bytes,
        "uncompressed_sha256": source_hash,
        "uncompressed_bytes": source_bytes,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("--source", type=Path, required=True)
    pack_parser.add_argument("--archive", type=Path, required=True)
    pack_parser.add_argument("--manifest", type=Path, required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--archive", type=Path, required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--source", type=Path)
    verify_parser.add_argument("--repack", action="store_true")

    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--archive", type=Path, required=True)
    materialize_parser.add_argument("--manifest", type=Path, required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "pack":
        source_hash, source_bytes = sha256(args.source)
        pack(args.source, args.archive)
        archive_hash, archive_bytes = sha256(args.archive)
        manifest = {
            "schema_version": 1,
            "format": "gzip",
            "determinism": {
                "compression_level": COMPRESSION_LEVEL,
                "filename": "",
                "mtime": 0,
            },
            "uncompressed": {
                "name": args.source.name,
                "sha256": source_hash,
                "bytes": source_bytes,
            },
            "archive": {
                "name": args.archive.name,
                "sha256": archive_hash,
                "bytes": archive_bytes,
            },
        }
        write_json(args.manifest, manifest)
        status = {"status": "packed", **verify_archive(args.archive, manifest)}
    elif args.command == "verify":
        manifest = load_manifest(args.manifest)
        status = {"status": "verified", **verify_archive(args.archive, manifest)}
        if args.source is not None:
            source_hash, source_bytes = sha256(args.source)
            assert source_hash == manifest["uncompressed"]["sha256"]
            assert source_bytes == manifest["uncompressed"]["bytes"]
        if args.repack:
            if args.source is None:
                raise SystemExit("--repack requires --source")
            with tempfile.TemporaryDirectory(prefix="freeze-large-json-") as directory:
                replay = Path(directory) / args.archive.name
                pack(args.source, replay)
                assert replay.read_bytes() == args.archive.read_bytes()
            status["deterministic_repack_verified"] = True
    else:
        manifest = load_manifest(args.manifest)
        verify_archive(args.archive, manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=args.output.name + ".", suffix=".tmp", dir=args.output.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as raw_output:
                with gzip.open(args.archive, "rb") as decompressed:
                    for block in iter(lambda: decompressed.read(CHUNK_BYTES), b""):
                        raw_output.write(block)
            Path(temporary_name).replace(args.output)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        output_hash, output_bytes = sha256(args.output)
        assert output_hash == manifest["uncompressed"]["sha256"]
        assert output_bytes == manifest["uncompressed"]["bytes"]
        status = {
            "status": "materialized",
            "output": str(args.output),
            "uncompressed_sha256": output_hash,
            "uncompressed_bytes": output_bytes,
        }

    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()
