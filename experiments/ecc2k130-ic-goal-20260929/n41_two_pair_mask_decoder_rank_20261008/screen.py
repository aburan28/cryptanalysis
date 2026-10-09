#!/usr/bin/env python3
"""Rank screen for quadratic pair-mask decoding from a two-pair group sum."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL))
from run_n41_disjoint_s5_sat import Curve, Field  # noqa: E402

VARIABLES = 93
FEATURES = 1 + VARIABLES + VARIABLES * (VARIABLES - 1) // 2


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def features(mask: int) -> int:
    active = [i for i in range(VARIABLES) if mask >> i & 1]
    value = 1
    for i in active:
        value |= 1 << (1 + i)
    for at, i in enumerate(active):
        base = 1 + VARIABLES + i * (2 * VARIABLES - i - 1) // 2
        for j in active[at + 1:]:
            value |= 1 << (base + j - i - 1)
    assert value.bit_length() <= FEATURES
    return value


def insert_high(basis: dict[int, int], value: int) -> bool:
    while value:
        pivot = value.bit_length() - 1
        if pivot not in basis:
            basis[pivot] = value
            return True
        value ^= basis[pivot]
    return False


def main() -> None:
    rows_out = HERE / "decoded_rows.json"
    result_out = HERE / "result.json"
    if rows_out.exists() or result_out.exists():
        raise FileExistsError("preserve the first screen")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {name: (HERE / protocol[name]).resolve() for name in
             ("input_rows", "input_sage_audit", "geometry", "curve_arithmetic")}
    for name, path in paths.items():
        assert sha(path) == protocol[f"{name}_sha256"]
    rows = json.loads(paths["input_rows"].read_text())
    audit = json.loads(paths["input_sage_audit"].read_text())
    geometry = json.loads(paths["geometry"].read_text())["n41"]
    assert rows["curve_id"] == geometry["curve_id"] == protocol["curve_id"]
    assert rows["accepted_sample_count"] == len(rows["rows"]) == protocol["sample_count"]
    assert audit["status"] == "PASS" and audit["sampled_rows_replayed"] == len(rows["rows"])
    assert audit["source_sha256"]["samples"] == sha(paths["input_rows"])
    assert protocol["feature_count"] == FEATURES
    field = Field(41, [0, 3])
    curve = Curve(field, 0)
    domains = []
    for rotation in protocol["pair_rotations"]:
        points = geometry["point_rows_by_unique_rotation"][str(rotation)]
        assert len(points) == 64
        states = []
        for i in range(64):
            for j in range(i + 1, 64):
                if points[i][2] == points[j][2]:
                    continue
                total = curve.add(tuple(points[i][:2]), tuple(points[j][:2]))
                assert total is not None
                states.append((points[i][3] ^ points[j][3], total))
        assert len(states) == 1956
        domains.append(states)

    basis: dict[int, int] = {}
    decoded = []
    pivotal_indices = []
    status = "SAMPLE_RANK_DEFICIT"
    for index, original in enumerate(rows["rows"]):
        a = domains[0][original["pair_state_indices"][2]]
        b = domains[1][original["pair_state_indices"][3]]
        assert a[0] == original["pair_seed_sums"][2]
        assert b[0] == original["pair_seed_sums"][3]
        residual = curve.add(a[1], b[1])
        assert residual is not None and residual[0] & 1 == 0
        x, y = residual
        packed = a[0] | (b[0] << 6) | ((x >> 1) << 12) | (y << 52)
        assert packed.bit_length() <= VARIABLES
        decoded.append({"source_index": index,
                        "pair_state_indices": original["pair_state_indices"][2:4],
                        "pair_seed_sums": [a[0], b[0]],
                        "sum_point": [x, y]})
        if insert_high(basis, features(packed)):
            pivotal_indices.append(index)
        if len(basis) == FEATURES:
            status = "FULL_RANK"
            break
        if (index + 1) % 64 == 0:
            if time.monotonic_ns() - start >= protocol["limits"]["screen_wall_seconds"] * 10**9:
                status = "TIME_CAP"
                break
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= protocol["limits"]["peak_rss_bytes"]:
                status = "MEMORY_CAP"
                break

    source_rows = {
        "kind": "n41_exact_two_pair_mask_decoder_rank_rows",
        "curve_id": protocol["curve_id"],
        "status": status,
        "rows": decoded,
        "source_sha256": {name: sha(path) for name, path in paths.items()},
    }
    rows_out.write_text(json.dumps(source_rows, sort_keys=True, separators=(",", ":")) + "\n")
    result = {
        "kind": protocol["kind"],
        "status": status,
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "feature_count": FEATURES,
        "rank": len(basis),
        "sample_rows_available": len(rows["rows"]),
        "sample_rows_consumed": len(decoded),
        "pivotal_row_indices": pivotal_indices,
        "basis_pivots_sha256": hashlib.sha256(
            ",".join(map(str, sorted(basis))).encode()).hexdigest(),
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "screen": sha(Path(__file__)),
                          "decoded_rows": sha(rows_out)},
        "claim_boundary": protocol["claim_boundary"],
    }
    result_out.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": status, "rank": len(basis),
                      "rows_consumed": len(decoded),
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
