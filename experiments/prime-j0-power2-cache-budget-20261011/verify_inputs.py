#!/usr/bin/env python3
"""Verify source-bound scalar draws and disjointness from prior panels."""

from hashlib import sha256
import json
from pathlib import Path

from make_inputs import (CONSTRUCTION_COMMIT, COUNT, ORDER, SEED, SOURCES)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "fresh-inputs.json").read_bytes()
    record = json.loads(raw)
    values = [int(value, 16) for value in record["scalars_hex"]]
    assert (record["schema"], record["seed"], record["count"], len(values)) == \
        (1, SEED, COUNT, COUNT)
    assert record["construction_commit"] == CONSTRUCTION_COMMIT
    assert record["scalar_sha256"] == digest(b"".join(
        value.to_bytes(32, "big") for value in values))
    assert set(record["source_sha256"]) == set(SOURCES)
    seen = set()
    for name in SOURCES:
        source = (ROOT / "experiments" / name).read_bytes()
        assert record["source_sha256"][name] == digest(source)
        seen.update(int(value, 16) % ORDER
                    for value in json.loads(source)["scalars_hex"])
    reduced = [value % ORDER for value in values]
    assert len(set(reduced)) == COUNT and not set(reduced) & seen
    output = {"schema": 1, "status": "passed", "count": COUNT,
              "input_sha256": digest(raw),
              "scalar_sha256": record["scalar_sha256"],
              "verifier_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "input-check.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
