#!/usr/bin/env python3
"""Verify the fresh seventeen-window tau scalar law and disjointness."""

import hashlib
import json
from pathlib import Path

from make_inputs import COUNT, N, SEED, SOURCES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    record = json.loads((HERE / "fresh-inputs.json").read_bytes())
    values = [int(value, 16) for value in record["scalars_hex"]]
    assert (record["schema"], record["seed"], record["count"], len(values)) == (
        1, SEED, COUNT, COUNT
    )
    assert record["scalar_sha256"] == sha(b"".join(v.to_bytes(32, "big") for v in values))
    assert set(record["source_sha256"]) == set(SOURCES)
    seen = set()
    for name in SOURCES:
        path = ROOT / "experiments" / name
        raw = path.read_bytes()
        assert record["source_sha256"][name] == sha(raw), name
        seen.update(int(value, 16) % N for value in json.loads(raw)["scalars_hex"])
    reduced = [value % N for value in values]
    assert len(set(reduced)) == COUNT
    assert not set(reduced) & seen
    print(f"input_verified=1 count={COUNT} scalar_sha256={record['scalar_sha256']}")


if __name__ == "__main__":
    main()
