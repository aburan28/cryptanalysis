#!/usr/bin/env python3
"""Replay Q1474 SAT models and verify the known ordinary point independently."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1420_root_theory"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, model_from_file,
)
from q1474_n53_positive_compact.prepare_inputs import (  # noqa: E402
    CASES, OUTPUT, context, render,
)
from q1474_n53_positive_compact.freeze_protocol import (  # noqa: E402
    render as render_protocol,
)
from run_probe import curves, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "archive_audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_model(name: str, model_path: Path) -> dict:
    folder = OUTPUT / name
    meta = json.loads((folder / "meta.json").read_text())
    raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
    header = next(line for line in raw.splitlines() if line.startswith(b"p cnf "))
    _, _, variables, clauses = header.split()
    variables, clauses = int(variables), int(clauses)
    model = model_from_file(model_path)
    check_cnf(raw, model, variables, clauses)
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)

    def value(bits: list[int]) -> int:
        return sum(1 << i for i, bit in enumerate(bits) if model[bit])

    masks = [value(bits) for bits in meta["leaf_variables"]]
    mids = [value(bits) for bits in meta["pair_mid_variables"]]
    selector = value(meta["target_selector_variables"])
    targets = [int(x, 16) for x in
               (folder / "targets.txt").read_text().splitlines()[1:]]
    assert 0 <= selector < len(targets)
    target_x = targets[selector]
    allowed = set(json.loads((PARENT /
        "q1467_density_bridge/n53_w3_26_orbits.json").read_text())[
            "allowed_raw_x_masks_onb_hex"])
    assert all(0 < mask < 1 << 53 and mask.bit_count() <= 3 and
               format(mask, "x") in allowed for mask in masks)
    for side in range(2):
        a = onb.fromCoords(masks[2 * side])
        b = onb.fromCoords(masks[2 * side + 1])
        roots = {int(onb.toCoords(x)) for x in s3_roots(onb, a, b)}
        assert mids[side] in roots
    final_roots = {int(onb.toCoords(x)) for x in s3_roots(
        onb, onb.fromCoords(mids[0]), onb.fromCoords(mids[1]))}
    assert target_x in final_roots
    raw_points, keys = [], []
    for mask in masks:
        raw_point = curve.pointFromX(onb.fromCoords(mask))
        if raw_point is None:
            return {"status": "nonrational_raw_x", "raw_leaf_x": masks}
        subgroup = curve.mul(raw_point, 428)
        if subgroup is None:
            return {"status": "identity_projection", "raw_leaf_x": masks}
        assert curve.mul(subgroup, 21044858204113) is None
        raw_points.append(raw_point)
        keys.append(canonical_rotation(orbit.cycle_bits(subgroup[0]), 53))
    if len(set(keys)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": masks}
    public = tuple(meta["public_target"])
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(raw_points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if (total is not None and
                int(onb.toCoords(total[0])) == target_x and
                curve.mul(total, 428) == public):
            return {
                "status": "verified_four_point_relation",
                "raw_leaf_x": masks,
                "signs": list(signs),
                "target_preimage_index": selector,
                "raw_target_x_onb_hex": format(target_x, "x"),
                "projected_column_keys_onb_hex": [format(k, "x")
                                                       for k in keys],
                "public_target": list(public),
            }
    return {"status": "x_only_model_not_public_relation",
            "raw_leaf_x": masks, "target_preimage_index": selector}


def describe() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol == render_protocol()
    manifest = json.loads((HERE / "input_manifest.json").read_text())
    regenerated, outputs = render()
    assert regenerated == manifest
    assert protocol["proposal_id"] == "Q1474"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["run_order"] == list(CASES)
    assert sha(HERE / "input_manifest.json") == protocol[
        "input_manifest_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(PARENT / "q1472_sat_work_meter/native_solver") == protocol[
        "solver_binary_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    for name, files in outputs.items():
        for leaf, content in files.items():
            assert (OUTPUT / name / leaf).read_bytes() == content
            assert sha(OUTPUT / name / leaf) == protocol[
                "cases"][name]["input_sha256"][leaf]
    q1469 = json.loads((PARENT /
        "q1469_n53_yield_panel/runs/001/receipt.json").read_text())
    assert sha(PARENT / "q1469_n53_yield_panel/runs/001/receipt.json") == (
        protocol["matched_pair_oracle_receipt_sha256"])
    assert q1469["status"] == "found"
    assert q1469["public_target"] == manifest["public_target"]
    rows = []
    for name in CASES:
        folder = HERE / "runs" / name
        receipt_path = folder / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1474"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["case"] == name
        assert receipt["stage_config_id"] == protocol[
            "stage_config_id"]
        assert receipt["stage_run_id"] == protocol[
            "cases"][name]["stage_run_id"]
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"]["experiments/compact-s3-m4-20261003/"
                             "q1474_n53_positive_compact/run_stage.py"]
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["solver_binary_sha256"] == protocol[
            "solver_binary_sha256"]
        assert receipt["solver_stdout_sha256"] == sha(
            folder / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            folder / "solver.stderr.txt")
        assert receipt["workload_id"] == protocol[
            "cases"][name]["workload_id"]
        assert receipt["public_target"] == manifest["public_target"]
        assert receipt["factor_base_actual_B"] == 2756
        assert receipt["folded_columns_K"] == 26
        assert receipt["factor_base_enumerated_set_sha256"] == manifest[
            "factor_base_enumerated_set_sha256"]
        report = receipt["native_report"]
        if report is not None:
            assert receipt["native_report_error"] is None
            assert report == json.loads((folder / "solver.stdout.txt")
                                        .read_text())
            assert report["propagations"] >= 0
            assert report["pair_cap"] == protocol["pair_candidate_cap"]
            assert report["cnf_variables"] == manifest["cases"][name][
                "cnf_variables"]
            assert report["cnf_clauses"] == manifest["cases"][name][
                "cnf_clauses"]
        status = receipt["native_status"]
        assert status in ("sat", "censored", "unsat", "error",
                          "external_timeout")
        if status in ("sat", "censored", "unsat"):
            assert report is not None
        relation = None
        if status == "sat":
            model_path = folder / "solver.model.txt"
            assert receipt["solver_model_sha256"] == sha(model_path)
            relation = verify_model(name, model_path)
            assert relation == receipt["independent_model_check"]
            assert receipt["independent_model_check_error"] is None
        else:
            assert receipt["solver_model_sha256"] is None
            assert receipt["independent_model_check"] is None
        verified = int(relation is not None and relation["status"] ==
                       "verified_four_point_relation")
        assert verified == receipt["verified_relation_count"]
        rows.append({
            "case": name,
            "target_preimage_x_count": manifest["cases"][name][
                "target_preimage_x_count"],
            "leaves_pinned": manifest["cases"][name]["leaves_pinned"],
            "workload_id": receipt["workload_id"],
            "native_status": status,
            "stop_reason": report["stop_reason"] if report else None,
            "sat_propagations": report["propagations"] if report else None,
            "sat_conflicts": report["conflicts"] if report else None,
            "field_calls": ({k: report[f"field_{k}_calls"]
                             for k in ("mul", "sqr", "inv")}
                            if report else None),
            "exact_joint_checks": (report["joint_eligible_checks"]
                                   if report else None),
            "verified_relation_count": verified,
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "receipt_sha256": sha(receipt_path),
        })
    control_passed = (rows[0]["native_status"] == "sat" and
                      rows[0]["verified_relation_count"] == 1)
    return {
        "kind": "q1474_n53_known_representable_ordinary_stage_audit",
        "status": "passed" if control_passed else "control_failed",
        "pinned_correctness_control_passed": control_passed,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "proposal_id": "Q1474",
        "stage_config_id": protocol["stage_config_id"],
        "point_decomposition_stage_code": "PDP4hybrid",
        "curve_id": manifest["curve_id"],
        "factor_base_actual_B": 2756,
        "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": manifest[
            "factor_base_enumerated_set_sha256"],
        "public_target": manifest["public_target"],
        "matched_q1469_workload_id": manifest[
            "matched_q1469_workload_id"],
        "matched_pair_oracle_query_field_calls": q1469[
            "native_report"]["query_field_calls"],
        "matched_pair_oracle_query_wall_ns_exploratory": q1469[
            "native_report"]["query_wall_ns"],
        "matched_pair_oracle_witness_indices": q1469[
            "native_report"]["witness_indices"],
        "raw_witness_preimage_index_in_full_coset": manifest[
            "raw_witness_preimage_index_in_full_coset"],
        "rows": rows,
        "natural_relation_yield_estimate": None,
        "successful_unpinned_cost": next(
            (row for row in rows[1:] if row["verified_relation_count"]), None),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "protocol_sha256": sha(PROTOCOL),
        "auditor_source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = describe()
    if args.emit:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, sort_keys=True, indent=2) +
                          "\n")
    else:
        assert result == json.loads(RESULT.read_text())
    print(json.dumps({"status": result["status"],
                      "rows": [(row["case"], row["native_status"],
                                row["verified_relation_count"])
                               for row in result["rows"]]}), flush=True)


if __name__ == "__main__":
    main()
