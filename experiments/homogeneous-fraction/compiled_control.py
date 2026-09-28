#!/usr/bin/env python3
"""Fresh-process, fully charged compiled direct control on frozen n=13 targets.

The C code independently constructs the identical fraction base and pair index,
checks point/group identities and rank over F_2003, and stops at rank eight.
The Python driver charges launch, output parsing, S4 and point replay; a separate
C-backed ToyCurve replay verifies the stored receipt after measurement.
Compilation is a separately recorded one-time implementation cost, not a
per-target construction cost (the Python baseline also uses installed Python).
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from math_model import GF2n
from relation_gate import COFACTOR, K, MODULUS, N, ORDER, Rank, digest, mul, relation_vector

HERE = Path(__file__).resolve().parent


def build(executable):
    executable.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter_ns()
    subprocess.run(["cc", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-o", str(executable), str(HERE / "direct_collector.c")], check=True)
    return time.perf_counter_ns() - start


def one(executable, reference):
    targets = reference["targets"]
    base = reference["base"]
    assert reference["target_rank"] == 8
    input_text = f"{len(targets)} 8\n" + "\n".join(map(str, targets)) + "\n"
    wall_start = time.perf_counter_ns()
    proc = subprocess.run([str(executable)], input=input_text, capture_output=True,
                          text=True, check=True, timeout=120)
    lines = proc.stdout.splitlines()
    assert len(lines) > 2 and lines[0].startswith("B ") and lines[-1].startswith("T ")
    bc = list(map(int, lines[0].split()[1:]))
    assert bc[0] == len(base["original_points"]) == 35
    assert bc[1:3] == base["generator"]
    assert list(zip(bc[3::2], bc[4::2])) == [tuple(p) for p in base["original_points"]]
    original = [tuple(p) for p in base["original_points"]]
    field = GF2n(N, MODULUS)
    projected = {p: mul(field, p, COFACTOR) for p in original}
    representatives = [tuple(p) for p in base["signed_representatives"]]
    signed_column = {p: (j, sign) for j, rep in enumerate(representatives)
                     for p, sign in ((rep, 1), ((rep[0], rep[1] ^ rep[0]), -1))}
    rank = Rank(len(representatives))
    attempts = []
    for line in lines[1:-1]:
        tokens = line.split()
        assert tokens[0] == "A" and len(tokens) == 23
        (idx, scalar, x, y, code, candidates, repeated, other_dep,
         before, after, i, j, k, solve_ns) = map(int, tokens[1:15])
        coefficients = list(map(int, tokens[15:]))
        assert idx == len(attempts) and scalar == targets[idx] and before == rank.value
        assert (x, y) == mul(field, tuple(base["generator"]), scalar)
        relation = None
        if code == 1:
            points = [original[a] for a in (i, j, k)]
            assert field.add(field.add(points[0], points[1]), points[2]) == (x, y)
            assert field.s4(*(p[0] for p in points), x) == 0
            assert field.add(field.add(*(projected[p] for p in points[:2])),
                             projected[points[2]]) == mul(field, (x, y), COFACTOR)
            assert tuple(coefficients) == relation_vector(points, projected, signed_column)
            novel, duplicate = rank.add(coefficients)
            assert novel and not duplicate and after == rank.value
            relation = {"points": points, "coefficients": coefficients,
                        "projected_rhs_scalar": COFACTOR * scalar % ORDER}
        else:
            assert code in (0, 2) and [i, j, k] == [-1, -1, -1]
            assert after == before
        assert (code == 0) == (candidates == 0)
        attempts.append({
            "index": idx, "target_scalar": scalar, "target_point": [x, y],
            "status": ("new_independent_relation" if code == 1 else
                       "dependent_relation" if code == 2 else "no_relation"),
            "rank_before": before, "rank_after": after,
            "candidates_verified": candidates, "repeated_rows": repeated,
            "other_dependent_rows": other_dep, "relation": relation,
            "timings_ns": {"total": solve_ns},
        })
    assert rank.value == 8 and attempts[-1]["rank_after"] == 8
    phase = list(map(int, lines[-1].split()[1:]))
    assert len(phase) == 2
    setup_ns, internal_ns = phase
    solve_ns = sum(a["timings_ns"]["total"] for a in attempts)
    assert internal_ns >= setup_ns + solve_ns
    internal_phases = {
        "base_and_pair_index_construction": setup_ns,
        "C_target_solve_verify_rank": solve_ns,
        "C_output_and_unattributed": internal_ns - setup_ns - solve_ns,
        "charged_total": internal_ns,
    }
    counts = {
        "attempt_budget": len(targets), "ordinary_attempts": len(attempts),
        "verified_relations": sum(a["candidates_verified"] > 0 for a in attempts),
        "novel_rows": rank.value,
        "failed_targets": sum(a["status"] == "no_relation" for a in attempts),
        "dependent_targets": sum(a["status"] == "dependent_relation" for a in attempts),
        "repeated_rows": sum(a["repeated_rows"] for a in attempts),
        "rank": rank.value, "effective_columns": len(representatives),
        "original_fraction_points": len(original),
        "projected_base_points": len(signed_column),
        "pair_entries": 630,
    }
    run = {
        "schema": "homogeneous-fraction-relation-gate.v1",
        "scope": "relation_collection_only; no final LA or DLP",
        "candidate_id": None,
        "solver": "compiled exact direct point-pair table",
        "target_rank": 8, "status": "rank_reached",
        "seed": reference["seed"], "repeat": reference["repeat"],
        "targets": targets, "workload_sha256": reference["workload_sha256"],
        "base": base, "base_sha256": digest(base),
        "counts": counts, "timings_ns": internal_phases, "attempts": attempts,
        "C_source_sha256": hashlib.sha256((HERE / "direct_collector.c").read_bytes()).hexdigest(),
    }
    run["driver_wall_ns_including_startup"] = time.perf_counter_ns() - wall_start
    assert run["driver_wall_ns_including_startup"] >= internal_ns
    run["driver_seconds_per_new_row"] = run["driver_wall_ns_including_startup"] / 1e9 / 8
    return run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", type=Path, default=HERE / "relation_gate_results.json")
    p.add_argument("--executable", type=Path, default=HERE / "strict_runs" / "direct_collector")
    p.add_argument("--out", type=Path, default=HERE / "compiled_control_results.json")
    args = p.parse_args()
    compilation_ns = build(args.executable)
    runs = []
    for reference in json.loads(args.reference.read_text())["runs"]:
        run = one(args.executable, reference)
        runs.append(run)
        args.out.write_text(json.dumps({"compilation_ns_excluded": compilation_ns,
                                        "runs": runs}, separators=(",", ":")) + "\n")
        print(json.dumps({"seed": run["seed"], "repeat": run["repeat"],
                          "attempts": run["counts"]["ordinary_attempts"],
                          "rank": run["counts"]["rank"],
                          "seconds_per_row": run["driver_seconds_per_new_row"]}), flush=True)


if __name__ == "__main__":
    main()
