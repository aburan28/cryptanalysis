#!/usr/bin/env python3
"""Exhaustively check the Q1479 partial-domain and guarded clauses in F_8."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import evaluate_s3, field  # noqa: E402

RESULT = HERE / "domain_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def states(n: int) -> list[tuple[int, int]]:
    return [(fixed, ones) for fixed in range(1 << n)
            for ones in range(1 << n) if ones & ~fixed == 0]


def matches(value: int, state: tuple[int, int]) -> bool:
    fixed, ones = state
    return value & fixed == ones


def describe() -> dict:
    n, weight = 3, 2
    onb = field.Onb(n)
    elements = [onb.fromCoords(value) for value in range(1 << n)]
    base = [value for value in range(1, 1 << n)
            if value.bit_count() <= weight]
    roots = {(a, b): frozenset(u for u in range(1 << n)
                              if evaluate_s3(onb, elements[a], elements[b],
                                             elements[u]) == 0)
             for a, b in itertools.product(base, repeat=2)}
    final = {(u, t): frozenset(v for v in range(1 << n)
                              if evaluate_s3(onb, elements[u], elements[t],
                                             elements[v]) == 0)
             for u in range(1 << n) for t in range(1, 1 << n)}
    for t in range(1, 1 << n):
        assert final[0, t] == {int(onb.toCoords(onb.inv(elements[t])))}

    partial_states = states(n)
    checked_domains = checked_guards = checked_witnesses = 0
    rejection_guards = implication_guards = 0
    for left, right in itertools.product(partial_states, repeat=2):
        if left[0] == right[0] == (1 << n) - 1:
            continue
        completions = [(a, b) for a, b in itertools.product(base, repeat=2)
                       if matches(a, left) and matches(b, right)]
        for target in range(1, 1 << n):
            # This is the exact overapproximation used by Q1479: it ignores
            # rational lifts, distinct folded columns and subgroup checks.
            domain = {v for a, b in completions for u in roots[a, b]
                      for v in final[u, target]}
            # Independently enumerate every complete x-only chain from the
            # direct polynomial truth tables, including zero midpoints.
            witnesses = {(a, b, u, v) for a, b in completions
                         for u in range(1 << n)
                         if u in roots[a, b]
                         for v in range(1 << n)
                         if v in final[u, target]}
            assert {v for _, _, _, v in witnesses} == domain
            checked_domains += 1
            checked_witnesses += len(witnesses)
            for mid in partial_states:
                compatible = {v for v in domain if matches(v, mid)}
                guarded = {v for a, b, u, v in witnesses
                           if matches(a, left) and matches(b, right)
                           and matches(v, mid)}
                assert guarded == compatible
                checked_guards += 1
                if not compatible:
                    assert not guarded  # guarded rejection preserves SAT
                    rejection_guards += 1
                    continue
                for bit in range(n):
                    if mid[0] >> bit & 1:
                        continue
                    observed = {(v >> bit) & 1 for v in compatible}
                    if len(observed) == 1:
                        forced = next(iter(observed))
                        assert all((v >> bit) & 1 == forced for v in guarded)
                        implication_guards += 1
    return {
        "kind": "q1479_exhaustive_small_field_guard_validation",
        "status": "passed", "degree_n": n, "weight_bound": weight,
        "partial_left_target_domains": checked_domains,
        "partial_midpoint_guards": checked_guards,
        "complete_x_only_chains_examined": checked_witnesses,
        "sound_rejection_guards": rejection_guards,
        "sound_implication_guards": implication_guards,
        "oracle": "direct evaluation of both S3 polynomials over every F_8 triple",
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = describe()
    if args.check:
        assert result == json.loads(RESULT.read_text())
    else:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
