#!/usr/bin/env python3
"""Freeze a large JSON artifact as deterministic, GitHub-sized gzip shards."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, BinaryIO, Iterable

CHUNK_BYTES = 1024 * 1024
COMPRESSION_LEVEL = 9
DEFAULT_SHARD_BYTES = 48 * 1024 * 1024


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


class ShardedWriter(io.RawIOBase):
    def __init__(self, directory: Path, logical_name: str, shard_bytes: int) -> None:
        super().__init__()
        if shard_bytes < 1:
            raise ValueError("shard_bytes must be positive")
        self.directory = directory
        self.logical_name = logical_name
        self.shard_bytes = shard_bytes
        self.full_digest = hashlib.sha256()
        self.total_bytes = 0
        self.records: list[dict[str, int | str]] = []
        self.current: BinaryIO | None = None
        self.current_digest: Any | None = None
        self.current_bytes = 0

    def writable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.total_bytes

    def _open_next(self) -> None:
        index = len(self.records)
        path = self.directory / f"{self.logical_name}.part-{index:03d}"
        self.current = path.open("wb")
        self.current_digest = hashlib.sha256()
        self.current_bytes = 0

    def _finish_current(self) -> None:
        if self.current is None or self.current_digest is None:
            return
        path = Path(self.current.name)
        self.current.flush()
        self.current.close()
        self.records.append(
            {
                "name": path.name,
                "sha256": self.current_digest.hexdigest(),
                "bytes": self.current_bytes,
            }
        )
        self.current = None
        self.current_digest = None
        self.current_bytes = 0

    def write(self, data: bytes | bytearray | memoryview) -> int:
        if self.closed:
            raise ValueError("write to closed sharded stream")
        view = memoryview(data)
        written = 0
        while written < len(view):
            if self.current is None:
                self._open_next()
            assert self.current is not None
            assert self.current_digest is not None
            capacity = self.shard_bytes - self.current_bytes
            piece = view[written : written + capacity]
            count = self.current.write(piece)
            if count is None:
                count = len(piece)
            emitted = piece[:count]
            self.current_digest.update(emitted)
            self.full_digest.update(emitted)
            self.current_bytes += count
            self.total_bytes += count
            written += count
            if self.current_bytes == self.shard_bytes:
                self._finish_current()
        return written

    def flush(self) -> None:
        if self.current is not None:
            self.current.flush()

    def close(self) -> None:
        if not self.closed:
            self._finish_current()
        super().close()


class ConcatenatedReader(io.RawIOBase):
    def __init__(self, paths: Iterable[Path]) -> None:
        super().__init__()
        self.paths = iter(paths)
        self.current: BinaryIO | None = None

    def readable(self) -> bool:
        return True

    def _advance(self) -> bool:
        if self.current is not None:
            self.current.close()
        try:
            self.current = next(self.paths).open("rb")
        except StopIteration:
            self.current = None
        return self.current is not None

    def readinto(self, buffer: bytearray | memoryview) -> int:
        view = memoryview(buffer)
        total = 0
        while total < len(view):
            if self.current is None and not self._advance():
                break
            assert self.current is not None
            count = self.current.readinto(view[total:])
            if count:
                total += count
            else:
                self._advance()
        return total

    def close(self) -> None:
        if self.current is not None:
            self.current.close()
            self.current = None
        super().close()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def shard_paths(archive_prefix: Path, manifest: dict) -> list[Path]:
    return [archive_prefix.parent / row["name"] for row in manifest["archive"]["shards"]]


def pack_shards(source: Path, archive_prefix: Path, shard_bytes: int) -> dict:
    archive_prefix.parent.mkdir(parents=True, exist_ok=True)
    source_hash, source_bytes = sha256(source)
    with tempfile.TemporaryDirectory(
        prefix=archive_prefix.name + ".", dir=archive_prefix.parent
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        writer = ShardedWriter(temporary_root, archive_prefix.name, shard_bytes)
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=COMPRESSION_LEVEL,
            fileobj=writer,
            mtime=0,
        ) as compressed:
            with source.open("rb") as raw_input:
                for block in iter(lambda: raw_input.read(CHUNK_BYTES), b""):
                    compressed.write(block)
        writer.close()
        expected_names = {str(row["name"]) for row in writer.records}
        for old_part in archive_prefix.parent.glob(archive_prefix.name + ".part-*"):
            if old_part.name not in expected_names:
                old_part.unlink()
        for row in writer.records:
            (temporary_root / str(row["name"])).replace(
                archive_prefix.parent / str(row["name"])
            )
    return {
        "schema_version": 1,
        "format": "gzip-shards",
        "determinism": {
            "compression_level": COMPRESSION_LEVEL,
            "filename": "",
            "mtime": 0,
            "shard_bytes": shard_bytes,
        },
        "uncompressed": {
            "name": source.name,
            "sha256": source_hash,
            "bytes": source_bytes,
        },
        "archive": {
            "logical_name": archive_prefix.name,
            "sha256": writer.full_digest.hexdigest(),
            "bytes": writer.total_bytes,
            "shards": writer.records,
        },
    }


def verify_shards(archive_prefix: Path, manifest: dict) -> dict[str, int | str]:
    assert manifest["format"] == "gzip-shards"
    assert manifest["archive"]["logical_name"] == archive_prefix.name
    paths = shard_paths(archive_prefix, manifest)
    assert paths
    combined_digest = hashlib.sha256()
    combined_bytes = 0
    for path, row in zip(paths, manifest["archive"]["shards"], strict=True):
        part_hash, part_bytes = sha256(path)
        assert part_hash == row["sha256"]
        assert part_bytes == row["bytes"]
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(CHUNK_BYTES), b""):
                combined_digest.update(block)
                combined_bytes += len(block)
    archive_hash = combined_digest.hexdigest()
    assert archive_hash == manifest["archive"]["sha256"]
    assert combined_bytes == manifest["archive"]["bytes"]
    joined = ConcatenatedReader(paths)
    with io.BufferedReader(joined) as buffered:
        with gzip.GzipFile(fileobj=buffered, mode="rb") as decompressed:
            source_hash, source_bytes = sha256_stream(decompressed)
    assert source_hash == manifest["uncompressed"]["sha256"]
    assert source_bytes == manifest["uncompressed"]["bytes"]
    return {
        "archive_sha256": archive_hash,
        "archive_bytes": combined_bytes,
        "archive_shards": len(paths),
        "uncompressed_sha256": source_hash,
        "uncompressed_bytes": source_bytes,
    }


def materialize(archive_prefix: Path, manifest: dict, output: Path) -> dict[str, int | str]:
    verify_shards(archive_prefix, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=output.name + ".", suffix=".tmp", dir=output.parent
    )
    try:
        paths = shard_paths(archive_prefix, manifest)
        joined = ConcatenatedReader(paths)
        with os.fdopen(descriptor, "wb") as raw_output:
            with io.BufferedReader(joined) as buffered:
                with gzip.GzipFile(fileobj=buffered, mode="rb") as decompressed:
                    for block in iter(lambda: decompressed.read(CHUNK_BYTES), b""):
                        raw_output.write(block)
        Path(temporary_name).replace(output)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    output_hash, output_bytes = sha256(output)
    assert output_hash == manifest["uncompressed"]["sha256"]
    assert output_bytes == manifest["uncompressed"]["bytes"]
    return {
        "output": str(output),
        "uncompressed_sha256": output_hash,
        "uncompressed_bytes": output_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("--source", type=Path, required=True)
    pack_parser.add_argument("--archive-prefix", type=Path, required=True)
    pack_parser.add_argument("--manifest", type=Path, required=True)
    pack_parser.add_argument("--shard-bytes", type=int, default=DEFAULT_SHARD_BYTES)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--archive-prefix", type=Path, required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--source", type=Path)
    verify_parser.add_argument("--repack", action="store_true")

    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--archive-prefix", type=Path, required=True)
    materialize_parser.add_argument("--manifest", type=Path, required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "pack":
        manifest = pack_shards(args.source, args.archive_prefix, args.shard_bytes)
        write_json(args.manifest, manifest)
        status = {"status": "packed", **verify_shards(args.archive_prefix, manifest)}
    elif args.command == "verify":
        manifest = load_manifest(args.manifest)
        status = {"status": "verified", **verify_shards(args.archive_prefix, manifest)}
        if args.source is not None:
            source_hash, source_bytes = sha256(args.source)
            assert source_hash == manifest["uncompressed"]["sha256"]
            assert source_bytes == manifest["uncompressed"]["bytes"]
        if args.repack:
            if args.source is None:
                raise SystemExit("--repack requires --source")
            with tempfile.TemporaryDirectory(prefix="freeze-large-json-sharded-") as directory:
                replay_prefix = Path(directory) / args.archive_prefix.name
                replay = pack_shards(
                    args.source,
                    replay_prefix,
                    manifest["determinism"]["shard_bytes"],
                )
                assert replay["archive"] == manifest["archive"]
                for expected, actual in zip(
                    shard_paths(args.archive_prefix, manifest),
                    shard_paths(replay_prefix, replay),
                    strict=True,
                ):
                    assert expected.read_bytes() == actual.read_bytes()
            status["deterministic_repack_verified"] = True
    else:
        manifest = load_manifest(args.manifest)
        status = {
            "status": "materialized",
            **materialize(args.archive_prefix, manifest, args.output),
        }
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()
