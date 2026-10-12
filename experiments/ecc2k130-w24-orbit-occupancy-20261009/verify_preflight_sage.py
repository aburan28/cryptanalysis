#!/usr/bin/env sage -python
"""Independently replay the W24 orbit bound with Sage field and matrix APIs."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import GF, PolynomialRing, matrix


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "CONFIG.json"
PREFLIGHT = HERE / "preflight.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(element) -> int:
    return sum(int(bit) << index for index, bit in enumerate(element.polynomial().list()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite an existing receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    assert isinstance(runtime, dict) and runtime
    config = json.loads(CONFIG.read_text())
    preflight = json.loads(PREFLIGHT.read_text())
    field = config["field"]
    assert field["degree"] == 131 and field["characteristic"] == 2

    f2 = GF(2)
    polynomial = PolynomialRing(f2, "t")
    t = polynomial.gen()
    modulus = sum(t**exponent for exponent in field["modulus_exponents"])
    assert modulus.is_irreducible()
    extension = GF(2**131, "t", modulus=modulus)
    generator = extension.gen()
    traces = [int((generator**j).trace()) for j in range(1, 25)]
    basis = [generator**j + traces[j-1] for j in range(1, 25)]
    assert all(encoded(element) == 1 << (j+1) for j, element in enumerate(basis))
    w_bits = sum(1 << index for index in range(1, 25))
    outside = [0, *range(25, 131)]

    current = basis[:]
    intersections: dict[str, int] = {}
    candidates: set[int] = set()
    for exponent in range(1, 131):
        current = [element**2 for element in current]
        words = [encoded(element) for element in current]
        rows = [[(word >> bit) & 1 for word in words] for bit in outside]
        kernel = matrix(f2, rows).right_kernel()
        dimension = int(kernel.dimension())
        if dimension:
            intersections[str(exponent)] = dimension
            masks = [0]
            for vector in kernel.basis():
                kernel_mask = sum(int(bit) << j for j, bit in enumerate(vector))
                masks += [mask ^ kernel_mask for mask in masks]
            candidates.update(mask for mask in masks if mask)

    histogram: Counter[int] = Counter()
    maximum = 0
    for mask in sorted(candidates):
        element = sum((basis[j] for j in range(24) if mask & (1 << j)),
                      extension.zero())
        initial = element
        members = 0
        for _ in range(131):
            members += encoded(element) & ~w_bits == 0
            element = element**2
        assert element == initial and members >= 2
        histogram[members] += 1
        maximum = max(maximum, members)

    selected = config["source_factor_base"]["signed_columns"]
    observed = {
        "all_basis_traces_zero": traces == [0] * 24,
        "nonzero_intersection_dimensions_by_k": intersections,
        "direct_overlap_candidate_masks": len(candidates),
        "maximum_direct_orbit_members_in_w24": maximum,
        "maximum_signed_orbit_members_in_w24": 2 * maximum,
        "minimum_selected_signed_frobenius_columns":
            (selected + 2 * maximum - 1) // (2 * maximum),
    }
    assert observed == config["preflight_expectations"] == preflight["observed"]
    assert dict(sorted(histogram.items())) == {
        int(key): value for key, value in
        preflight["direct_occupancy_histogram_candidate_masks"].items()
    }
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak * 1024
    receipt = {
        "schema": "ecc2k130-w24-orbit-preflight-sage-replay-v1",
        "status": "PASS_INDEPENDENT_SAGE_PREFLIGHT",
        "observed": observed,
        "candidate_occupancy_histogram": dict(sorted(histogram.items())),
        "config_sha256": sha256(CONFIG),
        "integer_preflight_sha256": sha256(PREFLIGHT),
        "runtime_info_sha256": sha256(args.runtime_info),
        "verifier_sha256": sha256(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak,
        "selected_source_orbit_columns": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(receipt["status"], observed)


if __name__ == "__main__":
    main()
