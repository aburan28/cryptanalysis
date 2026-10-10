"""Order-balanced comparative benchmarks for isogenous curve candidates."""

from __future__ import annotations

import math
import statistics
from typing import Any

from .registry import Candidate
from .rho import _benchmark_candidate_once


_T_975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _critical_value(sample_count: int) -> float:
    """Return the two-sided 95% Student-t critical value."""
    if sample_count < 2:
        return 0.0
    return _T_975.get(sample_count - 1, 1.96)


def execution_order(candidate_count: int, trial: int) -> list[int]:
    """Rotate candidates so a full block visits every timing position once."""
    if candidate_count < 1:
        raise ValueError("candidate_count must be positive")
    if trial < 0:
        raise ValueError("trial must be non-negative")
    block, offset = divmod(trial, candidate_count)
    order = list(range(candidate_count))
    if block % 2:
        order.reverse()
    return order[offset:] + order[:offset]


def _mean_ci(values: list[float]) -> tuple[float, float, float, float]:
    mean = statistics.fmean(values)
    if len(values) == 1:
        return mean, 0.0, mean, mean
    standard_deviation = statistics.stdev(values)
    half_width = (
        _critical_value(len(values)) * standard_deviation / math.sqrt(len(values))
    )
    return mean, standard_deviation, mean - half_width, mean + half_width


def _summarize(
    candidate: Candidate, measurements: list[dict[str, Any]]
) -> dict[str, Any]:
    rates = [row["iterations_per_second"] for row in measurements]
    mean_rate, standard_deviation, low, high = _mean_ci(rates)
    result = dict(measurements[0])
    result.update(
        {
            "elapsed_seconds": sum(row["elapsed_seconds"] for row in measurements),
            "iterations": sum(row["iterations"] for row in measurements),
            "iterations_per_second": mean_rate,
            "rate_trials": rates,
            "rate_standard_deviation": standard_deviation,
            "rate_95_percent_ci": [max(0.0, low), high],
            "rate_ci_method": "two-sided Student-t interval",
            "trials": len(measurements),
            "projected_generic_seconds_log2": result[
                "expected_generic_steps_log2"
            ]
            - math.log2(mean_rate),
            "cost_accounting": {
                "discovery_and_reusable_precomputation": candidate.cost_accounting.get(
                    "discovery_and_reusable_precomputation",
                    {"status": "not measured"},
                ),
                "per_instance_mapping": candidate.cost_accounting.get(
                    "per_instance_mapping",
                    {
                        "status": "not measured",
                        "required_source_points": 2 if candidate.path else 0,
                    },
                ),
                "per_instance_ecdlp": {
                    "iteration_rate_measured": True,
                    "generic_step_count_log2": result["expected_generic_steps_log2"],
                },
            },
            "limitations": [
                "reference Python implementation, not a production-optimized attack",
                "host CPU isolation and frequency stability must be verified separately",
                "does not use the negation-map quotient",
                "does not include parallel distinguished-point coordination",
                "an end-to-end speedup is not claimed until mapping cost is measured",
            ],
        }
    )
    return result


def benchmark_candidates_interleaved(
    candidates: list[Candidate],
    *,
    seconds: float,
    table_size: int = 16,
    batch_width: int = 64,
    trials: int = 7,
    seed: int = 20261005,
    warmup_seconds: float = 0.1,
) -> dict[str, Any]:
    """Benchmark candidates in rotating order and compare paired trial rates."""
    if not candidates:
        raise ValueError("at least one candidate is required")
    if trials < 1:
        raise ValueError("trials must be positive")
    if warmup_seconds < 0:
        raise ValueError("warmup_seconds must be non-negative")

    if warmup_seconds:
        for index, candidate in enumerate(candidates):
            _benchmark_candidate_once(
                candidate,
                seconds=warmup_seconds,
                table_size=table_size,
                batch_width=batch_width,
                seed=seed - 104729 - index,
            )

    measurements: list[list[dict[str, Any]]] = [[] for _ in candidates]
    orders: list[list[str]] = []
    for trial in range(trials):
        order = execution_order(len(candidates), trial)
        orders.append([candidates[index].candidate_id for index in order])
        for index in order:
            measurements[index].append(
                _benchmark_candidate_once(
                    candidates[index],
                    seconds=seconds,
                    table_size=table_size,
                    batch_width=batch_width,
                    seed=seed + trial * 65537,
                )
            )

    results = [
        _summarize(candidate, rows)
        for candidate, rows in zip(candidates, measurements)
    ]
    baseline = next(
        (row for row in results if row["candidate_id"] == "p256-root"), results[0]
    )
    baseline_rates = baseline["rate_trials"]
    baseline_rate = baseline["iterations_per_second"]
    for row in results:
        log2_ratios = [
            math.log2(candidate_rate / reference_rate)
            for candidate_rate, reference_rate in zip(
                row["rate_trials"], baseline_rates
            )
        ]
        mean_bits, _, low_bits, high_bits = _mean_ci(log2_ratios)
        row["relative_iteration_speed"] = row["iterations_per_second"] / baseline_rate
        row["constant_factor_security_delta_bits"] = math.log2(
            row["relative_iteration_speed"]
        )
        row["paired_log2_speedup_trials"] = log2_ratios
        row["paired_log2_speedup_mean"] = mean_bits
        row["paired_log2_speedup_95_percent_ci"] = [low_bits, high_bits]
        row["paired_relative_iteration_speed"] = 2**mean_bits
        row["paired_relative_iteration_speed_95_percent_ci"] = [
            2**low_bits,
            2**high_bits,
        ]
        row["paired_speedup_significant_at_95_percent"] = low_bits > 0.0

    return {
        "schema_version": 1,
        "baseline_candidate_id": baseline["candidate_id"],
        "benchmark_design": {
            "candidate_order": "rotating Latin-square positions; reversed on alternate full blocks",
            "execution_order_by_trial": orders,
            "warmup_seconds_per_candidate": warmup_seconds,
            "comparison": "paired per-trial log2 iteration-rate ratio",
            "comparison_ci": "two-sided Student-t interval",
            "seed": seed,
        },
        "results": results,
    }
