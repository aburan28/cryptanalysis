#!/usr/bin/env python3
"""Choose frozen exact sign-orbit rows without replacement."""

import hashlib
import json
import random
import struct
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "../n41_seed_bin_quadratic_filter_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sample_path = HERE / "sample.bin"
    index_path = HERE / "sample_indices.bin"
    receipt_path = HERE / "sample_receipt.json"
    if any(path.exists() for path in (sample_path, index_path, receipt_path)):
        raise FileExistsError("preserve first exact sampled rows")
    frozen = json.loads((HERE / "protocol.json").read_text())
    if sha(Path(__file__)) != frozen["source_sha256"]["sample.py"]:
        raise ValueError("sample source changed")
    for name, expected in frozen["input_sha256"].items():
        if sha(SOURCE / name) != expected:
            raise ValueError(f"exact suffix input changed: {name}")
    start = time.monotonic_ns()
    data = (SOURCE / "x_orbits.bin").read_bytes()
    if len(data) != frozen["exact_x_orbits"] * 12:
        raise ValueError("exact orbit file length changed")
    rng = random.Random(frozen["sample_random_seed"])
    indices = sorted(rng.sample(range(frozen["exact_x_orbits"]),
                                frozen["sample_rows"]))
    if len(set(indices)) != frozen["sample_rows"]:
        raise ValueError("sample index repeated")
    sampled = bytearray()
    packed_indices = bytearray()
    bins = Counter()
    for index in indices:
        record = data[index * 12:(index + 1) * 12]
        s, t = record[0], record[1]
        x = int.from_bytes(record[2:8], "little")
        if not (1 <= s <= 63 and 1 <= t <= 63) or x & 1 or x >> 41:
            raise ValueError("selected exact orbit encoding changed")
        bins[(s, t)] += 1
        packed_indices.extend(struct.pack("<I", index))
        sampled.extend(record[:8])
    if len(bins) < 3900:
        raise ValueError("sample seed-bin coverage lower than frozen preflight")
    sample_path.write_bytes(sampled)
    index_path.write_bytes(packed_indices)
    receipt = {
        "status": "FROZEN_EXACT_SAMPLE_WRITTEN",
        "curve_id": frozen["curve_id"], "rows": len(indices),
        "seed_bins_covered": len(bins),
        "minimum_sampled_bin_occupancy": min(bins.values()),
        "maximum_sampled_bin_occupancy": max(bins.values()),
        "sample_sha256": sha(sample_path),
        "sample_indices_sha256": sha(index_path),
        "source_x_orbits_sha256": sha(SOURCE / "x_orbits.bin"),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "wall_ns": time.monotonic_ns() - start,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "rows": receipt["rows"], "bins": len(bins)}))


if __name__ == "__main__":
    main()
