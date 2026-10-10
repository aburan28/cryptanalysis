#!/usr/bin/env python3
"""Q1427 early-root anchored four-summand ordinary-search experiment."""

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
Q1425 = ROOT / "experiments/compact-s3-m4-root-hybrid-20261010"
Q1426 = ROOT / "experiments/compact-s3-m4-lift-slice-20261010"
sys.path.insert(0, str(Q1425))

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load_module("q1425_anchor_parent", Q1425 / "run.py")
lift_parent = load_module("q1426_anchor_parent", Q1426 / "run.py")

from anchor_selection import select_anchor  # noqa: E402
from hybrid import MeteredField, bits_value, build_hybrid, exact_roots  # noqa: E402
from run_cell import OrbitKey, canonical_x, curves, pin_bits, read_base_keys  # noqa: E402
from stats_bridge import STATS_LIBRARY, StatsSolver  # noqa: E402

LIMITS = {"wall_seconds_per_anchor": 90, "solver_seconds_per_call": 25,
          "conflicts_per_call": 100000, "max_solver_calls": 17,
          "max_rejected_models": 16, "max_anchor_candidates": 5000,
          "rss_mib": 1536}
def read_base(profile, onb):
    curve = curves.Curve(onb)
    keys = read_base_keys(profile, onb)
    if profile["field_degree_n"] == 53:
        key = lambda point: canonical_x(onb, point[0])
    else:
        orbit = OrbitKey(onb)
        key = lambda point: orbit.canonical(point)[0]
    return curve, keys, key


def choose(profile, parent, anchor_number, onb, curve, keys, key):
    meter = MeteredField(onb)
    selected = select_anchor(
        n=profile["field_degree_n"],
        weight=profile["normal_basis_weight_bound"],
        curve_id=parent["curve_id"], workload_id=parent["workload_id"],
        anchor_number=anchor_number, onb=onb, curve=curve,
        cofactor=profile["cofactor"],
        subgroup_order=profile["subgroup_order_r"],
        exact_keys=keys, canonical_key=key,
        root_oracle=lambda a, b: exact_roots(meter, a, b),
        max_candidates=LIMITS["max_anchor_candidates"])
    selected["root_field_api_calls"] = dict(meter.calls)
    return selected


def freeze():
    path = HERE / "freeze.json"
    assert not path.exists()
    prior.check_freeze()
    lift_frozen = lift_parent.check_freeze()
    cases = {}
    for n in (53, 83):
        profile, parent, _, parent_path, _ = prior.load_case(
            n, "ordinary_both_lazy")
        onb = prior.field.Onb(n)
        curve, keys, key = read_base(profile, onb)
        anchors = [choose(profile, parent, index, onb, curve, keys, key)
                   for index in (0, 1)]
        controls, _, fixture, _, fixture_path = prior.load_case(
            n, "control_both_preseed")
        raw = fixture["fixture"]
        known_x = onb.toCoords(int(raw["raw_sum"][0]))
        known_pair = raw["raw_leaf_x"][:2]
        known_roots = exact_roots(MeteredField(onb), *known_pair)
        assert known_roots and controls["field_degree_n"] == n
        all_lifts = lift_frozen["cases"][str(n)]["selected_indices"]
        selected_lifts = all_lifts[:2] if n == 53 else all_lifts
        cases[str(n)] = {
            "curve_id": parent["curve_id"],
            "ordinary_workload_id": parent["workload_id"],
            "B": parent["factor_base_actual_B"],
            "K": parent["factor_base_folded_columns"],
            "base_digest": parent["factor_base_enumerated_set_sha256"],
            "base_archive_sha256": profile["factor_base_archive"]["sha256"],
            "normal_basis_weight_bound": profile["normal_basis_weight_bound"],
            "ordinary_receipt_sha256": prior.digest(parent_path),
            "control_fixture_sha256": prior.digest(fixture_path),
            "raw_lift_count": len(parent["raw_preimage_x_coordinates"]),
            "selected_lift_indices": selected_lifts,
            "selected_lift_x": [parent["raw_preimage_x_coordinates"][i]
                                for i in selected_lifts],
            "known_control": {"raw_leaf_x": known_pair,
                              "raw_target_x": known_x,
                              "roots": list(known_roots)},
            "ordinary_anchors": anchors,
        }
        assert tuple(cases[str(n)][field] for field in
                     ("curve_id", "ordinary_workload_id", "B", "K",
                      "base_digest")) == prior.CASES[n]
    frozen = {
        "schema": "q1427-anchor-root-freeze-v1", "proposal_id": "Q1427",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "protocol_sha256": prior.digest(HERE / "PROTOCOL.md"),
        "source_sha256": {name: prior.digest(HERE / name) for name in
                          ("run.py", "verify.py", "test_anchor.py",
                           "anchor_selection.py", "stats_bridge.py",
                           "cmsat_stats.cpp", "build_shim.sh")},
        "stats_library_sha256": prior.digest(STATS_LIBRARY),
        "cmsat_library_sha256": prior.digest(prior.LIBRARY),
        "q1425_freeze_sha256": prior.digest(Q1425 / "freeze.json"),
        "q1426_freeze_sha256": prior.digest(Q1426 / "freeze.json"),
        "q1425_runner_sha256": prior.digest(Q1425 / "run.py"),
        "q1426_runner_sha256": prior.digest(Q1426 / "run.py"),
        "cases": cases, "limits": LIMITS,
    }
    path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(prior.digest(path))


