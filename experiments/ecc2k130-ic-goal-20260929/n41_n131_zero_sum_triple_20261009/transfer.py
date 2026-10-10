#!/usr/bin/env python3
"""Exact descriptor-table work screen for the four-block N131 transfer."""

from decimal import Decimal, getcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = HERE / "transfer_result.json"
    if out.exists():
        raise FileExistsError(out)
    geometry = json.loads((HERE / "geometry_result.json").read_text())
    audit = json.loads((HERE / "audit.json").read_text())
    public = json.loads((HERE / "public/result.json").read_text())
    assert geometry["n131"]["unordered_zero_sum_triples"] == 1439333092
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_AUDIT"
    assert public["status"] == "VERIFIED_RAW_ROW"
    r = int(geometry["n131"]["subgroup_order"])
    shapes = int(geometry["n131"]["unordered_zero_sum_triples"])
    v = int(geometry["n131"]["valid_masks"])
    k = int(geometry["n131"]["existing_folded_columns_K"])
    m = 8 * shapes
    # At most v-k excess masks can share columns. One bad mask pair
    # determines at most one zero-sum triple (its third mask is their XOR).
    max_col_multiplicity = v - k + 1
    bad_shapes_upper = max_col_multiplicity * (max_col_multiplicity - 1) // 2
    admissible_states_lower = 8 * (shapes - bad_shapes_upper)
    # A mask occurs in at most (v-1)/2 unordered zero-sum triple shapes.
    # For one three-column left state, bound all right states colliding in
    # any column by a union over those three columns.
    col_incidence_upper = 8 * ((v - 1) // 2) * max_col_multiplicity
    left_entries_lower = admissible_states_lower * max(
        0, admissible_states_lower - 3 * col_incidence_upper)
    table_entries = m*m
    # A serialized key distinguishing r group values needs at least 130 bits.
    minimum_key_bytes = (r.bit_length() + 7) // 8
    literal_payload = table_entries * minimum_key_bytes
    literal_payload_lower = left_entries_lower * minimum_key_bytes
    cap = 4 * 1024**3
    max_keys = cap // minimum_key_bytes
    uniform_bound = Fraction(max_keys * table_entries, r - 1)
    getcontext().prec = 50
    predicted = Decimal(m)**4 / Decimal(r)
    bound_decimal = Decimal(uniform_bound.numerator) / Decimal(uniform_bound.denominator)
    result = {
        "status": "EXACT_TRANSFER_SCREEN", "candidate_id": None,
        "proposal_id": "Q20261009195000", "target_count": 1,
        "n131_triple_shape_count": geometry["n131"]["unordered_zero_sum_triples"],
        "valid_masks": v,
        "folded_columns": k,
        "max_column_multiplicity_from_count": max_col_multiplicity,
        "bad_triple_shapes_upper": bad_shapes_upper,
        "admissible_signed_states_per_block_lower": admissible_states_lower,
        "per_column_signed_state_incidence_upper": col_incidence_upper,
        "cross_distinct_two_block_descriptor_entries_lower": left_entries_lower,
        "signed_states_per_block_upper": m,
        "four_block_uniform_support_ratio_prediction": format(predicted, "f"),
        "literal_two_block_descriptor_entries": table_entries,
        "minimum_group_key_bytes": minimum_key_bytes,
        "literal_key_payload_bytes": literal_payload,
        "literal_cross_distinct_key_payload_bytes_lower": literal_payload_lower,
        "peak_rss_limit_bytes": cap,
        "max_keys_at_key_floor": max_keys,
        "uniform_target_max_keys_full_right_probability_bound_numerator": uniform_bound.numerator,
        "uniform_target_max_keys_full_right_probability_bound_denominator": uniform_bound.denominator,
        "uniform_target_max_keys_full_right_probability_bound_decimal": format(bound_decimal, "f"),
        "scope": "literal table storing every cross-column-admissible two-block descriptor; separately, uniform target independent of selected table keys. Output deduplication or target-conditioned symbolic elimination is outside this table bound",
        "sha256": {"source": sha(__file__),
                   "geometry": sha(HERE / "geometry_result.json"),
                   "audit": sha(HERE / "audit.json"),
                   "public": sha(HERE / "public/result.json"),
                   "protocol": sha(HERE / "protocol.json")},
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "signed_states": m,
                      "literal_entries": table_entries,
                      "cross_distinct_entries_lower": left_entries_lower,
                      "literal_key_payload_lower": literal_payload_lower,
                      "literal_key_payload_bytes": literal_payload,
                      "uniform_probability_bound": result["uniform_target_max_keys_full_right_probability_bound_decimal"]}))


if __name__ == "__main__":
    main()
