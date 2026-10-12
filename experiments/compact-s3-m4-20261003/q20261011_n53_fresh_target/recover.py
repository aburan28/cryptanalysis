#!/usr/bin/env python3
"""Expand Q1461 first match and recover the scalar from Q1457 verified logs."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PAIR = PARENT / "q20261011_n53_native_pair"
SETUP = PARENT / "q20261011_n53_full_pipeline"
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves  # noqa: E402
import field  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_points(path: Path) -> list[tuple[int, int]]:
    raw = path.read_bytes()
    assert len(raw) % 32 == 0
    return [(int.from_bytes(raw[i:i+16], "little"),
             int.from_bytes(raw[i+16:i+32], "little"))
            for i in range(0, len(raw), 32)]


def main() -> None:
    assert not (HERE / "recovery.json").exists()
    started = time.perf_counter_ns()
    protocol = json.loads((HERE / "protocol.json").read_text())
    public = json.loads((HERE / "public_target.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    setup = json.loads((SETUP / "independent_replay.json").read_text())
    assert measured["status"] == "first_match"
    assert measured["public_target_onb_xy"] == public["target_onb_xy"]
    assert setup["status"] == "PASS" and setup["factor_base_log_status"] == "solved_and_replayed"
    logs = setup["factor_base_logs"]
    r = protocol["subgroup_order"]
    eigen = protocol["frobenius_eigenvalue_mod_r"]
    assert len(logs) == protocol["factor_base_folded_columns_K"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(protocol["generator_onb_xy"])
    target = tuple(public["target_onb_xy"])
    assert curve.onCurve(target) and curve.mul(target, r) is None
    base = read_points(PAIR / "inputs/base.bin")
    assert len(base) == protocol["factor_base_actual_B"]
    with gzip.open(PARENT / "bases/n53_weight3_orbits.json.gz", "rt") as stream:
        archive = json.load(stream)
    factor = archive["factor_base"]
    packed = base64.b64decode(factor["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == protocol["factor_base_enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i+7], "little") for i in range(0, len(packed), 7)]
    assert len(keys) == len(logs)
    point_to_log = {}
    for column, (key, length) in enumerate(zip(keys, factor["orbit_lengths"])):
        representative = curve.pointFromX(onb.fromCoords(key))
        assert representative is not None
        for exponent in range(length):
            positive = curve.frob(representative, exponent)
            negative = curve.neg(positive)
            coefficient = pow(eigen, exponent, r)
            assert positive not in point_to_log and negative not in point_to_log
            point_to_log[positive] = column, coefficient
            point_to_log[negative] = column, -coefficient % r
    assert set(point_to_log) == set(base)
    base_rebuild_ns = time.perf_counter_ns() - started
    matches = measured["native"]["matches"]
    assert matches
    recovered = []
    relation_started = time.perf_counter_ns()
    for match in matches:
        query, ordinal, tfirst, tsecond, qfirst, qsecond, texp, qexp, tsign, qsign = match
        assert query == measured["native"]["query_samples_processed"]
        assert all(0 <= i < len(base) for i in (tfirst, tsecond, qfirst, qsecond))
        table_point = curve.add(base[tfirst], base[tsecond])
        query_point = curve.add(base[qfirst], base[qsecond])
        assert table_point is not None and query_point is not None
        complement = curve.add(target, curve.neg(query_point))
        assert complement is not None
        # Recompute the signed Frobenius match independently of native output.
        from orbit_key import OrbitKey  # noqa: E402
        quotient = OrbitKey(onb)
        tkey, et, st = quotient.canonical(table_point)
        qkey, eq, sq = quotient.canonical(complement)
        assert tkey == qkey and (et, st, eq, sq) == (texp, tsign, qexp, qsign)
        shift = (texp - qexp) % 53
        sign = tsign * qsign
        left = [curve.frob(base[tfirst], shift), curve.frob(base[tsecond], shift)]
        if sign < 0:
            left = [curve.neg(point) for point in left]
        points = left + [base[qfirst], base[qsecond]]
        total = None
        scalar = 0
        terms = []
        for point in points:
            assert point in point_to_log and curve.onCurve(point)
            total = curve.add(total, point)
            column, coefficient = point_to_log[point]
            scalar = (scalar + coefficient * logs[column]) % r
            terms.append([column, coefficient, logs[column]])
        assert total == target
        recovered.append({"query_number": query, "table_state_ordinal": ordinal,
                          "points": [[x, y] for x, y in points],
                          "factor_base_terms": terms, "scalar": scalar})
    relation_and_recovery_ns = time.perf_counter_ns() - relation_started
    scalars = {row["scalar"] for row in recovered}
    assert len(scalars) == 1
    scalar = next(iter(scalars))
    replay_started = time.perf_counter_ns()
    assert curve.mul(generator, scalar) == target
    scalar_replay_ns = time.perf_counter_ns() - replay_started
    output = {"proposal_id": "Q1461", "candidate_id": None, "run_id": None,
              "status": "SCALAR_RECOVERED_AND_REPLAYED",
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "workload_id": public["workload_id"],
              "target_onb_xy": list(target), "scalar": scalar,
              "verified_first_match_relations": recovered,
              "base_rebuild_ns_target_independent": base_rebuild_ns,
              "target_relation_and_recovery_ns": relation_and_recovery_ns,
              "target_scalar_replay_ns": scalar_replay_ns,
              "target_online_phase_sum_ns": (
                  measured["native"]["phase_wall_ns"]["target_query_and_lookup"] +
                  relation_and_recovery_ns + scalar_replay_ns),
              "measurement_sha256": sha(HERE / "native_measurement.json"),
              "setup_logs_sha256": sha(SETUP / "independent_replay.json"),
              "source_sha256": sha(Path(__file__)),
              "complete_solve_work_log2": None}
    (HERE / "recovery.json").write_text(json.dumps(output, indent=2,
                                                  sort_keys=True) + "\n")
    print("RECOVERED Q1461", scalar, "relations", len(recovered))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
    main()
