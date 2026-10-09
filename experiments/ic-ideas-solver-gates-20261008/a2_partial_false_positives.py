#!/usr/bin/env python3
"""Recover the 53 residual x values after 256 quartic membership equations."""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from a2_membership_degree import family, multiply  # noqa: E402
from a2_exact_quartic_membership import polynomial_truth  # noqa: E402

PRIOR = HERE.parent / "ic-ideas-20261007/results/a2_final.json"


def columns():
    return [sum(1 << i for i in subset)
            for degree in range(5)
            for subset in itertools.combinations(range(23), degree)]


def main():
    out = HERE / "a2_partial_false_positives.json"
    if out.exists():
        raise FileExistsError(out)
    prior = json.loads(PRIOR.read_text())
    _, values = family(prior["gamma_bits"], prior["field_modulus_bits"])
    value_set = set(values)
    equations_path = HERE / "a2_exact_quartic_equations.json.gz"
    equations = json.loads(gzip.decompress(equations_path.read_bytes()))
    assert len(equations) == 256
    candidates = np.ones(1 << 23, dtype=np.bool_)
    for polynomial in equations[:32]:
        candidates &= polynomial_truth(polynomial) == 0
    outside = [int(x) for x in np.flatnonzero(candidates) if int(x) not in value_set]
    assert len(outside) == 57
    positions = {mask: j for j, mask in enumerate(columns())}
    rows = {}
    for x in outside:
        support = [i for i in range(23) if x >> i & 1]
        rows[x] = sum(1 << positions[sum(1 << i for i in subset)]
                      for degree in range(5)
                      for subset in itertools.combinations(support, degree))
    for polynomial in equations[32:]:
        coeff = sum(1 << positions[mask] for mask in polynomial)
        outside = [x for x in outside if not ((rows[x] & coeff).bit_count() & 1)]
    assert len(outside) == 53
    modulus = prior["field_modulus_bits"]
    orbits = []
    seen = set()
    for value in outside:
        if value in seen:
            continue
        orbit = [value]
        nxt = multiply(value, value, modulus, 23)
        while nxt != value:
            orbit.append(nxt)
            nxt = multiply(nxt, nxt, modulus, 23)
        seen.update(orbit)
        orbits.append({"representative": value, "full_orbit_size": len(orbit),
                       "residual_members": sum(x in outside for x in orbit)})
    answer = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "first_32_false_positives": 57,
              "first_256_false_positives": len(outside),
              "false_positive_x_bits": outside,
              "frobenius_orbits": orbits,
              "equations_artifact_sha256": hashlib.sha256(equations_path.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"residual": len(outside), "orbits": orbits}))


if __name__ == "__main__":
    main()
