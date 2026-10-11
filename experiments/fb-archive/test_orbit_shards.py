"""Storage checks; these do not validate the mathematics of orbit annotations."""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import orbit_shards as shards  # noqa: E402


def _toy():
    path = next((HERE / "bases").glob("EC1N13C*/prefix-l3-s1-*.json.gz"))
    with gzip.open(path, "rb") as stream:
        doc = json.load(stream)
    record = {k: doc[k] for k in ("field", "curve", "factor_base")}
    rows = [{"point": p, "subgroup_projection": None, "orbit_key": None,
             "frobenius_phase": None, "sign": None, "column_id": None,
             "column_coefficient": None} for p in doc["points"]]
    return record, rows, doc


def test_existing_factor_base_streams_into_verified_bounded_shards(tmp_path: Path):
    record, rows, doc = _toy()
    manifest = shards.write_shards(tmp_path, record, iter(rows), shard_records=3)
    result = shards.verify(manifest)
    assert result == {"factor_base_sha256": doc["factor_base_sha256"],
                      "record_count": len(rows), "shards": 3,
                      "annotations_verified": False}
    body = json.loads(manifest.read_text())
    assert [entry["records"] for entry in body["shards"]] == [3, 3, 2]
    assert body["enumerated_set_sha256"] == doc["factor_base"]["enumerated_set_sha256"]
    assert shards.write_shards(tmp_path, record, iter(rows), shard_records=3) == manifest

    first = tmp_path / body["shards"][0]["path"]
    first.write_bytes(first.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="compressed shard"):
        shards.verify(manifest)


def test_exact_point_digest_and_order_are_required(tmp_path: Path):
    record, rows, _ = _toy()
    with pytest.raises(ValueError, match="strictly increasing"):
        shards.write_shards(tmp_path / "unsorted", record,
                            iter([rows[1], rows[0], *rows[2:]]), shard_records=3)
    with pytest.raises(ValueError, match="point count or enumerated"):
        shards.write_shards(tmp_path / "missing", record, iter(rows[:-1]), shard_records=3)
    recipe_only = json.loads(json.dumps(record))
    recipe_only["factor_base"]["actual_usable_point_count"] = None
    recipe_only["factor_base"]["enumerated_set_sha256"] = None
    with pytest.raises(ValueError, match="recipe-only"):
        shards.write_shards(tmp_path / "unknown", recipe_only, iter(rows))


def test_orbit_metadata_is_structured_but_explicitly_unverified(tmp_path: Path):
    record, rows, _ = _toy()
    rows[0] = {**rows[0], "subgroup_projection": rows[0]["point"],
               "orbit_key": rows[0]["point"][0], "frobenius_phase": 0,
               "sign": 1, "column_id": 0, "column_coefficient": 1}
    manifest = shards.write_shards(tmp_path, record, iter(rows), shard_records=4)
    assert shards.verify(manifest)["annotations_verified"] is False
    with pytest.raises(ValueError, match="both present"):
        shards.validate_row({**rows[0], "column_coefficient": None}, 13)
    with pytest.raises(ValueError, match="outside"):
        shards.validate_row({**rows[0], "frobenius_phase": 13}, 13)


def test_cli_ingests_jsonl_and_verifies_manifest(tmp_path: Path):
    record, rows, _ = _toy()
    metadata = tmp_path / "record.json"
    points = tmp_path / "points.jsonl"
    metadata.write_text(json.dumps(record), encoding="utf-8")
    points.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = subprocess.run([sys.executable, str(HERE / "orbit_shards.py"),
                             "ingest", "--record", str(metadata), "--rows", str(points),
                             "--out", str(tmp_path / "archive"), "--shard-records", "3"],
                            text=True, capture_output=True, check=True)
    check = subprocess.run([sys.executable, str(HERE / "orbit_shards.py"),
                            "verify", result.stdout.strip()],
                           text=True, capture_output=True, check=True)
    assert json.loads(check.stdout)["record_count"] == len(rows)
