#!/usr/bin/env python3
"""Retrospective source-cost screen of nearby equivalent scalar representatives."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS, norm
from mixed_atlas_screen import make_options
from mixed_radix_scalar import source_cost
from screen_radix_policy import recode as radix_recode
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"  # Already-inspected design data.
N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
LAMBDA_TAU = int("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0", 16)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = (-U[1], 303414439467246543595250775667605759171)
DET = U[0] * V[1] - U[1] * V[0]
assert DET == N
RADII = (1, 3, 5, 9, 13, 25)


def round_div(top, bottom):
    assert bottom > 0
    half = bottom // 2
    return -((-top + half) // bottom) if top < 0 else (top + half) // bottom


def candidates(scalar):
    center_u = round_div(scalar * V[1], DET)
    center_v = round_div(-scalar * U[1], DET)
    rows = []
    for du in range(-2, 3):
        for dv in range(-2, 3):
            u, v = center_u + du, center_v + dv
            a = scalar - u * U[0] - v * V[0]
            b = -u * U[1] - v * V[1]
            assert (a + b * LAMBDA_TAU - scalar) % N == 0
            rows.append((norm((a, b)), max(abs(a), abs(b)), a, b, du, dv))
    return sorted(rows)


def main():
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    assert len(fixture["cases"]) == 64
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    rows = []
    for case in fixture["cases"]:
        scalar = int(case["scalar_hex"], 16)
        choices = candidates(scalar)
        assert (choices[0][2], choices[0][3]) == (
            int(case["short_a_hex"], 16), int(case["short_b_hex"], 16))
        scored = []
        for rank, (n, _, a, b, du, dv) in enumerate(choices):
            actions, status = radix_recode((a, b), tables[0], "skip_zero_tau")
            assert status == "verified" and actions is not None
            radix = source_cost(actions)["total_M_plus_S"]
            _, selective = selective_recode((a, b), tables, options)
            score = min(radix, selective["total_M_plus_S"])
            scored.append({"norm_rank": rank, "norm": str(n), "du": du, "dv": dv,
                           "zero_tau_M_plus_S": radix,
                           "selective_M_plus_S": selective["total_M_plus_S"],
                           "selected_M_plus_S": score,
                           "selected_arm": "zero_tau" if radix < selective["total_M_plus_S"]
                           else "selective"})
        by_radius = {str(k): min(entry["selected_M_plus_S"] for entry in scored[:k])
                     for k in RADII}
        winner = min(scored, key=lambda entry: (entry["selected_M_plus_S"],
                                                entry["norm_rank"]))
        rows.append({"index": case["index"], "short_M_plus_S": scored[0]["selected_M_plus_S"],
                     "best_25_M_plus_S": winner["selected_M_plus_S"],
                     "saving_M_plus_S": (scored[0]["selected_M_plus_S"]
                                         - winner["selected_M_plus_S"]),
                     "winning_norm_rank": winner["norm_rank"],
                     "by_radius": by_radius, "choices": scored})
    assert sum(row["short_M_plus_S"] for row in rows) == 86405
    result = {"schema": 1, "scope": "retrospective_design_only",
              "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "cases": len(rows), "radii": RADII,
              "totals_by_radius": {str(k): sum(row["by_radius"][str(k)] for row in rows)
                                   for k in RADII},
              "wins": sum(row["saving_M_plus_S"] > 0 for row in rows),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_dependency_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                           for name in ("zero_tau_rule.py", "screen_radix_policy.py",
                                                        "selective_mixed_atlas.py", "alternate_digit_atlas.py")},
              "rows": rows, "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
