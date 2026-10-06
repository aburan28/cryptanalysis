#!/usr/bin/env python3
"""Lock a full-size witness at Frobenius shift one and map it back."""

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from chain_s3_orbit import build_orbit, decode_orbit_choice
from run_probe import HERE, curves, field, lift, parse_model, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("planted", "ordinary"),
                        required=True)
    args = parser.parse_args()
    assert args.kind == "planted" or args.n == 53
    baseline_path = HERE / "runs" / f"n{args.n}_{args.kind}_frozen.json"
    orbit_path = HERE / "runs" / f"n{args.n}_{args.kind}_orbit.json"
    coset_path = HERE / "runs" / f"n{args.n}_{args.kind}_raw_preimages.json"
    witness_path = HERE / "runs/n53_ordinary_raw_pair_witness.json"
    output = HERE / "runs" / f"n{args.n}_{args.kind}_orbit_locked_verify.json"
    assert not output.exists()
    baseline = json.loads(baseline_path.read_text())
    orbit = json.loads(orbit_path.read_text())
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
    xs = coset["raw_target_x_coordinates"]
    choice = xs.index(onb.toCoords(raw[0]))
    shift = 1
    rotated_leaves = [onb.toCoords(onb.frob(onb.fromCoords(x), shift))
                      for x in leaf_xs]
    rotated_mids = [onb.toCoords(onb.frob(onb.fromCoords(x), shift))
                    for x in mid_xs]
    formula, leaf_vars, mids, target, pre_selector, shift_selector = build_orbit(
        args.n, {53: 3, 83: 4}[args.n], xs)
    with tempfile.TemporaryDirectory() as name:
        path = Path(name) / "unlocked.xcnf"
        formula.write(path)
        assert sha(path) == orbit["xcnf_sha256"]
        for variables, value in zip(leaf_vars, rotated_leaves):
            formula.clauses.extend(([var if value >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
        for variables, value in zip(mids, rotated_mids):
            formula.clauses.extend(([var if value >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
        formula.clauses.extend(([var if choice >> i & 1 else -var]
                                for i, var in enumerate(pre_selector)))
        formula.clauses.extend(([var if shift >> i & 1 else -var]
                                for i, var in enumerate(shift_selector)))
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
    assert values is not None
    assert decode_orbit_choice(pre_selector, shift_selector, values) == (
        choice, shift)
    target_x = sum(1 << i for i, var in enumerate(target)
                   if values.get(var, False))
    shifted_raw = curve.frob(raw, shift)
    shifted_public = curve.frob(public, shift)
    assert target_x == onb.toCoords(shifted_raw[0])
    leaf_coords, relation, status = lift(onb, curve, leaf_vars, values,
                                         shifted_raw, shifted_public,
                                         coset["cofactor"])
    assert leaf_coords == rotated_leaves and relation is not None
    assert status == "verified_four_point_relation"
    original_points = []
    for encoded, sign in zip(relation["projected_points"],
                             relation["signs"]):
        projected = tuple(int(v) for v in encoded)
        signed = projected if sign == 1 else curve.neg(projected)
        original_points.append(curve.frob(signed, args.n - shift))
    total = None
    for point in original_points:
        total = curve.add(total, point)
    assert total == public
    report = {
        "kind": "full_size_frobenius_orbit_locked_witness_replay",
        "proposal_id": orbit["proposal_id"],
        "candidate_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"],
        "isogeny": "none",
        "n": args.n,
        "workload_kind": args.kind,
        "status": "verified_locked_sat_relation_mapped_back",
        "preimage_index": choice,
        "frobenius_shift": shift,
        "target_x": target_x,
        "leaf_x_coordinates": leaf_coords,
        "solver_wall_seconds": wall_seconds,
        "locked_xcnf_sha256": locked_sha,
        "unlocked_xcnf_sha256": orbit["xcnf_sha256"],
        "original_public_target": [str(v) for v in public],
        "mapped_back_projected_points": [[str(v) for v in point]
                                         for point in original_points],
        "matched_orbit_receipt_sha256": sha(orbit_path),
        "matched_baseline_receipt_sha256": sha(baseline_path),
        "witness_receipt_sha256": witness_sha,
        "coset_receipt_sha256": sha(coset_path),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"n": args.n, "kind": args.kind,
                      "preimage_index": choice, "shift": shift,
                      "status": report["status"],
                      "solver_wall_seconds": wall_seconds}))


if __name__ == "__main__":
    main()
