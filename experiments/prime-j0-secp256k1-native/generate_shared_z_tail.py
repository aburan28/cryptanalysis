#!/usr/bin/env python3
"""Build and audit the compact norm-4096 shared-Z mixed-radix tail policy.

The output stores one action per unit orbit and pending-tau state. This is a
source-operation model; it does not claim a measured CPU improvement.
"""

import hashlib
import heapq
import json
from collections import defaultdict
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from seed_chain_bound import orbit


HERE = Path(__file__).resolve().parent
TARGET = HERE / "shared-z-tail4096.bin"
LIMIT = 4096
TABLE = digit_table(SEEDS[0])
UNITS = sorted(set(orbit((1, 0))))
HALF = defaultdict(list)
RHO = {}
BAR_RHO = {}
for unit in UNITS:
    HALF[unit[0] % 2, unit[1] % 2].append(unit)
    RHO[(unit[0] - unit[1]) % 7] = unit
    BAR_RHO[(unit[0] - 3 * unit[1]) % 7] = unit
assert len(UNITS) == 6 and len(RHO) == len(BAR_RHO) == 6


def norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def multiply(left, right):
    a, b = left
    c, d = right
    return a * c - 3 * b * d, a * d + b * c + 3 * b * d


INVERSE = {unit: next(other for other in UNITS
                      if multiply(unit, other) == (1, 0)) for unit in UNITS}


def canonical(point):
    return min((multiply(point, unit), unit) for unit in UNITS)


def options(a, b):
    digit = TABLE[a % 9, b % 9] if a % 3 else None
    x, y = (a - digit[0][0], b - digit[0][1]) if digit else (a, b)
    yield "t", digit, x + y, -x // 3
    if a % 2 == b % 2 == 0:
        yield "h", None, a // 2, b // 2
    if a % 3:
        if (a - b) % 7 == 0:
            yield "r", None, (4 * a + 3 * b) // 7, (b - a) // 7
        if (a - 3 * b) % 7 == 0:
            yield "s", None, (a - 3 * b) // 7, (a + 4 * b) // 7
    parity = a % 2, b % 2
    if parity != (0, 0):
        for unit in HALF[parity]:
            x, y = a - unit[0], b - unit[1]
            yield "h", (unit, 0), x // 2, y // 2
    residue = (a - b) % 7
    if residue:
        unit = RHO[residue]
        x, y = a - unit[0], b - unit[1]
        yield "r", (unit, 0), (4 * x + 3 * y) // 7, (y - x) // 7
    residue = (a - 3 * b) % 7
    if residue:
        unit = BAR_RHO[residue]
        x, y = a - unit[0], b - unit[1]
        yield "s", (unit, 0), (x - 3 * y) // 7, (x + 4 * y) // 7


def successor(state, action):
    _, _, pending = state
    op, digit, x, y = action
    terminal = (x, y) == (0, 0)
    pair = pending and op == "t" and digit is None and not terminal
    weight = 0 if terminal else {"t": 6, "h": 7, "r": 13, "s": 13}[op]
    weight -= 2 if pair else 0
    weight += 11 if digit is not None and not terminal else 0
    return (x, y, op == "t" and not pair and not terminal), weight


def shortest_paths():
    reverse = defaultdict(list)
    states = 0
    edges = 0
    for a in range(-128, 129):
        for b in range(-73, 74):
            if not 0 < norm(a, b) <= LIMIT:
                continue
            for pending in (False, True):
                state = a, b, pending
                states += 1
                for action in options(a, b):
                    if norm(*action[2:]) > LIMIT:
                        continue
                    next_state, weight = successor(state, action)
                    if next_state[:2] == (0, 0):
                        next_state = 0, 0, False
                    reverse[next_state].append((state, weight, action))
                    edges += 1
    distance = {(0, 0, False): 0}
    chosen = {}
    queue = [(0, (0, 0, False))]
    while queue:
        value, state = heapq.heappop(queue)
        if value != distance[state]:
            continue
        for previous, weight, action in reverse[state]:
            candidate = value + weight
            if candidate < distance.get(previous, 10**9):
                distance[previous] = candidate
                chosen[previous] = action
                heapq.heappush(queue, (candidate, previous))
    assert len(chosen) == states == 29_688
    assert edges == 138_240
    return chosen, states, edges


def action_code(a, b, action):
    op, digit = action[:2]
    if digit is None:
        return {"t": 0, "h": 1, "r": 2, "s": 3}[op]
    if op == "t":
        return 0
    if op == "h":
        return 4 + HALF[a % 2, b % 2].index(digit[0])
    return {"r": 6, "s": 7}[op]


def decode(a, b, code):
    matching = [action for action in options(a, b)
                if action_code(a, b, action) == code]
    assert len(matching) == 1, (a, b, code)
    return matching[0]


def unrotate(action, unit):
    op, digit, x, y = action
    inverse = INVERSE[unit]
    adjusted = (multiply(digit[0], inverse), digit[1]) if digit else None
    return (op, adjusted, *multiply((x, y), inverse))


def reconstruction(actions):
    a = b = 0
    for op, digit, _, _ in reversed(actions):
        if op == "t":
            a, b = -3 * b, a + 3 * b
        elif op == "h":
            a, b = 2 * a, 2 * b
        elif op == "r":
            a, b = a - 3 * b, a + 4 * b
        else:
            a, b = 4 * a + 3 * b, b - a
        if digit is not None:
            a += digit[0][0]
            b += digit[0][1]
    return a, b


def main():
    chosen, states, edges = shortest_paths()
    canonical_states = {(*canonical((a, b))[0], pending)
                        for a, b, pending in chosen}
    assert len(canonical_states) * 6 == states
    rows = defaultdict(set)
    for a, b, _ in canonical_states:
        rows[a].add(b)
    first, last = min(rows), max(rows)
    offsets, minimums = [], []
    count = 0
    for a in range(first, last + 1):
        values = sorted(rows[a])
        assert values == list(range(values[0], values[-1] + 1))
        offsets.append(count)
        minimums.append(values[0])
        count += len(values)
    assert count * 2 == len(canonical_states) == 4_948
    actions = bytearray([255] * (count * 2))
    for a, b, pending in canonical_states:
        index = (offsets[a - first] + b - minimums[a - first]) * 2 + pending
        actions[index] = action_code(a, b, chosen[a, b, pending])
    assert 255 not in actions
    longest = 0
    for start in sorted(chosen):
        state = start
        path = []
        while state[:2] != (0, 0):
            a, b, pending = state
            (ca, cb), unit = canonical((a, b))
            index = (offsets[ca - first] + cb - minimums[ca - first]) * 2 + pending
            action = unrotate(decode(ca, cb, actions[index]), unit)
            assert action in tuple(options(a, b))
            path.append(action)
            state, _ = successor(state, action)
            assert len(path) <= 7
        assert reconstruction(path) == start[:2]
        longest = max(longest, len(path))
    blob = bytes(actions)
    blob += b"".join(offset.to_bytes(2, "little") for offset in offsets)
    blob += bytes(minimums)
    assert len(blob) == 5_329 and first == -128 and last == -2
    if TARGET.exists():
        assert TARGET.read_bytes() == blob, "frozen tail policy changed"
    else:
        TARGET.write_bytes(blob)
    print(json.dumps({"states": states, "edges": edges,
                      "unit_orbit_states": len(canonical_states),
                      "max_tail_steps": longest, "bytes": len(blob),
                      "sha256": hashlib.sha256(blob).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
