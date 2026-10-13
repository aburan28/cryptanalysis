#!/usr/bin/env python3
"""Encode Pareto-selected trees in the frozen 48-byte gauge plan format."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

from pareto import HERE, PRIOR, choose, search
from dag_depth import tree as dag_tree, load_module


def build():
    old_data = (PRIOR / "plans.bin").read_bytes()
    assert len(old_data) == 969 * 48
    old_format = load_module("dag_pareto_plan_format", PRIOR / "make_plans.py")
    records = bytearray()
    improved_patterns = 0
    max_frontier = 0
    for index, counts in enumerate(old_format.counts_in_order()):
        a, b, c = counts
        n = a + b + c
        assert index == n * (n + 1) * (n + 2) // 6 + a * (n + 1) - a * (a - 1) // 2 + b
        old_record = old_data[48 * index:48 * (index + 1)]
        old = dag_tree(counts, old_data)
        selected = choose(counts) if sum(counts) else None
        if selected is None:
            records.extend(old_record)
            continue
        steps = old_format.schedule(selected.tree, counts)
        work, weighted_path, rotations = old_format.replay(counts, steps)
        assert work == selected.node.work == old.work
        payload = bytearray(value for step in steps for value in step)
        payload.extend(bytes(45 - len(payload)))
        payload.extend((len(steps), rotations, weighted_path))
        assert len(payload) == 48
        records.extend(payload)
        improved_patterns += 1
        max_frontier = max(max_frontier, len(search(counts)))
    assert len(records) == 969 * 48
    new_data = bytes(records)
    for counts in old_format.counts_in_order():
        before = dag_tree(counts, old_data)
        after = dag_tree(counts, new_data)
        assert after.work == before.work
        assert after.depth() <= before.depth()
    return new_data, {"schema": 1,
                      "status": "all_pareto_plan_records_replayed",
                      "plans": 969, "table_bytes": len(records),
                      "improved_patterns": improved_patterns,
                      "max_frontier": max_frontier,
                      "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                      "pareto_source_sha256": sha256((HERE / "pareto.py").read_bytes()).hexdigest(),
                      "plan_sha256": sha256(new_data).hexdigest(),
                      "prior_plan_sha256": sha256(old_data).hexdigest()}


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
