#!/usr/bin/env python3
"""Lock a known full-size raw relation into the multi-preimage SAT formula."""

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from chain_s3_multitarget import build_multitarget, decode_choice
from run_probe import HERE, curves, field, lift, parse_model, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("planted", "ordinary"),
                        required=True)
    args = parser.parse_args()
    assert args.kind == "planted" or args.n == 53
    baseline_path = HERE / "runs" / f"n{args.n}_{args.kind}_frozen.json"
    multi_path = HERE / "runs" / f"n{args.n}_{args.kind}_multitarget.json"
    coset_path = HERE / "runs" / f"n{args.n}_{args.kind}_raw_preimages.json"
    witness_path = HERE / "runs/n53_ordinary_raw_pair_witness.json"
    output = HERE / "runs" / f"n{args.n}_{args.kind}_multitarget_locked_verify.json"
    assert not output.exists()
    baseline = json.loads(baseline_path.read_text())
    multi = json.loads(multi_path.read_text())
    coset = json.loads(coset_path.read_text())
    onb = field.Onb(args.n)
    curve = curves.Curve(onb)
    if args.kind == "planted":
        leaf_xs = baseline["fixture"]["planted_leaf_x"]
        mid_xs = baseline["fixture"]["planted_intermediate_x"]
        raw = tuple(int(v) for v in baseline["raw_target"])
        witness_sha = sha(baseline_path)
    else:
        witness = json.loads(witness_path.read_text())
        leaf_xs = [onb.toCoords(int(point[0]))
                   for point in witness["raw_leaf_points"]]
        mid_xs = witness["intermediate_x_coordinates"]
        raw = tuple(int(v) for v in witness["raw_target"])
        witness_sha = sha(witness_path)
    public = tuple(int(v) for v in baseline["public_subgroup_target"])
    assert curve.mul(raw, coset["cofactor"]) == public
    xs = coset["raw_target_x_coordinates"]
    choice = xs.index(onb.toCoords(raw[0]))
    assert tuple(int(v) for v in coset["raw_target_points"][choice]) == raw
    weight = {53: 3, 83: 4}[args.n]
    formula, leaf_vars, mids, _, selector = build_multitarget(
        args.n, weight, xs)
    with tempfile.TemporaryDirectory() as name:
        path = Path(name) / "unlocked.xcnf"
        formula.write(path)
        assert sha(path) == multi["xcnf_sha256"]
        for variables, value in zip(leaf_vars, leaf_xs):
            formula.clauses.extend(([var if value >> bit & 1 else -var]
                                    for bit, var in enumerate(variables)))
        for variables, value in zip(mids, mid_xs):
            formula.clauses.extend(([var if value >> bit & 1 else -var]
                                    for bit, var in enumerate(variables)))
        formula.clauses.extend(([var if choice >> bit & 1 else -var]
                                for bit, var in enumerate(selector)))
        locked_path = Path(name) / "locked.xcnf"
        formula.write(locked_path)
        locked_sha = sha(locked_path)
        started = time.perf_counter()
        result = subprocess.run(["cryptominisat5", "--verb", "0",
                                 "--threads", "1", str(locked_path)],
                                capture_output=True, text=True, timeout=30)
        wall_seconds = time.perf_counter() - started
    assert result.returncode == 10, result.stdout[-1000:]
    values = parse_model(result.stdout)
    assert values is not None and decode_choice(selector, values) == choice
    leaf_coords, relation, lift_status = lift(onb, curve, leaf_vars, values,
                                             raw, public, coset["cofactor"])
    assert relation is not None and lift_status == "verified_four_point_relation"
    assert leaf_coords == leaf_xs
    report = {
        "kind": "full_size_multitarget_locked_witness_replay",
        "proposal_id": multi["proposal_id"],
        "candidate_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"],
        "isogeny": "none",
        "n": args.n,
        "workload_kind": args.kind,
        "status": "verified_locked_sat_relation",
        "choice_index": choice,
        "raw_target_x": xs[choice],
        "leaf_x_coordinates": leaf_coords,
        "solver_wall_seconds": wall_seconds,
        "locked_xcnf_sha256": locked_sha,
        "unlocked_xcnf_sha256": multi["xcnf_sha256"],
        "relation": relation,
        "matched_multitarget_receipt_sha256": sha(multi_path),
        "matched_baseline_receipt_sha256": sha(baseline_path),
        "witness_receipt_sha256": witness_sha,
        "coset_receipt_sha256": sha(coset_path),
        "source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"n": args.n, "kind": args.kind,
                      "choice_index": choice, "status": report["status"],
                      "solver_wall_seconds": wall_seconds}))


if __name__ == "__main__":
    main()
