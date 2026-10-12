#!/usr/bin/env python3
"""Check Q1480 conditioned-pair rejection against direct S3 truth tables."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import evaluate_s3, field  # noqa: E402

RESULT = HERE / "conditioned_validation.json"


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
    elements = [onb.fromCoords(x) for x in range(1 << n)]
    base = [x for x in range(1, 1 << n) if x.bit_count() <= weight]
    s3 = {(a, b, c): evaluate_s3(onb, elements[a], elements[b],
                                  elements[c]) == 0
          for a, b, c in itertools.product(range(1 << n), repeat=3)}
    partials = states(n)
    options = {state: tuple(x for x in base if matches(x, state))
               for state in partials}
    support = {
        (mid, left, right): any(s3[a, b, mid]
                                for a in options[left]
                                for b in options[right])
        for mid in range(1 << n)
        for left, right in itertools.product(partials, repeat=2)
    }
    checked_pair_states = len(support)
    checked_target_roots = 0
    checked_left_guards = 0
    for target in range(1, 1 << n):
        for second in range(1 << n):
            first_roots = tuple(u for u in range(1 << n)
                                if s3[second, target, u])
            checked_target_roots += 1
            if second == 0:
                assert first_roots == (int(onb.toCoords(
                    onb.inv(elements[target]))),)
            for first_state in partials:
                roots = tuple(u for u in first_roots
                              if matches(u, first_state))
                for left, right in itertools.product(partials, repeat=2):
                    predicted = any(support[u, left, right] for u in roots)
                    direct = any(s3[a, b, u] and s3[u, second, target]
                                 for a in options[left]
                                 for b in options[right]
                                 for u in range(1 << n)
                                 if matches(u, first_state))
                    assert predicted == direct
                    checked_left_guards += 1

    # Exhaust every full four-leaf assignment, nonzero target and second
    # midpoint. The conditioned split must agree with direct three-link S3.
    checked_full_chains = 0
    full_witnesses = 0
    for leaves in itertools.product(base, repeat=4):
        a, b, c, d = leaves
        for target in range(1, 1 << n):
            for second in range(1 << n):
                first_roots = tuple(u for u in range(1 << n)
                                    if s3[second, target, u])
                predicted = (s3[c, d, second] and
                             any(s3[a, b, u] for u in first_roots))
                direct = any(s3[a, b, u] and s3[c, d, second] and
                             s3[u, second, target]
                             for u in range(1 << n))
                assert predicted == direct
                checked_full_chains += 1
                full_witnesses += int(direct)

    rng = random.Random(1480)
    checked_partial_guards = 0
    rejected_partial_guards = 0
    for _ in range(4096):
        first_state = rng.choice(partials)
        leaves = tuple(rng.choice(partials) for _ in range(4))
        target = rng.randrange(1, 1 << n)
        second = rng.randrange(1 << n)
        roots = tuple(u for u in range(1 << n)
                      if s3[second, target, u] and matches(u, first_state))
        predicted = (support[second, leaves[2], leaves[3]] and
                     any(support[u, leaves[0], leaves[1]] for u in roots))
        direct = any(s3[a, b, u] and s3[c, d, second] and
                     s3[u, second, target]
                     for a in options[leaves[0]]
                     for b in options[leaves[1]]
                     for c in options[leaves[2]]
                     for d in options[leaves[3]]
                     for u in range(1 << n)
                     if matches(u, first_state))
        assert predicted == direct
        checked_partial_guards += 1
        rejected_partial_guards += int(not predicted)
    return {
        "kind": "q1480_direct_s3_conditioned_guard_validation",
        "status": "passed", "degree_n": n, "weight_bound": weight,
        "pair_partial_states": checked_pair_states,
        "target_midpoint_root_cases": checked_target_roots,
        "partial_left_guard_cases": checked_left_guards,
        "complete_four_leaf_cases": checked_full_chains,
        "complete_x_only_witnesses": full_witnesses,
        "paired_partial_guard_cases": checked_partial_guards,
        "sound_paired_rejections": rejected_partial_guards,
        "oracle": "direct evaluation of each S3 polynomial on every F_8 triple",
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
