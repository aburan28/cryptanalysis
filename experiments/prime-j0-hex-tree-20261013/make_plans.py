#!/usr/bin/env python3
"""Freeze all gauge-count tree plans for at most sixteen selected points."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import comb
from pathlib import Path

from screen import tree_plan

HERE = Path(__file__).resolve().parent
PLAN_BYTES = 48  # fifteen three-byte joins, then length, rotations, depth
PLAN_COUNT = comb(19, 3)


def counts_in_order():
    for size in range(17):
        for a in range(size + 1):
            for b in range(size - a + 1):
                yield a, b, size - a - b


def index_of(counts: tuple[int, int, int]) -> int:
    a, b, c = counts
    size = a + b + c
    return comb(size + 2, 3) + a * (size + 1) - a * (a - 1) // 2 + b


def replay(counts, steps):
    nodes = [(g, 0, 0, True) for g, count in enumerate(counts)
             for _ in range(count)]
    rotations = 0
    for i, j, gauge in steps:
        assert 0 <= i < j < len(nodes) and gauge in (0, 1, 2)
        left, right = nodes[i], nodes[j]
        ra, rb = int(left[0] != gauge), int(right[0] != gauge)
        products = (6 if left[3] and right[3] else
                    10 if left[3] or right[3] else 14)
        depth = max(left[1] + ra, right[1] + rb) + products
        work = left[2] + right[2] + products + ra + rb
        rotations += ra + rb
        nodes.pop(j)
        nodes.pop(i)
        nodes.append((gauge, depth, work, False))
    if not nodes:
        assert not steps
        return 0, 0, 0
    assert len(nodes) == 1
    gauge, depth, work, _ = nodes[0]
    last = int(gauge != 0)
    return work + last, depth + last, rotations + last


def build():
    records = bytearray()
    max_depth = max_work = max_rotations = 0
    for position, counts in enumerate(counts_in_order()):
        assert index_of(counts) == position
        gauges = tuple(g for g, count in enumerate(counts)
                       for _ in range(count))
        work, depth, rotations, steps = tree_plan(gauges)
        assert len(steps) == max(0, len(gauges) - 1)
        assert replay(counts, steps) == (work, depth, rotations)
        payload = bytearray()
        for step in steps:
            payload.extend(step)
        payload.extend(bytes(45 - len(payload)))
        payload.extend((len(steps), rotations, depth))
        assert len(payload) == PLAN_BYTES
        records.extend(payload)
        max_depth = max(max_depth, depth)
        max_work = max(max_work, work)
        max_rotations = max(max_rotations, rotations)
    assert len(records) == PLAN_COUNT * PLAN_BYTES
    receipt = {"schema": 1, "status": "all_plan_indices_replayed",
               "plans": PLAN_COUNT, "record_bytes": PLAN_BYTES,
               "table_bytes": len(records), "max_depth": max_depth,
               "max_work": max_work, "max_rotations": max_rotations,
               "plan_sha256": sha256(records).hexdigest(),
               "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "screen_source_sha256": sha256((HERE / "screen.py").read_bytes()).hexdigest()}
    return bytes(records), receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data, receipt = build()
    binary = HERE / "plans.bin"
    summary = HERE / "plans.json"
    if args.write:
        binary.write_bytes(data)
        summary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        if binary.read_bytes() != data or json.loads(summary.read_text()) != receipt:
            raise SystemExit("plan artifacts differ")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
