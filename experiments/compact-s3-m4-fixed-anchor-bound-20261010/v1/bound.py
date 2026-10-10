#!/usr/bin/env python3
"""Exact uniform-subgroup fixed-anchor rank-work arithmetic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
PARENT = ROOT / "experiments/compact-s3-m4-rational-root-scan-20261010"
PROPOSAL = "Q20261010123500"
BASE_PATHS = {
    "N53_W3": OLD / "bases/n53_weight3_orbits.json.gz",
    "N83_W5": OLD / "bases/n83_weight5_full_orbits.json",
    "N131_W5": OLD / "runs/n131_q1413_projected_x_w5.json",
    "N131_W6": OLD / "runs/n131_q1413_projected_x_w6.json",
}
H_VALUES = (1, 2, 8)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def load_profile(label: str, path: Path) -> dict:
    data = read(path)
    if label.startswith("N131"):
        design = read(OLD / "protocol.json")["degree_131_design"]
        curve = design["curve"]
        n = data["field_degree_n"]
        b = data["actual_usable_points_B_before_folding"]
        k = data["signed_frobenius_columns_K"]
        r = curve["subgroup_order"]
        digest = data["enumerated_set_sha256"]
        curve_id = data["curve_id"]
        weight = data["normal_basis_weight_bound"]
        assert curve_id == curve["curve_id"]
    else:
        curve = data["curve"]
        base = data["factor_base"]
        n = data["field"]["n"]
        b = base["actual_usable_points_B_before_folding"]
        k = base["signed_frobenius_columns"]
        r = curve["subgroup_order"]
        digest = base["enumerated_set_sha256"]
        curve_id = curve["curve_id"]
        weight = base["normal_basis_weight_bound"]
        assert base["geometric_point_count_before_projection"] == b
    assert n in (53, 83, 131) and b > 0 and k > 0 and r > 2
    assert b == 2 * n * k
    assert len(digest) == 64
    return {"label": label, "field_degree_n": n,
            "normal_basis_weight_bound": weight,
            "curve_id": curve_id, "base_receipt_sha256": sha(path),
            "enumerated_set_sha256": digest,
            "actual_usable_points_B": b, "folded_columns_K": k,
            "rational_raw_x_masks_D": b // 2,
            "subgroup_order_r": r, "isogeny": "none"}


def check_freeze() -> dict:
    frozen = read(HERE / "freeze.json")
    assert frozen["proposal_id"] == PROPOSAL
    for name in ("bound.py", "audit.py", "PROTOCOL.md"):
        assert frozen["source_sha256"][name] == sha(HERE / name)
    for label, path in BASE_PATHS.items():
        assert frozen["base_receipt_sha256"][label] == sha(path)
    assert frozen["n131_protocol_sha256"] == sha(OLD / "protocol.json")
    assert frozen["n83_kernel_receipt_sha256"] == sha(
        PARENT / "runs/n83_control_w4096.scan.json")
    return frozen


def build() -> dict:
    frozen = check_freeze()
    measured = read(PARENT / "runs/n83_control_w4096.scan.json")
    mul = measured["operation_counts"]["scan"]["field_mul_calls"]
    roots = measured["operation_counts"]["scan"]["s3_root_calls"]
    assert measured["proposal_id"] == "Q20261010120000"
    assert measured["status"] == "WEIGHT_PAIR_FOUND"
    assert mul > roots > 0
    profiles = []
    for label, path in BASE_PATHS.items():
        profile = load_profile(label, path)
        b = profile["actual_usable_points_B"]
        k = profile["folded_columns_K"]
        d = profile["rational_raw_x_masks_D"]
        r = profile["subgroup_order_r"]
        pair_count = b * (b + 1) // 2
        profile["right_unordered_pairs_including_repeats"] = str(pair_count)
        profile["fanout_rows"] = []
        for h in H_VALUES:
            scans = ceil_div(19 * k * (r - 1), 20 * h * pair_count)
            visits = scans * d
            source_muls = ceil_div(visits * mul, roots)
            profile["fanout_rows"].append({
                "maximum_fixed_left_sums_per_scan_h": h,
                "necessary_complete_scans_for_95pct_rank": str(scans),
                "necessary_complete_scans_log2": math.log2(scans),
                "necessary_rational_root_visits": str(visits),
                "necessary_rational_root_visits_log2": math.log2(visits),
                "source_rate_field_mul_extrapolation": str(source_muls),
                "source_rate_field_mul_extrapolation_log2": math.log2(source_muls),
            })
        profiles.append(profile)
    return {
        "schema": "q20261010123500-fixed-anchor-bound-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "status": "PASS_ARITHMETIC_ONLY",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "profiles": profiles,
        "measured_n83_kernel_field_mul_numerator": mul,
        "measured_n83_kernel_root_denominator": roots,
        "workload_law": "one uniform nonidentity subgroup target; complete target-independent left schedule; at most h signed left sums per scan",
        "proof": "For a fixed signed left sum and each of M unordered right-point pairs, exactly one subgroup target can yield that representation. A uniform nonidentity target hits with probability at most 1/(r-1). Linearity bounds expected representations by S*h*M/(r-1); rank is no larger; Markov gives S >= ceil(0.95*K*(r-1)/(h*M)).",
        "scope": "Necessary scan and root-visit work for this fixed-anchor collector only. The fixed published target and target-adaptive left generators are outside the uniform-target theorem.",
        "is_measured_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_cold_work_log2": None,
        "complete_online_one_target_work_log2": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    out = HERE / "result.json"
    content = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert out.read_text() == content
        print("PASS: fixed-anchor exact bound")
    else:
        assert not out.exists()
        out.write_text(content)
        print(json.dumps({"status": "PASS", "profiles": len(BASE_PATHS)}))


if __name__ == "__main__":
    main()
