#!/usr/bin/env python3
"""Q1439 fixed-leaf four-summand compact-S3 feasibility experiment.

Fix a target-independent usable raw leaf A.  For every raw cofactor preimage
T of the public target and both signs of A, set U=T-(+/-A).  Search for three
sparse raw leaves B,C,D with S3(xB,xC,xM)=S3(xM,xD,xU)=0.  A returned model
is a relation only after the full curve group law and distinct columns replay.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import random
import resource
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from chain_s3 import (Formula, evaluate_s3, multiplication_table,  # noqa: E402
                      square_destinations)
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x, decode_choice  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits, read_profile  # noqa: E402
from run_group_add_probe import archive, coordinates, solve, stats  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402

Q1438 = PARENT / "q1438_dense_base"
Q1419 = PARENT / "q1419_partial_pin/protocol.json"
ORDINARY = {
    53: PARENT / "runs/n53_q1410_ordinary.json",
    83: PARENT / "runs/n83_q1408_ordinary.json",
}
PROTOCOL = HERE / "protocol.json"
SEEDS = {53: 1439053, 83: 1439083}
DEPENDENCIES = (
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py",
    "experiments/compact-s3-m4-20261003/run_group_add_probe.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def point_record(point):
    return [int(point[0]), int(point[1])]


def signed(curve, point, sign):
    return point if sign == 1 else curve.neg(point)


def group_sum(curve, points):
    total = None
    for point in points:
        total = curve.add(total, point)
    return total


def independent_anchor(n, onb, curve, weight, cofactor):
    """First usable exact-weight raw x from a target-independent PRNG stream."""
    rng = random.Random(SEEDS[n])
    for trial in range(1, 10_001):
        mask = sum(1 << bit for bit in rng.sample(range(n), weight))
        point = curve.pointFromX(onb.fromCoords(mask))
        if point is not None and curve.mul(point, cofactor) is not None:
            return mask, point, trial
    raise AssertionError("anchor stream did not find a usable point")


def fixture_signs(curve, fixture):
    data = fixture["fixture"]
    points = [tuple(map(int, point)) for point in data["raw_leaf_points"]]
    target = tuple(map(int, data["raw_sum"]))
    matches = [signs for signs in itertools.product((1, -1), repeat=4)
               if group_sum(curve, [signed(curve, p, s)
                                    for p, s in zip(points, signs)]) == target]
    assert matches
    if "signs" in data:
        assert tuple(data["signs"]) in matches
        return tuple(data["signs"])
    return matches[0]


def prepare(n, cell):
    assert n in (53, 83) and cell in ("control", "ordinary")
    dense = json.loads((Q1438 / "solver_protocol.json").read_text())
    instance = dense["instances"][str(n)]
    base_path = Q1438 / f"n{n}_w{instance['new_weight_bound']}_base.json"
    base = json.loads(base_path.read_text())
    assert base["curve_id"] == instance["curve_id"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    _, control_parent, fixture = read_profile(json.loads(Q1419.read_text()), n)
    parent = control_parent if cell == "control" else json.loads(ORDINARY[n].read_text())
    assert parent["curve_id"] == instance["curve_id"]
    public = tuple(map(int, parent["public_target"]))
    assert curve.onCurve(public) and curve.mul(public, instance["subgroup_order"]) is None
    if cell == "control":
        raw_point = tuple(map(int, fixture["fixture"]["raw_leaf_points"][0]))
        anchor_mask = fixture["fixture"]["raw_leaf_x"][0]
        anchor_trials = None
        control_signs = fixture_signs(curve, fixture)
    else:
        anchor_mask, raw_point, anchor_trials = independent_anchor(
            n, onb, curve, instance["new_weight_bound"], instance["cofactor"])
        control_signs = None
    assert onb.toCoords(raw_point[0]) == anchor_mask
    assert curve.onCurve(raw_point)
    assert curve.mul(raw_point, instance["cofactor"]) is not None
    assert anchor_mask.bit_count() <= instance["new_weight_bound"]
    cases = []
    identity_count = 0
    raw_xs = parent["raw_preimage_x_coordinates"]
    assert raw_xs and len(set(raw_xs)) == len(raw_xs)
    for raw_x in raw_xs:
        raw = curve.pointFromX(onb.fromCoords(raw_x))
        assert raw is not None
        projected = curve.mul(raw, instance["cofactor"])
        if projected == public:
            oriented = raw
        elif projected == curve.neg(public):
            oriented = curve.neg(raw)
        else:
            raise AssertionError("raw preimage does not project to public target")
        for sign in (1, -1):
            adjusted = curve.add(oriented, curve.neg(signed(curve, raw_point, sign)))
            if adjusted is None:
                identity_count += 1
                continue
            cases.append({
                "adjusted_x": onb.toCoords(adjusted[0]),
                "anchor_sign": sign,
                "raw_target_x": raw_x,
                "oriented_raw_target": point_record(oriented),
                "adjusted_target": point_record(adjusted),
            })
    target_xs = sorted({case["adjusted_x"] for case in cases})
    assert target_xs
    control_choice = None
    if cell == "control":
        raw_sum = tuple(map(int, fixture["fixture"]["raw_sum"]))
        adjusted = curve.add(raw_sum, curve.neg(signed(
            curve, raw_point, control_signs[0])))
        assert adjusted is not None
        control_choice = target_xs.index(onb.toCoords(adjusted[0]))
    return {
        "n": n, "cell": cell, "dense": dense, "instance": instance,
        "base": base, "base_path": base_path, "onb": onb, "curve": curve,
        "parent": parent, "fixture": fixture, "public": public,
        "anchor_mask": anchor_mask, "anchor_point": raw_point,
        "anchor_trials": anchor_trials, "control_signs": control_signs,
        "cases": cases, "target_xs": target_xs,
        "identity_adjustment_count": identity_count,
        "control_choice": control_choice,
    }


def build(prepared):
    n = prepared["n"]
    weight = prepared["instance"]["new_weight_bound"]
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(3)]
    mid = [formula.new() for _ in range(n)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, prepared["target_xs"])
    table = multiplication_table(prepared["onb"])
    squares = square_destinations(prepared["onb"])
    s3_link_factored(formula, leaves[0], leaves[1], mid, table, squares)
    s3_link_factored(formula, mid, leaves[2], target, table, squares)
    if prepared["cell"] == "control":
        for bits, mask in zip(leaves, prepared["fixture"]["fixture"]["raw_leaf_x"][1:]):
            pin_bits(formula, bits, mask)
        pin_bits(formula, selector, prepared["control_choice"])
    return formula, leaves, mid, selector


def check_formula_model(formula, model):
    assert model is not None
    assert all(bit in model for bit in range(1, formula.variables + 1))
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)


def check_relation(prepared, formula, leaves, mid, selector, model):
    check_formula_model(formula, model)
    n = prepared["n"]
    onb, curve = prepared["onb"], prepared["curve"]
    instance = prepared["instance"]
    choice = decode_choice(selector, model)
    assert 0 <= choice < len(prepared["target_xs"])
    chosen_x = prepared["target_xs"][choice]
    raw_masks = [coordinates(bits, model) for bits in leaves]
    middle_mask = coordinates(mid, model)
    assert all(0 < mask < (1 << n) and
               mask.bit_count() <= instance["new_weight_bound"]
               for mask in raw_masks)
    assert evaluate_s3(onb, onb.fromCoords(raw_masks[0]),
                       onb.fromCoords(raw_masks[1]),
                       onb.fromCoords(middle_mask)) == 0
    assert evaluate_s3(onb, onb.fromCoords(middle_mask),
                       onb.fromCoords(raw_masks[2]),
                       onb.fromCoords(chosen_x)) == 0
    points = [curve.pointFromX(onb.fromCoords(mask)) for mask in raw_masks]
    if any(point is None for point in points):
        return {"status": "nonrational_raw_x", "raw_leaf_x": raw_masks}
    all_points = [prepared["anchor_point"], *points]
    projected = [curve.mul(point, instance["cofactor"]) for point in all_points]
    if any(point is None for point in projected):
        return {"status": "identity_projection", "raw_leaf_x": raw_masks}
    assert all(curve.mul(point, instance["subgroup_order"]) is None
               for point in projected)
    orbit = OrbitKey(onb)
    keys = [canonical_rotation(orbit.cycle_bits(point[0]), n)
            for point in projected]
    if len(set(keys)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": raw_masks}
    matching_cases = [case for case in prepared["cases"]
                      if case["adjusted_x"] == chosen_x]
    for case in matching_cases:
        adjusted = tuple(case["adjusted_target"])
        for signs in itertools.product((1, -1), repeat=3):
            triple = group_sum(curve, [signed(curve, point, sign)
                                       for point, sign in zip(points, signs)])
            if triple != adjusted:
                continue
            total = curve.add(signed(curve, prepared["anchor_point"],
                                     case["anchor_sign"]), triple)
            if curve.mul(total, instance["cofactor"]) == prepared["public"]:
                return {
                    "status": "verified_four_point_relation",
                    "raw_leaf_x": [prepared["anchor_mask"], *raw_masks],
                    "signs": [case["anchor_sign"], *signs],
                    "projected_columns": keys,
                    "projected_points": [point_record(point) for point in projected],
                    "target_choice": choice,
                    "target_x": chosen_x,
                    "distinct_columns": 4,
                    "public_target": point_record(prepared["public"]),
                }
    return {"status": "no_signed_public_sum", "raw_leaf_x": raw_masks,
            "target_choice": choice, "target_x": chosen_x}


def frozen_cell(prepared, cap):
    n, cell = prepared["n"], prepared["cell"]
    instance, base = prepared["instance"], prepared["base"]
    target_source = (Q1419 if cell == "control" else ORDINARY[n])
    workload = {
        "curve_id": instance["curve_id"],
        "subgroup_order_r": instance["subgroup_order"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "public_target": point_record(prepared["public"]),
        "target_source_sha256": sha(target_source),
        "raw_target_preimage_x_sha256": digest(
            prepared["parent"]["raw_preimage_x_coordinates"]),
        "input_law": ("archived planted witness; first leaf and other three "
                      "x coordinates pinned" if cell == "control" else
                      "one archived ordinary public target; independent "
                      "fixed-leaf seed; no witness pins"),
        "anchor_seed": SEEDS[n] if cell == "ordinary" else None,
        "anchor_raw_x": prepared["anchor_mask"],
        "cold_or_warm_target_count": 1,
        "cache_state": "cold",
    }
    config = {
        "curve_id": instance["curve_id"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "factor_base_actual_B": base["actual_usable_points_B_before_folding"],
        "m": 4, "solver": "fixed-leaf two-link factored S3 XCNF CryptoMiniSat5",
        "anchor_rule": ("archived witness first leaf" if cell == "control" else
                        "first usable exact-weight mask from fixed PRNG stream"),
        "anchor_raw_x": prepared["anchor_mask"],
        "leaf_weight_bound": instance["new_weight_bound"],
        "isogeny": "none",
    }
    config_sha = digest(config)
    stage_id = (f"PS1N{n}Ckb1fb{config['factor_base_actual_B']}"
                f"PDP4sath{config_sha[:12]}")
    return {
        "curve_id": instance["curve_id"],
        "factor_base_actual_B": config["factor_base_actual_B"],
        "folded_columns_K": base["signed_frobenius_columns_K"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "base_receipt_sha256": sha(prepared["base_path"]),
        "public_target": point_record(prepared["public"]),
        "anchor_seed": SEEDS[n] if cell == "ordinary" else None,
        "anchor_raw_x": prepared["anchor_mask"],
        "anchor_point": point_record(prepared["anchor_point"]),
        "anchor_selection_trials": prepared["anchor_trials"],
        "raw_target_preimage_count": len(prepared["parent"]["raw_preimage_x_coordinates"]),
        "adjustment_case_count": len(prepared["cases"]),
        "identity_adjustment_count": prepared["identity_adjustment_count"],
        "adjusted_target_x_count": len(prepared["target_xs"]),
        "adjustment_cases_sha256": digest(prepared["cases"]),
        "adjusted_target_x_sha256": digest(prepared["target_xs"]),
        "control_target_choice": prepared["control_choice"],
        "stage_config_id": stage_id,
        "stage_config_sha256": config_sha,
        "workload_id": digest(workload)[:12],
        "workload_record": workload,
        "stage_run_id": f"{stage_id}W{digest(workload)[:12]}R1",
        "input_law": workload["input_law"],
        "solver_wall_cap_seconds": cap["wall_seconds"],
        "solver_conflict_cap": cap["conflicts"],
    }


def check_protocol():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1439"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["solver_binary_sha256"] == sha(Path(shutil.which("cryptominisat5")))
    assert protocol["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for name, source_hash in protocol["dependency_sha256"].items():
        assert sha(ROOT / name) == source_hash
    for name, input_hash in protocol["input_sha256"].items():
        assert sha(ROOT / name) == input_hash
    return protocol


def freeze():
    assert not PROTOCOL.exists(), "refuse to overwrite frozen protocol"
    runtime = HERE / "sage_runtime_info.json"
    assert runtime.exists() and json.loads(runtime.read_text())["status"] == "verified"
    binary = Path(shutil.which("cryptominisat5"))
    caps = {"control": {"wall_seconds": 30, "conflicts": 200_000},
            "ordinary": {"wall_seconds": 60, "conflicts": 1_000_000}}
    cells = {}
    input_paths = [Q1438 / "solver_protocol.json", Q1419, *ORDINARY.values()]
    for n in (53, 83):
        instance = json.loads((Q1438 / "solver_protocol.json").read_text())[
            "instances"][str(n)]
        input_paths.append(Q1438 / f"n{n}_w{instance['new_weight_bound']}_base.json")
        profile = json.loads(Q1419.read_text())["profiles"][str(n)]
        for field_name in ("parent_receipt", "fixture_receipt"):
            input_paths.append(ROOT / profile[field_name]["path"])
        for cell in ("control", "ordinary"):
            prepared = prepare(n, cell)
            row = frozen_cell(prepared, caps[cell])
            formula, _, _, _ = build(prepared)
            row["formula_stats"] = stats(formula)
            cells[f"n{n}_{cell}"] = row
    protocol = {
        "kind": "q1439_frozen_fixed_leaf_three_sum_stage_protocol",
        "proposal_id": "Q1439", "candidate_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "solver_family": "cryptominisat5_native_xor",
        "method": "one fixed usable raw leaf plus two factored S3 links",
        "solution_preservation": "For every signed four-raw-leaf decomposition of Q with the fixed anchor, its raw sum is among the enumerated cofactor preimages; subtracting its signed anchor gives one adjusted target. A three-leaf S3 chain contains its x coordinates. Identity adjustments are excluded and counted; none occur in this frozen panel if the count is zero.",
        "claim_boundary": "This is a bounded stage diagnostic, not a complete IC solve. A control witness is not natural yield. CPU wall times are exploratory without host isolation. Failed and timed-out attempts remain rows; complete N131 work and cost per useful row remain null unless measured.",
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {path: sha(ROOT / path) for path in DEPENDENCIES},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in sorted(set(input_paths))},
        "runtime_info_sha256": sha(runtime),
        "solver_binary_sha256": sha(binary),
        "run_order": ["n53_control", "n53_ordinary", "n83_control", "n83_ordinary"],
        "cells": cells,
    }
    assert all(row["identity_adjustment_count"] == 0 for row in cells.values())
    PROTOCOL.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "frozen", "proposal_id": "Q1439",
                      "cells": {key: {"anchor_raw_x": value["anchor_raw_x"],
                                       "adjusted_target_x_count": value["adjusted_target_x_count"],
                                       "formula_stats": value["formula_stats"]}
                                for key, value in cells.items()}}, sort_keys=True),
          flush=True)


def run(n, cell):
    protocol = check_protocol()
    key = f"n{n}_{cell}"
    assert key in protocol["run_order"]
    frozen = protocol["cells"][key]
    output = HERE / "runs" / key
    assert not output.exists(), "refuse to overwrite frozen run"
    build_started = time.perf_counter()
    prepared = prepare(n, cell)
    assert frozen_cell(prepared, {"wall_seconds": frozen["solver_wall_cap_seconds"],
                                  "conflicts": frozen["solver_conflict_cap"]}) == {
        name: value for name, value in frozen.items() if name != "formula_stats"}
    formula, leaves, mid, selector = build(prepared)
    assert stats(formula) == frozen["formula_stats"]
    build_seconds = time.perf_counter() - build_started
    output.mkdir(parents=True)
    formula_path = output / "system.xcnf"
    formula.write(formula_path)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = solve(formula_path, Path(shutil.which("cryptominisat5")),
                   frozen["solver_wall_cap_seconds"],
                   frozen["solver_conflict_cap"])
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    check_started = time.perf_counter()
    checked = check_error = None
    if result["model"] is not None:
        try:
            checked = check_relation(prepared, formula, leaves, mid, selector,
                                     result["model"])
        except Exception as error:
            check_error = repr(error)
    check_seconds = time.perf_counter() - check_started
    compressed, raw_bytes, raw_sha = archive(formula_path)
    verified = int(checked is not None and checked.get("status") ==
                   "verified_four_point_relation")
    receipt = {
        "kind": "q1439_fixed_leaf_compact_s3_stage_run",
        "proposal_id": "Q1439", "candidate_id": None,
        "curve_id": frozen["curve_id"], "isogeny": "none",
        "degree_n": n, "cell": cell,
        "factor_base_actual_B": frozen["factor_base_actual_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen[
            "factor_base_enumerated_set_sha256"],
        "stage_config_id": frozen["stage_config_id"],
        "workload_id": frozen["workload_id"],
        "stage_run_id": frozen["stage_run_id"],
        "public_target": frozen["public_target"],
        "input_law": frozen["input_law"],
        "anchor_raw_x": frozen["anchor_raw_x"],
        "adjustment_case_count": frozen["adjustment_case_count"],
        "adjusted_target_x_count": frozen["adjusted_target_x_count"],
        "formula": stats(formula),
        "formula_raw_bytes": raw_bytes,
        "formula_raw_sha256": raw_sha,
        "formula_archive_sha256": sha(compressed),
        "solver_status": result["status"],
        "solver_return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "solver_wall_seconds_exploratory": result["wall_seconds"],
        "target_preparation_and_formula_wall_seconds_exploratory": build_seconds,
        "relation_check_wall_seconds_exploratory": check_seconds,
        "charged_stage_wall_seconds_exploratory": build_seconds + result["wall_seconds"] + check_seconds,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "model_check": checked,
        "model_check_error": check_error,
        "verified_relation_count": verified,
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_solve_work_log2": None,
        "cpu_wall_speedup_claim": False,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                     sort_keys=True) + "\n")
    print(json.dumps({"key": key, "status": result["status"],
                      "verified_relation_count": verified,
                      "model_check_error": check_error,
                      "wall_seconds": result["wall_seconds"]}, sort_keys=True),
          flush=True)


def verify(emit):
    protocol = check_protocol()
    rows = []
    for key in protocol["run_order"]:
        n = int(key[1:3])
        cell = key.split("_", 1)[1]
        frozen = protocol["cells"][key]
        output = HERE / "runs" / key
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["source_sha256"] == sha(Path(__file__))
        assert receipt["stage_run_id"] == frozen["stage_run_id"]
        assert receipt["formula_archive_sha256"] == sha(output / "system.xcnf.gz")
        assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
        prepared = prepare(n, cell)
        formula, leaves, mid, selector = build(prepared)
        assert stats(formula) == frozen["formula_stats"]
        temp = HERE / f".verify_{key}.xcnf"
        assert not temp.exists()
        try:
            formula.write(temp)
            assert temp.read_bytes() == gzip.decompress(
                (output / "system.xcnf.gz").read_bytes())
            assert sha(temp) == receipt["formula_raw_sha256"]
        finally:
            temp.unlink(missing_ok=True)
        stdout = (output / "solver.stdout.txt").read_text()
        from run_probe import parse_model
        model = parse_model(stdout)
        if model is not None:
            checked = check_relation(prepared, formula, leaves, mid, selector,
                                     model)
            assert checked == receipt["model_check"]
            assert receipt["model_check_error"] is None
        else:
            assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == int(
            receipt["model_check"] is not None and
            receipt["model_check"]["status"] == "verified_four_point_relation")
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["cost_per_useful_row"] is None
        assert receipt["complete_solve_work_log2"] is None
        rows.append({"key": key, "solver_status": receipt["solver_status"],
                     "verified_relation_count": receipt["verified_relation_count"],
                     "receipt_sha256": sha(receipt_path)})
    result = {"kind": "q1439_fixed_leaf_archive_replay",
              "status": "passed", "proposal_id": "Q1439",
              "candidate_id": None, "isogeny": "none", "rows": rows,
              "protocol_sha256": sha(PROTOCOL),
              "source_sha256": sha(Path(__file__)),
              "scope": "rebuilds every XCNF and replays any returned four-point model through group arithmetic; no ordinary yield or complete cost inferred from censored rows"}
    if emit:
        path = HERE / "verification.json"
        assert not path.exists(), "refuse to overwrite verification"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    run_parser.add_argument("--cell", choices=("control", "ordinary"), required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze()
    elif args.command == "run":
        run(args.degree, args.cell)
    else:
        verify(args.emit)


if __name__ == "__main__":
    main()
