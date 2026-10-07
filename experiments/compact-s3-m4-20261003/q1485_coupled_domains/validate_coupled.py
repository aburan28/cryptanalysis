#!/usr/bin/env python3
"""Exhaust the small-field domains used by Q1485 against direct S3."""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from chain_s3 import evaluate_s3, field  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    n, weight = 3, 2
    onb = field.Onb(n)
    elements = [onb.fromCoords(i) for i in range(1 << n)]
    s3 = {(a, b, c): evaluate_s3(onb, elements[a], elements[b],
                                  elements[c]) == 0
          for a, b, c in itertools.product(range(1 << n), repeat=3)}
    states = [(fixed, ones) for fixed in range(1 << n)
              for ones in range(1 << n) if ones & ~fixed == 0]
    base = [x for x in range(1, 1 << n) if x.bit_count() <= weight]
    options = {state: tuple(x for x in base
                            if x & state[0] == state[1])
               for state in states}
    roots = {(a, b): tuple(c for c in range(1 << n) if s3[a, b, c])
             for a, b in itertools.product(range(1 << n), repeat=2)}

    left_domains = {}
    checked_left = 0
    for target in range(1, 1 << n):
        for a_state, b_state in itertools.product(states, repeat=2):
            a_values, b_values = options[a_state], options[b_state]
            first_mid = {u for a in a_values for b in b_values
                         for u in roots[a, b]}
            constructed = {v for u in first_mid for v in roots[u, target]}
            direct = {v for v in range(1 << n)
                      if any(s3[a, b, u] and s3[u, v, target]
                             for a in a_values for b in b_values
                             for u in range(1 << n))}
            assert constructed == direct
            left_domains[target, a_state, b_state] = constructed
            checked_left += 1

    right_domains = {}
    checked_right = 0
    for c_state, d_state in itertools.product(states, repeat=2):
        c_values, d_values = options[c_state], options[d_state]
        constructed = {v for c in c_values for d in d_values
                       for v in roots[c, d]}
        direct = {v for v in range(1 << n)
                  if any(s3[c, d, v] for c in c_values for d in d_values)}
        assert constructed == direct
        right_domains[c_state, d_state] = constructed
        checked_right += 1

    # Intersection of two exhaustive exact domains is the exact three-link
    # chain projection. Check every assigned-mask state for each domain and
    # exercise both-domain guards on a fixed seeded cross-product sample.
    checked_midpoint_filters = 0
    for domain in itertools.chain(left_domains.values(),
                                  right_domains.values()):
        for fixed, ones in states:
            compatible = {v for v in domain if v & fixed == ones}
            common = ((1 << n) - 1)
            any_one = 0
            for v in compatible:
                common &= v
                any_one |= v
            if compatible:
                for bit in range(n):
                    if fixed & (1 << bit):
                        continue
                    if common & (1 << bit):
                        assert all(v & (1 << bit) for v in compatible)
                    if not any_one & (1 << bit):
                        assert all(not v & (1 << bit)
                                   for v in compatible)
            checked_midpoint_filters += 1

    rng = random.Random(1485)
    checked_coupled = rejected_coupled = forced_coupled = 0
    for _ in range(16384):
        target = rng.randrange(1, 1 << n)
        a_state, b_state, c_state, d_state = (
            rng.choice(states) for _ in range(4))
        fixed, ones = rng.choice(states)
        left = left_domains[target, a_state, b_state]
        right = right_domains[c_state, d_state]
        predicted = {v for v in left & right if v & fixed == ones}
        direct = {v for v in range(1 << n)
                  if v & fixed == ones and
                  any(s3[a, b, u] and s3[c, d, v] and s3[u, v, target]
                      for a in options[a_state] for b in options[b_state]
                      for c in options[c_state] for d in options[d_state]
                      for u in range(1 << n))}
        assert predicted == direct
        checked_coupled += 1
        rejected_coupled += int(not predicted)
        if predicted:
            for bit in range(n):
                if fixed & (1 << bit):
                    continue
                if all(v & (1 << bit) for v in predicted) or all(
                        not v & (1 << bit) for v in predicted):
                    forced_coupled += 1

    result = {
        "kind": "q1485_small_field_coupled_domain_validation",
        "status": "passed",
        "degree_n": n, "weight_bound": weight,
        "oracle": "direct evaluation of S3 on every F_8 triple",
        "all_partial_leaf_states": len(states),
        "exhaustive_left_target_pair_domains": checked_left,
        "exhaustive_right_pair_domains": checked_right,
        "exhaustive_domain_midpoint_mask_filters": checked_midpoint_filters,
        "seeded_four_leaf_guard_checks": checked_coupled,
        "seeded_empty_intersections": rejected_coupled,
        "seeded_forced_midpoint_bits": forced_coupled,
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    path = HERE / "coupled_validation.json"
    assert not path.exists(), "refuse overwrite"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
