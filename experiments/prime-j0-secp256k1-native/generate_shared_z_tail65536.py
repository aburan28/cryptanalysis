#!/usr/bin/env python3
"""Generate the exact sixfold-symmetric norm-65536 shared-Z tail atlas.

This is an offline source-operation optimum over the frozen action vocabulary.
The generated table is immutable once checked in; no CPU speedup is inferred.
"""

import hashlib
import json
from collections import defaultdict
from functools import lru_cache

from generate_shared_z_tail import (
    HERE, action_code, canonical, decode, norm, options, reconstruction,
    shortest_paths, successor, unrotate,
)


LIMIT = 65_536
TARGET = HERE / "shared-z-tail65536.bin"


def build():
    points = []
    for a in range(-512, 513):
        for b in range(-296, 297):
            size = norm(a, b)
            if 0 < size <= LIMIT and canonical((a, b))[0] == (a, b):
                points.append((size, a, b))
    points.sort()
    assert len(points) == 39_621

    distance = {(0, 0, False): 0, (0, 0, True): 0}
    chosen = {}
    nonshrinking = []
    for size, a, b in points:
        for pending in (False, True):
            state = (a, b, pending)
            best = None
            for priority, action in enumerate(options(a, b)):
                following, weight = successor(state, action)
                if norm(*following[:2]) >= size:
                    nonshrinking.append((state, action))
                    continue
                key = (*canonical(following[:2])[0], following[2])
                proposal = (weight + distance[key], priority, action)
                if best is None or proposal < best:
                    best = proposal
            assert best is not None, state
            distance[state] = best[0]
            chosen[state] = best[2]
    assert len(chosen) == 79_242
    assert len(nonshrinking) == 10
    assert max(norm(*state[:2]) for state, _ in nonshrinking) == 49

    old, _, _ = shortest_paths()

    @lru_cache(None)
    def old_cost(state):
        if state[:2] == (0, 0):
            return 0
        following, weight = successor(state, old[state])
        return weight + old_cost(following)

    for state in old:
        key = (*canonical(state[:2])[0], state[2])
        assert distance[key] == old_cost(state), state

    @lru_cache(None)
    def score(state, cutoff):
        a, b, pending = state
        if (a, b) == (0, 0):
            return 0
        size = norm(a, b)
        if size <= cutoff:
            return distance[*canonical((a, b))[0], pending]
        available = tuple(options(a, b))
        tau = available[0]
        even = a % 2 == b % 2 == 0
        if a % 3:
            action = next((candidate for radix in ("h", "r", "s")
                           for candidate in available
                           if candidate[0] == radix and candidate[1] is None), tau)
        elif even and not pending and size > 39_083:
            action = next(candidate for candidate in available
                          if candidate[0] == "h" and candidate[1] is None)
        else:
            action = tau
        following, weight = successor(state, action)
        return weight + score(following, cutoff)

    panels = {}
    for name in ("fixture.json", "fresh-fixture.json", "coset-fixture.json",
                 "linked-fresh-fixture.json", "zero-tau-fixture.json"):
        cases = json.loads((HERE / name).read_text())["cases"]
        starts = [(int(case["short_a_hex"], 16), int(case["short_b_hex"], 16), False)
                  for case in cases]
        panels[name] = {str(cutoff): sum(140 + score(state, cutoff) for state in starts)
                        for cutoff in (4_096, 65_536)}
    assert [panels[name]["4096"] for name in panels] == [
        83_240, 333_095, 332_943, 332_749, 332_844]

    rows = defaultdict(list)
    for _, a, b in points:
        rows[a].append(b)
    assert min(rows) == -512 and max(rows) == -2 and len(rows) == 511
    offsets, minimums = [], []
    count = 0
    for a in range(-512, -1):
        values = sorted(rows[a])
        assert values == list(range(values[0], values[-1] + 1))
        offsets.append(count)
        minimums.append(values[0])
        count += len(values)
    assert count == 39_621 and max(minimums) == 256

    actions = bytearray([255] * (2 * count))
    for (_, a, b) in points:
        for pending in (False, True):
            index = 2 * (offsets[a + 512] + b - minimums[a + 512]) + pending
            actions[index] = action_code(a, b, chosen[a, b, pending])
    assert 255 not in actions
    blob = bytes(actions)
    blob += b"".join(offset.to_bytes(2, "little") for offset in offsets)
    blob += b"".join(minimum.to_bytes(2, "little") for minimum in minimums)
    assert len(blob) == 81_286

    def table_action(state):
        a, b, pending = state
        (ca, cb), unit = canonical((a, b))
        index = 2 * (offsets[ca + 512] + cb - minimums[ca + 512]) + pending
        return unrotate(decode(ca, cb, blob[index]), unit)

    longest = 0
    for _, a, b in points:
        for pending in (False, True):
            state = a, b, pending
            path = []
            while state[:2] != (0, 0):
                action = table_action(state)
                assert action in tuple(options(*state[:2])), state
                path.append(action)
                state, _ = successor(state, action)
                assert len(path) <= 12, (a, b, pending)
            assert reconstruction(path) == (a, b)
            longest = max(longest, len(path))

    if TARGET.exists():
        assert TARGET.read_bytes() == blob, "frozen atlas changed"
    else:
        TARGET.write_bytes(blob)
    return {"limit": LIMIT, "canonical_points": count,
            "state_action_slots": len(actions), "bytes": len(blob),
            "max_tail_steps": longest, "sha256": hashlib.sha256(blob).hexdigest(),
            "old_cost_states_matched": len(old),
            "nonshrinking_actions_excluded": len(nonshrinking),
            "panel_source_M_plus_S": panels}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
