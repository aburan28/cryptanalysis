#!/usr/bin/env python3
"""Freeze one new ordinary N83 target and its exact compact four-S3 XCNF."""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q20261011_wdsat_shared_prefix"))
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from cofactor_preimages import kernel_of_cofactor  # noqa: E402
from run_probe import curves, field  # noqa: E402
from run_q1404_raw_preimage_w5 import preimage_coset  # noqa: E402
from prepare import transform  # noqa: E402

SEED = 14720083
KERNEL_SEED = 130083
BASE = PARENT / "bases/n83_weight5_full_orbits.json"
Q1463 = PARENT / "q20261011_wdsat_ordinary"
Q1467 = PARENT / "q20261011_wdsat_order"
Q1469 = PARENT / "q20261011_wdsat_prefix_search"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    target_path = HERE / "target.json"
    assert not target_path.exists()
    assert not (HERE / "original.xcnf.gz").exists()
    assert not (HERE / "width4.xcnf.gz").exists()
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    base = json.loads(BASE.read_text())
    assert base["field"]["n"] == 83
    curve_record = base["curve"]
    assert curve_record["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert curve_record["cofactor"] == 4
    fb = base["factor_base"]
    assert fb["actual_usable_points_B_before_folding"] == 30977592
    assert fb["signed_frobenius_columns"] == 186612
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(map(int, curve_record["generator"]))
    order = int(curve_record["subgroup_order"])
    assert curve.onCurve(generator) and curve.mul(generator, order) is None
    scalar = random.Random(SEED).randrange(1, order)
    public = curve.mul(generator, scalar)
    assert public is not None and curve.onCurve(public)
    assert curve.mul(public, order) is None
    archived = json.loads((PARENT / "runs/n83_q1408_ordinary.json").read_text())
    assert list(public) != archived["public_target"]
    began = time.perf_counter()
    kernel, kernel_generators, kernel_trials = kernel_of_cofactor(
        curve, onb, order, 4, KERNEL_SEED)
    raw_points, raw_xs = preimage_coset(onb, curve, order, public, kernel)
    preimage_seconds = time.perf_counter() - began
    assert len(raw_xs) == len(set(raw_xs)) == 4
    assert all(curve.mul(point, 4) == public for point in raw_points)
    formula_started = time.perf_counter()
    formula, leaves, mids, _, selectors = build_balanced(83, 5, raw_xs)
    original_path = HERE / "original.xcnf"
    assert not original_path.exists()
    formula.write(original_path)
    original = original_path.read_bytes()
    original_path.unlink()
    derived, _, stats = transform(original)
    formula_seconds = time.perf_counter() - formula_started
    q1467 = json.loads((Q1467 / "order_manifest.json").read_text())["cells"]["n83"]
    assert formula.variables == q1467["original_variables"]
    assert selectors == q1467["selector_priority"]
    assert [bit for pair in mids for bit in pair] == q1467["pair_mid_first_ids"]
    assert [leaves[leaf][bit] for bit in range(83) for leaf in range(4)] == q1467[
        "interleaved_leaves_priority"]
    from q20261011_wdsat_ordinary.prepare import sizes  # type: ignore  # noqa: E402
    dimensions = sizes(derived)
    assert dimensions["variables"] == stats["derived_variables"]
    build = json.loads((Q1469 / "build_receipt.json").read_text())
    caps = build["per_degree"]["n83"]["config"]
    assert dimensions["variables"] <= caps["MAX_ID"]
    assert dimensions["rows"] < caps["MAX_EQ"]
    assert dimensions["xor_rows"] < caps["MAX_XEQ"]
    assert dimensions["max_cnf_width"] < caps["MAX_EQ_SIZE"]
    assert dimensions["max_xor_width"] < caps["MAX_XEQ_SIZE"]
    assert dimensions["cnf_occurrences"] + dimensions["xor_occurrences"] < caps[
        "MAX_BUFFER_SIZE"]
    assert dimensions["cnf_implication_slots"] < caps["MAX_BUFFER_SIZE"]
    source_archive = gzip.compress(original, mtime=0)
    derived_archive = gzip.compress(derived, mtime=0)
    (HERE / "original.xcnf.gz").write_bytes(source_archive)
    (HERE / "width4.xcnf.gz").write_bytes(derived_archive)
    workload = {
        "curve_id": curve_record["curve_id"],
        "subgroup_order_r": order,
        "target_group": curve_record["target_group"],
        "target_count": 1,
        "target_generation": {"law": "uniform_nonzero_scalar",
                              "rng": "python_random_mt19937", "seed": SEED,
                              "interval": "1..r-1"},
        "public_target": list(public),
        "cofactor_preimage_policy": "all_four_exact",
        "cache_policy": "precomputed_base_new_target",
    }
    workload_id = canonical_hash(workload)[:12]
    output = {
        "proposal_id": "Q1472", "candidate_id": None, "run_id": None,
        "isogeny": "none", "curve_id": curve_record["curve_id"],
        "workload_id": workload_id, "workload_record": workload,
        "fixture_scalar": str(scalar),
        "public_target": list(public),
        "factor_base_actual_B": fb["actual_usable_points_B_before_folding"],
        "factor_base_folded_columns_K": fb["signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "raw_preimage_x_coordinates": raw_xs,
        "raw_preimage_points": [list(point) for point in raw_points],
        "kernel_generator_points": [list(point) for point in kernel_generators],
        "kernel_generation_trials": kernel_trials,
        "target_preimage_seconds_exploratory": preimage_seconds,
        "formula_build_seconds_exploratory": formula_seconds,
        "original_variables": formula.variables,
        "derived_variables": dimensions["variables"],
        "original_raw_sha256": hashlib.sha256(original).hexdigest(),
        "derived_raw_sha256": hashlib.sha256(derived).hexdigest(),
        "original_archive_sha256": hashlib.sha256(source_archive).hexdigest(),
        "derived_archive_sha256": hashlib.sha256(derived_archive).hexdigest(),
        "transform_stats": stats, "dimensions": dimensions,
        "base_receipt_sha256": sha(BASE),
        "runtime_info_sha256": sha(runtime_path),
        "q1467_order_manifest_sha256": sha(Q1467 / "order_manifest.json"),
        "q1469_build_receipt_sha256": sha(Q1469 / "build_receipt.json"),
        "balanced_source_sha256": sha(PARENT / "chain_s3_balanced_multitarget.py"),
        "cofactor_source_sha256": sha(PARENT / "cofactor_preimages.py"),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "transform_source_sha256": sha(PARENT / "q20261011_wdsat_shared_prefix/prepare.py"),
        "source_sha256": sha(Path(__file__)),
    }
    target_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"curve_id": output["curve_id"], "workload_id": workload_id,
                      "public_target": output["public_target"],
                      "original_vars": formula.variables,
                      "derived_vars": dimensions["variables"]}))


if __name__ == "__main__":
    main()
