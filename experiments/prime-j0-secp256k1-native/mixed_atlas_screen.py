#!/usr/bin/env python3
"""Design-data screen for a union of the three width-four tau digit atlases."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import HERE, digit_table
from atlas_portfolio import SEEDS, baseline_scan, norm


TAIL_HORIZON = 16
UNION_PREPARATION = 107


def make_options(tables, union):
    options = {}
    for ra in range(9):
        for rb in range(9):
            residue = (ra, rb)
            if ra % 3 == 0:
                options[residue] = [(None, None)]
                continue
            if not union:
                options[residue] = [tables[2][residue]]
                continue
            choices = {}
            original = tables[0][residue][0]
            for table in tables:
                coefficient, slot = table[residue]
                seed = slot if coefficient == original else 9 + slot - 5
                assert 0 <= seed < 12
                choices[coefficient] = (coefficient, seed)
            options[residue] = list(choices.values())
    assert sum(len(x) == 2 for x in options.values()) == (18 if union else 0)
    return options


def best_cost(states, options, preparation):
    # State: carry, last nonzero position, highest digit's seed, cache mask.
    # The partial cost charges each previous highest digit when a new one
    # appears. This leaves the final highest digit uncharged, as in the
    # native evaluator's first insertion. Zero runs determine paired tau
    # stride savings when the next nonzero digit closes the run.
    current = {((0, 0), -1, -1, 0): 0}
    peak_states = 1
    for position in range(len(states) + TAIL_HORIZON):
        (ra, rb), old = states[position] if position < len(states) else ((0, 0), None)
        da, db = (0, 0) if old is None else old[0]
        following = {}
        for (carry, last, high, mask), cost in current.items():
            residue = ((ra + carry[0]) % 9, (rb + carry[1]) % 9)
            for coefficient, seed in options[residue]:
                ea, eb = (0, 0) if coefficient is None else coefficient
                x = da + carry[0] - ea
                y = db + carry[1] - eb
                assert x % 3 == 0
                next_carry = (x + y, -x // 3)
                assert norm(next_carry) <= 896
                if coefficient is None:
                    next_last, next_high, next_mask, extra = last, high, mask, 0
                elif last < 0:
                    next_last, next_high, next_mask = position, seed, mask
                    extra = 6 * position - 2 * (position // 2)
                else:
                    gap = position - last - 1
                    cache = 2 if high > 0 and not mask & (1 << high) else 0
                    next_last, next_high = position, seed
                    next_mask = mask | ((1 << high) if high > 0 else 0)
                    extra = (6 * (position - last) - 2 * ((gap + 1) // 2)
                             + (11 if high == 0 else 14) + cache)
                key = (next_carry, next_last, next_high, next_mask)
                value = cost + extra
                if value < following.get(key, 10**9):
                    following[key] = value
        current = following
        peak_states = max(peak_states, len(current))
    best = min((cost for (carry, _, _, _), cost in current.items()
                if carry == (0, 0)), default=None)
    assert best is not None
    return preparation + best, peak_states


def main():
    fixture_path = HERE / "fixture.json"
    portfolio_path = HERE / "portfolio-result.json"
    fixture = json.loads(fixture_path.read_bytes())
    portfolio = json.loads(portfolio_path.read_bytes())
    tables = [digit_table(seeds) for seeds in SEEDS]
    union_options = make_options(tables, True)
    linked_options = make_options(tables, False)
    design_rows = portfolio["panels"][0]["rows"]
    assert len(fixture["cases"]) == len(design_rows) == 64
    rows = []
    for case, reference in zip(fixture["cases"], design_rows):
        assert case["index"] == reference["index"]
        short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        states = baseline_scan(short, tables[0])
        linked, _ = best_cost(states, linked_options, 75)
        assert linked == reference["costs"][2]
        union, peak = best_cost(states, union_options, UNION_PREPARATION)
        rows.append({"index": case["index"], "linked_M_plus_S": linked,
                     "portfolio_M_plus_S": reference["selected_cost"],
                     "union_M_plus_S": union,
                     "union_minus_portfolio": union - reference["selected_cost"],
                     "peak_dp_states": peak})
    result = {
        "schema": 1,
        "scope": "exploratory_original_design_panel_only",
        "tail_horizon": TAIL_HORIZON,
        "union_preparation_M_plus_S": UNION_PREPARATION,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "portfolio_result_sha256": hashlib.sha256(portfolio_path.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dependency_sha256": hashlib.sha256((HERE / "atlas_portfolio.py").read_bytes()).hexdigest(),
        "linked_control_total": sum(row["linked_M_plus_S"] for row in rows),
        "portfolio_total": sum(row["portfolio_M_plus_S"] for row in rows),
        "union_total": sum(row["union_M_plus_S"] for row in rows),
        "union_wins": sum(row["union_minus_portfolio"] < 0 for row in rows),
        "union_ties": sum(row["union_minus_portfolio"] == 0 for row in rows),
        "max_dp_states": max(row["peak_dp_states"] for row in rows),
        "rows": rows,
        "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    assert result["linked_control_total"] == 88089
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