def check_freeze():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["schema"] == "q1427-anchor-root-freeze-v1"
    assert frozen["protocol_sha256"] == prior.digest(HERE / "PROTOCOL.md")
    assert all(prior.digest(HERE / name) == value for name, value in
               frozen["source_sha256"].items())
    assert frozen["stats_library_sha256"] == prior.digest(STATS_LIBRARY)
    assert frozen["cmsat_library_sha256"] == prior.digest(prior.LIBRARY)
    assert frozen["q1425_freeze_sha256"] == prior.digest(Q1425 / "freeze.json")
    assert frozen["q1426_freeze_sha256"] == prior.digest(Q1426 / "freeze.json")
    assert frozen["q1425_runner_sha256"] == prior.digest(Q1425 / "run.py")
    assert frozen["q1426_runner_sha256"] == prior.digest(Q1426 / "run.py")
    prior.check_freeze()
    lift_parent.check_freeze()
    for n in (53, 83):
        _, parent, _, parent_path, _ = prior.load_case(n, "ordinary_both_lazy")
        case = frozen["cases"][str(n)]
        assert case["ordinary_receipt_sha256"] == prior.digest(parent_path)
        assert case["selected_lift_x"] == [
            parent["raw_preimage_x_coordinates"][i]
            for i in case["selected_lift_indices"]]
    return frozen


def assumptions(bits, value):
    return [bit if value >> offset & 1 else -bit
            for offset, bit in enumerate(bits)]


