#!/usr/bin/env python3
"""Stream an enumerated factor base into content-addressed point/orbit shards.

The archive stores mathematical identities supplied by a producer, but does
not prove an orbit key or column coefficient. Those need separate verification
before they can be used as relation-matrix evidence.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable

SCHEMA = "ic-factor-base-shards/1"
FIELDS = {"point", "subgroup_projection", "orbit_key", "frobenius_phase",
          "sign", "column_id", "column_coefficient"}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _hex_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        c in "0123456789abcdef" for c in value)


def _point(value: object, degree: int) -> bool:
    return (isinstance(value, list) and len(value) == 2
            and all(type(x) is int and 0 <= x < (1 << degree) for x in value))


def validate_row(row: object, degree: int) -> tuple[int, int]:
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError(f"row requires exactly {sorted(FIELDS)}")
    if not _point(row["point"], degree):
        raise ValueError("point must contain two field elements")
    projection = row["subgroup_projection"]
    if projection is not None and not _point(projection, degree):
        raise ValueError("subgroup_projection must be a point or null")
    for field in ("orbit_key", "frobenius_phase", "column_id"):
        value = row[field]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"{field} must be a nonnegative integer or null")
    if row["frobenius_phase"] is not None and row["frobenius_phase"] >= degree:
        raise ValueError("frobenius_phase is outside the field orbit")
    if row["sign"] is not None and (
            type(row["sign"]) is not int or row["sign"] not in (-1, 1)):
        raise ValueError("sign must be -1, 1 or null")
    coeff = row["column_coefficient"]
    if coeff is not None and (type(coeff) is not int or coeff < 0):
        raise ValueError("column_coefficient must be nonnegative or null")
    if (row["column_id"] is None) != (coeff is None):
        raise ValueError("column_id and coefficient must be both present or both null")
    return tuple(row["point"])


def _metadata(record: dict) -> tuple[dict, int, int, str]:
    if not isinstance(record, dict) or set(record) != {"field", "curve", "factor_base"}:
        raise ValueError("record requires field, curve and factor_base")
    fb, curve, field = record["factor_base"], record["curve"], record["field"]
    if not all(isinstance(x, dict) for x in (fb, curve, field)):
        raise ValueError("field, curve and factor_base must be objects")
    degree = field.get("degree")
    if type(degree) is not int or degree < 1:
        raise ValueError("field.degree must be a positive integer")
    if (not isinstance(curve.get("curve_id"), str)
            or curve["curve_id"] != fb.get("curve_id")):
        raise ValueError("curve ID mismatch")
    count = fb.get("actual_usable_point_count")
    expected = fb.get("enumerated_set_sha256")
    if type(count) is not int or count < 0 or not _hex_sha(expected):
        raise ValueError("recipe-only bases have unknown count/digest; enumerate first")
    return fb, degree, count, expected


def _safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("shard path leaves archive directory")
    return path


def _file_sha(path: Path) -> tuple[str, int]:
    h, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _publish(source: Path, destination: Path, sha: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if _file_sha(destination)[0] != sha:
            raise ValueError("existing content-addressed object differs")
        source.unlink()
    else:
        os.replace(source, destination)


def write_shards(root: Path, record: dict, rows: Iterable[dict], *,
                 shard_records: int = 100_000) -> Path:
    """Write sorted point rows with bounded memory; return immutable manifest."""
    if shard_records < 1:
        raise ValueError("shard_records must be positive")
    fb, degree, expected_count, expected_sha = _metadata(record)
    root.mkdir(parents=True, exist_ok=True)
    total, entries, previous = 0, [], None
    points_hash = hashlib.sha256()
    points_hash.update(b"[")
    iterator = iter(rows)
    while True:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".shard-", delete=False) as temp:
            temporary = Path(temp.name)
            content_hash = hashlib.sha256()
            count, first, last = 0, None, None
            with gzip.GzipFile(filename="", mode="wb", fileobj=temp, mtime=0,
                               compresslevel=9) as zipped:
                for row in iterator:
                    key = validate_row(row, degree)
                    if previous is not None and key <= previous:
                        raise ValueError("points must be strictly increasing (x, y)")
                    previous = key
                    point_bytes = canonical(row["point"])
                    if total:
                        points_hash.update(b",")
                    points_hash.update(point_bytes)
                    line = canonical(row) + b"\n"
                    zipped.write(line)
                    content_hash.update(line)
                    count += 1
                    total += 1
                    if first is None:
                        first = row["point"]
                    last = row["point"]
                    if count == shard_records:
                        break
            temp.flush()
            os.fsync(temp.fileno())
        if count == 0:
            temporary.unlink()
            break
        file_sha, size = _file_sha(temporary)
        rel = f"shards/{content_hash.hexdigest()[:2]}/{content_hash.hexdigest()}.jsonl.gz"
        _publish(temporary, root / rel, file_sha)
        entries.append({"path": rel, "first_point": first, "last_point": last,
                        "records": count, "content_sha256": content_hash.hexdigest(),
                        "file_sha256": file_sha, "bytes": size})
    points_hash.update(b"]")
    if total != expected_count or points_hash.hexdigest() != expected_sha:
        raise ValueError("point count or enumerated_set_sha256 differs from factor_base record")
    manifest = {"schema": SCHEMA, "field": record["field"], "curve": record["curve"],
                "factor_base": fb, "factor_base_sha256": digest(fb),
                "enumerated_set_sha256": expected_sha, "record_count": total,
                "shards": entries,
                "annotations_verified": False}
    payload = canonical(manifest) + b"\n"
    manifest_sha = hashlib.sha256(payload).hexdigest()
    target = root / "manifests" / f"{manifest_sha}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != payload:
        raise ValueError("existing manifest digest collision")
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".manifest-",
                                         delete=False) as temp:
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
            os.replace(temp.name, target)
    return target


def verify(manifest_path: Path) -> dict:
    """Verify content, order, and the existing base digest; no orbit math claim."""
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent.parent
    payload = manifest_path.read_bytes()
    if manifest_path.name != hashlib.sha256(payload).hexdigest() + ".json":
        raise ValueError("manifest filename does not match content")
    manifest = json.loads(payload)
    if payload != canonical(manifest) + b"\n" or manifest.get("schema") != SCHEMA:
        raise ValueError("invalid manifest encoding or schema")
    record = {k: manifest[k] for k in ("field", "curve", "factor_base")}
    fb, degree, expected_count, expected_sha = _metadata(record)
    if (manifest["factor_base_sha256"] != digest(fb)
            or manifest["enumerated_set_sha256"] != expected_sha
            or manifest["record_count"] != expected_count
            or manifest["annotations_verified"] is not False):
        raise ValueError("manifest identity or count mismatch")
    total, previous = 0, None
    points_hash = hashlib.sha256()
    points_hash.update(b"[")
    for entry in manifest["shards"]:
        path = _safe_path(root, entry["path"])
        file_sha, size = _file_sha(path)
        if file_sha != entry["file_sha256"] or size != entry["bytes"]:
            raise ValueError(f"{entry['path']}: compressed shard digest/size mismatch")
        content_hash = hashlib.sha256()
        count, first, last = 0, None, None
        with gzip.open(path, "rb") as stream:
            for line in stream:
                row = json.loads(line)
                if line != canonical(row) + b"\n":
                    raise ValueError("noncanonical row")
                key = validate_row(row, degree)
                if previous is not None and key <= previous:
                    raise ValueError("points not strictly sorted or repeated")
                previous = key
                if total:
                    points_hash.update(b",")
                points_hash.update(canonical(row["point"]))
                content_hash.update(line)
                count += 1
                total += 1
                if first is None:
                    first = row["point"]
                last = row["point"]
        if (count != entry["records"] or first != entry["first_point"]
                or last != entry["last_point"]
                or content_hash.hexdigest() != entry["content_sha256"]
                or not entry["path"].endswith(content_hash.hexdigest() + ".jsonl.gz")):
            raise ValueError(f"{entry['path']}: shard identity/count mismatch")
    points_hash.update(b"]")
    if total != expected_count or points_hash.hexdigest() != expected_sha:
        raise ValueError("enumerated point set does not match factor_base record")
    return {"factor_base_sha256": manifest["factor_base_sha256"],
            "record_count": total, "shards": len(manifest["shards"]),
            "annotations_verified": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="stream sorted JSONL rows into shards")
    ingest.add_argument("--record", type=Path, required=True,
                        help="JSON object with field, curve, factor_base")
    ingest.add_argument("--rows", required=True, help="JSONL file or - for stdin")
    ingest.add_argument("--out", type=Path, required=True)
    ingest.add_argument("--shard-records", type=int, default=100_000)
    check = sub.add_parser("verify", help="verify a content-addressed manifest")
    check.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            print(json.dumps(verify(args.manifest), sort_keys=True))
        else:
            record = json.loads(args.record.read_text())
            stream = sys.stdin if args.rows == "-" else open(args.rows, encoding="utf-8")
            try:
                target = write_shards(args.out, record,
                    (json.loads(line) for line in stream if line.strip()),
                    shard_records=args.shard_records)
            finally:
                if stream is not sys.stdin:
                    stream.close()
            print(target)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"factor-base shard error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
