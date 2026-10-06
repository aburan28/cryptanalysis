#!/usr/bin/env python3
"""Exact counting screen for N83 shifted pair-prefix and four-pair joins."""

from __future__ import annotations

from decimal import Decimal, getcontext
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n83-costed-candidate-screen-20261005"
LABELS = ("shifted_m7_d12", "shifted_m8_d11")
RAW_PAIR_RECORD_BYTES = 16
COMPRESSED_POINT_BYTES = 12
RSS_CAP_BYTES = 2 * 1024**3


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    getcontext().prec = 60
    rows = []
    for label in LABELS:
        geometry_path = PRIOR / "runs" / f"{label}_v1" / "geometry.json"
        geometry = json.loads(geometry_path.read_text())
        assert geometry["status"] == "EXACT_GEOMETRY_PASS"
        assert geometry["curve_id"] == "EC1N83Ckb1h2bcb59d56ad6"
        b = geometry["actual_usable_projected_points_B_per_slot"]
        m = geometry["arity"]
        r = int(geometry["subgroup_order"])
        assert m in (7, 8) and b > 0
        pair_count = b**2
        residual_tuples = b ** (m - 2)
        full_tuples = b**m
        residual_lambda = Decimal(residual_tuples) / Decimal(r)
        full_lambda = Decimal(full_tuples) / Decimal(r)
        assert abs(full_lambda - Decimal(str(geometry["ordered_tuples_per_subgroup_element"]))) \
            < Decimal("1e-34")
        row = {
            "label": label,
            "curve_id": geometry["curve_id"],
            "candidate_id": None,
            "geometry_sha256": sha(geometry_path),
            "arity": m,
            "actual_usable_factor_base_points_B_per_slot": b,
            "effective_signed_frobenius_columns_K":
                geometry["effective_signed_frobenius_columns_K"],
            "logical_distinct_slot_pair_entries": str(pair_count),
            "raw_one_pair_table_bytes_at_16_bytes_per_entry": str(pair_count * RAW_PAIR_RECORD_BYTES),
            "residual_summands_after_one_pair": m - 2,
            "residual_ordered_tuples": str(residual_tuples),
            "exact_average_residual_tuples_per_uniform_subgroup_target": str(residual_lambda),
            "uniform_residual_support_probability_upper_bound": str(min(Decimal(1), residual_lambda)),
            # Union bound over a target-independent ordered list of distinct
            # projected pair sums. Correlation can only make coverage smaller.
            "fixed_pair_prefixes_necessary_for_50pct_uniform_target_coverage":
                (r + 2 * residual_tuples - 1) // (2 * residual_tuples),
            "full_ordered_tuples": str(full_tuples),
            "exact_average_full_tuples_per_uniform_subgroup_target": str(full_lambda),
            "first_success_pair_probes_independent_occupancy_heuristic":
                str(Decimal(1) / residual_lambda),
            "full_four_factor_join_states": str(b**4),
            "full_four_factor_join_raw_point_bytes_at_12_bytes_per_state":
                str(b**4 * COMPRESSED_POINT_BYTES),
            "geometry_count_is_not_solver_yield": True,
            "fixed_prefix_bound_scope":
                "Any fixed target-independent list of pair prefixes on a uniform subgroup target; no independence assumption. Adaptive target-dependent prefix selection is outside this bound.",
        }
        if m == 8:
            # Four pair-sum lists have pair-of-pair size B^4. Under a uniform
            # t-bit filter, the expected surviving representations are
            # (B^8/r)/2^t. Choose the largest t preserving mean >= 1.
            filtering_bits = max(0, full_tuples.bit_length() - r.bit_length())
            while Decimal(full_tuples) / (Decimal(r) * (1 << filtering_bits)) < 1:
                filtering_bits -= 1
            while Decimal(full_tuples) / (Decimal(r) * (1 << (filtering_bits + 1))) >= 1:
                filtering_bits += 1
            survivors = Decimal(b**4) / Decimal(1 << filtering_bits)
            row["four_pair_uniform_filter_bits_for_mean_at_least_one"] = filtering_bits
            row["four_pair_expected_intermediate_states_after_filter"] = str(survivors)
            row["four_pair_expected_raw_point_bytes_after_filter"] = \
                str(survivors * COMPRESSED_POINT_BYTES)
            row["four_pair_expected_raw_point_bytes_over_2GiB_cap"] = \
                str(survivors * COMPRESSED_POINT_BYTES / Decimal(RSS_CAP_BYTES))
            row["four_pair_join_model"] = \
                "Uniform-hash balanced pair-of-pair filtering; counts are conditional expectations, not a lower bound on every algorithm."
        rows.append(row)
    output = {
        "schema_version": 1,
        "kind": "n83_shifted_pair_index_exact_counting_screen",
        "candidate_id": None,
        "source_sha256": sha(Path(__file__)),
        "rho_operation_scale_sqrt_r_floor": str(math.isqrt(int(
            json.loads((PRIOR / "runs/shifted_m8_d11_v1/geometry.json").read_text())
            ["subgroup_order"]))),
        "rho_measured_online_wall_ns": None,
        "ic_measured_online_wall_ns": None,
        "speedup": None,
        "rows": rows,
        "claim_boundary": "Exact tuple and storage counts plus explicitly labeled uniform-target and uniform-filter expectations. No pair table, residual solver, ordinary yield, matrix, target DLP, or paired rho has been measured here.",
    }
    (HERE / "pair_index_screen.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
