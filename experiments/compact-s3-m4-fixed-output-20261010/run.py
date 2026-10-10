#!/usr/bin/env python3
"""Q1429 frozen three-encoding fixed-output S3 search grid."""

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
Q1428 = ROOT / "experiments/compact-s3-m4-double-root-20261010"
sys.path.insert(0, str(Q1428))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parent = load_module("q1428_fixed_output_parent", Q1428 / "run.py")
prior = parent.prior

from formula import VARIANTS, build, shape  # noqa: E402
from hybrid import MeteredField, bits_value, exact_roots  # noqa: E402
from stats_bridge import StatsSolver  # noqa: E402

LIMITS = {"wall_seconds_per_cell": 30, "solver_seconds_per_call": 10,
          "conflicts_per_call": 100000, "rss_mib": 1536}


def source_hashes():
    return {name: prior.digest(HERE / name)
            for name in ("run.py", "formula.py", "test_formula.py",
                         "verify.py")}


def choose_branch(case, kind):
    if kind == "control":
        matches = [branch for branch in case["control_join"]["branches"]
                   if branch["right_output_x"] == case["control_right_mid_x"]]
        assert matches
        return matches[0]
    assert kind == "ordinary"
    branches = case["ordinary_joins"][0]["branches"]
    assert branches
    return branches[0]


def freeze():
    path = HERE / "freeze.json"
    assert not path.exists()
    old = parent.check_freeze()
    cases = {}
    for n in (53, 83):
        case = old["cases"][str(n)]
        selected = {}
        for kind in ("control", "ordinary"):
            branch = choose_branch(case, kind)
            selected[kind] = {
                "branch": branch,
                "formula": {variant: shape(build(
                    n, case["normal_basis_weight_bound"],
                    branch["right_output_x"], variant)[0])
                    for variant in VARIANTS},
                "q1428_receipt_sha256": prior.digest(Q1428 / (
                    f"n{n}_control.json" if kind == "control" else
                    f"n{n}_ordinary_anchor0.json")),
            }
        cases[str(n)] = {
            "curve_id": case["curve_id"],
            "ordinary_workload_id": case["ordinary_workload_id"],
            "B": case["B"], "K": case["K"],
            "base_digest": case["base_digest"],
            "normal_basis_weight_bound": case["normal_basis_weight_bound"],
            "selected": selected,
        }
    frozen = {
        "schema": "q1429-fixed-output-freeze-v2",
        "proposal_id": "Q1429", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "variants": list(VARIANTS), "limits": LIMITS,
        "source_sha256": source_hashes(),
        "protocol_sha256": prior.digest(HERE / "PROTOCOL.md"),
        "q1428_freeze_sha256": prior.digest(Q1428 / "freeze.json"),
        "q1428_runner_sha256": prior.digest(Q1428 / "run.py"),
        "stats_library_sha256": prior.digest(parent.parent.STATS_LIBRARY),
        "cmsat_library_sha256": prior.digest(prior.LIBRARY),
        "cases": cases,
    }
    path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(prior.digest(path))


def check_freeze():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["schema"] == "q1429-fixed-output-freeze-v2"
    assert frozen["variants"] == list(VARIANTS)
    assert frozen["source_sha256"] == source_hashes()
    assert frozen["protocol_sha256"] == prior.digest(HERE / "PROTOCOL.md")
    assert frozen["q1428_freeze_sha256"] == prior.digest(Q1428 / "freeze.json")
    assert frozen["q1428_runner_sha256"] == prior.digest(Q1428 / "run.py")
    assert frozen["stats_library_sha256"] == prior.digest(
        parent.parent.STATS_LIBRARY)
    assert frozen["cmsat_library_sha256"] == prior.digest(prior.LIBRARY)
    old = parent.check_freeze()
    for n in (53, 83):
        case = frozen["cases"][str(n)]
        source = old["cases"][str(n)]
        assert tuple(case[key] for key in ("curve_id", "ordinary_workload_id",
                                           "B", "K", "base_digest")) == tuple(
            source[key] for key in ("curve_id", "ordinary_workload_id",
                                    "B", "K", "base_digest"))
        for kind in ("control", "ordinary"):
            item = case["selected"][kind]
            assert item["branch"] == choose_branch(source, kind)
            assert item["q1428_receipt_sha256"] == prior.digest(Q1428 / (
                f"n{n}_control.json" if kind == "control" else
                f"n{n}_ordinary_anchor0.json"))
    return frozen


