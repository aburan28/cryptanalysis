#!/usr/bin/env python3
"""Generate a bounded shortest-path policy allowing two digits per tau pair."""

import argparse
import hashlib
from heapq import heappop, heappush
from pathlib import Path

from make_tau_tail_gate import canonical_cost
from make_tau_tail_oracle import BOUND, INF, PHASES, SIDE, generate as restricted_generate
from make_tau_tail_oracle import index, tau2
from run import TABLE


NONE = 255
UNREACHABLE = 254
DIGITS = [(9 * x + y, digit) for (x, y), digit in sorted(TABLE.items())]


def choices_for_phase(phase):
    """Keep the cheapest realization of each exact pair contribution."""
    options = {}

    def offer(even, odd, da, db, rotations):
        key = da, db
        item = (16 * (even != NONE) + 16 * (odd != NONE) + rotations, even, odd)
        if key not in options or item < options[key]:
            options[key] = item

    offer(NONE, NONE, 0, 0, 0)
    for even_slot, even in DIGITS:
        ea, eb, _seed, epower, _sign = even
        even_rot = int((epower + phase) % 3 != 0)
        offer(even_slot, NONE, ea, eb, even_rot)
        for odd_slot, odd in DIGITS:
            oa, ob, _seed, opower, _sign = odd
            odd_a, odd_b = -3 * ob, oa + 3 * ob
            odd_rot = int((opower + phase) % 3 != 0)
            offer(even_slot, odd_slot, ea + odd_a, eb + odd_b, even_rot + odd_rot)
    for odd_slot, odd in DIGITS:
        oa, ob, _seed, power, _sign = odd
        offer(NONE, odd_slot, -3 * ob, oa + 3 * ob,
              int((power + phase) % 3 != 0))
    return [(da, db, *item) for (da, db), item in sorted(options.items())]


def step(a, b, phase, even, odd):
    da = db = digit_cost = 0
    for slot, shifted in ((even, False), (odd, True)):
        if slot == NONE:
            continue
        digit = TABLE[(slot // 9, slot % 9)]
        x, y, _seed, power, _sign = digit
        if shifted:
            x, y = -3 * y, x + 3 * y
        da += x
        db += y
        digit_cost += 16 + int((power + phase) % 3 != 0)
    ax, by = a - da, b - db
    if ax % 3 or by % 3:
        raise AssertionError("nonintegral tau-pair quotient")
    qa, qb = 2 * (ax // 3) + by, -(ax + by) // 3
    edge = digit_cost + (10 if (qa, qb) != (0, 0) else 0)
    return qa, qb, edge


def generate():
    costs = [INF] * (PHASES * SIDE * SIDE)
    actions = [None] * len(costs)
    heap = []
    choices = [choices_for_phase(phase) for phase in range(PHASES)]
    for phase in range(PHASES):
        costs[index(0, 0, phase)] = 0
        actions[index(0, 0, phase)] = (NONE, NONE)
        heappush(heap, (0, 0, 0, phase))
    while heap:
        cost, qa, qb, next_phase = heappop(heap)
        if cost != costs[index(qa, qb, next_phase)]:
            continue
        phase = (next_phase - 1) % PHASES
        base_a, base_b = tau2(qa, qb)
        for da, db, digit_cost, even, odd in choices[phase]:
            a, b = base_a + da, base_b + db
            if not (-BOUND <= a <= BOUND and -BOUND <= b <= BOUND) or (a, b) == (0, 0):
                continue
            edge = digit_cost + (10 if (qa, qb) != (0, 0) else 0)
            new = cost + edge
            pos = index(a, b, phase)
            if new < costs[pos] or (new == costs[pos] and (even, odd) < actions[pos]):
                costs[pos], actions[pos] = new, (even, odd)
                heappush(heap, (new, a, b, phase))
    return costs, actions


def validate(costs, actions):
    reachable = double_action_states = max_steps = 0
    for phase in range(PHASES):
        for a in range(-BOUND, BOUND + 1):
            for b in range(-BOUND, BOUND + 1):
                pos = index(a, b, phase)
                if actions[pos] is None:
                    assert costs[pos] == INF
                    continue
                reachable += 1
                x, y, p, steps = a, b, phase, 0
                while (x, y) != (0, 0):
                    old = index(x, y, p)
                    even, odd = actions[old]
                    double_action_states += even != NONE and odd != NONE
                    qx, qy, edge = step(x, y, p, even, odd)
                    assert -BOUND <= qx <= BOUND and -BOUND <= qy <= BOUND
                    new = index(qx, qy, (p + 1) % PHASES)
                    assert costs[old] == edge + costs[new]
                    assert costs[new] < costs[old]
                    x, y, p, steps = qx, qy, (p + 1) % PHASES, steps + 1
                    assert steps <= 256
                max_steps = max(max_steps, steps)
    return reachable, double_action_states, max_steps


def gate_bits(costs, actions):
    bits = bytearray((len(costs) + 7) // 8)
    improved = 0
    for phase in range(PHASES):
        for a in range(-BOUND, BOUND + 1):
            for b in range(-BOUND, BOUND + 1):
                pos = index(a, b, phase)
                if actions[pos] is not None and costs[pos] < canonical_cost(a, b, phase):
                    bits[pos >> 3] |= 1 << (pos & 7)
                    improved += 1
    return bytes(bits), improved


def render(actions, bits):
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    lines = ["/* Generated by make_tau_tail_double.py; do not edit.",
             f" * Generator SHA-256: {source_hash}",
             " * High byte is even slot; low byte is odd slot.",
             " * 255 = no digit; 254/254 = unreachable state.",
             " */", "#ifndef CA_TAU_TAIL_DOUBLE_H", "#define CA_TAU_TAIL_DOUBLE_H",
             "#include <stdint.h>",
             "#define CA_TAU_DOUBLE_BOUND 64", "#define CA_TAU_DOUBLE_SIDE 129",
             "static const uint16_t ca_tau_double_action[3][129][129] = {"]
    for phase in range(PHASES):
        lines.append("    {")
        for a in range(-BOUND, BOUND + 1):
            row = actions[index(a, -BOUND, phase):index(a, BOUND, phase) + 1]
            values = [((even << 8) | odd) if item is not None else 0xfefe
                      for item in row for even, odd in [item or (0, 0)]]
            lines.append("        {" + ", ".join(str(value) for value in values) + "},")
        lines.append("    },")
    lines.extend(["};", f"static const uint8_t ca_tau_double_gate[{len(bits)}] = {{"])
    for offset in range(0, len(bits), 16):
        lines.append("    " + ", ".join(str(value) for value in bits[offset:offset + 16]) + ",")
    lines.extend(["};", "#endif", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] /
                        "src/generated/tau_tail_double.h")
    args = parser.parse_args()
    costs, actions = generate()
    reachable, double_states, max_steps = validate(costs, actions)
    restricted_costs, _restricted_actions = restricted_generate()
    assert all(new <= old for new, old in zip(costs, restricted_costs))
    better_states = sum(new < old for new, old in zip(costs, restricted_costs))
    bits, improved = gate_bits(costs, actions)
    data = render(actions, bits)
    if args.output.exists() and args.output.read_text() != data:
        raise SystemExit(f"generated double-pair policy changed: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(data)
    print(f"reachable={reachable} better_than_restricted_states={better_states} "
          f"double_actions_on_paths={double_states} "
          f"max_steps={max_steps} gated_states={improved} "
          f"action_bytes={len(actions) * 2} gate_bytes={len(bits)} "
          f"header_sha256={hashlib.sha256(data.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
