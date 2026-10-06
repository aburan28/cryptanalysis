"""Bounded Boolean Macaulay construction and persistent packed-row caching.

The ring is GF(2)[v_0, ..., v_n]/(v_i**2 + v_i). Monomials are variable
masks; a matrix row is an integer whose bits index ascending grevlex columns.
This module performs no root extraction or elliptic-curve operations.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import math
import os
import struct
import sys
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


CACHE_SCHEMA = 1
RING_VERSION = "gf2-squarefree-grevlex-v1"
MAGIC = b"BMAC001\n"
MAX_HEADER_BYTES = 4096
MAX_VARIABLES = 4096
DEFAULT_MAX_BYTES = 64 * 1024 * 1024


def _json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _natural(value, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def ring_identity(nvars: int, variables=None) -> dict:
    _natural(nvars, "nvars")
    if nvars > MAX_VARIABLES:
        raise ValueError(f"nvars exceeds the supported limit of {MAX_VARIABLES}")
    names = tuple(f"v{i}" for i in range(nvars)) if variables is None else tuple(variables)
    if (len(names) != nvars or any(not isinstance(v, str) or not v for v in names)
            or len(set(names)) != nvars):
        raise ValueError("variables must contain nvars distinct nonempty names")
    return {"representation": RING_VERSION, "variables": names}


class MacaulayCache:
    """Memory LRU plus optional Redis and atomic disk caches for integer rows.

    Disk records are checksummed, length-bounded data, never pickle objects.
    Disk capacity is a best-effort bound under concurrent writers. Each entry
    has a strict payload limit; the LRU bounds accounted retained bytes.
    Cache I/O failure rebuilds the requested rows and is visible in stats.
    """

    def __init__(self, directory=None, *, memory_bytes=32 * 1024 * 1024,
                 max_entry_bytes=DEFAULT_MAX_BYTES,
                 disk_bytes=256 * 1024 * 1024, redis_store=None):
        for name, value in (("memory_bytes", memory_bytes),
                            ("max_entry_bytes", max_entry_bytes),
                            ("disk_bytes", disk_bytes)):
            _natural(value, name)
        self.directory = None if directory is None else Path(directory)
        self.memory_bytes = memory_bytes
        self.max_entry_bytes = max_entry_bytes
        self.disk_bytes = disk_bytes
        self.redis_store = redis_store
        self._memory = OrderedDict()
        self._memory_size = 0
        self.stats = dict.fromkeys((
            "requests", "memory_hits", "disk_hits", "misses", "builds",
            "invalid_entries", "read_errors", "writes", "write_errors",
            "oversize_skips", "disk_evictions", "bytes_read", "bytes_written",
        ), 0)
        self.stats.update(dict.fromkeys((
            "key_seconds", "read_seconds", "build_seconds", "write_seconds",
            "total_seconds",
        ), 0.0))
        self.stats["redis"] = None if redis_store is None else redis_store.stats

    @classmethod
    def from_environment(cls, directory=None, **kwargs):
        """Use the offering's Redis endpoint if configured; no eager network I/O."""
        from macaulay_redis import RedisArtifactStore

        return cls(directory, redis_store=RedisArtifactStore.from_environment(), **kwargs)

    @staticmethod
    def key(spec: dict, ncols: int, nrows: int) -> str:
        return hashlib.sha256(_json_bytes({
            "schema": CACHE_SCHEMA, "spec": spec, "ncols": ncols, "nrows": nrows,
        })).hexdigest()

    def path_for(self, key: str) -> Path:
        if self.directory is None:
            raise ValueError("memory-only cache has no disk path")
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("invalid cache key")
        return self.directory / f"v{CACHE_SCHEMA}-{key}.bmc"

    @staticmethod
    def _validate(rows: tuple[int, ...], ncols: int, nrows: int) -> None:
        if len(rows) != nrows or any(
                type(row) is not int or row < 0 or row.bit_length() > ncols
                for row in rows):
            raise ValueError("cached row dimensions or coefficients do not match")

    def _remember(self, key: str, rows: tuple[int, ...]) -> None:
        size = sys.getsizeof(rows) + sum(sys.getsizeof(row) for row in rows)
        size += sys.getsizeof(key) + 128  # account for the LRU entry as well
        if size > self.memory_bytes:
            return
        while self._memory and self._memory_size + size > self.memory_bytes:
            _, (_, old_size) = self._memory.popitem(last=False)
            self._memory_size -= old_size
        self._memory[key] = (rows, size)
        self._memory_size += size

    @staticmethod
    def _decode_record(read, key: str, ncols: int, nrows: int) -> tuple[int, ...]:
        stride = max(1, (ncols + 7) // 8)
        expected_size = stride * nrows
        if read(len(MAGIC)) != MAGIC:
            raise ValueError("cache format mismatch")
        length = read(4)
        if len(length) != 4:
            raise ValueError("truncated cache header")
        header_size, = struct.unpack("<I", length)
        if header_size > MAX_HEADER_BYTES:
            raise ValueError("oversize cache header")
        header = json.loads(read(header_size))
        payload = read(expected_size + 1)
        expected_header = {
            "schema": CACHE_SCHEMA, "key": key, "ncols": ncols, "nrows": nrows,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if header != expected_header or len(payload) != expected_size:
            raise ValueError("cache identity, length or checksum mismatch")
        rows = tuple(int.from_bytes(payload[i:i + stride], "little")
                     for i in range(0, len(payload), stride))
        MacaulayCache._validate(rows, ncols, nrows)
        return rows

    def _read(self, key: str, ncols: int, nrows: int) -> tuple[int, ...]:
        with self.path_for(key).open("rb") as source:
            def read(size):
                chunk = source.read(size)
                self.stats["bytes_read"] += len(chunk)
                return chunk

            return self._decode_record(read, key, ncols, nrows)

    def _read_redis(self, key: str, ncols: int, nrows: int):
        payload_size = nrows * max(1, (ncols + 7) // 8)
        store = self.redis_store
        if payload_size > store.max_bytes:
            store.stats["oversize_skips"] += 1
            return None
        limit = len(MAGIC) + 4 + MAX_HEADER_BYTES + payload_size
        record = store.get(store.key(key, CACHE_SCHEMA), limit)
        if record is None:
            return None
        try:
            rows = self._decode_record(io.BytesIO(record).read, key, ncols, nrows)
        except (ValueError, UnicodeError, RecursionError):
            store.stats["invalid_entries"] += 1
            return None
        store.stats["hits"] += 1
        return rows

    def _make_room(self, path: Path, size: int) -> None:
        entries = []
        for candidate in self.directory.glob(f"v{CACHE_SCHEMA}-*.bmc"):
            stem = candidate.stem.split("-", 1)[-1]
            if (len(stem) != 64 or any(c not in "0123456789abcdef" for c in stem)
                    or candidate.is_symlink()):
                continue
            try:
                stat = candidate.stat()
            except FileNotFoundError:  # another writer may have evicted it
                continue
            if candidate != path:
                entries.append((stat.st_mtime_ns, candidate, stat.st_size))
        total = size + sum(entry[2] for entry in entries)
        for _, candidate, entry_size in sorted(entries):
            if total <= self.disk_bytes:
                break
            try:
                candidate.unlink()
                self.stats["disk_evictions"] += 1
            except FileNotFoundError:
                pass
            total -= entry_size

    @staticmethod
    def _encode_record(key: str, ncols: int, rows: tuple[int, ...]) -> bytes:
        stride = max(1, (ncols + 7) // 8)
        payload = b"".join(row.to_bytes(stride, "little") for row in rows)
        header = _json_bytes({
            "schema": CACHE_SCHEMA, "key": key, "ncols": ncols, "nrows": len(rows),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
        return MAGIC + struct.pack("<I", len(header)) + header + payload

    def _write(self, key: str, record: bytes) -> None:
        size = len(record)
        if size > self.disk_bytes:
            self.stats["oversize_skips"] += 1
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(key)
        self._make_room(path, size)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".bmac-",
                                             delete=False) as destination:
                temporary = Path(destination.name)
                destination.write(record)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, path)
            self.stats["writes"] += 1
            self.stats["bytes_written"] += size
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

    def _store(self, key: str, ncols: int, rows: tuple[int, ...], *, disk=True, remote=True):
        disk = disk and self.directory is not None
        remote = remote and self.redis_store is not None
        if not disk and not remote:
            return
        started = time.perf_counter()
        try:
            record = self._encode_record(key, ncols, rows)
            if disk:
                try:
                    self._write(key, record)
                except OSError:
                    self.stats["write_errors"] += 1
            if remote:
                self.redis_store.put(self.redis_store.key(key, CACHE_SCHEMA), record)
        finally:
            self.stats["write_seconds"] += time.perf_counter() - started

    def get_or_build(self, spec: dict, ncols: int, nrows: int, build) -> tuple[int, ...]:
        """Reuse only the exact versioned identity, shape and ordered inputs."""
        _natural(ncols, "ncols")
        _natural(nrows, "nrows")
        started = time.perf_counter()
        self.stats["requests"] += 1
        try:
            key = self.key(spec, ncols, nrows)
            self.stats["key_seconds"] += time.perf_counter() - started
            cacheable = nrows * max(1, (ncols + 7) // 8) <= self.max_entry_bytes
            read_started = time.perf_counter()
            rows = None
            source = None
            try:
                if key in self._memory:
                    rows, _ = self._memory[key]
                    self._memory.move_to_end(key)
                    self.stats["memory_hits"] += 1
                    return rows
                if cacheable and self.redis_store is not None:
                    rows = self._read_redis(key, ncols, nrows)
                    if rows is not None:
                        source = "redis"
                if rows is None and cacheable and self.directory is not None:
                    try:
                        rows = self._read(key, ncols, nrows)
                    except FileNotFoundError:
                        pass
                    except (ValueError, UnicodeError, RecursionError):
                        self.stats["invalid_entries"] += 1
                    except OSError:
                        self.stats["read_errors"] += 1
                    else:
                        self.stats["disk_hits"] += 1
                        source = "disk"
            finally:
                self.stats["read_seconds"] += time.perf_counter() - read_started
            if rows is not None:
                self._remember(key, rows)
                # A local precompute can populate the shared offering; remote
                # hits also become local fallbacks without refreshing their TTL.
                self._store(key, ncols, rows, disk=source == "redis", remote=source == "disk")
                return rows
            self.stats["misses"] += 1
            build_started = time.perf_counter()
            try:
                rows = tuple(build())
                self._validate(rows, ncols, nrows)
            finally:
                self.stats["build_seconds"] += time.perf_counter() - build_started
            self.stats["builds"] += 1
            if cacheable:
                self._remember(key, rows)
                self._store(key, ncols, rows)
            else:
                self.stats["oversize_skips"] += 1
            return rows
        finally:
            self.stats["total_seconds"] += time.perf_counter() - started


def monomial_count(nvars: int, degree: int) -> int:
    _natural(nvars, "nvars")
    _natural(degree, "degree")
    if nvars > MAX_VARIABLES:
        raise ValueError(f"nvars exceeds the supported limit of {MAX_VARIABLES}")
    return sum(math.comb(nvars, d) for d in range(min(nvars, degree) + 1))


def monomial_layout(nvars: int, degree: int, *, cache=None, variables=None,
                    max_columns=100_000) -> tuple[int, ...]:
    _natural(nvars, "nvars")
    _natural(degree, "degree")
    count = monomial_count(nvars, degree)
    if count > max_columns:
        raise ValueError(f"monomial layout needs {count} columns; limit is {max_columns}")
    ring = ring_identity(nvars, variables)

    def build():
        if degree >= nvars:
            masks = range(1 << nvars)
        else:
            masks = (sum(1 << i for i in indices)
                     for d in range(degree + 1)
                     for indices in itertools.combinations(range(nvars), d))
        # For squarefree masks, -mask is the reverse lexicographic tie break.
        return sorted(masks, key=lambda mask: (mask.bit_count(), -mask))

    if cache is None:
        return tuple(build())
    return cache.get_or_build({"kind": "monomial-layout-v1", "ring": ring,
                               "degree": degree}, nvars, count, build)


@dataclass(frozen=True)
class MacaulayMatrix:
    columns: tuple[int, ...]
    sources: tuple[tuple[int, int], ...]  # (input equation index, multiplier mask)
    rows: tuple[int, ...]
    key: str


def boolean_macaulay(equations, nvars: int, degree: int, *, cache=None,
                      variables=None, context=None, max_columns=100_000,
                      max_rows=100_000, max_matrix_bytes=DEFAULT_MAX_BYTES) -> MacaulayMatrix:
    """Rows t*f_i for squarefree t with deg(t) <= degree - deg(f_i).

    Multiplication is in the Boolean quotient, including GF(2) cancellation.
    Zero generators have no rows. A degree below any nonzero input degree is
    rejected, so the matrix never silently drops an input equation.
    """
    _natural(nvars, "nvars")
    _natural(degree, "degree")
    ncols = monomial_count(nvars, degree)
    if ncols > max_columns:
        raise ValueError(f"matrix needs {ncols} columns; limit is {max_columns}")
    ring = ring_identity(nvars, variables)
    canonical = []
    degrees = []
    for equation in equations:
        terms = set()
        for mask in equation:
            _natural(mask, "monomial mask")
            if mask.bit_length() > nvars:
                raise ValueError("monomial uses a variable outside the ring")
            terms.symmetric_difference_update((mask,))
        canonical.append(tuple(sorted(terms)))
        degrees.append(max((mask.bit_count() for mask in terms), default=-1))
    if any(d > degree for d in degrees):
        raise ValueError("degree bound is below an input equation's degree")
    nrows = sum(monomial_count(nvars, degree - d) for d in degrees if d >= 0)
    if nrows > max_rows:
        raise ValueError(f"matrix needs {nrows} rows; limit is {max_rows}")
    if nrows * max(1, (ncols + 7) // 8) > max_matrix_bytes:
        raise ValueError("matrix exceeds the packed-byte construction limit")
    columns = monomial_layout(nvars, degree, cache=cache,
                              variables=ring["variables"], max_columns=max_columns)
    multipliers = {d: monomial_layout(nvars, degree - d, cache=cache,
                                      variables=ring["variables"], max_columns=max_columns)
                   for d in set(degrees) if d >= 0}
    sources = tuple((i, mask) for i, d in enumerate(degrees) if d >= 0
                    for mask in multipliers[d])
    spec = {"kind": "boolean-macaulay-v1", "ring": ring, "degree": degree,
            "equations": canonical, "context": context}

    def build():
        ranks = {mask: rank for rank, mask in enumerate(columns)}
        for i, multiplier in sources:
            row = 0
            for mask in canonical[i]:
                row ^= 1 << ranks[mask | multiplier]
            yield row

    rows = tuple(build()) if cache is None else cache.get_or_build(spec, ncols, nrows, build)
    return MacaulayMatrix(columns, sources, rows, MacaulayCache.key(spec, ncols, nrows))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="JSON with nvars and equations as monomial masks")
    source.add_argument("--nvars", type=int, help="precompute just the target-independent layout")
    parser.add_argument("--degree", type=int, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/macaulay"))
    args = parser.parse_args()
    cache = MacaulayCache.from_environment(args.cache_dir)
    started = time.perf_counter()
    try:
        if args.input is None:
            columns = monomial_layout(args.nvars, args.degree, cache=cache)
            report = {"artifact": "monomial_layout", "columns": len(columns)}
        else:
            data = json.loads(args.input.read_text())
            matrix = boolean_macaulay(data["equations"], data["nvars"], args.degree,
                                       cache=cache, variables=data.get("variables"),
                                       context=data.get("context"))
            report = {"artifact": "boolean_macaulay", "key": matrix.key,
                      "columns": len(matrix.columns), "rows": len(matrix.rows),
                      "nonzeros": sum(row.bit_count() for row in matrix.rows)}
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    report.update({"cache_dir": str(args.cache_dir), "cache": cache.stats,
                   "elapsed_seconds": time.perf_counter() - started})
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
