#!/usr/bin/env python3
"""Q1425 incremental SAT with exact selected S3 root lemmas."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import resource
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(OLD / "q1419_partial_pin"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from cmsat_native import IncrementalSolver, LIBRARY  # noqa: E402
from hybrid import (MeteredField, bits_value, build_hybrid, check_clauses,
                    exact_roots, root_lemma)  # noqa: E402
from run_cell import pin_bits, verify_relation  # noqa: E402
from run_probe import field  # noqa: E402

Q1419 = OLD / "q1419_partial_pin/protocol.json"
ORDINARY = {
    53: OLD / "runs/n53_q1410_ordinary.json",
    83: OLD / "runs/n83_q1408_ordinary.json",
}
OLD_SOURCES = (
    "chain_s3.py", "chain_s3_factored.py", "chain_s3_multitarget.py",
    "chain_s3_balanced_multitarget.py", "s3_root_oracle.py",
    "q1419_partial_pin/run_cell.py", "run_probe.py",
)
ROOT_SOURCES = (
    "ecc2k130/codegen/field.py", "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
)
INPUTS = (
    "q1419_partial_pin/protocol.json",
    "runs/n53_q1410_ordinary.json", "runs/n53_q1410_witness_locked.json",
    "runs/n83_q1408_ordinary.json", "runs/n83_q1408_planted_unpinned.json",
    "runs/n83_q1408_planted_locked.json",
    "bases/n53_weight3_orbits.json.gz",
    "bases/n83_weight5_full_point_orbits.bin",
)
CASES = {
    53: ("EC1N53Ckb1hf77aab617904", "74f2979b3e68", 24062, 227,
         "05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5"),
    83: ("EC1N83Ckb1h876c2921cb64", "bab50a1e5f66", 30977592, 186612,
         "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8"),
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def freeze():
    assert LIBRARY.is_file()
    protocol = json.loads(Q1419.read_text())
    assert protocol["proposal_id"] == "Q1419"
    for n, case in CASES.items():
        ordinary = json.loads(ORDINARY[n].read_text())
        assert (ordinary["curve_id"], ordinary["workload_id"],
                ordinary["factor_base_actual_B"],
                ordinary["factor_base_folded_columns"],
                ordinary["factor_base_enumerated_set_sha256"]) == case
        assert protocol["profiles"][str(n)]["curve_id"] == case[0]
    frozen = {
        "schema": "q1425-root-hybrid-freeze-v2", "proposal_id": "Q1425",
        "candidate_id": None, "isogeny": "none",
        "protocol_sha256": digest(HERE / "PROTOCOL.md"),
        "runner_sha256": digest(__file__),
        "hybrid_sha256": digest(HERE / "hybrid.py"),
        "bridge_sha256": digest(HERE / "cmsat_native.py"),
        "lemma_test_sha256": digest(HERE / "test_lemma.py"),
        "verifier_sha256": digest(HERE / "verify.py"),
        "cmsat_library": str(LIBRARY.resolve()),
        "cmsat_library_sha256": digest(LIBRARY),
        "old_source_sha256": {name: digest(OLD / name) for name in OLD_SOURCES},
        "root_source_sha256": {name: digest(ROOT / name) for name in ROOT_SOURCES},
        "input_sha256": {name: digest(OLD / name) for name in INPUTS},
        "ordinary_cases": {str(n): {"curve_id": row[0],
                                     "workload_id": row[1], "B": row[2],
                                     "K": row[3], "base_digest": row[4]}
                           for n, row in CASES.items()},
        "limits": {"wall_seconds": 90, "solver_seconds_per_call": 25,
                   "conflicts_per_call": 100000, "max_refinements": 16,
                   "max_solver_calls": 17, "rss_mib": 1536},
        "modes": ["control_both_preseed", "ordinary_left_lazy",
                  "ordinary_both_lazy"],
    }
    path = HERE / "freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(digest(path))


def check_freeze():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["proposal_id"] == "Q1425"
    assert frozen["protocol_sha256"] == digest(HERE / "PROTOCOL.md")
    assert frozen["runner_sha256"] == digest(__file__)
    assert frozen["hybrid_sha256"] == digest(HERE / "hybrid.py")
    assert frozen["bridge_sha256"] == digest(HERE / "cmsat_native.py")
    assert frozen["lemma_test_sha256"] == digest(HERE / "test_lemma.py")
    assert frozen["verifier_sha256"] == digest(HERE / "verify.py")
    assert frozen["cmsat_library_sha256"] == digest(LIBRARY)
    assert all(digest(OLD / name) == value
               for name, value in frozen["old_source_sha256"].items())
    assert all(digest(ROOT / name) == value
               for name, value in frozen["root_source_sha256"].items())
    assert all(digest(OLD / name) == value
               for name, value in frozen["input_sha256"].items())
    return frozen


def load_case(n, mode):
    protocol = json.loads(Q1419.read_text())
    profile = copy.deepcopy(protocol["profiles"][str(n)])
    if mode == "control_both_preseed":
        parent_path = ROOT / profile["parent_receipt"]["path"]
        fixture_path = ROOT / profile["fixture_receipt"]["path"]
        fixture = json.loads(fixture_path.read_text())
    else:
        parent_path = ORDINARY[n]
        fixture_path = None
        fixture = None
    parent = json.loads(parent_path.read_text())
    case = CASES[n]
    assert (parent["curve_id"], parent["factor_base_actual_B"],
            parent["factor_base_folded_columns"],
            parent["factor_base_enumerated_set_sha256"]) == (
        case[0], case[2], case[3], case[4])
    assert len(parent["raw_preimage_x_coordinates"]) == profile["cofactor"]
    profile["public_target"] = parent["public_target"]
    profile["workload_id"] = parent["workload_id"]
    if mode.startswith("ordinary"):
        assert parent["workload_id"] == case[1]
    return profile, parent, fixture, parent_path, fixture_path


def check_formula_model(formula, added_clauses, model):
    assert model is not None
    assert all(bit in model for bit in range(1, formula.variables + 1))
    assert check_clauses(formula.clauses, model)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    assert check_clauses(added_clauses, model)


def mismatch(bits, value):
    return [(-bit if value >> i & 1 else bit)
            for i, bit in enumerate(bits)]


def formula_stats(formula, deferred_pairs):
    return {"variables": formula.variables, "cnf_clauses": len(formula.clauses),
            "xor_rows": len(formula.xors), "and_gates": len(formula.and_cache),
            "s3_links_inside_sat": 3 - len(deferred_pairs),
            "s3_links_external": len(deferred_pairs),
            "four_variable_leaves": True}


def run_case(n, mode):
    frozen = check_freeze()
    assert mode in frozen["modes"]
    deferred_pairs = (0,) if mode == "ordinary_left_lazy" else (0, 1)
    stem = f"n{n}_{mode}"
    output = HERE / f"{stem}.json"
    trace_path = HERE / f"{stem}.trace.jsonl"
    assert not output.exists() and not trace_path.exists()
    limits = frozen["limits"]
    setup_at = time.perf_counter()
    profile, parent, fixture, parent_path, fixture_path = load_case(n, mode)
    onb = field.Onb(n)
    metered = MeteredField(onb)
    setup_seconds = time.perf_counter() - setup_at
    started = time.perf_counter()
    formula, leaves, mids, _, selector = build_hybrid(
        n, profile["normal_basis_weight_bound"],
        parent["raw_preimage_x_coordinates"], deferred_pairs)
    if fixture is not None:
        raw = fixture["fixture"]
        for bits, value in zip(leaves, raw["raw_leaf_x"]):
            pin_bits(formula, bits, value)
        selected_x = onb.toCoords(int(raw["raw_sum"][0]))
        pin_bits(formula, selector,
                 parent["raw_preimage_x_coordinates"].index(selected_x))
    build_seconds = time.perf_counter() - started
    lemma_receipts, added_clauses = [], []
    root_cache = {}
    root_calls = Counter()
    trace = []
    result, accepted = None, None
    solver_elapsed = lemma_elapsed = relation_elapsed = 0.0
    wall_stop = False
    with IncrementalSolver(formula.variables) as solver:
        load_at = time.perf_counter()
        solver.load_formula(formula)
        load_seconds = time.perf_counter() - load_at
        root_at = time.perf_counter()

        def add_root_lemma(pair, a, b, *, origin):
            nonlocal lemma_elapsed
            key = (pair, tuple(sorted((a, b))))
            assert key not in root_cache
            began = time.perf_counter()
            roots = exact_roots(metered, a, b)
            root_calls["oracle_misses"] += 1
            root_calls[f"roots_{len(roots)}"] += 1
            root_cache[key] = roots
            branch = solver.new_var() if len(roots) == 2 else None
            clauses = root_lemma(leaves[2 * pair], leaves[2 * pair + 1],
                                 mids[pair],
                                 a, b, roots, branch)
            assert all(solver.add_clause(row) for row in clauses)
            added_clauses.extend(clauses)
            lemma_elapsed += time.perf_counter() - began
            lemma_receipts.append({
                "origin": origin, "pair": pair,
                "left_x": a, "right_x": b,
                "root_x": roots, "branch_var": branch,
                "clauses": len(clauses), "clause_digest": canonical_hash(clauses),
            })
            return roots

        if fixture is not None:
            raw = fixture["fixture"]["raw_leaf_x"]
            for pair in deferred_pairs:
                add_root_lemma(pair, raw[2 * pair], raw[2 * pair + 1],
                               origin="known_control_preseed")
        root_preseed_seconds = time.perf_counter() - root_at
        timer = threading.Timer(limits["wall_seconds"], solver.interrupt)
        timer.daemon = True
        timer.start()
        try:
            with trace_path.open("w") as stream:
                for call_number in range(1, limits["max_solver_calls"] + 1):
                    remaining = limits["wall_seconds"] - (time.perf_counter() - started)
                    if remaining <= 0:
                        result, wall_stop = "BOUNDED_UNKNOWN", True
                        break
                    solve_at = time.perf_counter()
                    state, model = solver.solve(
                        seconds=min(limits["solver_seconds_per_call"], remaining),
                        conflicts=limits["conflicts_per_call"])
                    elapsed = time.perf_counter() - solve_at
                    solver_elapsed += elapsed
                    event = {"solver_call": call_number, "state": state,
                             "solver_wall_seconds": elapsed,
                             "root_lemmas_before": len(lemma_receipts),
                             "clauses_before": solver.clauses_added}
                    if state != "SAT":
                        result = state
                    else:
                        check_formula_model(formula, added_clauses, model)
                        pair_results = []
                        for pair in deferred_pairs:
                            a = bits_value(leaves[2 * pair], model)
                            b = bits_value(leaves[2 * pair + 1], model)
                            mid = bits_value(mids[pair], model)
                            key = (pair, tuple(sorted((a, b))))
                            if key not in root_cache:
                                roots = add_root_lemma(
                                    pair, a, b, origin="lazy_sat_model")
                            else:
                                roots = root_cache[key]
                                root_calls["oracle_cache_hits"] += 1
                            pair_results.append({
                                "pair": pair, "left_x": a, "right_x": b,
                                "mid_x": mid, "root_count": len(roots),
                                "link_valid": mid in roots})
                        event["pairs"] = pair_results
                        if not all(row["link_valid"] for row in pair_results):
                            result = None
                        else:
                            check_at = time.perf_counter()
                            checked = verify_relation(profile, model, leaves)
                            relation_elapsed += time.perf_counter() - check_at
                            event["relation_status"] = checked["status"]
                            if checked["status"] == "verified_four_point_relation":
                                result, accepted = "VERIFIED_RELATION", checked
                            else:
                                # The candidate leaf set cannot yield an
                                # accepted distinct-column public relation.
                                block = []
                                for bits in leaves:
                                    block.extend(mismatch(bits, bits_value(bits, model)))
                                block.extend(mismatch(selector,
                                                       bits_value(selector, model)))
                                assert solver.add_clause(block)
                                added_clauses.append(block)
                                event["rejected_model_clause_digest"] = canonical_hash(block)
                                result = None
                    trace.append(event)
                    stream.write(json.dumps(event, sort_keys=True) + "\n")
                    stream.flush()
                    if result is not None:
                        break
                    if len(lemma_receipts) >= limits["max_refinements"]:
                        result = "BOUNDED_UNKNOWN"
                        break
                if result is None:
                    result = "BOUNDED_UNKNOWN"
        finally:
            timer.cancel()
            timer.join()
        total_variables = solver.variables
        total_clauses = solver.clauses_added
        total_xors = solver.xors_added
    total_seconds = time.perf_counter() - started
    assert result is not None
    receipt = {
        "schema": "q1425-root-hybrid-run-v1", "proposal_id": "Q1425",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": CASES[n][0],
        "workload_id": CASES[n][1] if mode.startswith("ordinary") else profile["workload_id"],
        "input_law": "ordinary" if mode.startswith("ordinary") else "known_solution_control",
        "factor_base_actual_B": CASES[n][2],
        "factor_base_folded_columns_K": CASES[n][3],
        "factor_base_enumerated_set_sha256": CASES[n][4],
        "n": n, "mode": mode,
        "deferred_pairs": list(deferred_pairs),
        "public_target": [str(value) for value in profile["public_target"]],
        "ordinary_or_control_receipt_sha256": digest(parent_path),
        "fixture_receipt_sha256": digest(fixture_path) if fixture_path else None,
        "target_independent_setup_seconds": setup_seconds,
        "formula_build_seconds": build_seconds,
        "formula_load_seconds": load_seconds,
        "root_preseed_seconds": root_preseed_seconds,
        "solver_wall_seconds": solver_elapsed,
        "lemma_oracle_and_add_seconds": lemma_elapsed,
        "relation_check_seconds": relation_elapsed,
        "pdp_wall_seconds": total_seconds,
        "pdp_other_seconds": max(0.0, total_seconds - build_seconds -
                                  load_seconds - solver_elapsed -
                                  lemma_elapsed - relation_elapsed),
        "target_pdp_wall_seconds": total_seconds if mode.startswith("ordinary") else None,
        "formula": formula_stats(formula, deferred_pairs),
        "status": result, "wall_cap_fired": wall_stop,
        "solver_calls": len(trace),
        "oracle_root_calls": dict(root_calls),
        "root_field_api_calls": dict(metered.calls),
        "refinement_lemmas": lemma_receipts,
        "final_solver_variables": total_variables,
        "final_solver_clauses": total_clauses,
        "final_solver_xors": total_xors,
        "trace_sha256": digest(trace_path),
        "trace_rows": len(trace),
        "verified_relation": accepted,
        "natural_relation_yield_estimate": None,
        "field_operations_complete": None,
        "n131_complete_cold_work_log2": None,
        "n131_complete_online_one_target_work_log2": None,
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "freeze_sha256": digest(HERE / "freeze.json"),
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(stem, result, "calls", len(trace), "lemmas", len(lemma_receipts),
          "wall", round(total_seconds, 3), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--n", type=int, choices=(53, 83))
    parser.add_argument("--mode", choices=("control_both_preseed",
                                            "ordinary_left_lazy",
                                            "ordinary_both_lazy"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        if args.n is None or args.mode is None:
            parser.error("run requires --n and --mode")
        run_case(args.n, args.mode)


if __name__ == "__main__":
    main()
