#!/usr/bin/env python3
"""Exhaust exact F32 inverse-S3 support over partial cyclic-window domains."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1486 = HERE.parent / "q1486_window_aware_pair"
sys.path.insert(0, str(Q1486))
from validate_window_completion import direct_leaf_options, states  # noqa: E402
from chain_s3 import evaluate_s3, field  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    n, d = 5, 2
    masks = [sum(1 << ((start + j) % n) for j in range(d))
             for start in range(n)]
    base = [x for x in range(1, 1 << n)
            if any(x & ~mask == 0 for mask in masks)]
    assert len(base) == 10
    domains = set()
    partial_states = 0
    for coordinate in states(n):
        for assigned, positive in states(n):
            domains.add(direct_leaf_options(
                base, masks, coordinate, (positive, assigned ^ positive)))
            partial_states += 1
    domains.discard(frozenset())
    ordered = sorted(domains, key=lambda values: (len(values), tuple(values)))
    onb = field.Onb(n)
    elements = [onb.fromCoords(x) for x in range(1 << n)]
    s3 = {(a, b, u): evaluate_s3(
        onb, elements[a], elements[b], elements[u]) == 0
        for a in range(1 << n) for b in range(1 << n)
        for u in range(1 << n)}
    roots = {(a, u): tuple(b for b in range(1 << n) if s3[a, u, b])
             for a in range(1, 1 << n) for u in range(1 << n)}
    for a in range(1, 1 << n):
        for u in range(1 << n):
            assert len(roots[a, u]) <= 2
            if u == 0:
                assert len(roots[a, u]) == 1
                assert onb.mul(elements[a], elements[roots[a, u][0]]) == (
                    onb.one())
            assert roots[a, u] == tuple(
                b for b in range(1 << n) if s3[a, b, u])
    checks = supported = 0
    for a_values in ordered:
        for b_values in ordered:
            anchor, partner = ((a_values, b_values)
                               if len(a_values) <= len(b_values)
                               else (b_values, a_values))
            for u in range(1 << n):
                direct = any(s3[a, b, u] for a in a_values
                             for b in b_values)
                inverse = any(b in partner for a in anchor
                              for b in roots[a, u])
                assert direct == inverse
                checks += 1
                supported += int(direct)
    result = {
        "kind": "q1487_exact_inverse_s3_small_field_validation",
        "status": "passed",
        "degree_n": n,
        "window_dimension_d": d,
        "raw_partial_leaf_states_checked": partial_states,
        "distinct_nonempty_leaf_domains": len(ordered),
        "ordered_domain_pair_midpoint_checks": checks,
        "supported_checks": supported,
        "all_nonzero_leaf_midpoint_root_sets_checked": (31 * 32),
        "zero_midpoint_reciprocal_checked": True,
        "parent_window_validator_sha256": sha(Q1486 /
                                               "validate_window_completion.py"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": sha(Path(__file__)),
    }
    path = HERE / "small_field_validation.json"
    assert not path.exists(), "refuse overwrite"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
