#!/usr/bin/env python3
"""Bounded rank gate for an exact two-pair/target cubic propagator."""

from __future__ import annotations

import hashlib
import itertools
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FEATURE_COUNT = 2819
PAIR_BITS = 12
TARGET_BITS = 40
TOTAL_BITS = PAIR_BITS + TARGET_BITS
QUADRATIC_END = 1 + TOTAL_BITS + TOTAL_BITS * (TOTAL_BITS - 1) // 2


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_inputs(protocol: dict) -> tuple[dict, Path, Path]:
    rows_path = (HERE / protocol["input_rows"]).resolve()
    audit_path = (HERE / protocol["input_sage_audit"]).resolve()
    assert digest(rows_path) == protocol["input_rows_sha256"]
    assert digest(audit_path) == protocol["input_sage_audit_sha256"]
    rows = json.loads(rows_path.read_text())
    audit = json.loads(audit_path.read_text())
    assert rows["curve_id"] == protocol["curve_id"]
    assert rows["accepted_sample_count"] == len(rows["rows"]) == protocol["input_row_count"]
    assert audit["status"] == "PASS" and audit["sampled_rows_replayed"] == len(rows["rows"])
    assert audit["source_sha256"]["samples"] == digest(rows_path)
    assert protocol["feature_count"] == FEATURE_COUNT
    return rows, rows_path, audit_path


def input_bits(row: dict) -> int:
    sums = row["pair_seed_sums"]
    assert len(sums) == 4 and all(0 <= s < 64 for s in sums)
    x = row["target"][0]
    assert 0 < x < (1 << 41) and x & 1 == 0
    return sums[0] | (sums[1] << 6) | ((x >> 1) << PAIR_BITS)


def feature_vector(row: dict) -> int:
    mask = input_bits(row)
    active = [i for i in range(TOTAL_BITS) if (mask >> i) & 1]
    vector = 1
    for i in active:
        vector |= 1 << (1 + i)
    for i, j in itertools.combinations(active, 2):
        index = 1 + TOTAL_BITS + i * (2 * TOTAL_BITS - i - 1) // 2 + j - i - 1
        vector |= 1 << index
    for a in range(6):
        if not (mask >> a) & 1:
            continue
        for b in range(6):
            if not (mask >> (6 + b)) & 1:
                continue
            for t in range(TARGET_BITS):
                if (mask >> (PAIR_BITS + t)) & 1:
                    vector |= 1 << (QUADRATIC_END + (a * 6 + b) * TARGET_BITS + t)
    assert vector.bit_length() <= FEATURE_COUNT
    return vector


def insert_high(basis: dict[int, int], value: int) -> bool:
    while value:
        pivot = value.bit_length() - 1
        prior = basis.get(pivot)
        if prior is None:
            basis[pivot] = value
            return True
        value ^= prior
    return False


def main() -> None:
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError("preserve the frozen first run")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    rows, rows_path, audit_path = check_inputs(protocol)
    basis: dict[int, int] = {}
    pivotal_indices: list[int] = []
    for index, row in enumerate(rows["rows"]):
        if insert_high(basis, feature_vector(row)):
            pivotal_indices.append(index)
        if len(basis) == FEATURE_COUNT:
            break
    report = {
        "kind": protocol["kind"],
        "curve_id": protocol["curve_id"],
        "status": "FULL_RANK" if len(basis) == FEATURE_COUNT else "SAMPLE_RANK_DEFICIT",
        "candidate_id": None,
        "run_id": None,
        "feature_count": FEATURE_COUNT,
        "rank": len(basis),
        "sample_rows_available": len(rows["rows"]),
        "sample_rows_consumed": index + 1,
        "pivotal_row_indices": pivotal_indices,
        "basis_pivots_sha256": hashlib.sha256(
            ",".join(map(str, sorted(basis))).encode()).hexdigest(),
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "source_sha256": {
            "protocol": digest(protocol_path),
            "screen": digest(Path(__file__)),
            "rows": digest(rows_path),
            "prior_sage_audit": digest(audit_path),
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    assert report["exploratory_wall_ns"] <= protocol["resource_cap_seconds"] * 1_000_000_000
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "rank", "sample_rows_consumed", "exploratory_wall_ns")}))


if __name__ == "__main__":
    main()
