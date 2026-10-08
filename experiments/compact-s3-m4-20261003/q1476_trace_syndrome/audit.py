#!/usr/bin/env python3
"""Independently replay Q1476 models, parity cuts, and run custody."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
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
from q1476_trace_syndrome.prepare_inputs import (  # noqa: E402
    CASES, OUTPUT, render,
)
from q1476_trace_syndrome.freeze_protocol import (  # noqa: E402
    render as render_protocol,
)
from run_probe import curves, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "archive_audit.json"
BASELINES = {name: PARENT / "q1475_ordered_leaves" / "runs" / name /
             "receipt.json" for name in CASES}


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
    n = meta["degree_n"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    cofactor = 428 if n == 53 else 4
    subgroup_order = 21044858204113 if n == 53 else 2417851639230796216685689

    def value(bits: list[int]) -> int:
        return sum(1 << j for j, bit in enumerate(bits) if model[bit])

    masks = [value(bits) for bits in meta["leaf_variables"]]
    assert all(left < right for left, right in zip(masks, masks[1:]))
    assert all(0 < mask < 1 << n and
               mask.bit_count() <= meta["normal_basis_weight_bound"]
               for mask in masks)
    if n == 53:
        allowed = set(json.loads((PARENT /
            "q1467_density_bridge/n53_w3_26_orbits.json").read_text())[
                "allowed_raw_x_masks_onb_hex"])
        assert all(format(mask, "x") in allowed for mask in masks)
    if meta["leaves_pinned"]:
        assert masks == [int(x, 16) for x in meta[
            "sorted_pinned_raw_x_onb_hex"]]
    mids = [value(bits) for bits in meta["pair_mid_variables"]]
    selector = value(meta["target_selector_variables"])
    targets = [int(x, 16) for x in
               (folder / "targets.txt").read_text().splitlines()[1:]]
    assert 0 <= selector < len(targets)
    target_x = targets[selector]
    assert (masks[0].bit_count() ^ masks[1].bit_count() ^
            mids[0].bit_count()) & 1 == 0
    assert (masks[2].bit_count() ^ masks[3].bit_count() ^
            mids[1].bit_count()) & 1 == 0
    assert (mids[0].bit_count() ^ mids[1].bit_count() ^
            target_x.bit_count()) & 1 == 0
    for side in range(2):
        a = onb.fromCoords(masks[2 * side])
        b = onb.fromCoords(masks[2 * side + 1])
        roots = {int(onb.toCoords(x)) for x in s3_roots(onb, a, b)}
        assert mids[side] in roots
    final_roots = {int(onb.toCoords(x)) for x in s3_roots(
        onb, onb.fromCoords(mids[0]), onb.fromCoords(mids[1]))}
    assert target_x in final_roots
    raw_points, columns = [], []
    for mask in masks:
        raw_point = curve.pointFromX(onb.fromCoords(mask))
        if raw_point is None:
            return {"status": "nonrational_raw_x", "raw_leaf_x": masks}
        subgroup = curve.mul(raw_point, cofactor)
        if subgroup is None:
            return {"status": "identity_projection", "raw_leaf_x": masks}
        assert curve.mul(subgroup, subgroup_order) is None
        raw_points.append(raw_point)
        columns.append(canonical_rotation(orbit.cycle_bits(subgroup[0]), n))
    if len(set(columns)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": masks}
    public = tuple(meta["public_target"])
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(raw_points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if (total is not None and
                int(onb.toCoords(total[0])) == target_x and
                curve.mul(total, cofactor) == public):
            return {
                "status": "verified_four_point_relation",
                "raw_leaf_x": masks,
                "signs": list(signs),
                "target_preimage_index": selector,
                "raw_target_x_onb_hex": format(target_x, "x"),
                "projected_column_keys_onb_hex": [format(k, "x")
                                                       for k in columns],
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
    assert protocol["proposal_id"] == "Q1476"
    assert protocol["candidate_id"] is protocol["run_id"] is None
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
    rows = []
    for name, files in outputs.items():
        cell = manifest["cases"][name]
        for leaf, content in files.items():
            assert (OUTPUT / name / leaf).read_bytes() == content
            assert sha(OUTPUT / name / leaf) == protocol[
                "cases"][name]["input_sha256"][leaf]
        folder = HERE / "runs" / name
        receipt_path = folder / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1476"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["case"] == name
        assert receipt["stage_config_id"] == protocol[
            "cases"][name]["stage_config_id"]
        assert receipt["stage_run_id"] == protocol[
            "cases"][name]["stage_run_id"]
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"]["experiments/compact-s3-m4-20261003/"
                             "q1476_trace_syndrome/run_stage.py"]
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["solver_binary_sha256"] == protocol[
            "solver_binary_sha256"]
        assert receipt["solver_stdout_sha256"] == sha(
            folder / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            folder / "solver.stderr.txt")
        for key in ("curve_id", "degree_n", "factor_base_actual_B",
                    "folded_columns_K", "factor_base_enumerated_set_sha256",
                    "public_target", "workload_id", "leaves_pinned",
                    "cnf_sha256", "trace_syndrome"):
            assert receipt[key] == cell[key], (name, key)
        report = receipt["native_report"]
        if report is not None:
            assert receipt["native_report_error"] is None
            assert report == json.loads((folder / "solver.stdout.txt")
                                        .read_text())
            assert report["propagations"] >= 0
            assert report["pair_cap"] == protocol["pair_candidate_cap"]
            assert report["cnf_variables"] == cell["cnf_variables"]
            assert report["cnf_clauses"] == cell["cnf_clauses"]
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
            assert receipt["independent_model_check"] is None
            assert receipt["verified_relation_count"] == 0
        verified = int(relation is not None and relation["status"] ==
                       "verified_four_point_relation")
        assert verified == receipt["verified_relation_count"]
        baseline = None
        if name in BASELINES:
            prior_path = BASELINES[name]
            assert sha(prior_path) == protocol["cases"][name][
                "baseline_receipt_sha256"]
            prior = json.loads(prior_path.read_text())
            assert prior["public_target"] == cell["public_target"]
            assert prior["curve_id"] == cell["curve_id"]
            assert prior["factor_base_actual_B"] == cell[
                "factor_base_actual_B"]
            assert prior["folded_columns_K"] == cell["folded_columns_K"]
            assert prior["factor_base_enumerated_set_sha256"] == cell[
                "factor_base_enumerated_set_sha256"]
            assert prior["workload_id"] == cell["workload_id"]
            assert prior["native_report"]["pair_cap"] == protocol[
                "pair_candidate_cap"]
            baseline = {
                "receipt_sha256": sha(prior_path),
                "native_status": prior["native_status"],
                "sat_propagations": prior["native_report"]["propagations"],
                "field_calls": {k: prior["native_report"][
                    f"field_{k}_calls"] for k in ("mul", "sqr", "inv")},
            }
        rows.append({
            "case": name, "degree_n": cell["degree_n"],
            "input_role": cell["input_role"],
            "leaves_pinned": cell["leaves_pinned"],
            "workload_id": cell["workload_id"],
            "stage_config_id": receipt["stage_config_id"],
            "stage_run_id": receipt["stage_run_id"],
            "native_status": status,
            "stop_reason": report["stop_reason"] if report else None,
            "sat_propagations": report["propagations"] if report else None,
            "sat_conflicts": report["conflicts"] if report else None,
            "field_calls": ({k: report[f"field_{k}_calls"]
                             for k in ("mul", "sqr", "inv")}
                            if report else None),
            "joint_eligible_checks": (report["joint_eligible_checks"]
                                      if report else None),
            "joint_cap_skips": (report["joint_cap_skips"]
                                if report else None),
            "verified_relation_count": verified,
            "baseline": baseline,
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "receipt_sha256": sha(receipt_path),
        })
    controls_passed = all(row["native_status"] == "sat" and
                          row["verified_relation_count"] == 1
                          for row in rows[:2])
    return {
        "kind": "q1476_trace_syndrome_compact_stage_audit",
        "status": "passed" if controls_passed else "control_failed",
        "pinned_correctness_controls_passed": controls_passed,
        "proposal_id": "Q1476", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "stages": protocol["stages"],
        "rows": rows,
        "natural_relation_yield_estimate": None,
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
