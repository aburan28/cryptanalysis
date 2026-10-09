#!/usr/bin/env python3
"""Posthoc source-bound fixed-prefix density bound for the N131 d13 policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PAIR = HERE / "d13_pair_source.json"
MANIFEST = HERE / "d13_manifest_source.json"
OUTPUT = HERE / "d13_fixed_prefix_bound.json"
ORIGINAL_PAIR = GOAL / "n131_d13_same_rotation_pairs_20261009/result.json"
ORIGINAL_MANIFEST = (GOAL / "n131_phi_torsion_frobenius_domains_20261005"
                     / "m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("preserve first posthoc d13 bound")
    if sha(PAIR) != sha(ORIGINAL_PAIR) or sha(MANIFEST) != sha(ORIGINAL_MANIFEST):
        raise ValueError("source snapshots differ from original records")
    pair = json.loads(PAIR.read_text())
    manifest = json.loads(MANIFEST.read_text())
    curve = manifest["candidate_record"]["curve"]
    if (pair["status"] != "PASS_EXACT_PAIR_INVERSE_CONTROLS" or
            pair["curve_id"] != curve["curve_id"] or
            pair["rotation_schedule"] != [0, 0, 22, 22, 44, 44, 66, 66,
                                          88, 88, 110, 110] or
            pair["valid_selector_count"] != 4134 or
            pair["unordered_distinct_pair_descriptors"] != 8542911):
        raise ValueError("source is not the fixed d13 six-pair policy")
    r = int(curve["subgroup_order"])
    unordered_codes = pair["unordered_distinct_pair_descriptors"]
    pair_output_upper = 4 * unordered_codes
    last_two_output_upper = pair_output_upper**2
    lower_prefixes = ((r - 1) + 2 * last_two_output_upper - 1) // (2 * last_two_output_upper)
    result = {
        "kind": "n131_d13_six_pair_four_fixed_two_free_uniform_target_bound",
        "status": "EXACT_UNION_BOUND_FROM_FROZEN_INPUTS",
        "curve_id": curve["curve_id"],
        "candidate_id": None,
        "run_id": None,
        "subgroup_order": str(r),
        "unordered_distinct_selector_pairs": unordered_codes,
        "sign_choices_per_selector_pair_upper": 4,
        "one_pair_group_output_descriptor_upper": pair_output_upper,
        "two_free_pair_output_assignment_upper": last_two_output_upper,
        "uniform_nonidentity_target_completion_probability_upper": {
            "numerator": last_two_output_upper,
            "denominator": r - 1,
        },
        "fixed_four_pair_prefixes_for_half_success_lower_by_union_bound": lower_prefixes,
        "required_fixed_prefix_probes_per_second_at_600s_lower": {
            "numerator": lower_prefixes,
            "denominator": 600,
        },
        "input_sha256": {"pair_result": sha(PAIR), "candidate_manifest": sha(MANIFEST),
                         "source": sha(Path(__file__))},
        "scope": "uniform target independent of fixed four-pair prefixes; target-adaptive generation and symbolic family elimination are outside this bound",
    }
    with OUTPUT.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "one_pair_upper": pair_output_upper,
                      "four_fixed_prefix_lower": lower_prefixes}, sort_keys=True))


if __name__ == "__main__":
    main()
