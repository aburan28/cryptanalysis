#!/usr/bin/env python3
"""Exact union-bound work frontier for six same-rotation d13 pair blocks."""

import hashlib
import json
from decimal import Decimal, localcontext
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decimal_ratio(numerator, denominator):
    with localcontext() as context:
        context.prec = 45
        return format(Decimal(numerator) / Decimal(denominator), ".12g")


def ceil_div(numerator, denominator):
    return (numerator + denominator - 1) // denominator


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError("preserve first exact bound receipt")
    protocol = json.loads((HERE / "protocol.json").read_text())
    for name, source in protocol["source_paths"].items():
        if digest(Path(source)) != protocol["source_sha256"][name]:
            raise ValueError("frozen source changed: " + name)
    geometry = json.loads(Path(protocol["source_paths"]["d13_geometry"]).read_text())
    manifest = json.loads(Path(protocol["source_paths"]["d13_candidate_manifest"]).read_text())
    pair = json.loads(Path(protocol["source_paths"]["d13_pair_inverse_result"]).read_text())
    census = json.loads(Path(protocol["source_paths"]["n41_exact_census"]).read_text())
    n41 = json.loads(Path(protocol["source_paths"]["n41_public_row"]).read_text())
    sage = json.loads(Path(protocol["source_paths"]["n41_public_row_sage_audit"]).read_text())
    r = int(protocol["n131_subgroup_order"])
    valid = protocol["valid_seed_codes_per_unrotated_domain"]
    assert manifest["candidate_record"]["curve"]["subgroup_order"] == r
    assert geometry["factor_base"]["distinct_nonidentity_signed_subgroup_options_per_position"] == valid
    assert pair["valid_selector_count"] == valid
    assert pair["unordered_distinct_pair_descriptors"] == comb(valid, 2)
    assert pair["rotation_schedule"] == protocol["leaf_rotations"]
    assert sage["status"] == "PASS" and n41["status"] == "VERIFIED_RAW_ROW"
    assert census["status"] == "COMPLETE_CENSUS" and census["first_row"] == n41["row"]
    assert census["first_valid_index"] == n41["residuals"] == 513088
    assert census["target"] == n41["target"]
    assert census["distinct_completion_points"] == 1956**2
    m = 4 * comb(valid, 2)
    intervals = []
    for free in range(1, protocol["pair_blocks"] + 1):
        support_upper = m**free
        lower_prefixes = ceil_div(r - 1, 2 * support_upper)
        intervals.append({
            "fixed_pair_blocks": protocol["pair_blocks"] - free,
            "free_pair_blocks": free,
            "one_prefix_completion_support_upper": str(support_upper),
            "one_prefix_uniform_hit_probability_upper":
                decimal_ratio(min(support_upper, r - 1), r - 1),
            "prefixes_necessary_for_50_percent_union_bound": str(lower_prefixes),
            "necessary_average_full_probes_per_second_exact": {
                "numerator": str(lower_prefixes),
                "denominator": protocol["online_cap_seconds"],
            },
            "necessary_average_full_probes_per_second_decimal":
                decimal_ratio(lower_prefixes, protocol["online_cap_seconds"]),
            "maximum_seconds_per_complete_probe_if_all_600s_used":
                decimal_ratio(protocol["online_cap_seconds"], lower_prefixes),
        })
    n41_support = census["distinct_completion_points"]
    n41_r = census["subgroup_order"]
    report = {
        "kind": "n131_d13_six_pair_target_independent_prefix_frontier",
        "status": "EXACT_CONDITIONAL_BOUND",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "target_law": protocol["target_law"],
        "pair_group_output_states_upper": m,
        "pair_state_derivation": "4*C(4134,2)",
        "pair_blocks": protocol["pair_blocks"],
        "subgroup_order": str(r),
        "online_cap_seconds": protocol["online_cap_seconds"],
        "rows": intervals,
        "n41_control": {
            "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
            "same_public_target": True,
            "last_two_pair_completion_support_exact": n41_support,
            "uniform_nonidentity_completion_probability_exact":
                decimal_ratio(n41_support, n41_r - 1),
            "first_exact_completion_prefix": census["first_hit_index"],
            "first_eight_column_row_prefix": census["first_valid_index"],
            "independent_sage_row_audit": sage["status"],
        },
        "source_sha256": {"protocol": digest(HERE / "protocol.json"),
                          "bound": digest(Path(__file__)),
                          "n41_census": digest(Path(protocol["source_paths"]["n41_exact_census"])),
                          "n131_pair": digest(Path(protocol["source_paths"]["d13_pair_inverse_result"]))},
        "claim_boundary": "Union bound for a uniform nonidentity target independent of a predeclared prefix schedule. It does not constrain a fixed published Q, target-adaptive prefix choice, or symbolic joint elimination. N41 census is a separate exact fixed-point control, not an N131 success estimate.",
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print("EXACT_CONDITIONAL_BOUND")


if __name__ == "__main__":
    main()
