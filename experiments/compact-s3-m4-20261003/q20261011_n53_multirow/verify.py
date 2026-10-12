#!/usr/bin/env python3
"""Independently expand the archived N53 base and replay Q1448's rows."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves  # noqa: E402
import field  # noqa: E402

MEASUREMENT = HERE / "measurement.json"
ARCHIVE = PARENT / "bases/n53_weight3_orbits.json.gz"
REFERENCE = PARENT / "runs/n53_ordinary_matched_pair_table.json"
OUT = HERE / "independent_replay.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rank_mod_r(rows: list[list[int]], r: int) -> int:
    work = [row[:] for row in rows]
    rank = 0
    for col in range(len(work[0]) if work else 0):
        pivot = next((i for i in range(rank, len(work)) if work[i][col] % r), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        inverse = pow(work[rank][col], -1, r)
        work[rank] = [value * inverse % r for value in work[rank]]
        for i in range(rank + 1, len(work)):
            factor = work[i][col]
            if factor:
                work[i] = [(a - factor * b) % r
                           for a, b in zip(work[i], work[rank])]
        rank += 1
        if rank == len(work):
            break
    return rank


def main() -> None:
    assert not OUT.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    receipt = json.loads(MEASUREMENT.read_text())
    reference = json.loads(REFERENCE.read_text())
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    assert receipt["status"] == "completed_query_cap"
    assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
    assert receipt["source_sha256"] == sha(HERE / "run.py")
    assert receipt["curve_id"] == archive["curve"]["curve_id"] == protocol["curve_id"]
    assert receipt["workload_id"] == reference["workload_id"] == protocol["workload_id"]
    assert receipt["isogeny"] == protocol["isogeny"] == "none"
    factor = archive["factor_base"]
    packed = base64.b64decode(factor["packed_canonical_x_keys_base64"])
    assert sha(ARCHIVE) == json.loads((HERE / "freeze.json").read_text())[
        "archive_sha256"]
    assert hashlib.sha256(packed).hexdigest() == protocol[
        "factor_base_enumerated_set_sha256"]
    assert len(packed) == 7 * protocol["factor_base_folded_columns_K"]
    keys = [int.from_bytes(packed[i:i + 7], "little")
            for i in range(0, len(packed), 7)]
    assert keys == sorted(set(keys))
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    r = protocol["rank_accounting"]["modulus"]
    eigen = protocol["rank_accounting"]["frobenius_eigenvalue_mod_r"]
    target = tuple(map(int, reference["target"]))
    assert curve.onCurve(target) and curve.mul(target, r) is None

    # Choose the pointFromX lift of each archived x-orbit key as this
    # verifier's column orientation. This is independent of run.py's packed
    # full-point OrbitKey orientation; rank is invariant under column scaling.
    point_to_column: dict[tuple[int, int], tuple[int, int]] = {}
    for col, (key, length) in enumerate(zip(keys, factor["orbit_lengths"])):
        representative = curve.pointFromX(onb.fromCoords(key))
        assert representative is not None and curve.onCurve(representative)
        for exponent in range(length):
            positive = curve.frob(representative, exponent)
            negative = curve.neg(positive)
            coefficient = pow(eigen, exponent, r)
            assert positive not in point_to_column
            assert negative not in point_to_column
            point_to_column[positive] = (col, coefficient)
            point_to_column[negative] = (col, -coefficient % r)
    assert len(point_to_column) == factor["actual_usable_points_B_before_folding"]
    assert len(point_to_column) == receipt["factor_base_actual_B"]

    rows = []
    point_multisets = set()
    verified = []
    for record in receipt["relations"]:
        relation = record["relation"]
        points = [tuple(map(int, item)) for item in relation["points"]]
        assert len(points) == len(set(points)) == 4
        assert all(point in point_to_column and curve.onCurve(point)
                   and curve.mul(point, r) is None for point in points)
        total = None
        row = [0] * (len(keys) + 1)
        for point in points:
            total = curve.add(total, point)
            col, coefficient = point_to_column[point]
            row[col] = (row[col] + coefficient) % r
        assert total == target
        row[-1] = r - 1
        rows.append(row)
        point_multisets.add(tuple(sorted(points)))
        verified.append({"query_number": record["query_number"],
                         "nonzero_row_entries": [[i, v] for i, v in enumerate(row) if v]})
    rank = rank_mod_r(rows, r)
    assert len(rows) == receipt["verified_relation_occurrences"]
    assert len(point_multisets) == receipt["distinct_point_multisets"]
    assert rank == receipt["augmented_rank"]
    assert max(0, rank - 1) == receipt["same_target_homogeneous_difference_rank"]
    assert receipt["relations"][0]["relation"] == reference["ordinary_query"]["relation"]
    output = {
        "status": "PASS",
        "proposal_id": "Q1448",
        "candidate_id": None, "run_id": None,
        "curve_id": receipt["curve_id"], "workload_id": receipt["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": len(point_to_column),
        "factor_base_folded_columns_K": len(keys),
        "factor_base_enumerated_set_sha256": hashlib.sha256(packed).hexdigest(),
        "base_key_packed_sha256": hashlib.sha256(packed).hexdigest(),
        "measurement_sha256": sha(MEASUREMENT),
        "reference_sha256": sha(REFERENCE),
        "archive_sha256": sha(ARCHIVE),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "source_sha256": sha(Path(__file__)),
        "verified_relation_occurrences": len(rows),
        "distinct_point_multisets": len(point_multisets),
        "independent_augmented_rank": rank,
        "same_target_homogeneous_difference_rank": max(0, rank - 1),
        "rows": verified,
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"PASS Q1448 {len(rows)} relations, augmented rank {rank}")


if __name__ == "__main__":
    main()
