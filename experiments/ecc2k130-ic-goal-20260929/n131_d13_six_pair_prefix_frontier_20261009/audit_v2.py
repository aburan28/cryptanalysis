#!/usr/bin/env python3
"""Independent integer-arithmetic audit of the d13 six-pair frontier."""

import hashlib
import json
from fractions import Fraction
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve independent bound audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_BOUND_RUN"
    assert result["status"] == "EXACT_CONDITIONAL_BOUND"
    assert result["source_sha256"]["protocol"] == digest(HERE / "protocol.json")
    assert result["source_sha256"]["bound"] == digest(HERE / "bound.py")
    for name, path in protocol["source_paths"].items():
        assert protocol["source_sha256"][name] == digest(Path(path))
    valid = int(protocol["valid_seed_codes_per_unrotated_domain"])
    r = int(protocol["n131_subgroup_order"])
    m = 2 * valid * (valid - 1)
    assert m == result["pair_group_output_states_upper"] == 4 * comb(valid, 2)
    assert len(result["rows"]) == protocol["pair_blocks"] == 6
    for row in result["rows"]:
        free = row["free_pair_blocks"]
        assert row["fixed_pair_blocks"] + free == 6
        support = m**free
        assert int(row["one_prefix_completion_support_upper"]) == support
        fraction = Fraction(r - 1, 2 * support)
        necessary = -(-fraction.numerator // fraction.denominator)
        assert int(row["prefixes_necessary_for_50_percent_union_bound"]) == necessary
        assert int(row["whole_prefix_probes_per_second_necessary_within_600s"]) == -(-necessary // 600)
        assert Fraction(support, r - 1) > 0
    four_free = next(row for row in result["rows"] if row["free_pair_blocks"] == 4)
    assert int(four_free["prefixes_necessary_for_50_percent_union_bound"]) == 249560561
    assert int(four_free["whole_prefix_probes_per_second_necessary_within_600s"]) == 415935
    n41 = result["n41_control"]
    assert n41["last_two_pair_completion_support_exact"] == 3825936
    assert n41["first_exact_completion_prefix"] == 155013
    assert n41["first_eight_column_row_prefix"] == 513088
    report = {
        "kind": "n131_d13_six_pair_prefix_frontier_independent_audit",
        "status": "PASS_EXACT_ARITHMETIC_AND_SOURCE_HASHES",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "four_free_pair_prefixes_necessary_for_50_percent": 249560561,
        "four_free_pair_probes_per_second_necessary": 415935,
        "result_sha256": digest(HERE / "result.json"),
        "audit_source_sha256": digest(Path(__file__)),
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
