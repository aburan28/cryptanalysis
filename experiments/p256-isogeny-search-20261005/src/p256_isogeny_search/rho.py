"""Reference r-adding Pollard-rho walk and benchmark utilities.

The walk is intended for comparative research and collision validation.  It is
not a record-setting implementation and it is not constant-time.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any

from .ec import JacobianPoint, ShortWeierstrassCurve
from .registry import Candidate


@dataclass(slots=True)
class WalkState:
    point: JacobianPoint
    alpha: int
    beta: int


class RAddingWalk:
    def __init__(
        self,
        curve: ShortWeierstrassCurve,
        order: int,
        generator: JacobianPoint,
        target: JacobianPoint,
        *,
        table_size: int = 16,
        seed: int = 1,
    ) -> None:
        if table_size < 4:
            raise ValueError("table_size must be at least four")
        self.curve = curve
        self.order = order
        self.generator = generator
        self.target = target
        self.table_size = table_size
        rng = random.Random(seed)
        table: list[tuple[JacobianPoint, int, int]] = []
        while len(table) < table_size:
            alpha = rng.randrange(order)
            beta = rng.randrange(order)
            increment = curve.add(
                curve.scalar_mul(alpha, generator), curve.scalar_mul(beta, target)
            )
            if not increment.is_infinity:
                table.append((curve.normalize(increment), alpha, beta))
        self.table = tuple(table)

    def initial_state(self, seed: int) -> WalkState:
        rng = random.Random(seed)
        alpha = rng.randrange(self.order)
        beta = rng.randrange(self.order)
        point = self.curve.add(
            self.curve.scalar_mul(alpha, self.generator),
            self.curve.scalar_mul(beta, self.target),
        )
        return WalkState(self.curve.normalize(point), alpha, beta)

    def advance_projective(self, state: WalkState) -> None:
        # The caller keeps the state normalized before this operation. The
        # partition is therefore a well-defined function of affine x.
        index = 0 if state.point.is_infinity else state.point.x % self.table_size
        increment, alpha, beta = self.table[index]
        state.point = self.curve.add(state.point, increment)
        state.alpha = (state.alpha + alpha) % self.order
        state.beta = (state.beta + beta) % self.order

    def step(self, state: WalkState) -> None:
        self.advance_projective(state)
        state.point = self.curve.normalize(state.point)


def _candidate_model(candidate: Candidate) -> tuple[ShortWeierstrassCurve, JacobianPoint]:
    curve = ShortWeierstrassCurve(candidate.p, candidate.a, candidate.b)
    return curve, curve.from_affine((candidate.gx, candidate.gy))


def _benchmark_candidate_once(
    candidate: Candidate,
    *,
    seconds: float = 1.0,
    table_size: int = 16,
    batch_width: int = 64,
    seed: int = 20261005,
) -> dict[str, Any]:
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    curve, generator = _candidate_model(candidate)
    secret = (0xC0DEC0FFEE12345 % (candidate.n - 1)) + 1
    target = curve.scalar_mul(secret, generator)
    walk = RAddingWalk(
        curve,
        candidate.n,
        generator,
        target,
        table_size=table_size,
        seed=seed,
    )
    if batch_width < 1:
        raise ValueError("batch_width must be positive")
    states = [
        walk.initial_state((seed ^ 0xA5A5A5A5) + index * 104729)
        for index in range(batch_width)
    ]

    def advance_batch() -> None:
        for state in states:
            walk.advance_projective(state)
        normalized = curve.batch_normalize([state.point for state in states])
        for state, point in zip(states, normalized):
            state.point = point

    for _ in range(8):
        advance_batch()
    start = time.perf_counter()
    iterations = 0
    while True:
        for _ in range(8):
            advance_batch()
        iterations += 8 * batch_width
        if time.perf_counter() - start >= seconds:
            break
    elapsed = time.perf_counter() - start
    ips = iterations / elapsed

    expected_steps_log2 = math.log2(math.sqrt(math.pi * candidate.n / 2))
    relation_check = all(
        curve.equal(
            state.point,
            curve.add(
                curve.scalar_mul(state.alpha, generator),
                curve.scalar_mul(state.beta, target),
            ),
        )
        for state in states[: min(4, len(states))]
    )
    if not relation_check:
        raise AssertionError("rho state lost its linear relation")

    return {
        "candidate_id": candidate.candidate_id,
        "field_bits": candidate.p.bit_length(),
        "order_bits": candidate.n.bit_length(),
        "path_length": len(candidate.path),
        "path_degree_product": str(math.prod(step["degree"] for step in candidate.path)),
        "walk": "parallel r-adding walks with batch affine normalization",
        "table_size": table_size,
        "batch_width": batch_width,
        "elapsed_seconds": elapsed,
        "iterations": iterations,
        "iterations_per_second": ips,
        "expected_generic_steps_log2": expected_steps_log2,
        "projected_generic_seconds_log2": expected_steps_log2 - math.log2(ips),
        "linear_relation_verified": relation_check,
    }


def benchmark_candidate(
    candidate: Candidate,
    *,
    seconds: float = 1.0,
    table_size: int = 16,
    batch_width: int = 64,
    trials: int = 3,
    seed: int = 20261005,
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    measurements = [
        _benchmark_candidate_once(
            candidate,
            seconds=seconds,
            table_size=table_size,
            batch_width=batch_width,
            seed=seed + trial * 65537,
        )
        for trial in range(trials)
    ]
    rates = [row["iterations_per_second"] for row in measurements]
    mean_rate = statistics.fmean(rates)
    standard_deviation = statistics.stdev(rates) if len(rates) > 1 else 0.0
    ci_half_width = (
        1.96 * standard_deviation / math.sqrt(len(rates)) if len(rates) > 1 else 0.0
    )
    result = dict(measurements[0])
    result.update(
        {
            "elapsed_seconds": sum(row["elapsed_seconds"] for row in measurements),
            "iterations": sum(row["iterations"] for row in measurements),
            "iterations_per_second": mean_rate,
            "rate_trials": rates,
            "rate_standard_deviation": standard_deviation,
            "rate_95_percent_ci": [
                max(0.0, mean_rate - ci_half_width),
                mean_rate + ci_half_width,
            ],
            "trials": trials,
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
                "does not use the negation-map quotient",
                "does not include parallel distinguished-point coordination",
                "an end-to-end speedup is not claimed until mapping cost is measured",
            ],
        }
    )
    return result


def benchmark_candidates(
    candidates: list[Candidate],
    *,
    seconds: float,
    table_size: int = 16,
    batch_width: int = 64,
    trials: int = 3,
) -> dict[str, Any]:
    results = [
        benchmark_candidate(
            candidate,
            seconds=seconds,
            table_size=table_size,
            batch_width=batch_width,
            trials=trials,
        )
        for candidate in candidates
    ]
    baseline = next(
        (row for row in results if row["candidate_id"] == "p256-root"), results[0]
    )
    baseline_rate = baseline["iterations_per_second"]
    for row in results:
        row["relative_iteration_speed"] = (
            row["iterations_per_second"] / baseline_rate
        )
        row["constant_factor_security_delta_bits"] = math.log2(
            row["relative_iteration_speed"]
        )
    return {
        "schema_version": 1,
        "baseline_candidate_id": baseline["candidate_id"],
        "results": results,
    }


def solve_toy_log(
    candidate: Candidate,
    secret: int,
    *,
    table_size: int = 16,
    seed: int = 7,
    attempts: int = 16,
) -> dict[str, Any]:
    """Solve a small prime-order instance and verify collision extraction."""
    curve, generator = _candidate_model(candidate)
    secret %= candidate.n
    target = curve.scalar_mul(secret, generator)
    max_steps = 24 * math.isqrt(candidate.n) + 128

    for attempt in range(attempts):
        attempt_seed = seed + 1009 * attempt
        walk = RAddingWalk(
            curve,
            candidate.n,
            generator,
            target,
            table_size=table_size,
            seed=attempt_seed,
        )
        state = walk.initial_state(attempt_seed ^ 0x5A5A)
        seen: dict[tuple[int, int] | None, tuple[int, int]] = {}
        for iteration in range(1, max_steps + 1):
            key = curve.to_affine(state.point)
            previous = seen.get(key)
            if previous is not None:
                old_alpha, old_beta = previous
                denominator = (old_beta - state.beta) % candidate.n
                if denominator:
                    recovered = (
                        (state.alpha - old_alpha)
                        * pow(denominator, -1, candidate.n)
                    ) % candidate.n
                    if curve.equal(curve.scalar_mul(recovered, generator), target):
                        return {
                            "candidate_id": candidate.candidate_id,
                            "secret": secret,
                            "recovered": recovered,
                            "iterations": iteration,
                            "attempt": attempt + 1,
                            "verified": True,
                        }
            else:
                seen[key] = (state.alpha, state.beta)
            walk.step(state)
    raise RuntimeError("rho did not yield a usable collision within the attempt budget")
