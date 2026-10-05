#!/usr/bin/env python3
"""Audit the six-phase exact-pair table and screen its operation-only value."""

import hashlib
import json
from pathlib import Path

from make_tau_pair_fused import ZERO, catalog, decode, omega


def exact_index(word, phase):
    if word == ZERO:
        return None
    orbit = word & 127
    power = (word >> 7) & 3
    negative = bool(word & 512)
    assert orbit < 121 and power < 3 and 0 <= phase < 6
    return 6 * orbit + 3 * (negative ^ bool(phase & 1)) + (power + phase) % 3


def coordinate_at_index(index, representatives):
    orbit, remainder = divmod(index, 6)
    negative, power = divmod(remainder, 3)
    a, b = representatives[orbit]
    for _ in range(power):
        a, b = omega(a, b)
    return (-a, -b) if negative else (a, b)


def audit():
    root = Path(__file__).resolve().parent
    representatives, _recipes, words, _even, _odd = catalog()
    assert len(words) == 727 and len(representatives) == 121
    seen = set()
    phase_checks = 0
    for point, word in words.items():
        if word == ZERO:
            assert point == (0, 0)
            continue
        assert decode(word, representatives) == point
        seen.add(exact_index(word, 0))
        for phase in range(6):
            a, b = point
            for _ in range(phase):
                a, b = omega(a, b)
            if phase & 1:
                a, b = -a, -b
            assert coordinate_at_index(exact_index(word, phase), representatives) == (a, b)
            phase_checks += 1
    assert seen == set(range(726)) and phase_checks == 4356

    prior_path = root / "tail-pair-fused-panel.json"
    prior = json.loads(prior_path.read_text())
    rows = []
    for row in prior["results"]:
        assert row["verified"]
        fused = row["runs"]["tail-pair-fused"]["operations"]
        earlier = row["weighted_scores"]["tail-double-residue"]
        new_score = 10 * fused["triples"] + 16 * fused["adds"]
        assert earlier > row["weighted_scores"]["tail-pair-fused"] > new_score
        rows.append({"id": row["id"], "prior_two_digit_score": earlier,
                     "orbit_pair_score": row["weighted_scores"]["tail-pair-fused"],
                     "exact_pair_score_predicted": new_score,
                     "removed_online_rotations": fused["rotations"]})
    result = {"schema": 1, "status": "design_data_counterfactual_only",
              "phase_checks": phase_checks, "distinct_exact_points": len(seen),
              "point_table_bytes": 726 * 32,
              "added_setup_rotations_model": 2 * len(representatives),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "prior_receipt_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
              "cases": rows}
    (root / "phase-complete-pair-screen.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "phase_checks": phase_checks,
                      "cases": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    audit()
