#!/usr/bin/env python3
"""Regression check for the distinct endpoint and chain-root counts."""

import json
from pathlib import Path

import run_d10_m15_single_target as runner

HERE = Path(__file__).resolve().parent


def main():
    diagnostic = json.loads((HERE / "diagnose_target_formula_counts_20261009.json").read_text())
    expected = diagnostic["expected_official_q"]
    assert expected["roots"] == 4 * runner.pipeline.N
    for case in diagnostic["cases"].values():
        assert case["roots"] == (runner.LEAVES - 1) * runner.pipeline.N
        assert runner.validate_target_formula_counts(
            case["stats"], range(case["roots"]), range(4), expected)
        assert not runner.validate_target_formula_counts(
            case["stats"], range(expected["roots"]), range(4), expected)
        assert not runner.validate_target_formula_counts(
            case["stats"], range(case["roots"]), range(3), expected)
    print(json.dumps({"status": "PASS", "cases": list(diagnostic["cases"]),
                      "endpoint_coordinate_bits": expected["roots"],
                      "chain_equation_roots": case["roots"]}))


if __name__ == "__main__":
    main()
