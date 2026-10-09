#!/usr/bin/env python3
"""Generate exact unseen N41 pair-pair sums for equation validation."""

import hashlib
import json
import random
import struct
import time
from pathlib import Path

from produce import Curve, Field, pair_states

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    freeze = json.loads((HERE / "holdout_protocol.json").read_text())
    for name, expected in freeze["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"holdout input changed: {name}")
    if digest(Path(__file__)) != freeze["source_sha256"]["holdout.py"]:
        raise ValueError("holdout source changed after freeze")
    output = HERE / "holdout.bin"
    receipt = HERE / "holdout_production.json"
    if output.exists() or receipt.exists():
        raise FileExistsError("preserve first frozen held-out rows")
    protocol = json.loads((HERE / "protocol.json").read_text())
    geometry = json.loads(Path(protocol["inputs"]["geometry"]).read_text())["n41"]
    curve = Curve(Field(41, [0, 3]), 0)
    domains = [pair_states(curve, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in protocol["pair_rotations"]]
    used = set()
    training = (HERE / "rows.bin").read_bytes()
    if len(training) != protocol["row_count"] * 18:
        raise ValueError("training row count changed")
    for offset in range(0, len(training), 18):
        i, j = struct.unpack_from("<HH", training, offset + 14)
        used.add((i, j))
    if len(used) != protocol["row_count"]:
        raise ValueError("training index-pair duplicates")
    start = time.monotonic_ns()
    rng = random.Random(freeze["random_seed"])
    records = bytearray()
    draws = repeat = column_rejects = accepted = 0
    while accepted < freeze["row_count"]:
        if draws >= freeze["max_draws"]:
            raise TimeoutError("held-out draw cap before row count")
        i, j = rng.randrange(1956), rng.randrange(1956)
        draws += 1
        if (i, j) in used:
            repeat += 1
            continue
        used.add((i, j))
        left, right = domains[0][i], domains[1][j]
        if left[2] & right[2]:
            column_rejects += 1
            continue
        point = curve.add(left[1], right[1])
        if point is None or point[0] & 1:
            raise ValueError("held-out subgroup sum invalid")
        records.extend(bytes([left[0], right[0]]) +
                       point[0].to_bytes(6, "little") +
                       point[1].to_bytes(6, "little") + struct.pack("<HH", i, j))
        accepted += 1
    output.write_bytes(records)
    result = {"status": "EXACT_UNSEEN_ROWS_WRITTEN", "rows": accepted,
              "draws": draws, "training_or_holdout_duplicate_draws": repeat,
              "column_rejects": column_rejects,
              "rows_sha256": digest(output),
              "holdout_protocol_sha256": digest(HERE / "holdout_protocol.json"),
              "source_sha256": digest(Path(__file__)),
              "wall_ns": time.monotonic_ns() - start}
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "rows": accepted,
                      "draws": draws, "wall_s": result["wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
