#!/usr/bin/env python3
"""Independently replay native Q1455 key matches and rank useful rows."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path
from freeze import Q1454

HERE = Path(__file__).resolve().parent
INPUT_DIR = Q1454 / "inputs"
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402

MEASUREMENT = HERE / "native_measurement.json"
ARCHIVE = PARENT / "bases/n53_weight3_orbits.json.gz"
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


def read_points(path: Path) -> list[tuple[int, int]]:
    raw = path.read_bytes()
    assert len(raw) % 32 == 0
    return [(int.from_bytes(raw[i:i + 16], "little"),
             int.from_bytes(raw[i + 16:i + 32], "little"))
            for i in range(0, len(raw), 32)]


def main() -> None:
    assert not OUT.exists()
    started = time.perf_counter_ns()
    protocol = json.loads((HERE / "protocol.json").read_text())
    measured = json.loads(MEASUREMENT.read_text())
    exported = json.loads((Q1454 / "export_receipt.json").read_text())
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    assert measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["q1454_export_receipt_sha256"] == sha(Q1454 / "export_receipt.json")
    assert measured["curve_id"] == protocol["curve_id"] == archive["curve"]["curve_id"]
    assert measured["isogeny"] == protocol["isogeny"] == "none"
    assert measured["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    base = read_points(INPUT_DIR / "base.bin")
    assert len(base) == protocol["factor_base_actual_B"]
    assert sha(INPUT_DIR / "base.bin") == exported["files"]["base.bin"]["sha256"]
    base_set = set(base)
    assert len(base_set) == len(base)
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    quotient = OrbitKey(onb)
    target = int(exported["target_x_hex"], 16), int(exported["target_y_hex"], 16)
    r = protocol["rank_accounting"]["modulus"]
    eigen = protocol["rank_accounting"]["frobenius_eigenvalue_mod_r"]
    assert curve.onCurve(target) and curve.mul(target, r) is None
    factor = archive["factor_base"]
    packed = base64.b64decode(factor["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == protocol[
        "factor_base_enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i + 7], "little")
            for i in range(0, len(packed), 7)]
    point_to_column = {}
    for col, (key, length) in enumerate(zip(keys, factor["orbit_lengths"])):
        representative = curve.pointFromX(onb.fromCoords(key))
        assert representative is not None
        for exponent in range(length):
            positive = curve.frob(representative, exponent)
            negative = curve.neg(positive)
            coefficient = pow(eigen, exponent, r)
            assert positive not in point_to_column and negative not in point_to_column
            point_to_column[positive] = (col, coefficient)
            point_to_column[negative] = (col, -coefficient % r)
    assert set(point_to_column) == base_set
    base_rebuild_ns = time.perf_counter_ns() - started

    cap_results = {}
    rejections = 0
    for cap in protocol["point_decomposition"]["table_caps"]:
        rows, point_multisets, checked = [], set(), []
        per_query = {}
        for match in measured["matches"]:
            query, ordinal, tfirst, tsecond, qfirst, qsecond, texp, qexp, tsign, qsign = match
            if ordinal > cap:
                continue
            assert 1 <= query <= measured["query_samples_processed"]
            assert 1 <= ordinal <= measured["table_states_generated"]
            table_point = curve.add(base[tfirst], base[tsecond])
            query_pair = curve.add(base[qfirst], base[qsecond])
            assert table_point is not None and query_pair is not None
            complement = curve.add(target, curve.neg(query_pair))
            assert complement is not None
            key0, exponent0, sign0 = quotient.canonical(table_point)
            key1, exponent1, sign1 = quotient.canonical(complement)
            assert key0 == key1
            assert (texp, tsign) == (exponent0, sign0)
            assert (qexp, qsign) == (exponent1, sign1)
            shift = (texp - qexp) % 53
            sign = tsign * qsign
            left = [curve.frob(base[tfirst], shift),
                    curve.frob(base[tsecond], shift)]
            if sign < 0:
                left = [curve.neg(point) for point in left]
            points = left + [base[qfirst], base[qsecond]]
            assert all(point in base_set and curve.onCurve(point)
                       and curve.mul(point, r) is None for point in points)
            if any(points[i] == curve.neg(points[j])
                   for i in range(4) for j in range(i)):
                rejections += 1
                continue
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
            per_query[query] = per_query.get(query, 0) + 1
            checked.append({"query_number": query,
                            "table_state_ordinal": ordinal,
                            "points": [[x, y] for x, y in points]})
        rank = rank_mod_r(rows, r)
        cap_results[str(cap)] = {
            "candidate_matches": sum(match[1] <= cap for match in measured["matches"]),
            "verified_relation_occurrences": len(rows),
            "distinct_point_multisets": len(point_multisets),
            "distinct_quotient_rows": len(set(tuple(row) for row in rows)),
            "augmented_rank": rank,
            "same_target_homogeneous_difference_rank": max(0, rank - 1),
            "queries_with_multiple_occurrences": sum(count > 1 for count in per_query.values()),
            "maximum_occurrences_per_query": max(per_query.values(), default=0),
            "relations": checked,
        }
    match_replay_rank_ns = time.perf_counter_ns() - started - base_rebuild_ns
    output = {"status": "PASS", "proposal_id": "Q1455",
              "candidate_id": None, "run_id": None,
              "curve_id": measured["curve_id"], "workload_id": measured["workload_id"],
              "isogeny": "none", "factor_base_actual_B": len(base),
              "factor_base_folded_columns_K": len(keys),
              "factor_base_enumerated_set_sha256": hashlib.sha256(packed).hexdigest(),
              "measurement_sha256": sha(MEASUREMENT),
              "source_sha256": sha(Path(__file__)),
              "base_rebuild_ns": base_rebuild_ns,
              "match_replay_rank_ns": match_replay_rank_ns,
              "proper_rejections_across_caps": rejections,
              "cap_results": cap_results}
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("PASS Q1455", {cap: value["augmented_rank"]
                         for cap, value in cap_results.items()})


if __name__ == "__main__":
    main()
