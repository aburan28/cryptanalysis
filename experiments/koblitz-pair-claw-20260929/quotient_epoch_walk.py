#!/usr/bin/env python3
"""Bounded, independently salted epochs of the signed-Frobenius claw walk.

The salt changes the deterministic mapping between epochs. Distinguished
endpoints are compared only inside one epoch, where every trail follows the
same mapping. Exact output-key counts diagnose repeated-state saturation.
"""

import hashlib
import random
import time

from orbit_key import KEY_BYTES


def digest(key, epoch):
    assert 0 <= epoch < 1 << 32
    encoded = b"identity" if key == -1 else key.to_bytes(KEY_BYTES, "little")
    return hashlib.blake2s(encoded, digest_size=16,
                           key=b"qep1" + epoch.to_bytes(4, "little")).digest()


def step(curve, base, target, orbit, state_key, epoch):
    value = digest(state_key, epoch)
    color = value[0] & 1
    first = int.from_bytes(value[1:5], "little") % len(base)
    second = int.from_bytes(value[5:9], "little") % len(base)
    pair = curve.add(base[first], base[second])
    raw_output = pair if color == 0 else curve.add(target, curve.neg(pair))
    output_key, exponent, sign = orbit.canonical(raw_output)
    return output_key, (color, first, second, exponent, sign)


def distinguished(state_key, epoch, bits):
    return int.from_bytes(digest(state_key, epoch)[12:16], "little") & (
        (1 << bits) - 1) == 0


def replay_endpoint(curve, base, base_set, target, orbit, epoch,
                    first, second):
    first_seed, first_length = first
    second_seed, second_length = second
    replay_steps = 0
    first_states = []
    state = first_seed
    for _ in range(first_length + 1):
        first_states.append(state)
        state, _ = step(curve, base, target, orbit, state, epoch)
        replay_steps += 1
    first_position = {}
    for index, key in enumerate(first_states):
        first_position.setdefault(key, index)
    state, previous = second_seed, None
    for second_index in range(second_length + 1):
        first_index = first_position.get(state)
        if first_index is not None:
            if first_index == 0 or second_index == 0:
                return None, replay_steps
            first_output, first_meta = step(curve, base, target, orbit,
                                            first_states[first_index - 1], epoch)
            second_output, second_meta = step(curve, base, target, orbit,
                                              previous, epoch)
            replay_steps += 2
            assert first_output == second_output == state
            if first_meta[0] == second_meta[0]:
                return None, replay_steps
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
            assert all(point in base_set for point in points)
            if any(points[i] == curve.neg(points[j])
                   for i in range(4) for j in range(i)):
                return None, replay_steps
            total = None
            for point in points:
                total = curve.add(total, point)
            assert total == target
            return {"points": [list(point) for point in points],
                    "zero_meta": list(zero), "one_meta": list(one),
                    "frobenius_shift_of_zero_pair": shift,
                    "sign_of_zero_pair": sign,
                    "merge_depths": [first_index, second_index]}, replay_steps
        previous = state
        state, _ = step(curve, base, target, orbit, state, epoch)
        replay_steps += 1
    return None, replay_steps


def walk_epochs(curve, base, generator, order, target, orbit, seed,
                distinguished_bits, max_trail, max_evaluations, epochs):
    assert epochs > 0 and max_evaluations % epochs == 0
    rng = random.Random(seed)
    base_set = set(base)
    per_epoch = max_evaluations // epochs
    total_evaluations = total_replay_steps = 0
    epoch_rows = []
    started = time.perf_counter_ns()
    for epoch in range(epochs):
        endpoints = {}
        seen_outputs = set()
        evaluations = trails = replays = rejected = discarded = replay_steps = 0
        relation = None
        while evaluations < per_epoch:
            start = orbit.canonical(curve.mul(generator,
                                              rng.randrange(1, order)))[0]
            state, length = start, 0
            while length < max_trail and evaluations < per_epoch:
                state, _ = step(curve, base, target, orbit, state, epoch)
                seen_outputs.add(state)
                length += 1
                evaluations += 1
                if distinguished(state, epoch, distinguished_bits):
                    break
            if not distinguished(state, epoch, distinguished_bits):
                discarded += 1
                continue
            trails += 1
            earlier = endpoints.get(state)
            if earlier is None:
                endpoints[state] = (start, length)
                continue
            replays += 1
            relation, replay_cost = replay_endpoint(
                curve, base, base_set, target, orbit, epoch,
                earlier, (start, length))
            replay_steps += replay_cost
            if relation is not None:
                break
            rejected += 1
        total_evaluations += evaluations
        total_replay_steps += replay_steps
        epoch_rows.append({
            "epoch": epoch,
            "main_step_evaluations_excluding_replay": evaluations,
            "distinct_output_keys": len(seen_outputs),
            "trails": trails,
            "endpoint_rows": len(endpoints),
            "endpoint_replays": replays,
            "rejected_replays": rejected,
            "discarded_no_endpoint": discarded,
            "replay_step_evaluations": replay_steps,
        })
        if relation is not None:
            return {"status": "verified_four_point_relation",
                    "main_step_evaluations_excluding_replay": total_evaluations,
                    "replay_step_evaluations": total_replay_steps,
                    "wall_ns": time.perf_counter_ns() - started,
                    "epochs_completed": len(epoch_rows),
                    "epochs": epoch_rows, "relation": relation}
    return {"status": "budget",
            "main_step_evaluations_excluding_replay": total_evaluations,
            "replay_step_evaluations": total_replay_steps,
            "wall_ns": time.perf_counter_ns() - started,
            "epochs_completed": len(epoch_rows),
            "epochs": epoch_rows, "relation": None}
