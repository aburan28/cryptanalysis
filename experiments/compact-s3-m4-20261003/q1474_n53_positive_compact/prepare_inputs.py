#!/usr/bin/env python3
"""Materialize the Q1469 positive ordinary point as exact chained-S3 inputs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from cofactor_preimages import kernel_of_cofactor  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1438_dense_base.build_formula import encode_map  # noqa: E402
from q1467_density_bridge import build_inputs as q1467  # noqa: E402
from run_probe import curves, field  # noqa: E402

Q1468 = PARENT / "q1468_n53_pair_oracle"
Q1469 = PARENT / "q1469_n53_yield_panel"
OUTPUT = HERE / "inputs"
CASES = ("pinned_control", "selected_preimage", "full_coset")
PANEL_INDEX = 1
KERNEL_SEED = 14740053


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def workload_id(value: dict) -> str:
    return sha_bytes(canonical(value))[:12]


def context() -> dict:
    panel = json.loads((Q1469 / "panel.json").read_text())
    prior = json.loads((Q1469 / "runs" /
                        f"{PANEL_INDEX:03d}/receipt.json").read_text())
    row = panel["targets"][PANEL_INDEX]
    assert row["index"] == PANEL_INDEX
    assert prior["status"] == "found"
    assert prior["public_target"] == row["public_target"]
    assert prior["independent_check"]["status"] == (
        "verified_four_point_relation")
    witness_indices = prior["native_report"]["witness_indices"]
    assert witness_indices == [784, 1851, 349, 2038]
    assert prior["factor_base_actual_B"] == 2756
    assert prior["folded_columns_K"] == 26
    assert prior["factor_base_enumerated_set_sha256"] == (
        "cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70")
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    public = tuple(row["public_target"])
    assert curve.onCurve(public)
    r, h = panel["subgroup_order"], 428
    assert math.gcd(r, h) == 1
    assert curve.mul(public, r) is None
    selected = q1467.base(53)
    assert selected["B"] == 2756 and selected["K"] == 26
    assert selected["digest"] == prior[
        "factor_base_enumerated_set_sha256"]
    point_to_raw = {}
    for mask in selected["allowed"]:
        raw = curve.pointFromX(onb.fromCoords(mask))
        assert raw is not None
        projected = curve.mul(raw, h)
        assert projected is not None
        for p, q in ((projected, raw),
                     (curve.neg(projected), curve.neg(raw))):
            assert p not in point_to_raw
            point_to_raw[p] = q
    assert len(point_to_raw) == 2756
    base_lines = (Q1468 / "inputs/base_points.txt").read_text().splitlines()
    assert base_lines[0] == "Q1468BASE1 53 2756 26"
    base_points = []
    base_columns = []
    for line in base_lines[1:]:
        column, x, y = line.split()
        base_columns.append(int(column))
        base_points.append((onb.fromCoords(int(x, 16)),
                            onb.fromCoords(int(y, 16))))
    assert len(base_points) == 2756
    assert len({base_columns[index] for index in witness_indices}) == 4
    raw_leaves = [point_to_raw[base_points[index]]
                  for index in witness_indices]
    raw_masks = [int(onb.toCoords(point[0])) for point in raw_leaves]
    assert all(mask in selected["allowed"] for mask in raw_masks)
    raw_sum = None
    for point in raw_leaves:
        raw_sum = curve.add(raw_sum, point)
    assert raw_sum is not None and curve.mul(raw_sum, h) == public
    kernel, generators, trials = kernel_of_cofactor(
        curve, onb, r, h, KERNEL_SEED)
    raw_base = curve.mul(public, pow(h, -1, r))
    assert raw_base is not None and curve.mul(raw_base, h) == public
    raw_points = {curve.add(raw_base, torsion) for torsion in kernel}
    assert len(raw_points) == h and None not in raw_points
    assert raw_sum in raw_points
    ordered = sorted(raw_points, key=lambda point: (
        onb.toCoords(point[0]), onb.toCoords(point[1])))
    raw_xs = [int(onb.toCoords(point[0])) for point in ordered]
    assert len(raw_xs) == len(set(raw_xs)) == h
    selected_x = int(onb.toCoords(raw_sum[0]))
    witness_preimage_index = raw_xs.index(selected_x)
    packed = b"".join(x.to_bytes(7, "little") for x in raw_xs)
    return {
        "panel": panel, "prior": prior,
        "public": public,
        "raw_xs": raw_xs,
        "raw_masks": raw_masks,
        "selected_x": selected_x,
        "witness_preimage_index": witness_preimage_index,
        "raw_x_sha256": sha_bytes(packed),
        "witness_indices": witness_indices,
        "kernel_generator_points": [list(point) for point in generators],
        "kernel_generation_trials": trials,
    }


def render() -> tuple[dict, dict[str, dict[str, bytes]]]:
    ctx = context()
    panel = ctx["panel"]
    public = list(ctx["public"])
    metadata = {
        "kind": "q1474_n53_known_representable_ordinary_inputs",
        "proposal_id": "Q1474", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "curve_id": panel["curve_id"], "degree_n": 53,
        "subgroup_order": panel["subgroup_order"], "cofactor": 428,
        "factor_base_actual_B": 2756, "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": ctx["prior"][
            "factor_base_enumerated_set_sha256"],
        "public_target": public,
        "input_law": panel["input_law"],
        "target_generation_seed": panel["seed"],
        "q1469_panel_index": PANEL_INDEX,
        "matched_q1469_workload_id": panel["targets"][PANEL_INDEX][
            "workload_id"],
        "matched_q1469_witness_indices": ctx["witness_indices"],
        "raw_witness_leaf_x_masks_onb_hex": [format(x, "x")
                                                 for x in ctx["raw_masks"]],
        "raw_witness_target_x_onb_hex": format(ctx["selected_x"], "x"),
        "raw_witness_preimage_index_in_full_coset": ctx[
            "witness_preimage_index"],
        "full_raw_preimage_count": len(ctx["raw_xs"]),
        "full_raw_preimage_x_sha256": ctx["raw_x_sha256"],
        "kernel_seed": KERNEL_SEED,
        "kernel_generation_trials": ctx["kernel_generation_trials"],
        "kernel_generator_points": ctx["kernel_generator_points"],
        "cases": {},
    }
    outputs = {}
    old_ordinary = q1467.ordinary
    try:
        for name in CASES:
            targets = (ctx["raw_xs"] if name == "full_coset"
                       else [ctx["selected_x"]])
            workload = {
                "curve_id": panel["curve_id"],
                "subgroup_order": panel["subgroup_order"],
                "public_target": public,
                "input_law": panel["input_law"],
                "target_generation_seed": panel["seed"],
                "panel_index": PANEL_INDEX,
                "raw_target_x_onb_hex": [format(x, "x") for x in targets],
                "target_count": 1,
                "cache_state": "cold_compact_s3",
                "control_pins": name == "pinned_control",
            }
            q1467.ordinary = lambda n, values=targets, wid=workload_id(
                workload): (values, public, wid)
            cnf, varmap, target_bytes, meta, variables, clauses, formula = (
                q1467.make_case("n53_ordinary"))
            if name == "pinned_control":
                for bits, mask in zip(meta["leaf_variables"],
                                      ctx["raw_masks"]):
                    pin_bits(formula, bits, mask)
                variables, clauses = convert_to_cnf(formula)
                cnf = serialize_cnf(variables, clauses)
            meta.update({
                "proposal_id": "Q1474", "case": name,
                "input_role": "ordinary_known_representable_control",
                "leaves_pinned": name == "pinned_control",
                "matched_q1469_workload_id": metadata[
                    "matched_q1469_workload_id"],
                "raw_witness_preimage_index_in_full_coset": ctx[
                    "witness_preimage_index"],
            })
            varmap = encode_map(meta)
            assert meta["workload_id"] == workload_id(workload)
            assert meta["public_target"] == public
            assert meta["factor_base_actual_B"] == 2756
            assert meta["folded_columns_K"] == 26
            assert target_bytes == q1467.encode_targets(53, targets)
            files = {
                "system.cnf.gz": gzip.compress(cnf, mtime=0),
                "variables.txt": varmap,
                "targets.txt": target_bytes,
                "meta.json": (json.dumps(meta, sort_keys=True,
                                         indent=2) + "\n").encode(),
            }
            metadata["cases"][name] = {
                "workload_id": workload_id(workload),
                "workload_record": workload,
                "target_preimage_x_count": len(targets),
                "leaves_pinned": name == "pinned_control",
                "cnf_variables": variables,
                "cnf_clauses": len(clauses),
                "cnf_sha256": sha_bytes(cnf),
                "input_sha256": {leaf: sha_bytes(payload)
                                 for leaf, payload in files.items()},
            }
            outputs[name] = files
    finally:
        q1467.ordinary = old_ordinary
    return metadata, outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    metadata, outputs = render()
    meta_path = HERE / "input_manifest.json"
    if args.check:
        assert metadata == json.loads(meta_path.read_text())
        for name, files in outputs.items():
            assert all((OUTPUT / name / leaf).read_bytes() == payload
                       for leaf, payload in files.items())
    else:
        assert not meta_path.exists() and not OUTPUT.exists()
        meta_path.write_text(json.dumps(metadata, sort_keys=True,
                                        indent=2) + "\n")
        OUTPUT.mkdir()
        for name, files in outputs.items():
            (OUTPUT / name).mkdir()
            for leaf, payload in files.items():
                (OUTPUT / name / leaf).write_bytes(payload)
    print(json.dumps({"status": "pass", "cases": list(CASES),
                      "witness_preimage_index": metadata[
                          "raw_witness_preimage_index_in_full_coset"],
                      "full_preimages": metadata[
                          "full_raw_preimage_count"]}), flush=True)


if __name__ == "__main__":
    main()
