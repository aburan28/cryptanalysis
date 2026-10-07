#!/usr/bin/env python3
"""Recompute the adaptive-mask diagnostic and portfolio screen from artifacts."""

import json
from pathlib import Path
import random
import statistics

import hybrid_subset as hybrid


HERE = Path(__file__).resolve().parent


def short_pair(row):
    return int(row["short_a_hex"], 16), int(row["short_b_hex"], 16)


def main():
    fresh = json.loads((HERE / "adaptive-mask-result.json").read_text())
    earlier = json.loads((HERE / "hybrid-holdout-result.json").read_text())
    assert fresh["verified"] and earlier["verified"]
    assert len(fresh["rows"]) == len(earlier["rows"]) == 64
    old_costs = []
    for row in earlier["rows"]:
        a, b = short_pair(row)
        old_costs.append([
            hybrid.model(hybrid.recode(a, b, mask))[
                "m_plus_s_excluding_inversion"]
            for mask in range(64)
        ])
    portfolio = [63]
    best = [costs[63] for costs in old_costs]
    portfolios = {}
    for size in range(2, 9):
        next_mask = min(
            (mask for mask in range(63) if mask not in portfolio),
            key=lambda mask: (
                sum(min(best[index], costs[mask])
                    for index, costs in enumerate(old_costs)), mask),
        )
        portfolio.append(next_mask)
        best = [min(best[index], costs[next_mask])
                for index, costs in enumerate(old_costs)]
        portfolios[size] = tuple(portfolio)

    savings = []
    unique_state_positions = 0
    recoded_positions = 0
    for row in fresh["rows"]:
        a0, b0 = short_pair(row)
        costs = row["mask_costs_m_plus_s"]
        assert len(costs) == 64
        selected_mask = min(range(64), key=lambda mask: (costs[mask], mask))
        assert selected_mask == row["selected_mask"]
        assert costs[selected_mask] == row["arms"]["selected"]["model"][
            "m_plus_s_excluding_inversion"]
        assert costs[63] == row["arms"]["width4"]["model"][
            "m_plus_s_excluding_inversion"]
        savings.append(costs[63] - costs[selected_mask])
        states = set()
        for mask in range(64):
            a, b = a0, b0
            digits = hybrid.recode(a, b, mask)
            assert costs[mask] == hybrid.model(digits)[
                "m_plus_s_excluding_inversion"]
            recoded_positions += len(digits)
            for position, digit in enumerate(digits):
                states.add((position, a, b))
                if digit is not None:
                    a -= digit[0]
                    b -= digit[1]
                a, b = a + b, -a // 3
            assert (a, b) == (0, 0)
        unique_state_positions += len(states)
    assert recoded_positions == fresh["all_recode_positions"]
    width4_total = fresh["totals"]["width4"][
        "m_plus_s_excluding_inversion"]
    selected_total = fresh["totals"]["selected"][
        "m_plus_s_excluding_inversion"]
    assert sum(savings) == width4_total - selected_total
    rng = random.Random(0x20261007)
    means = sorted(sum(rng.choices(savings, k=64)) / 64
                   for _ in range(10_000))
    portfolio_rows = {}
    for size in (2, 3, 4, 8):
        masks = portfolios[size]
        total = sum(row["mask_costs_m_plus_s"][63] - min(
            row["mask_costs_m_plus_s"][mask] for mask in masks)
            for row in fresh["rows"])
        portfolio_rows[size] = {"masks": masks, "fresh_total_saving": total,
                                "fresh_mean_saving": total / 64}
    print(json.dumps({
        "cases": 64, "width4_total": width4_total,
        "selected_total": selected_total,
        "total_saving": sum(savings),
        "mean_saving": statistics.mean(savings),
        "median_saving": statistics.median(savings),
        "saving_range": [min(savings), max(savings)],
        "positive_savings": sum(value > 0 for value in savings),
        "bootstrap_mean_95": [means[250], means[9749]],
        "all_recode_positions": recoded_positions,
        "unique_state_positions": unique_state_positions,
        "portfolios": portfolio_rows,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
