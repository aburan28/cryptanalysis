#!/usr/bin/env python3
"""Encode and independently replay every count-based low-work tree."""

from __future__ import annotations

from hashlib import sha256
import json
from math import comb
from pathlib import Path
import sys

from optimize import finish, greedy_cost

HERE = Path(__file__).resolve().parent
RECORD_BYTES = 48


def counts_in_order():
    for n in range(17):
        for a in range(n + 1):
            for b in range(n - a + 1):
                yield a, b, n - a - b


def schedule(tree, counts):
    n = sum(counts)
    active = list(range(n))
    next_leaf = [0, counts[0], counts[0] + counts[1]]
    next_id = n
    steps = []

    def visit(node):
        nonlocal next_id
        kind, gauge = node[:2]
        if kind == "leaf":
            leaf = next_leaf[gauge]
            next_leaf[gauge] += 1
            return leaf
        assert kind == "join"
        left = visit(node[2])
        right = visit(node[3])
        i, j = sorted((active.index(left), active.index(right)))
        steps.append((i, j, gauge))
        active.pop(j)
        active.pop(i)
        parent = next_id
        next_id += 1
        active.append(parent)
        return parent

    if tree:
        assert visit(tree) == active[0]
    assert next_leaf == [counts[0], counts[0] + counts[1], n]
    assert len(active) == (1 if n else 0)
    assert len(steps) == max(0, n - 1)
    return tuple(steps)


def replay(counts, steps):
    nodes = [(g, 0, 0, True) for g, count in enumerate(counts)
             for _ in range(count)]
    rotations = 0
    for i, j, gauge in steps:
        assert 0 <= i < j < len(nodes) and gauge in (0, 1, 2)
        left, right = nodes[i], nodes[j]
        ra, rb = int(left[0] != gauge), int(right[0] != gauge)
        products = 6 if left[3] and right[3] else 10 if left[3] or right[3] else 14
        joined = (gauge, max(left[1] + ra, right[1] + rb) + products,
                  left[2] + right[2] + products + ra + rb, False)
        rotations += ra + rb
        nodes.pop(j)
        nodes.pop(i)
        nodes.append(joined)
    if not nodes:
        return 0, 0, 0
    last = int(nodes[0][0] != 0)
    return nodes[0][2] + last, nodes[0][1] + last, rotations + last


def build():
    records = bytearray()
    changed = 0
    max_depth = max_work = max_rotations = 0
    for index, counts in enumerate(counts_in_order()):
        n = sum(counts)
        plan = finish(counts)
        steps = schedule(plan.tree, counts)
        assert replay(counts, steps) == (plan.work, plan.depth, plan.rotations)
        changed += plan.work < greedy_cost(counts)[0]
        encoded = bytearray()
        for step in steps:
            encoded.extend(step)
        encoded.extend(bytes(45 - len(encoded)))
        encoded.extend((len(steps), plan.rotations, plan.depth))
        assert len(encoded) == RECORD_BYTES
        assert index == comb(n + 2, 3) + counts[0] * (n + 1) - counts[0] * (counts[0] - 1) // 2 + counts[1]
        records.extend(encoded)
        max_depth = max(max_depth, plan.depth)
        max_work = max(max_work, plan.work)
        max_rotations = max(max_rotations, plan.rotations)
    assert len(records) == comb(19, 3) * RECORD_BYTES
    return bytes(records), {
        "schema": 1, "status": "all_count_plans_independently_replayed",
        "plans": comb(19, 3), "record_bytes": RECORD_BYTES,
        "table_bytes": len(records), "changed_work_plans": changed,
        "max_work": max_work, "max_depth": max_depth,
        "max_rotations": max_rotations,
        "plan_sha256": sha256(records).hexdigest(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "optimizer_sha256": sha256((HERE / "optimize.py").read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    data, receipt = build()
    output = HERE / "plans.bin"
    summary = HERE / "plans.json"
    if "--write" in sys.argv:
        assert not output.exists() and not summary.exists()
        output.write_bytes(data)
        summary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        assert output.read_bytes() == data
        assert json.loads(summary.read_text()) == receipt
    print(json.dumps(receipt, sort_keys=True))
