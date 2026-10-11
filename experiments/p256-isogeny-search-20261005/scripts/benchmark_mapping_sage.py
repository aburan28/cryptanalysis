#!/usr/bin/env sage -python
"""Measure reusable path setup and per-key P,Q isogeny evaluation separately.

The input registries are the frozen output of ``explore_sage.py``.  Each path's
retained rational maps are parsed over F_p, checked against the stored
j-invariant chain and mapped generator, and then evaluated on both source
points required to transfer one ECDLP instance.  The kernel polynomials remain
in the registry as independent path evidence; rebuilding from a kernel alone
can choose an isomorphic, but differently scaled, codomain model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

try:
    from sage.all import EllipticCurve, GF, PolynomialRing
    from sage.env import SAGE_VERSION
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_maps(candidate: dict[str, Any]) -> tuple[Any, list[tuple[Any, Any]]]:
    spec = candidate["curve"]
    field = GF(int(spec["p"]))
    endpoint = EllipticCurve(field, [int(spec["a"]), int(spec["b"])])
    ring = PolynomialRing(field, 2, names=("x", "y"))
    fraction_field = ring.fraction_field()
    maps: list[tuple[Any, Any]] = []
    expected_domain_j = int(
        EllipticCurve(
            field,
            [
                -3,
                int(
                    "5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b",
                    16,
                ),
            ],
        ).j_invariant()
    )
    for index, step in enumerate(candidate["path"]):
        if expected_domain_j != int(step["domain_j"]):
            raise AssertionError(f"step {index}: retained j-invariant chain mismatch")
        records = [step["map"]["isogeny"]]
        model_map = step["map"]["codomain_short_model_isomorphism"]
        if model_map is not None:
            records.append(model_map)
        for record in records:
            rational_maps = record["rational_maps"]
            if rational_maps is None or len(rational_maps) != 2:
                raise AssertionError(f"step {index}: missing affine rational maps")
            maps.append(
                (
                    fraction_field(rational_maps[0]),
                    fraction_field(rational_maps[1]),
                )
            )
        expected_domain_j = int(step["codomain_j"])
    if expected_domain_j != int(spec["j_invariant"]):
        raise AssertionError("final retained j mismatch")
    return endpoint, maps


def evaluate_coordinates(x_value: Any, y_value: Any, maps: list[tuple[Any, Any]]) -> tuple[Any, Any]:
    for x_map, y_map in maps:
        old_x, old_y = x_value, y_value
        x_value = x_map.numerator()(old_x, old_y) / x_map.denominator()(old_x, old_y)
        y_value = y_map.numerator()(old_x, old_y) / y_map.denominator()(old_x, old_y)
    return x_value, y_value


def t95(degrees_of_freedom: int) -> float:
    """Accurate asymptotic expansion of the two-sided 95% t critical value."""

    if degrees_of_freedom <= 0:
        raise ValueError("degrees of freedom must be positive")
    z = 1.959963984540054
    v = float(degrees_of_freedom)
    return (
        z
        + (z**3 + z) / (4 * v)
        + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * v**2)
        + (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / (384 * v**3)
    )


def benchmark_candidate(
    candidate: dict[str, Any], samples: int, repeats: int, warmup: int
) -> dict[str, Any]:
    setup_start = time.perf_counter_ns()
    curve, maps = prepare_maps(candidate)
    setup_seconds = (time.perf_counter_ns() - setup_start) / 1e9

    field = curve.base_field()
    first_domain = EllipticCurve(
        field,
        [
            -3,
            int(
                "5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b",
                16,
            ),
        ],
    )
    # Use the canonical P-256 generator and a deterministic, nontrivial public Q.
    generator = first_domain(
        int("6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296", 16),
        int("4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5", 16),
    )
    order = int(candidate["curve"]["n"])
    q_scalar = int.from_bytes(
        hashlib.sha256(b"p256-isogeny-mapping-benchmark-q-v1").digest(), "big"
    ) % order
    if q_scalar in (0, 1):
        raise AssertionError("unexpected benchmark scalar")
    public_q = q_scalar * generator

    mapped_p_xy = evaluate_coordinates(generator[0], generator[1], maps)
    mapped_q_xy = evaluate_coordinates(public_q[0], public_q[1], maps)
    mapped_p = curve(*mapped_p_xy)
    mapped_q = curve(*mapped_q_xy)
    stored = candidate["curve"]["generator"]
    if int(mapped_p[0]) != int(stored["x"]) or int(mapped_p[1]) != int(stored["y"]):
        raise AssertionError("reconstructed path does not reproduce retained generator")
    if mapped_q != q_scalar * mapped_p:
        raise AssertionError("mapped P,Q do not retain their discrete-log relation")

    for _ in range(warmup):
        evaluate_coordinates(generator[0], generator[1], maps)
        evaluate_coordinates(public_q[0], public_q[1], maps)

    sample_seconds: list[float] = []
    checksum = 0
    for _ in range(samples):
        start = time.perf_counter_ns()
        for _ in range(repeats):
            out_p = evaluate_coordinates(generator[0], generator[1], maps)
            out_q = evaluate_coordinates(public_q[0], public_q[1], maps)
            checksum ^= int(out_p[0]) ^ int(out_q[1])
        elapsed = (time.perf_counter_ns() - start) / 1e9
        sample_seconds.append(elapsed / repeats)

    mean = statistics.fmean(sample_seconds)
    stdev = statistics.stdev(sample_seconds)
    half_width = t95(samples - 1) * stdev / math.sqrt(samples)
    return {
        "candidate_id": candidate["candidate_id"],
        "path_degrees": [int(step["degree"]) for step in candidate["path"]],
        "path_degree_product": math.prod(
            int(step["degree"]) for step in candidate["path"]
        ),
        "reusable_map_parsing_seconds": setup_seconds,
        "per_key_mapping": {
            "source_points_evaluated": 2,
            "mean_seconds": mean,
            "median_seconds": statistics.median(sample_seconds),
            "standard_deviation_seconds": stdev,
            "mean_95_percent_ci_seconds": [mean - half_width, mean + half_width],
            "samples": samples,
            "repetitions_per_sample": repeats,
            "raw_sample_seconds_per_key": sample_seconds,
        },
        "verification": {
            "retained_generator_reproduced": True,
            "discrete_log_relation_preserved": True,
            "endpoint_model_and_retained_maps_reproduced": True,
            "checksum_low_64": checksum & ((1 << 64) - 1),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, action="append", required=True)
    parser.add_argument(
        "--candidate-id",
        action="append",
        help="candidate to time; repeat as needed (default: every non-root candidate)",
    )
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--repeats", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples < 2 or args.repeats < 1 or args.warmup < 0:
        raise SystemExit("samples >= 2, repeats >= 1, and warmup >= 0 are required")

    by_id: dict[str, dict[str, Any]] = {}
    inputs = []
    for path in args.candidates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        inputs.append({"path": str(path), "sha256": sha256(path)})
        for candidate in payload["candidates"]:
            existing = by_id.get(candidate["candidate_id"])
            if existing is not None and existing != candidate:
                raise AssertionError(f"conflicting candidate {candidate['candidate_id']}")
            by_id[candidate["candidate_id"]] = candidate

    selected_ids = args.candidate_id or [
        candidate_id for candidate_id in by_id if candidate_id != "p256-root"
    ]
    missing = [candidate_id for candidate_id in selected_ids if candidate_id not in by_id]
    if missing:
        raise SystemExit(f"candidate IDs not found: {missing}")

    started = time.time()
    results = [
        benchmark_candidate(by_id[candidate_id], args.samples, args.repeats, args.warmup)
        for candidate_id in selected_ids
    ]
    output = {
        "schema_version": 1,
        "benchmark": "explicit P-256 isogeny path evaluation on P and Q",
        "sage_version": str(SAGE_VERSION),
        "clock": "time.perf_counter_ns",
        "host_cpu_isolation": "unverified; wall-time results are exploratory",
        "inputs": inputs,
        "cost_boundary": {
            "reusable": "parse the retained affine rational maps over F_p",
            "per_key": "evaluate the already-parsed path on source P and public Q",
            "excluded": "candidate discovery and ECDLP walk",
        },
        "results": results,
        "elapsed_wall_seconds": time.time() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