def run_case(n, kind, anchor_number=None):
    frozen = check_freeze()
    case = frozen["cases"][str(n)]
    assert kind in ("control", "ordinary")
    if kind == "ordinary":
        assert anchor_number in (0, 1)
        stem = f"n{n}_ordinary_anchor{anchor_number}"
    else:
        assert anchor_number is None
        stem = f"n{n}_control"
    path, trace_path = HERE / f"{stem}.json", HERE / f"{stem}.trace.jsonl"
    assert not path.exists() and not trace_path.exists()
    setup_at = time.perf_counter()
    profile, parent, fixture, parent_path, fixture_path = prior.load_case(
        n, "ordinary_both_lazy" if kind == "ordinary" else
        "control_both_preseed")
    onb = prior.field.Onb(n)
    if kind == "ordinary":
        curve, keys, key = read_base(profile, onb)
    setup_seconds = time.perf_counter() - setup_at
    started = time.perf_counter()
    if kind == "ordinary":
        selected = choose(profile, parent, anchor_number, onb, curve,
                          keys, key)
        assert selected == case["ordinary_anchors"][anchor_number]
        lift_indices = case["selected_lift_indices"]
        lift_x = case["selected_lift_x"]
    else:
        known = case["known_control"]
        meter = MeteredField(onb)
        roots = exact_roots(meter, *known["raw_leaf_x"])
        assert list(roots) == known["roots"]
        selected = {"leaves": [{"raw_x": x} for x in known["raw_leaf_x"]],
                    "roots": list(roots), "counts": {"root_oracle_calls": 1},
                    "root_field_api_calls": dict(meter.calls)}
        lift_indices = [parent["raw_preimage_x_coordinates"].index(
            known["raw_target_x"])]
        lift_x = [known["raw_target_x"]]
    selection_seconds = time.perf_counter() - started
    anchor_x = [entry["raw_x"] for entry in selected["leaves"]]
    trace, formulas, accepted = [], [], None
    phase = Counter()
    call_count = rejected_models = 0
    any_unknown = wall_stop = call_cap_fired = False
    status = None
    with trace_path.open("w") as stream:
        for lift_index, target_x in zip(lift_indices, lift_x):
            if status == "VERIFIED_RELATION":
                break
            if time.perf_counter() - started >= LIMITS["wall_seconds_per_anchor"]:
                any_unknown = wall_stop = True
                break
            build_at = time.perf_counter()
            formula, leaves, mids, _, selector = build_hybrid(
                n, profile["normal_basis_weight_bound"], [target_x], (0,))
            for bits, value in zip(leaves[:2], anchor_x):
                pin_bits(formula, bits, value)
            phase["formula_build_seconds"] += time.perf_counter() - build_at
            formulas.append({"lift_index": lift_index,
                             "stats": prior.formula_stats(formula, (0,))})
            with StatsSolver(formula.variables) as solver:
                load_at = time.perf_counter()
                solver.load_formula(formula)
                phase["formula_load_seconds"] += time.perf_counter() - load_at
                added_clauses = []
                for root_index, root_x in enumerate(selected["roots"]):
                    branch_done = False
                    while not branch_done:
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
                                assumptions(mids[0], root_x),
                                seconds=min(LIMITS["solver_seconds_per_call"],
                                            remaining),
                                conflicts=LIMITS["conflicts_per_call"])
                        finally:
                            timer.cancel()
                            timer.join()
                        elapsed = time.perf_counter() - solve_at
                        phase["solver_wall_seconds"] += elapsed
                        event = {"lift_index": lift_index,
                                 "root_index": root_index, "root_x": root_x,
                                 "solver_call": call_count, "state": state,
                                 "solver_wall_seconds": elapsed,
                                 "solver_counters": counters}
                        if state == "SAT":
                            prior.check_formula_model(formula, added_clauses,
                                                      model)
                            assert bits_value(mids[0], model) == root_x
                            assert bits_value(selector, model) == 0
                            check_at = time.perf_counter()
                            checked = prior.verify_relation(profile, model,
                                                            leaves)
                            phase["relation_check_seconds"] += (
                                time.perf_counter() - check_at)
                            event["relation_status"] = checked["status"]
                            event["right_leaf_x"] = [
                                bits_value(bits, model) for bits in leaves[2:]]
                            if checked["status"] == "verified_four_point_relation":
                                accepted, status = checked, "VERIFIED_RELATION"
                                branch_done = True
                            else:
                                block = [literal for bits in leaves[2:]
                                         for literal in prior.mismatch(
                                             bits, bits_value(bits, model))]
                                event["block_root_consistent"] = (
                                    solver.add_clause(block))
                                added_clauses.append(block)
                                rejected_models += 1
                                event["rejection_digest"] = (
                                    prior.canonical_hash(block))
                                if rejected_models >= LIMITS["max_rejected_models"]:
                                    any_unknown = branch_done = True
                        elif state == "BOUNDED_UNKNOWN":
                            any_unknown = branch_done = True
                        else:
                            assert state == "UNSAT"
                            branch_done = True
                        trace.append(event)
                        stream.write(json.dumps(event, sort_keys=True) + "\n")
                        stream.flush()
                        if status == "VERIFIED_RELATION":
                            break
                    if wall_stop or call_cap_fired or (
                            status == "VERIFIED_RELATION") or (
                            rejected_models >= LIMITS["max_rejected_models"]):
                        break
            if (wall_stop or call_cap_fired or
                    rejected_models >= LIMITS["max_rejected_models"]):
                break
    if status is None:
        status = "BOUNDED_UNKNOWN" if any_unknown else "UNSAT_TESTED_SUBSET"
    total_seconds = time.perf_counter() - started
    charged = selection_seconds + sum(phase.values())
    phase["pdp_other_seconds"] = max(0.0, total_seconds - charged)
    receipt = {
        "schema": "q1427-anchor-root-run-v1", "proposal_id": "Q1427",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "n": n, "kind": kind, "anchor_number": anchor_number,
        "curve_id": case["curve_id"],
        "workload_id": parent["workload_id"],
        "input_law": ("frozen_ordinary_target_hash_anchor_subset" if
                      kind == "ordinary" else "known_solution_control"),
        "public_target": [str(x) for x in profile["public_target"]],
        "factor_base_actual_B": case["B"],
        "factor_base_folded_columns_K": case["K"],
        "factor_base_enumerated_set_sha256": case["base_digest"],
        "parent_receipt_sha256": prior.digest(parent_path),
        "fixture_receipt_sha256": (prior.digest(fixture_path)
                                    if fixture_path else None),
        "raw_target_lift_count": len(parent["raw_preimage_x_coordinates"]),
        "attempted_lift_indices": [row["lift_index"] for row in formulas],
        "selected_anchor": selected,
        "status": status, "wall_cap_fired": wall_stop,
        "solver_call_cap_fired": call_cap_fired,
        "target_independent_setup_seconds": setup_seconds,
        "target_pdp_wall_seconds": total_seconds,
        "anchor_selection_seconds": selection_seconds,
        "phase_seconds": dict(phase),
        "formula_per_lift": formulas,
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
    print(stem, status, "SAT calls", call_count, "conflicts",
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
