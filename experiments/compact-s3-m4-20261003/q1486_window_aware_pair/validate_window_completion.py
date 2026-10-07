#!/usr/bin/env python3
"""Exhaust F32 window completions and check coupled S3 guards directly."""

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


def states(n: int) -> list[tuple[int, int]]:
    return [(fixed, ones) for fixed in range(1 << n)
            for ones in range(1 << n) if ones & ~fixed == 0]


def direct_leaf_options(base: list[int], masks: list[int],
                        coordinate: tuple[int, int],
                        window: tuple[int, int]) -> frozenset[int]:
    fixed, ones = coordinate
    positive, negative = window
    return frozenset(x for x in base if x & fixed == ones and
        all(x & ~mask == 0 for index, mask in enumerate(masks)
            if (positive >> index) & 1) and
        (positive != 0 or any(x & ~mask == 0
            for index, mask in enumerate(masks)
            if not (negative >> index) & 1)))


def enumerated_leaf_options(n: int, masks: list[int],
                            coordinate: tuple[int, int],
                            window: tuple[int, int]) -> tuple[frozenset[int], int]:
    fixed, ones = coordinate
    positive, negative = window
    if positive:
        allowed = (1 << n) - 1
        for index, mask in enumerate(masks):
            if (positive >> index) & 1:
                allowed &= mask
        possible_masks = [allowed]
    else:
        possible_masks = [mask for index, mask in enumerate(masks)
                          if not (negative >> index) & 1]
    values = set()
    count_bound = 0
    for mask in possible_masks:
        if ones & ~mask:
            continue
        free = [index for index in range(n)
                if (mask >> index) & 1 and not (fixed >> index) & 1]
        count_bound += (1 << len(free)) - int(ones == 0)
        for selected in range(1 << len(free)):
            x = ones
            for j, coordinate_index in enumerate(free):
                if (selected >> j) & 1:
                    x |= 1 << coordinate_index
            if x:
                values.add(x)
    return frozenset(values), count_bound


def main() -> None:
    n, d = 5, 2
    masks = [sum(1 << ((start + j) % n) for j in range(d))
             for start in range(n)]
    base = [x for x in range(1, 1 << n)
            if any(x & ~mask == 0 for mask in masks)]
    assert len(base) == 10
    coordinate_states = states(n)
    window_states = states(n)
    options = {}
    empty = multiple_positive = 0
    for coord, (assigned, positive) in itertools.product(
            coordinate_states, window_states):
        window = (positive, assigned ^ positive)
        direct = direct_leaf_options(base, masks, coord, window)
        predicted, count_bound = enumerated_leaf_options(
            n, masks, coord, window)
        assert predicted == direct and count_bound >= len(predicted)
        options[coord, window] = predicted
        empty += int(not predicted)
        multiple_positive += int(window[0].bit_count() > 1)

    onb = field.Onb(n)
    elements = [onb.fromCoords(x) for x in range(1 << n)]
    s3 = {(a, b, c): evaluate_s3(onb, elements[a], elements[b],
                                  elements[c]) == 0
          for a, b, c in itertools.product(range(1 << n), repeat=3)}
    roots = {(a, b): tuple(c for c in range(1 << n) if s3[a, b, c])
             for a, b in itertools.product(range(1 << n), repeat=2)}
    rng = random.Random(1486)
    nonempty = [state for state, values in options.items() if values]
    coupled_checks = rejected = forced_bits = 0
    for _ in range(2048):
        a, b, c, d_state = (rng.choice(nonempty) for _ in range(4))
        target = rng.randrange(1, 1 << n)
        mid_fixed, mid_ones = rng.choice(coordinate_states)
        aa, bb, cc, dd = (options[state]
                           for state in (a, b, c, d_state))
        left = {v for x in aa for y in bb for u in roots[x, y]
                for v in roots[u, target]}
        right = {v for x in cc for y in dd for v in roots[x, y]}
        predicted = {v for v in left & right
                     if v & mid_fixed == mid_ones}
        direct = {v for v in range(1 << n)
                  if v & mid_fixed == mid_ones and
                  any(s3[x, y, u] and s3[z, w, v] and s3[u, v, target]
                      for x in aa for y in bb for z in cc for w in dd
                      for u in range(1 << n))}
        assert predicted == direct
        coupled_checks += 1
        rejected += int(not predicted)
        if predicted:
            for bit in range(n):
                if mid_fixed & (1 << bit):
                    continue
                all_one = all(v & (1 << bit) for v in predicted)
                all_zero = all(not v & (1 << bit) for v in predicted)
                if all_one or all_zero:
                    assert all((v >> bit) & 1 == int(all_one)
                               for v in direct)
                    forced_bits += 1

    result = {
        "kind": "q1486_exact_window_completion_and_s3_validation",
        "status": "passed", "degree_n": n, "window_dimension_d": 2,
        "oracle": "original existential window clauses and direct S3 on F32",
        "exact_partial_leaf_state_checks": len(options),
        "empty_partial_leaf_states": empty,
        "multiple_true_window_state_checks": multiple_positive,
        "seeded_coupled_direct_chain_checks": coupled_checks,
        "seeded_empty_intersections": rejected,
        "seeded_forced_midpoint_bits": forced_bits,
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    path = HERE / "window_validation.json"
    assert not path.exists(), "refuse overwrite"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
