#!/usr/bin/env python3
"""Post-run scale diagnostic for Q1486's fixed-left midpoint search.

The model assumes independent uniform x roots across the observed left and
right domains. SAT choices and the target-conditioned left domain need not
follow that law; the result is not a probability bound or solve estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
AUDIT = HERE / "archive_audit.json"
OUT = HERE / "coverage_diagnostic.json"
CASES = ("n53_ordinary", "n83_ordinary")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    audit = json.loads(AUDIT.read_text())
    assert protocol["proposal_id"] == audit["proposal_id"] == "Q1486"
    assert audit["status"] == "passed"
    assert audit["protocol_sha256"] == sha(PROTOCOL)
    rows = []
    by_case = {row["case"]: row for row in audit["rows"]}
    for case in CASES:
        receipt_path = HERE / "runs" / case / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        native = receipt["native_report"]
        audit_row = by_case[case]
        n = protocol["cases"][case]["degree_n"]
        assert n in (53, 83)
        assert audit_row["receipt_sha256"] == sha(receipt_path)
        assert audit_row["status"] == "censored"
        assert audit_row["verified_relation_count"] == 0
        assert native["domain_builds"] == 1
        assert native["coupled_left_builds"] == 0
        assert native["coupled_nonempty_intersections"] == 0
        left_max = native["domain_max_output_values"]
        right_pair_calls = native["coupled_right_pair_root_calls"]
        assert left_max > 0 and right_pair_calls > 0
        # A quadratic S3 link has at most two roots in F_(2^n).
        root_upper = 2 * right_pair_calls
        numerator = left_max * root_upper
        denominator = 1 << n
        rows.append({
            "case": case,
            "field_degree_n": n,
            "left_domain_builds": native["domain_builds"],
            "left_output_values_max": left_max,
            "right_domain_builds": native["coupled_right_builds"],
            "right_pair_root_calls": right_pair_calls,
            "right_root_count_upper": root_upper,
            "observed_supported_intersections": native[
                "coupled_nonempty_intersections"],
            "uniform_independent_x_expected_intersections_upper_fraction": {
                "numerator": numerator,
                "denominator": denominator,
            },
            "uniform_independent_x_expected_intersections_upper_log2": (
                math.log2(numerator) - n),
            "receipt_sha256": sha(receipt_path),
        })
    return {
        "kind": "q1486_postrun_fixed_left_coverage_diagnostic",
        "proposal_id": "Q1486",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "model_law": (
            "Each right S3 root is an independent uniform field x value "
            "relative to the fixed target-conditioned left output set. "
            "At most two roots arise per right pair. This is a scale "
            "diagnostic; SAT choices and algebraic correlations need not "
            "satisfy the assumed law."),
        "rows": rows,
        "is_probability_bound": False,
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "protocol_sha256": sha(PROTOCOL),
        "archive_audit_sha256": sha(AUDIT),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    serialized = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == serialized
        print("Q1486 post-run coverage diagnostic PASS (archived)")
    else:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(serialized)
        print("Q1486 post-run coverage diagnostic written")


if __name__ == "__main__":
    main()
