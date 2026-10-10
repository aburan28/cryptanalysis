#!/usr/bin/env python3
"""Verify the frozen full-registry normalized-coefficient audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit_retained_coefficients import build_report

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "coefficient-cost-audit-20261007"
FROZEN = RESULTS / "audit.json"
RECEIPT = ROOT / "receipt-coefficient-cost-audit-20261007.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    frozen = load(FROZEN)
    assert frozen == build_report()
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    coverage = frozen["coverage"]
    assert coverage == {
        "records_reconstructed": 2226,
        "retained_curves_including_p256": 2226,
        "source_registries": 14,
        "unique_candidate_ids": 2226,
    }
    results = frozen["results"]
    assert results["eligible_candidates"] == 0
    assert results["eligible_candidate_ids"] == []
    assert results["all_normalizations_verified"]
    assert results["minimum_bit_length_row"]["normalized_3b_absolute_bit_length"] == 243
    assert results["minimum_bit_length_row"]["signed_addition_chain_operation_lower_bound"] == 242
    assert results["minimum_binary_upper_bound_row"]["binary_double_and_add_operation_upper_bound"] == 352
    assert results["minimum_popcount"] == 100
    assert results["p256_root"]["normalized_a"] == 1
    assert results["p256_root"]["normalized_3b_absolute_bit_length"] == 251
    assert len(frozen["candidate_metrics"]) == 2226
    assert receipt["decision"] == "No coefficient-specialized candidate advances to native timing."
    print(json.dumps({
        "status": "verified",
        "curves": 2226,
        "minimum_lower_bound": 242,
        "minimum_binary_upper_bound": 352,
        "eligible_candidates": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
