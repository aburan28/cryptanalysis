#!/usr/bin/env python3
"""Retain the frozen tree shapes and evaluate them in absolute gauge zero."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-dag-pareto-20261013"


def transform() -> tuple[bytes, dict]:
    old = (PRIOR / "plans.bin").read_bytes()
    assert len(old) == 969 * 48
    out = bytearray()
    saved_rotations = changed = 0
    for n in range(17):
        for a in range(n + 1):
            for b in range(n - a + 1):
                c = n - a - b
                index = n * (n + 1) * (n + 2) // 6 + a * (n + 1) - a * (a - 1) // 2 + b
                rec = bytearray(old[48 * index:48 * (index + 1)])
                assert len(rec) == 48 and rec[45] == max(0, n - 1)
                nodes = [(True, 0)] * n
                for k in range(0, 3 * rec[45], 3):
                    i, j, _ = rec[k:k + 3]
                    assert i < j < len(nodes)
                    left, right = nodes[i], nodes[j]
                    cost = (6 if left[0] and right[0] else
                            10 if left[0] or right[0] else 14)
                    depth = max(left[1], right[1]) + cost
                    nodes.pop(j)
                    nodes.pop(i)
                    nodes.append((False, depth))
                    rec[k + 2] = 0
                saved_rotations += rec[46]
                rec[46] = 0
                rec[47] = nodes[0][1] if nodes else 0
                assert rec[47] < 256
                changed += bytes(rec) != old[48 * index:48 * (index + 1)]
                out.extend(rec)
    assert len(out) == len(old)
    return bytes(out), {"schema": 1, "status": "absolute_gauge_plans_replayed",
                        "patterns": 969, "changed_patterns": changed,
                        "table_bytes": len(out), "saved_rotations_all_patterns": saved_rotations,
                        "parent_plan_sha256": sha256(old).hexdigest(),
                        "plan_sha256": sha256(out).hexdigest(),
                        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    data, receipt = transform()
    if "--write" in sys.argv:
        assert not (HERE / "plans.bin").exists()
        (HERE / "plans.bin").write_bytes(data)
        (HERE / "plans.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        assert (HERE / "plans.bin").read_bytes() == data
        assert json.loads((HERE / "plans.json").read_text()) == receipt
    print(json.dumps(receipt, sort_keys=True))
