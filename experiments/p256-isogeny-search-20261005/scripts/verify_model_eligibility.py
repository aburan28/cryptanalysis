#!/usr/bin/env python3
"""Verify the frozen P-256 isogeny-class model eligibility certificate."""

from __future__ import annotations

import json
from pathlib import Path

from analyze_model_eligibility import build_report

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "results" / "model-eligibility-20261006" / "model-eligibility.json"


def main() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    replay = build_report()
    assert frozen == replay
    invariants = frozen["isogeny_class_invariants"]
    assert invariants["group_order_prime"]
    assert invariants["group_order_mod_2"] == 1
    assert invariants["group_order_mod_3"] == 1
    assert not invariants["anomalous"]
    assert not invariants["embedding_degree_at_most_1000"]
    obligations = frozen["model_obligations"]
    assert all(item["status"] == "refuted" for item in obligations.values())
    normalization = frozen["short_weierstrass_a_normalization"]
    assert normalization["p_mod_4"] == 3
    assert normalization["fourth_power_image_equals_square_subgroup"]
    certificate = normalization["p256_certificate"]
    assert certificate["target_a"] == "1"
    assert certificate["u_fourth_equals_a_over_target_a"]
    assert certificate["transported_generator_on_target"]
    schedule = frozen["native_benchmark_schedule"]
    assert schedule["complete_addition_full_a_multiplications"] == 3
    assert schedule["complete_addition_full_3b_multiplications"] == 2
    assert schedule["doubling_full_a_multiplications"] == 3
    assert schedule["doubling_full_3b_multiplications"] == 2
    assert schedule["timed_batch_calls_complete_addition"]
    assert not schedule["timed_batch_calls_doubling"]
    assert not schedule["candidate_dependent_formula_branch"]
    assert not frozen["assessment"]["dramatic_speedup_found"]
    print(json.dumps({"status": "verified", "artifact": str(FROZEN.relative_to(ROOT))}, sort_keys=True))


if __name__ == "__main__":
    main()
