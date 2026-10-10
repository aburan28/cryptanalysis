#!/usr/bin/env python3
"""Exact binary-field preflight for the frozen W24 Frobenius census."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rank(vectors: list[int]) -> int:
    pivots: dict[int, int] = {}
    for vector in vectors:
        while vector:
            pivot = vector.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = vector
                break
            vector ^= pivots[pivot]
    return len(pivots)


def nullspace_masks(columns: list[int]) -> list[int]:
    """Kernel basis of a 24-column binary map; masks name input columns."""
    pivots: dict[int, tuple[int, int]] = {}
    kernel = []
    for index, column in enumerate(columns):
        value, mask = column, 1 << index
        while value:
            pivot = value.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = (value, mask)
                break
            old_value, old_mask = pivots[pivot]
            value ^= old_value
            mask ^= old_mask
        if value == 0:
            kernel.append(mask)
    assert len(kernel) + len(pivots) == len(columns)
    return kernel


def square_mod(value: int, modulus: int, degree: int) -> int:
    squared = 0
    while value:
        bit = value & -value
        squared ^= 1 << (2 * (bit.bit_length() - 1))
        value ^= bit
    while squared.bit_length() > degree:
        squared ^= modulus << (squared.bit_length() - degree - 1)
    return squared


def gcd_binary(left: int, right: int) -> int:
    while right:
        while left.bit_length() >= right.bit_length():
            left ^= right << (left.bit_length() - right.bit_length())
        left, right = right, left
    return left


def derive(config: dict, started: float) -> dict:
    field = config["field"]
    degree = field["degree"]
    assert field["characteristic"] == 2 and degree == 131
    modulus = sum(1 << exponent for exponent in field["modulus_exponents"])
    assert modulus == (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
    assert all(degree % divisor for divisor in range(2, int(degree**0.5) + 1))
    x = 2
    for _ in range(degree):
        x = square_mod(x, modulus, degree)
    assert x == 2 and gcd_binary(0b110, modulus) == 1  # Rabin, prime degree.

    def square(value: int) -> int:
        return square_mod(value, modulus, degree)

    def trace(value: int) -> int:
        total = 0
        for _ in range(degree):
            total ^= value
            value = square(value)
        assert total in (0, 1)
        return total

    traces = [trace(1 << index) for index in range(1, 25)]
    assert traces == [0] * 24
    basis = [(1 << index) ^ traces[index - 1] for index in range(1, 25)]
    w_bits = sum(basis)
    assert rank(basis) == 24 and w_bits == sum(1 << index for index in range(1, 25))

    current = basis[:]
    intersections: dict[str, int] = {}
    candidates: set[int] = set()
    for exponent in range(1, degree):
        current = [square(value) for value in current]
        dimension = len(basis) * 2 - rank(basis + current)
        kernel = nullspace_masks([value & ~w_bits for value in current])
        assert dimension == len(kernel)
        if dimension:
            intersections[str(exponent)] = dimension
            masks = [0]
            for vector in kernel:
                masks += [mask ^ vector for mask in masks]
            candidates.update(mask for mask in masks if mask)

    histogram: Counter[int] = Counter()
    max_members = 0
    examples: list[int] = []
    for mask in sorted(candidates):
        value = mask << 1
        members = 0
        for _ in range(degree):
            members += value != 0 and value & ~w_bits == 0
            value = square(value)
        assert value == mask << 1 and members >= 2
        histogram[members] += 1
        if members > max_members:
            max_members, examples = members, [mask]
        elif members == max_members and len(examples) < 8:
            examples.append(mask)

    maximum_signed = 2 * max_members
    selected = config["source_factor_base"]["signed_columns"]
    minimum_columns = (selected + maximum_signed - 1) // maximum_signed
    observed = {
        "all_basis_traces_zero": all(bit == 0 for bit in traces),
        "nonzero_intersection_dimensions_by_k": intersections,
        "direct_overlap_candidate_masks": len(candidates),
        "maximum_direct_orbit_members_in_w24": max_members,
        "maximum_signed_orbit_members_in_w24": maximum_signed,
        "minimum_selected_signed_frobenius_columns": minimum_columns,
    }
    assert observed == config["preflight_expectations"]
    archive = ROOT / config["source_factor_base"]["archive_path"]
    parent = ROOT / config["parent_config_path"]
    assert sha256(archive) == config["source_factor_base"]["archive_gzip_sha256"]
    assert sha256(parent) == config["parent_config_sha256"]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    return {
        "schema": "ecc2k130-w24-orbit-preflight-v1",
        "status": "PASS_INTEGER_PREFLIGHT_PENDING_INDEPENDENT_REPLAY",
        "proposal_id": config["proposal_id"],
        "candidate_id": None,
        "basis_trace_bits": traces,
        "observed": observed,
        "direct_occupancy_histogram_candidate_masks": dict(sorted(histogram.items())),
        "max_direct_example_masks": examples,
        "config_sha256": sha256(CONFIG),
        "parent_config_sha256": sha256(parent),
        "source_archive_gzip_sha256": sha256(archive),
        "producer_sha256": sha256(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak,
        "selected_source_orbit_columns": None,
        "selected_source_direct_orbit_columns": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite an existing receipt")
    started = time.perf_counter()
    config = json.loads(CONFIG.read_text())
    result = derive(config, started)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(result["status"], result["observed"])


if __name__ == "__main__":
    main()
