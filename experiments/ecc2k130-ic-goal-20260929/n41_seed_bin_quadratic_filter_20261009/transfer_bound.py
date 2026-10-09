#!/usr/bin/env python3
"""Exact source-bound N131 resource projection for the literal bin-filter design."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTIER = HERE / "../first_pair_generation_frontier.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "transfer_result.json"
    if output.exists():
        raise FileExistsError("preserve first literal N131 transfer projection")
    frozen = json.loads((HERE / "transfer_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"transfer input changed: {name}")
    if (sha(FRONTIER) != frozen["frontier_sha256"] or
            sha(Path(__file__)) != frozen["producer_sha256"]):
        raise ValueError("source or N131 frontier changed")
    frontier = json.loads(FRONTIER.read_text())["n131"]
    if (frontier["curve_id"] != frozen["curve_id"] or
            frontier["usable_points_per_window_B"] != 262614 or
            frontier["distinct_column_pair_states_lower"] != 34448654064):
        raise ValueError("N131 W18 source geometry changed")
    seed_bits = 18
    bins = (2**seed_bits - 1)**2
    coordinate_bits = 130
    feature_count = 1 + coordinate_bits + coordinate_bits * (coordinate_bits - 1) // 2
    words_per_equation = (feature_count + 63) // 64
    equations_per_bin = 16
    bytes_per_bin = 4 + equations_per_bin * words_per_equation * 8
    table_bytes = bins * bytes_per_bin
    cap_bytes = frozen["limits"]["rss_bytes"]
    pair_states = frontier["distinct_column_pair_states_lower"]
    pair_min_bytes_at_one_bit = (pair_states + 7) // 8
    pair_product = pair_states * pair_states
    result = {
        "status": "FAIL_LITERAL_N131_W18_MEMORY_AND_WORK_GATE",
        "kind": "literal_n131_seed_bin_quadratic_filter_transfer",
        "curve_id": frozen["curve_id"],
        "candidate_id": None, "proposal_id": frozen["proposal_id"],
        "seed_bits": seed_bits, "literal_seed_bins": bins,
        "coordinate_bits_after_trace": coordinate_bits,
        "quadratic_features_per_bin": feature_count,
        "words_per_equation": words_per_equation,
        "equations_per_bin": equations_per_bin,
        "literal_bytes_per_bin": bytes_per_bin,
        "literal_filter_table_bytes": table_bytes,
        "literal_filter_table_gib_rounded_up": (table_bytes + (1 << 30) - 1) // (1 << 30),
        "compression_factor_needed_to_fit_4gib_rounded_up":
            (table_bytes + cap_bytes - 1) // cap_bytes,
        "distinct_column_pair_states_per_domain_lower": pair_states,
        "one_bit_per_pair_state_domain_bytes_lower": pair_min_bytes_at_one_bit,
        "one_domain_one_bit_excess_over_cap_bytes_lower": pair_min_bytes_at_one_bit - cap_bytes,
        "four_domain_one_bit_bytes_lower": 4 * pair_min_bytes_at_one_bit,
        "literal_suffix_pair_pair_combinations_lower": pair_product,
        "literal_suffix_pair_pair_combinations_per_second_in_600s_lower_rounded_up":
            (pair_product + frozen["limits"]["wall_seconds"] - 1) //
            frozen["limits"]["wall_seconds"],
        "full_bin_scan_equation_evaluations_per_residual_upper_if_all_bins_have_16":
            bins * equations_per_bin,
        "memory_cap_bytes": cap_bytes,
        "wall_cap_seconds": frozen["limits"]["wall_seconds"],
        "source_boundary": "Applies to the literal fixed-size per-bin table, full pair-state materialization, and pair-pair enumeration implemented in the N41 design. A symbolic or target-guided successor needs its own bound.",
        "transfer_protocol_sha256": sha(HERE / "transfer_protocol.json"),
        "frontier_sha256": sha(FRONTIER),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "literal_filter_table_bytes": table_bytes,
                      "pair_state_domain_one_bit_bytes_lower": pair_min_bytes_at_one_bit}))


if __name__ == "__main__":
    main()
