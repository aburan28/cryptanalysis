#!/usr/bin/env python3
"""Q1428 exact outer-root join with one right-pair S3 SAT formula."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import resource
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
Q1427 = ROOT / "experiments/compact-s3-m4-anchor-root-20261010"
sys.path.insert(0, str(Q1427))

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parent = load_module("q1427_double_root_parent", Q1427 / "run.py")
prior = parent.prior

from hybrid import MeteredField, bits_value, exact_roots  # noqa: E402
from right_pair import build_right_pair  # noqa: E402
from stats_bridge import StatsSolver  # noqa: E402

LIMITS = {"wall_seconds_per_anchor": 90, "solver_seconds_per_call": 25,
          "conflicts_per_call": 100000, "max_solver_calls": 17,
          "max_rejected_models": 16, "rss_mib": 1536}


def joined_branches(onb, anchor, lifts):
    """Enumerate every outer S3 root for the frozen anchor and lifts."""
    meter = MeteredField(onb)
    branches = []
    root_calls = 0
    for lift_index, target_x in lifts:
        assert target_x
        for left_index, left_root in enumerate(anchor["roots"]):
            assert left_root
            roots = exact_roots(meter, left_root, target_x)
            root_calls += 1
            for right_index, right_root in enumerate(roots):
                branches.append({"lift_index": lift_index,
                                 "target_x": target_x,
                                 "left_root_index": left_index,
                                 "left_root": left_root,
                                 "right_root_index": right_index,
                                 "right_output_x": right_root})
    return {"branches": branches, "outer_root_calls": root_calls,
            "outer_field_api_calls": dict(meter.calls)}


def source_hashes():
    return {name: prior.digest(HERE / name)
            for name in ("run.py", "verify.py", "test_right_pair.py",
                         "right_pair.py")}


def freeze():
    path = HERE / "freeze.json"
    assert not path.exists()
    parent_frozen = parent.check_freeze()
    cases = {}
    for n in (53, 83):
        case = parent_frozen["cases"][str(n)]
        onb = prior.field.Onb(n)
        control_profile, control_parent, fixture, _, fixture_path = (
            prior.load_case(n, "control_both_preseed"))
        known = case["known_control"]
        known_index = control_parent["raw_preimage_x_coordinates"].index(
            known["raw_target_x"])
        control_anchor = {"leaves": [{"raw_x": value}
                                     for value in known["raw_leaf_x"]],
                          "roots": known["roots"]}
        control_join = joined_branches(
            onb, control_anchor, [(known_index, known["raw_target_x"])])
        expected_right_x = onb.toCoords(int(fixture["fixture"][
            "raw_pair_sum_points"][1][0]))
        assert expected_right_x in [branch["right_output_x"]
                                    for branch in control_join["branches"]]
        ordinary_lifts = list(zip(case["selected_lift_indices"],
                                  case["selected_lift_x"]))
        ordinary_joins = [joined_branches(onb, anchor, ordinary_lifts)
                          for anchor in case["ordinary_anchors"]]
        cases[str(n)] = {
            "curve_id": case["curve_id"],
            "ordinary_workload_id": case["ordinary_workload_id"],
            "B": case["B"], "K": case["K"],
            "base_digest": case["base_digest"],
            "normal_basis_weight_bound": case["normal_basis_weight_bound"],
            "ordinary_receipt_sha256": case["ordinary_receipt_sha256"],
            "control_fixture_sha256": prior.digest(fixture_path),
            "raw_lift_count": case["raw_lift_count"],
            "ordinary_lifts": ordinary_lifts,
            "ordinary_anchors": case["ordinary_anchors"],
            "ordinary_joins": ordinary_joins,
            "control_anchor": control_anchor,
            "control_lifts": [[known_index, known["raw_target_x"]]],
            "control_join": control_join,
            "control_right_mid_x": expected_right_x,
        }
        assert control_profile["field_degree_n"] == n
        assert tuple(cases[str(n)][name] for name in
                     ("curve_id", "ordinary_workload_id", "B", "K",
                      "base_digest")) == prior.CASES[n]
    frozen = {
        "schema": "q1428-double-root-freeze-v1", "proposal_id": "Q1428",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "protocol_sha256": prior.digest(HERE / "PROTOCOL.md"),
        "source_sha256": source_hashes(),
        "q1427_freeze_sha256": prior.digest(Q1427 / "freeze.json"),
        "q1427_runner_sha256": prior.digest(Q1427 / "run.py"),
        "stats_library_sha256": prior.digest(parent.STATS_LIBRARY),
        "cmsat_library_sha256": prior.digest(prior.LIBRARY),
        "cases": cases, "limits": LIMITS,
    }
    path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(prior.digest(path))


def check_freeze():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["schema"] == "q1428-double-root-freeze-v1"
    assert frozen["protocol_sha256"] == prior.digest(HERE / "PROTOCOL.md")
    assert frozen["source_sha256"] == source_hashes()
    assert frozen["q1427_freeze_sha256"] == prior.digest(Q1427 / "freeze.json")
    assert frozen["q1427_runner_sha256"] == prior.digest(Q1427 / "run.py")
    assert frozen["stats_library_sha256"] == prior.digest(parent.STATS_LIBRARY)
    assert frozen["cmsat_library_sha256"] == prior.digest(prior.LIBRARY)
    parent.check_freeze()
    return frozen


def assumptions(bits, value):
    return [bit if value >> offset & 1 else -bit
            for offset, bit in enumerate(bits)]


def synthetic_model(n, variables, anchor_x, model, right_leaves):
    left_leaves = [list(range(variables + 1 + pair * n,
                              variables + 1 + (pair + 1) * n))
                   for pair in (0, 1)]
    augmented = dict(model)
    for bits, value in zip(left_leaves, anchor_x):
        augmented.update({bit: bool(value >> offset & 1)
                          for offset, bit in enumerate(bits)})
    return augmented, left_leaves + right_leaves


def run_case(n, kind, anchor_number=None):
    frozen = check_freeze()
    case = frozen["cases"][str(n)]
    assert kind in ("control", "ordinary")
    assert (anchor_number in (0, 1)) if kind == "ordinary" else (
        anchor_number is None)
    stem = (f"n{n}_ordinary_anchor{anchor_number}" if
            kind == "ordinary" else f"n{n}_control")
    path, trace_path = HERE / f"{stem}.json", HERE / f"{stem}.trace.jsonl"
    assert not path.exists() and not trace_path.exists()
    setup_at = time.perf_counter()
    profile, parent_receipt, fixture, parent_path, fixture_path = (
        prior.load_case(n, "ordinary_both_lazy" if kind == "ordinary" else
                        "control_both_preseed"))
    onb = prior.field.Onb(n)
    if kind == "ordinary":
        curve, keys, key = parent.read_base(profile, onb)
    setup_seconds = time.perf_counter() - setup_at
    started = time.perf_counter()
    if kind == "ordinary":
        anchor = parent.choose(profile, parent_receipt, anchor_number,
                               onb, curve, keys, key)
        assert anchor == case["ordinary_anchors"][anchor_number]
        lifts = case["ordinary_lifts"]
        expected_join = case["ordinary_joins"][anchor_number]
    else:
        anchor = case["control_anchor"]
        meter = MeteredField(onb)
        roots = exact_roots(meter, *[leaf["raw_x"]
                                     for leaf in anchor["leaves"]])
        assert list(roots) == anchor["roots"]
        anchor = {**anchor, "root_field_api_calls": dict(meter.calls)}
        lifts = case["control_lifts"]
        expected_join = case["control_join"]
    selection_seconds = time.perf_counter() - started
    join_at = time.perf_counter()
    joined = joined_branches(onb, anchor, lifts)
    join_seconds = time.perf_counter() - join_at
    assert joined == expected_join
    anchor_x = [leaf["raw_x"] for leaf in anchor["leaves"]]
    build_at = time.perf_counter()
    formula, right_leaves, output = build_right_pair(
        n, case["normal_basis_weight_bound"])
    build_seconds = time.perf_counter() - build_at
    trace, accepted, status = [], None, None
    phase = Counter()
    phase["formula_build_seconds"] = build_seconds
    call_count = rejected_models = 0
    any_unknown = wall_stop = call_cap_fired = False
    with StatsSolver(formula.variables) as solver:
        load_at = time.perf_counter()
        solver.load_formula(formula)
        phase["formula_load_seconds"] = time.perf_counter() - load_at
        added_clauses = []
        with trace_path.open("w") as stream:
            for branch in joined["branches"]:
                if status == "VERIFIED_RELATION":
                    break
                while True:
                    remaining = (LIMITS["wall_seconds_per_anchor"] -
                                 (time.perf_counter() - started))
                    if remaining <= 0 or call_count >= LIMITS["max_solver_calls"]:
                        any_unknown = True
                        wall_stop = remaining <= 0
                        call_cap_fired = call_count >= LIMITS["max_solver_calls"]
                        break
                    call_count += 1
                    timer = threading.Timer(remaining, solver.interrupt)
                    timer.daemon = True
                    timer.start()
                    solve_at = time.perf_counter()
                    try:
                        state, model, counters = solver.solve_assuming(
                            assumptions(output, branch["right_output_x"]),
                            seconds=min(LIMITS["solver_seconds_per_call"],
                                        remaining),
                            conflicts=LIMITS["conflicts_per_call"])
                    finally:
                        timer.cancel()
                        timer.join()
                    elapsed = time.perf_counter() - solve_at
                    phase["solver_wall_seconds"] += elapsed
                    event = {"solver_call": call_count, "branch": branch,
                             "state": state, "solver_counters": counters,
                             "solver_wall_seconds": elapsed}
                    if state == "SAT":
                        prior.check_formula_model(formula, added_clauses,
                                                  model)
                        assert bits_value(output, model) == branch[
                            "right_output_x"]
                        augmented, four_leaves = synthetic_model(
                            n, formula.variables, anchor_x, model,
                            right_leaves)
                        check_at = time.perf_counter()
                        checked = prior.verify_relation(profile, augmented,
                                                        four_leaves)
                        phase["relation_check_seconds"] += (
                            time.perf_counter() - check_at)
                        event["relation_status"] = checked["status"]
                        event["right_leaf_x"] = [bits_value(bits, model)
                                                 for bits in right_leaves]
                        if checked["status"] == "verified_four_point_relation":
                            status, accepted = "VERIFIED_RELATION", checked
                        else:
                            block = [literal for bits in right_leaves
                                     for literal in prior.mismatch(
                                         bits, bits_value(bits, model))]
                            event["block_root_consistent"] = (
                                solver.add_clause(block))
                            added_clauses.append(block)
                            rejected_models += 1
                            event["rejection_digest"] = (
                                prior.canonical_hash(block))
                            if rejected_models >= LIMITS["max_rejected_models"]:
                                any_unknown = True
                    elif state == "BOUNDED_UNKNOWN":
                        any_unknown = True
                    else:
                        assert state == "UNSAT"
                    trace.append(event)
                    stream.write(json.dumps(event, sort_keys=True) + "\n")
                    stream.flush()
                    if (state != "SAT" or status == "VERIFIED_RELATION" or
                            rejected_models >= LIMITS["max_rejected_models"]):
                        break
                if (status == "VERIFIED_RELATION" or wall_stop or
                        call_cap_fired or
                        rejected_models >= LIMITS["max_rejected_models"]):
                    break
    if status is None:
        status = "BOUNDED_UNKNOWN" if any_unknown else "UNSAT_TESTED_SUBSET"
    total_seconds = time.perf_counter() - started
    wall_stop = wall_stop or total_seconds >= LIMITS["wall_seconds_per_anchor"]
    charged = selection_seconds + join_seconds + sum(phase.values())
    phase["pdp_other_seconds"] = max(0.0, total_seconds - charged)
    receipt = {
        "schema": "q1428-double-root-run-v1", "proposal_id": "Q1428",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "n": n, "kind": kind, "anchor_number": anchor_number,
        "curve_id": case["curve_id"],
        "workload_id": parent_receipt["workload_id"],
        "input_law": ("frozen_ordinary_target_hash_anchor_subset" if
                      kind == "ordinary" else "known_solution_control"),
        "public_target": [str(x) for x in profile["public_target"]],
        "factor_base_actual_B": case["B"],
        "factor_base_folded_columns_K": case["K"],
        "factor_base_enumerated_set_sha256": case["base_digest"],
        "parent_receipt_sha256": prior.digest(parent_path),
        "fixture_receipt_sha256": (prior.digest(fixture_path)
                                    if fixture_path else None),
        "selected_anchor": anchor,
        "raw_target_lift_count": len(parent_receipt[
            "raw_preimage_x_coordinates"]),
        "scheduled_lifts": lifts,
        "outer_join": joined,
        "attempted_branches": len(set((row["branch"]["lift_index"],
                                       row["branch"]["left_root_index"],
                                       row["branch"]["right_root_index"])
                                      for row in trace)),
        "status": status, "wall_cap_fired": wall_stop,
        "solver_call_cap_fired": call_cap_fired,
        "target_independent_setup_seconds": setup_seconds,
        "target_pdp_wall_seconds": total_seconds,
        "anchor_selection_seconds": selection_seconds,
        "outer_join_seconds": join_seconds,
        "phase_seconds": dict(phase),
        "formula": {"variables": formula.variables,
                    "cnf_clauses": len(formula.clauses),
                    "xor_rows": len(formula.xors),
                    "and_gates": len(formula.and_cache),
                    "right_variable_leaves": 2,
                    "external_s3_links": 2,
                    "inside_sat_s3_links": 1},
        "solver_calls": call_count,
        "solver_conflicts": sum(row["solver_counters"]["conflicts"]
                                for row in trace),
        "solver_propagations": sum(row["solver_counters"]["propagations"]
                                   for row in trace),
        "solver_decisions": sum(row["solver_counters"]["decisions"]
                                for row in trace),
        "rejected_models": rejected_models,
        "trace_sha256": prior.digest(trace_path),
        "trace_rows": len(trace),
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
    print(stem, status, "calls", call_count, "conflicts",
          receipt["solver_conflicts"], "wall", round(total_seconds, 3),
          flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--n", type=int, choices=(53, 83))
    parser.add_argument("--kind", choices=("control", "ordinary"))
    parser.add_argument("--anchor", type=int, choices=(0, 1))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        if args.n is None or args.kind is None:
            parser.error("run requires --n and --kind")
        run_case(args.n, args.kind, args.anchor)


if __name__ == "__main__":
    main()
