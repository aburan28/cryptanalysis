#!/usr/bin/env python3
"""Frozen Q1426 ordinary target-lift slices of Q1425's S3 root hybrid."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
Q1425 = ROOT / "experiments/compact-s3-m4-root-hybrid-20261010"
sys.path.insert(0, str(Q1425))

import run as prior  # noqa: E402
from cmsat_native import IncrementalSolver, LIBRARY  # noqa: E402
from hybrid import MeteredField, bits_value, build_hybrid, exact_roots, root_lemma  # noqa: E402

LIMITS = {"wall_seconds": 90, "solver_seconds_per_call": 25,
          "conflicts_per_call": 100000, "max_refinements": 16,
          "max_solver_calls": 17, "rss_mib": 1536}


def selected_indices(n, count, curve_id, workload_id):
    if n == 83:
        assert count == 4
        return list(range(count))
    assert n == 53 and count == 428
    selected = []
    counter = 0
    while len(selected) < 4:
        seed = f"Q1426:{curve_id}:{workload_id}:{counter}".encode()
        index = int.from_bytes(hashlib.sha256(seed).digest(), "big") % count
        if index not in selected:
            selected.append(index)
        counter += 1
    return selected


def freeze():
    path = HERE / "freeze.json"
    assert not path.exists()
    prior.check_freeze()
    cases = {}
    for n in (53, 83):
        profile, parent, _, parent_path, _ = prior.load_case(n, "ordinary_both_lazy")
        raw = parent["raw_preimage_x_coordinates"]
        indices = selected_indices(n, len(raw), parent["curve_id"],
                                   parent["workload_id"])
        cases[str(n)] = {
            "curve_id": parent["curve_id"],
            "workload_id": parent["workload_id"],
            "B": parent["factor_base_actual_B"],
            "K": parent["factor_base_folded_columns"],
            "base_digest": parent["factor_base_enumerated_set_sha256"],
            "normal_basis_weight_bound": profile["normal_basis_weight_bound"],
            "raw_lift_count": len(raw),
            "selected_indices": indices,
            "selected_x": [raw[index] for index in indices],
            "ordinary_receipt_sha256": prior.digest(parent_path),
        }
        assert tuple(cases[str(n)][key] for key in
                     ("curve_id", "workload_id", "B", "K", "base_digest")) == (
                         prior.CASES[n])
    frozen = {
        "schema": "q1426-lift-slice-freeze-v1", "proposal_id": "Q1426",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "protocol_sha256": prior.digest(HERE / "PROTOCOL.md"),
        "runner_sha256": prior.digest(__file__),
        "verifier_sha256": prior.digest(HERE / "verify.py"),
        "slice_control_sha256": prior.digest(HERE / "test_slice.py"),
        "q1425_freeze_sha256": prior.digest(Q1425 / "freeze.json"),
        "q1425_source_sha256": {name: prior.digest(Q1425 / name)
                                for name in ("run.py", "hybrid.py", "cmsat_native.py")},
        "cmsat_library_sha256": prior.digest(LIBRARY),
        "cases": cases, "limits": LIMITS,
    }
    path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(prior.digest(path))


def check_freeze():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["schema"] == "q1426-lift-slice-freeze-v1"
    assert frozen["protocol_sha256"] == prior.digest(HERE / "PROTOCOL.md")
    assert frozen["runner_sha256"] == prior.digest(__file__)
    assert frozen["verifier_sha256"] == prior.digest(HERE / "verify.py")
    assert frozen["slice_control_sha256"] == prior.digest(HERE / "test_slice.py")
    assert frozen["q1425_freeze_sha256"] == prior.digest(Q1425 / "freeze.json")
    assert all(prior.digest(Q1425 / name) == value for name, value in
               frozen["q1425_source_sha256"].items())
    assert frozen["cmsat_library_sha256"] == prior.digest(LIBRARY)
    prior.check_freeze()
    for n in (53, 83):
        _, parent, _, parent_path, _ = prior.load_case(n, "ordinary_both_lazy")
        case = frozen["cases"][str(n)]
        raw = parent["raw_preimage_x_coordinates"]
        assert case["ordinary_receipt_sha256"] == prior.digest(parent_path)
        assert case["selected_indices"] == selected_indices(
            n, len(raw), parent["curve_id"], parent["workload_id"])
        assert case["selected_x"] == [raw[i] for i in case["selected_indices"]]
    return frozen


def run_cell(n, index):
    frozen = check_freeze()
    case = frozen["cases"][str(n)]
    assert index in case["selected_indices"]
    stem = f"n{n}_lift{index:03d}"
    path, trace_path = HERE / f"{stem}.json", HERE / f"{stem}.trace.jsonl"
    assert not path.exists() and not trace_path.exists()
    setup_at = time.perf_counter()
    profile, parent, _, parent_path, _ = prior.load_case(n, "ordinary_both_lazy")
    field = MeteredField(prior.field.Onb(n))
    setup_seconds = time.perf_counter() - setup_at
    started = time.perf_counter()
    target_x = parent["raw_preimage_x_coordinates"][index]
    formula, leaves, mids, _, selector = build_hybrid(
        n, case["normal_basis_weight_bound"], [target_x], (0, 1))
    build_seconds = time.perf_counter() - started
    root_cache, root_calls, lemmas, added_clauses, trace = {}, Counter(), [], [], []
    solver_elapsed = lemma_elapsed = check_elapsed = 0.0
    accepted = status = None
    wall_stop = False
    with IncrementalSolver(formula.variables) as solver:
        loaded_at = time.perf_counter()
        solver.load_formula(formula)
        load_seconds = time.perf_counter() - loaded_at

        def insert_lemma(pair, a, b):
            nonlocal lemma_elapsed
            key = (pair, tuple(sorted((a, b))))
            assert key not in root_cache
            began = time.perf_counter()
            roots = exact_roots(field, a, b)
            root_cache[key] = roots
            root_calls["oracle_misses"] += 1
            root_calls[f"roots_{len(roots)}"] += 1
            branch = solver.new_var() if len(roots) == 2 else None
            rows = root_lemma(leaves[2 * pair], leaves[2 * pair + 1],
                              mids[pair], a, b, roots, branch)
            consistent = True
            for row in rows:
                consistent = solver.add_clause(row) and consistent
            added_clauses.extend(rows)
            lemma_elapsed += time.perf_counter() - began
            lemmas.append({"pair": pair, "left_x": a, "right_x": b,
                           "root_x": list(roots), "branch_var": branch,
                           "clauses": len(rows),
                           "clause_digest": prior.canonical_hash(rows),
                           "root_consistent": consistent})
            return roots

        timer = threading.Timer(LIMITS["wall_seconds"], solver.interrupt)
        timer.daemon = True
        timer.start()
        try:
            with trace_path.open("w") as stream:
                for number in range(1, LIMITS["max_solver_calls"] + 1):
                    remaining = LIMITS["wall_seconds"] - (time.perf_counter() - started)
                    if remaining <= 0:
                        status, wall_stop = "BOUNDED_UNKNOWN", True
                        break
                    solve_at = time.perf_counter()
                    state, model = solver.solve(
                        seconds=min(LIMITS["solver_seconds_per_call"], remaining),
                        conflicts=LIMITS["conflicts_per_call"])
                    elapsed = time.perf_counter() - solve_at
                    solver_elapsed += elapsed
                    event = {"solver_call": number, "state": state,
                             "solver_wall_seconds": elapsed,
                             "root_lemmas_before": len(lemmas)}
                    if state != "SAT":
                        status = state
                    else:
                        prior.check_formula_model(formula, added_clauses, model)
                        assert bits_value(selector, model) == 0
                        pairs = []
                        for pair in (0, 1):
                            a = bits_value(leaves[2 * pair], model)
                            b = bits_value(leaves[2 * pair + 1], model)
                            mid = bits_value(mids[pair], model)
                            key = (pair, tuple(sorted((a, b))))
                            roots = root_cache.get(key)
                            if roots is None:
                                roots = insert_lemma(pair, a, b)
                            else:
                                root_calls["oracle_cache_hits"] += 1
                            pairs.append({"pair": pair, "a": a, "b": b,
                                          "mid": mid, "root_count": len(roots),
                                          "link_valid": mid in roots})
                        event["pairs"] = pairs
                        if all(row["link_valid"] for row in pairs):
                            began = time.perf_counter()
                            checked = prior.verify_relation(profile, model, leaves)
                            check_elapsed += time.perf_counter() - began
                            event["relation_status"] = checked["status"]
                            if checked["status"] == "verified_four_point_relation":
                                status, accepted = "VERIFIED_RELATION", checked
                            else:
                                clause = [literal for leaf in leaves for literal in
                                          prior.mismatch(leaf, bits_value(leaf, model))]
                                assert solver.add_clause(clause)
                                added_clauses.append(clause)
                                event["rejection_digest"] = prior.canonical_hash(clause)
                    trace.append(event)
                    stream.write(json.dumps(event, sort_keys=True) + "\n")
                    stream.flush()
                    if status is not None:
                        break
                    if len(lemmas) >= LIMITS["max_refinements"]:
                        status = "BOUNDED_UNKNOWN"
                        break
                if status is None:
                    status = "BOUNDED_UNKNOWN"
        finally:
            timer.cancel()
            timer.join()
        final_vars, final_clauses, final_xors = (
            solver.variables, solver.clauses_added, solver.xors_added)
    total_seconds = time.perf_counter() - started
    other_seconds = max(0.0, total_seconds - build_seconds - load_seconds -
                        solver_elapsed - lemma_elapsed - check_elapsed)
    receipt = {
        "schema": "q1426-lift-slice-run-v1", "proposal_id": "Q1426",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "n": n, "curve_id": case["curve_id"], "workload_id": case["workload_id"],
        "input_law": "frozen_ordinary_target_deterministic_lift_slice",
        "factor_base_actual_B": case["B"], "factor_base_folded_columns_K": case["K"],
        "factor_base_enumerated_set_sha256": case["base_digest"],
        "public_target": [str(x) for x in profile["public_target"]],
        "lift_index": index, "lift_count": case["raw_lift_count"],
        "target_x_coords": target_x, "selected_lifts": case["selected_indices"],
        "ordinary_receipt_sha256": prior.digest(parent_path),
        "status": status, "wall_cap_fired": wall_stop,
        "target_independent_setup_seconds": setup_seconds,
        "target_pdp_wall_seconds": total_seconds,
        "formula_build_seconds": build_seconds,
        "formula_load_seconds": load_seconds,
        "solver_wall_seconds": solver_elapsed,
        "lemma_oracle_and_add_seconds": lemma_elapsed,
        "relation_check_seconds": check_elapsed,
        "pdp_other_seconds": other_seconds,
        "formula": prior.formula_stats(formula, (0, 1)),
        "solver_calls": len(trace), "root_calls": dict(root_calls),
        "root_field_api_calls": dict(field.calls), "root_lemmas": lemmas,
        "final_solver_variables": final_vars,
        "final_solver_clauses": final_clauses,
        "final_solver_xors": final_xors,
        "trace_sha256": prior.digest(trace_path), "trace_rows": len(trace),
        "verified_relation": accepted,
        "natural_relation_yield_estimate": None,
        "cost_per_novel_rank_row": None,
        "field_operations_complete": None,
        "n131_complete_cold_work_log2": None,
        "n131_complete_online_one_target_work_log2": None,
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "freeze_sha256": prior.digest(HERE / "freeze.json"),
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(stem, status, "calls", len(trace), "lemmas", len(lemmas),
          "wall", round(total_seconds, 3), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--n", type=int, choices=(53, 83))
    parser.add_argument("--index", type=int)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        if args.n is None or args.index is None:
            parser.error("run requires --n and --index")
        run_cell(args.n, args.index)


if __name__ == "__main__":
    main()
