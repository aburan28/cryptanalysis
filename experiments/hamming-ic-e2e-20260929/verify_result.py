#!/usr/bin/env python3
"""Independent arithmetic and accounting replay for an N9 FC-Hamming IC run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF_PATH = ROOT / "experiments/factor-base-yield/run-002/sources/reference_group.py"
spec = importlib.util.spec_from_file_location("hamming_n9_reference_group", REF_PATH)
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

N, MODULUS, R, COFACTOR = 9, 0x211, 127, 4


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def point(value):
    return None if value is None else tuple(value)


def add(a, b):
    return ref.add(a, b, N, MODULUS)


def mul(a, scalar):
    return ref.scalar_mul(a, scalar, N, MODULUS)


def group_sum(points):
    result = None
    for value in points:
        result = add(result, value)
    return result


def negate(value):
    return None if value is None else (value[0], value[0] ^ value[1])


def verify_witness(witness, query, reps, base, normal_x):
    raw = [point(p) for p in witness["raw_points"]]
    projected = [point(p) for p in witness["projected_points"]]
    assert len(raw) == len(projected) == 5
    assert [p[0] for p in raw] == witness["x"]
    assert all(p[0] in normal_x and ref.on_curve(p, N, MODULUS) for p in raw)
    assert all(mul(p, COFACTOR) == q and q in base for p, q in zip(raw, projected))
    sign = witness["target_sign"]
    assert sign in (-1, 1)
    signed_query = query if sign == 1 else negate(query)
    total = group_sum(raw)
    assert total in (signed_query, add(signed_query, (0, 1)))
    assert witness["through_two_torsion"] == (total != signed_query)
    assert group_sum(projected) == mul(signed_query, COFACTOR)
    row = witness["row"]
    assert len(row) == len(reps)
    assert group_sum(mul(rep, coeff) for rep, coeff in zip(reps, row)) == group_sum(projected)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    folder = args.run_dir
    result = json.loads((folder / "result.json").read_text())
    candidate_file = json.loads((folder / "candidate.json").read_text())
    workload_file = json.loads((folder / "workload.json").read_text())
    row = json.loads((folder / "run.jsonl").read_text())
    candidate = candidate_file["record"]
    curve = candidate["curve"]
    raw_curve = {key: value for key, value in curve.items() if key != "curve_id"}
    assert curve["curve_id"] == "EC1N9Ckb1h" + digest({"field": candidate["field"],
                                                       "curve": raw_curve})[:12]
    expected = "IC1N9Ckb1fb36PDP5satRCsampleLAgaussTDdescentISO0h" + digest(candidate)[:12]
    assert candidate_file["candidate_id"] == result["candidate_id"] == expected
    assert candidate["point_decomposition"]["variant"] == result["weight_encoding"] + "_weight2_s3_chain"
    assert workload_file["workload_id"] == result["workload_id"] == (
        "W" + digest(workload_file["record"])[:12])
    assert result["run_id"].startswith(expected + result["workload_id"] + "R")
    assert result["run_id"].rsplit("R", 1)[-1].isdigit()
    assert row["run_id"] == result["run_id"]
    assert row["candidate_id"] == result["candidate_id"]
    assert row["workload_id"] == result["workload_id"]
    assert candidate["isogeny"] == "none"
    assert candidate["factor_base"]["actual_usable_points"] == 36
    assert candidate["factor_base"]["effective_columns"] == 2
    for relative, expected_hash in candidate["implementation"]["source_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected_hash
    generator = point(curve["G"])
    assert ref.on_curve(generator, N, MODULUS) and mul(generator, R) is None
    conj = candidate["factor_base"]["normal_conjugates"]
    assert len(conj) == N
    assert all(ref.mul(conj[i], conj[i], MODULUS) == conj[(i + 1) % N]
               for i in range(N))
    xs = {conj[i] ^ conj[j] for i, j in itertools.combinations(range(N), 2)}
    enumerated = set()
    for x in xs:
        for y in range(1 << N):
            raw = (x, y)
            if ref.on_curve(raw, N, MODULUS):
                projected = mul(raw, COFACTOR)
                if projected is not None:
                    enumerated.add(projected)
    base = {point(p) for p in candidate["factor_base"]["encoded_points"]}
    assert enumerated == base and len(base) == 36
    assert digest(candidate["factor_base"]["encoded_points"]) == candidate["factor_base"]["point_set_sha256"]
    reps = [point(p) for p in candidate["factor_base"]["representatives"]]
    logs = result["preparation"]["factor_logs"]["logs"]
    assert all(mul(generator, value) == rep for value, rep in zip(logs, reps))
    pre = result["preparation"]["factor_logs"]
    assert pre["rank"] == len(reps) == 2
    assert len(pre["records"]) == 2
    for item in pre["records"]:
        query = point(item["target"])
        assert mul(generator, item["query_scalar"]) == query
        if item["witness"]:
            verify_witness(item["witness"], query, reps, base, xs)
            rhs = item["witness"]["target_sign"] * COFACTOR * item["query_scalar"] % R
            assert sum(a * b for a, b in zip(item["witness"]["row"], logs)) % R == rhs
    fixture = result["fixture"]
    assert workload_file["record"] == fixture
    target = point(fixture["target"])
    assert mul(generator, result["audit_fixture_scalar"]) == target
    assert target not in {point(item["target"]) for item in pre["records"]}
    online = result["ic"]
    assert online["status"] == result["rho"]["status"] == "complete"
    assert sum(online["online_phase_wall_ns"].values()) == online["online_wall_ns"]
    assert row["online_phase_wall_ns"] == online["online_phase_wall_ns"]
    assert row["online_wall_ns"] == online["online_wall_ns"]
    assert row["rho_online_wall_ns"] == result["rho"]["online_wall_ns"]
    assert set(online["online_phase_wall_ns"]) == {
        "target_query", "target_pdp", "target_relation_check",
        "target_descent", "target_recovery_check"}
    for item in online["trace"]:
        translated = point(item["translated"])
        assert add(target, mul(generator, item["shift"])) == translated
        if item["witness"]:
            verify_witness(item["witness"], translated, reps, base, xs)
            dot = sum(a * b for a, b in zip(item["witness"]["row"], logs)) % R
            recovered = (item["witness"]["target_sign"] * pow(COFACTOR, -1, R)
                         * dot - item["shift"]) % R
            assert recovered == online["scalar"]
    assert online["scalar"] == result["rho"]["scalar"] == result["audit_fixture_scalar"]
    assert mul(generator, online["scalar"]) == target
    assert abs(result["online_speedup"] -
               result["rho"]["online_wall_ns"] / online["online_wall_ns"]) < 1e-15
    print(json.dumps({"status": "PASS", "run_id": result["run_id"],
                      "base_points": len(base), "columns": len(reps),
                      "relation_rank": pre["rank"], "recovered_scalar": online["scalar"]},
                     indent=2))


if __name__ == "__main__":
    main()
