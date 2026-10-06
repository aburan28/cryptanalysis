#!/usr/bin/env python3
"""Signed-Frobenius quotient version of the two-color pair-claw walk."""

import random
import time

from orbit_key import digest_key


def step(curve, base, target, orbit, state_key):
    digest = digest_key(state_key)
    color = digest[0] & 1
    first = int.from_bytes(digest[1:5], "little") % len(base)
    second = int.from_bytes(digest[5:9], "little") % len(base)
    pair = curve.add(base[first], base[second])
    raw_output = pair if color == 0 else curve.add(target, curve.neg(pair))
    output_key, exponent, sign = orbit.canonical(raw_output)
    return output_key, (color, first, second, exponent, sign)


def distinguished(state_key, bits):
    return int.from_bytes(digest_key(state_key)[12:16], "little") & (
        (1 << bits) - 1) == 0


def replay_endpoint(curve, base, base_set, target, orbit, first, second):
    first_seed, first_length = first
    second_seed, second_length = second
    first_states = []
    state = first_seed
    for _ in range(first_length + 1):
        first_states.append(state)
        state, _ = step(curve, base, target, orbit, state)
    first_position = {}
    for index, key in enumerate(first_states):
        first_position.setdefault(key, index)
    state, previous = second_seed, None
    for second_index in range(second_length + 1):
        first_index = first_position.get(state)
        if first_index is not None:
            if first_index == 0 or second_index == 0:
                return None
            first_output, first_meta = step(curve, base, target, orbit,
                                            first_states[first_index - 1])
            second_output, second_meta = step(curve, base, target, orbit,
                                              previous)
            assert first_output == second_output == state
            if first_meta[0] == second_meta[0]:
                return None
            zero = first_meta if first_meta[0] == 0 else second_meta
            one = second_meta if first_meta[0] == 0 else first_meta
            shift = (zero[3] - one[3]) % orbit.n
            sign = zero[4] * one[4]
            left = [base[zero[1]], base[zero[2]]]
            right = [base[one[1]], base[one[2]]]
            transformed = [curve.frob(point, shift) for point in left]
            if sign < 0:
                transformed = [curve.neg(point) for point in transformed]
            points = transformed + right
            if not all(point in base_set for point in points):
                raise AssertionError("quotient witness left the Frobenius-stable base")
            if any(points[i] == curve.neg(points[j])
                   for i in range(4) for j in range(i)):
                return None
            total = None
            for point in points:
                total = curve.add(total, point)
            assert total == target
            return {"points": [list(point) for point in points],
                    "zero_meta": list(zero), "one_meta": list(one),
                    "frobenius_shift_of_zero_pair": shift,
                    "sign_of_zero_pair": sign,
                    "merge_depths": [first_index, second_index]}
        previous = state
        state, _ = step(curve, base, target, orbit, state)
    return None


def walk(curve, base, generator, order, target, orbit, seed,
         distinguished_bits, max_trail, max_evaluations):
    rng = random.Random(seed)
    base_set = set(base)
    endpoints = {}
    evaluations = trails = replays = rejected = discarded = 0
    started = time.perf_counter_ns()
    while evaluations < max_evaluations:
        start = orbit.canonical(curve.mul(generator,
                                          rng.randrange(1, order)))[0]
        state, length = start, 0
        while length < max_trail and evaluations < max_evaluations:
            state, _ = step(curve, base, target, orbit, state)
            length += 1
            evaluations += 1
            if distinguished(state, distinguished_bits):
                break
        if not distinguished(state, distinguished_bits):
            discarded += 1
            continue
        trails += 1
        earlier = endpoints.get(state)
        if earlier is None:
            endpoints[state] = (start, length)
            continue
        replays += 1
        relation = replay_endpoint(curve, base, base_set, target, orbit,
                                   earlier, (start, length))
        if relation is not None:
            return {"status": "verified_four_point_relation",
                    "main_step_evaluations_excluding_replay": evaluations,
                    "wall_ns": time.perf_counter_ns() - started,
                    "trails": trails, "endpoint_rows": len(endpoints),
                    "endpoint_replays": replays,
                    "rejected_replays": rejected,
                    "discarded_no_endpoint": discarded,
                    "relation": relation}
        rejected += 1
    return {"status": "budget",
            "main_step_evaluations_excluding_replay": evaluations,
            "wall_ns": time.perf_counter_ns() - started,
            "trails": trails, "endpoint_rows": len(endpoints),
            "endpoint_replays": replays,
            "rejected_replays": rejected,
            "discarded_no_endpoint": discarded,
            "relation": None}
