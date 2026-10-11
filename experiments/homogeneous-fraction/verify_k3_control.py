#!/usr/bin/env python3
"""Independent replay of the n=13,k=3 compiled collector receipts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from math_model import GF2n  # noqa: E402
from relation_gate import MODULUS, N, ORDER, Rank, mul, negative, relation_vector  # noqa: E402


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def verify(receipt_path: Path = HERE / "compiled_k3_control_results.json") -> dict:
    receipt = json.loads(receipt_path.read_text())
    refs = json.loads((HERE / "relation_gate_results.json").read_text())["runs"]
    controls = json.loads((HERE / "compiled_control_results.json").read_text())["runs"]
    refmap = {(r["seed"], r.get("repeat", 0)): r for r in refs}
    controlmap = {(r["seed"], r.get("repeat", 0)): r for r in controls}
    assert len(receipt["runs"]) == len(refmap) == len(controlmap) == 6
    field = GF2n(N, MODULUS)
    certificates = 0
    raw_attempts = 0
    for run in receipt["runs"]:
        key = (run["seed"], run["repeat"])
        ref, control = refmap[key], controlmap[key]
        assert run["target_stream_sha256"] == ref["workload_sha256"] == control["workload_sha256"]
        assert ref["targets"] == control["targets"]
        base = run["factor_base"]
        assert base["field_degree"] == N and base["fraction_k"] == 3
        assert tuple(base["generator"]) == tuple(ref["base"]["generator"])
        assert tuple(base["generator"]) == tuple(control["base"]["generator"])
        original = [tuple(p) for p in base["original_points"]]
        projected = {p: mul(field, p, 4) for p in original}
        projected_points = sorted(set(projected.values()) - {None})
        assert [list(p) for p in projected_points] == base["projected_nonidentity_points"]
        reps = [tuple(p) for p in base["signed_representatives"]]
        signed_column = {
            p: (j, sign)
            for j, rep in enumerate(reps)
            for p, sign in ((rep, 1), (negative(rep), -1))
        }
        assert len(original) == 115 and len(projected_points) == 56 and len(reps) == 28
        assert run["factor_base_sha256"] == digest(base)
        assert run["matched_k2_target_points"]
        target_points = [list(mul(field, tuple(base["generator"]), s))
                         for s in ref["targets"]]
        assert run["target_points_sha256"] == digest(target_points)

        raw_path = REPO / run["raw_stdout_path"]
        raw = raw_path.read_text()
        assert hashlib.sha256(raw.encode()).hexdigest() == run["raw_stdout_sha256"]
        lines = raw.splitlines()
        assert lines[0].startswith("B ") and lines[-1].startswith("T ")
        base_tokens = list(map(int, lines[0].split()[1:]))
        assert base_tokens[0] == len(original)
        assert base_tokens[1:3] == list(base["generator"])
        assert list(zip(base_tokens[3::2], base_tokens[4::2])) == original
        assert len(lines[1:-1]) == len(run["attempts"])

        rank = Rank(len(reps))
        for idx, (line, rec) in enumerate(zip(lines[1:-1], run["attempts"])):
            tokens = line.split()
            assert tokens[0] == "A" and len(tokens) == 15 + len(reps)
            vals = list(map(int, tokens[1:15]))
            (ordinal, scalar, x, y, code, candidates, repeated, dep,
             before, after, i, j, k, solve_ns) = vals
            coeff = list(map(int, tokens[15:]))
            assert ordinal == idx == rec["target_index"]
            assert scalar == rec["target_scalar"] == ref["targets"][idx]
            Q = mul(field, tuple(base["generator"]), scalar)
            assert [x, y] == rec["target_point"] == list(Q)
            assert before == rank.value == rec["rank_before"]
            assert rec["C_target_query_verify_rank_ns"] == solve_ns
            status = {0: "no_relation", 1: "new_independent_relation",
                      2: "dependent_relation"}[code]
            assert rec["status"] == status
            assert rec["relation_candidates_exactly_verified_in_C"] == candidates
            assert rec["repeated_rows"] == repeated and rec["other_dependent_rows"] == dep
            if code == 1:
                points = [original[z] for z in (i, j, k)]
                assert field.add(field.add(points[0], points[1]), points[2]) == Q
                assert field.s4(*(p[0] for p in points), Q[0]) == 0
                projected_sum = field.add(
                    field.add(projected[points[0]], projected[points[1]]), projected[points[2]])
                assert projected_sum == mul(field, Q, 4)
                row = relation_vector(points, projected, signed_column)
                assert coeff == list(row) == rec["relation"]["coefficients"]
                assert rec["relation"]["points"] == [list(p) for p in points]
                novel, duplicate = rank.add(coeff)
                assert novel and not duplicate
                certificates += 1
            else:
                assert (i, j, k) == (-1, -1, -1)
                assert (code == 0) == (candidates == 0)
            assert after == rank.value == rec["rank_after"]
            raw_attempts += 1
        assert rank.value == run["counts"]["final_rank"] == 8
        assert len(lines[-1].split()) == 3
        setup_ns, internal_ns = map(int, lines[-1].split()[1:])
        assert run["timings"]["C_base_and_pair_index_construction_ns"] == setup_ns
        assert run["timings"]["fully_charged_driver_wall_ns"] >= internal_ns
        assert run["timings"]["fully_charged_driver_wall_ns"] >= (
            internal_ns + run["timings"]["independent_python_parse_and_replay_ns"])
        counts = run["counts"]
        assert counts["ordinary_targets_processed_until_rank8"] == len(run["attempts"])
        assert counts["failed_targets"] == sum(a["status"] == "no_relation"
                                                  for a in run["attempts"])
        assert counts["dependent_targets"] == sum(a["status"] == "dependent_relation"
                                                    for a in run["attempts"])
        assert counts["repeated_rows"] == sum(a["repeated_rows"] for a in run["attempts"])
    return {"status": "PASS", "runs": len(receipt["runs"],),
            "ordinary_attempts": raw_attempts,
            "independent_relation_certificates": certificates,
            "independent_implementation": "pure-Python GF(2^13) arithmetic and rank replay"}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "compiled_k3_control_results.json"
    print(json.dumps(verify(path)))