def run_case(n, kind, variant):
    assert kind in ("control", "ordinary") and variant in VARIANTS
    frozen = check_freeze()
    case = frozen["cases"][str(n)]
    old = parent.check_freeze()["cases"][str(n)]
    stem = f"n{n}_{kind}_{variant}"
    path, trace_path = HERE / f"{stem}.json", HERE / f"{stem}.trace.jsonl"
    assert not path.exists() and not trace_path.exists()
    setup_at = time.perf_counter()
    profile, parent_receipt, fixture, parent_path, fixture_path = (
        prior.load_case(n, "control_both_preseed" if kind == "control" else
                        "ordinary_both_lazy"))
    if kind == "ordinary":
        # Reusable archive loading remains outside target-dependent timing.
        onb = prior.field.Onb(n)
        curve, keys, key = parent.parent.read_base(profile, onb)
    setup_seconds = time.perf_counter() - setup_at
    started = time.perf_counter()
    phase = Counter()
    select_at = time.perf_counter()
    if kind == "ordinary":
        selected = parent.parent.choose(profile, parent_receipt, 0,
                                        onb, curve, keys, key)
        assert selected == old["ordinary_anchors"][0]
        lifts, expected_join = old["ordinary_lifts"], old["ordinary_joins"][0]
    else:
        onb = prior.field.Onb(n)
        selected = old["control_anchor"]
        roots = exact_roots(MeteredField(onb), *(
            leaf["raw_x"] for leaf in selected["leaves"]))
        assert list(roots) == selected["roots"]
        lifts, expected_join = old["control_lifts"], old["control_join"]
    phase["anchor_selection_seconds"] = time.perf_counter() - select_at
    join_at = time.perf_counter()
    joined = parent.joined_branches(onb, selected, lifts)
    assert joined == expected_join
    phase["outer_join_seconds"] = time.perf_counter() - join_at
    branch = case["selected"][kind]["branch"]
    assert branch in joined["branches"]
    value = branch["right_output_x"]
    build_at = time.perf_counter()
    formula, leaves, output, assumptions = build(
        n, case["normal_basis_weight_bound"], value, variant)
    phase["formula_build_seconds"] = time.perf_counter() - build_at
    assert shape(formula) == case["selected"][kind]["formula"][variant]
    with StatsSolver(formula.variables) as solver:
        load_at = time.perf_counter()
        solver.load_formula(formula)
        phase["formula_load_seconds"] = time.perf_counter() - load_at
        remaining = max(0.001, LIMITS["wall_seconds_per_cell"] -
                        (time.perf_counter() - started))
        timer = threading.Timer(remaining, solver.interrupt)
        timer.daemon = True
        timer.start()
        solve_at = time.perf_counter()
        try:
            state, model, counters = solver.solve_assuming(
                assumptions,
                seconds=min(remaining, LIMITS["solver_seconds_per_call"]),
                conflicts=LIMITS["conflicts_per_call"])
        finally:
            timer.cancel()
            timer.join()
        phase["solver_wall_seconds"] = time.perf_counter() - solve_at
    relation = None
    right_x = None
    if state == "SAT":
        prior.check_formula_model(formula, [], model)
        assert output is None or bits_value(output, model) == value
        right_x = [bits_value(bits, model) for bits in leaves]
        assert value in exact_roots(MeteredField(onb), *right_x)
        augmented, four_leaves = parent.synthetic_model(
            n, formula.variables,
            [leaf["raw_x"] for leaf in selected["leaves"]], model, leaves)
        check_at = time.perf_counter()
        relation = prior.verify_relation(profile, augmented, four_leaves)
        phase["relation_check_seconds"] = time.perf_counter() - check_at
        status = ("VERIFIED_RELATION" if relation["status"] ==
                  "verified_four_point_relation" else "SAT_NONRELATION")
    elif state == "UNSAT":
        status = "UNSAT_FOR_FIXED_OUTPUT"
    else:
        assert state == "BOUNDED_UNKNOWN"
        status = state
    elapsed = time.perf_counter() - started
    phase["other_seconds"] = max(0.0, elapsed - sum(phase.values()))
    trace = {"state": state, "solver_counters": counters,
             "solver_wall_seconds": phase["solver_wall_seconds"],
             "right_leaf_x": right_x,
             "relation_status": relation["status"] if relation else None}
    trace_path.write_text(json.dumps(trace, sort_keys=True) + "\n")
    receipt = {
        "schema": "q1429-fixed-output-run-v1", "proposal_id": "Q1429",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "n": n, "kind": kind, "variant": variant,
        "curve_id": case["curve_id"],
        "workload_id": parent_receipt["workload_id"],
        "input_law": ("known_solution_output_free_right_leaves" if
                      kind == "control" else
                      "frozen_ordinary_target_first_outer_root"),
        "public_target": [str(x) for x in profile["public_target"]],
        "factor_base_actual_B": case["B"],
        "factor_base_folded_columns_K": case["K"],
        "factor_base_enumerated_set_sha256": case["base_digest"],
        "parent_receipt_sha256": prior.digest(parent_path),
        "fixture_receipt_sha256": (prior.digest(fixture_path)
                                    if fixture_path else None),
        "selected_anchor": selected,
        "outer_join": joined,
        "branch": branch, "right_output_x": value,
        "formula": shape(formula), "status": status,
        "solver_calls": 1,
        "solver_conflicts": counters["conflicts"],
        "solver_propagations": counters["propagations"],
        "solver_decisions": counters["decisions"],
        "target_independent_setup_seconds": setup_seconds,
        "target_pdp_wall_seconds": elapsed,
        "phase_seconds": dict(phase),
        "right_leaf_x": right_x,
        "relation_check": relation,
        "natural_relation_yield_estimate": None,
        "cost_per_novel_rank_row": None,
        "field_operations_complete": None,
        "n131_complete_cold_work_log2": None,
        "n131_complete_online_one_target_work_log2": None,
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "trace_sha256": prior.digest(trace_path),
        "freeze_sha256": prior.digest(HERE / "freeze.json"),
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(stem, status, "conflicts", counters["conflicts"],
          "wall", round(elapsed, 3), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--n", type=int, choices=(53, 83))
    parser.add_argument("--kind", choices=("control", "ordinary"))
    parser.add_argument("--variant", choices=VARIANTS)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        if args.n is None or args.kind is None or args.variant is None:
            parser.error("run requires --n, --kind, and --variant")
        run_case(args.n, args.kind, args.variant)


if __name__ == "__main__":
    main()
