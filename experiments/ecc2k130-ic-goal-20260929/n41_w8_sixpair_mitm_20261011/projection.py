"""Exact tuple-count and memory lower-bound projection to N131 W18."""

import hashlib
import json
from fractions import Fraction
from math import factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_fixed_seed_ninepair_cubic_20261011/support_result.json"


def main():
    source = json.loads(SUPPORT.read_text())
    rows = {}
    for row in source["rows"]:
        order = int(row["subgroup_order"])
        coeff = list(map(int, row["matching_coefficients_k0_to_k9"]))
        states = 4 * int(row["valid_unordered_pairs"])
        rows[row["label"]] = {
            "signed_states_per_slot": states,
            "distinct_column_ordered_triplets": str(coeff[3] * factorial(3) * 4**3),
            "six_pair_raw_group_mean_ceiling":
                str(Fraction(coeff[6] * factorial(6) * 4**6, 4 * order)),
            "six_pair_raw_group_mean_ceiling_decimal":
                format(float(Fraction(coeff[6] * factorial(6) * 4**6,
                                      4 * order)), ".9g"),
            "eight_pair_raw_group_mean_ceiling_decimal":
                format(float(Fraction(coeff[8] * factorial(8) * 4**8,
                                      4 * order)), ".9g"),
            "explicit_three_sum_key_bytes_at_16_bytes_each":
                str(coeff[3] * factorial(3) * 4**3 * 16),
        }
    result = {"status": "PASS_EXACT_SOURCE_BOUND_MITM_PROJECTION",
              "scope": "explicit three-sum storage, before hash and witness overhead",
              "source_sha256": hashlib.sha256(SUPPORT.read_bytes()).hexdigest(),
              "rows": rows}
    with (HERE / "projection_result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    for label, row in rows.items():
        print(label, row["distinct_column_ordered_triplets"],
              row["six_pair_raw_group_mean_ceiling_decimal"])


if __name__ == "__main__":
    main()
