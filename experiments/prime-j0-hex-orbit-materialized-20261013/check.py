#!/usr/bin/env python3
"""Check absolute-gauge native rows and the compressed-orbit cost model."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "prime-j0-hex-workdepth-20261013"))
from dag_depth import Node, join, tree, load_module, plan_index  # noqa: E402

ENTRIES = 174_883
EXPECTED_BYTES = 11_552_448 + 32 * ENTRIES


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def absolute_tree(counts: tuple[int, int, int], plans: bytes) -> Node:
    n = sum(counts)
    record = plans[48 * plan_index(counts):48 * (plan_index(counts) + 1)]
    assert len(record) == 48 and record[45] == max(0, n - 1)
    nodes = [Node(0, True) for _ in range(n)]
    for k in range(0, 3 * record[45], 3):
        i, j, gauge = record[k:k + 3]
        assert i < j < len(nodes) and gauge == 0
        result = join(nodes[i], nodes[j], 0)
        nodes.pop(j)
        nodes.pop(i)
        nodes.append(result)
    assert record[46] == 0
    return nodes[0] if nodes else Node(0, False)


def check(fixture_path: Path, rows_path: Path) -> dict:
    fixture = json.loads(fixture_path.read_text())
    cases = fixture["cases"]
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert len(cases) == len(rows) and len({c["scalar_hex"] for c in cases}) == len(cases)
    screen = load_module("orbit_materialized_screen", EXP / "prime-j0-hex-tree-20261013/screen.py")
    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("orbit_materialized_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("orbit_materialized_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    new_plans = (HERE / "plans.bin").read_bytes()
    old_plans = (EXP / "prime-j0-hex-dag-pareto-20261013/plans.bin").read_bytes()
    totals = {"verified": 0, "additions": 0, "rotations": 0,
              "old_work": 0, "new_work": 0, "old_dag_depth": 0,
              "new_dag_depth": 0, "saved_calls": 0}
    for case, row in zip(cases, rows):
        expected = ("identity" if case["expected_identity"] else
                    f"{case['expected_x_hex']}:{case['expected_y_hex']}")
        assert row["index"] == case["index"] and row["verified"] is True
        assert row["point"] == expected
        assert row["retained_bytes"] == EXPECTED_BYTES
        gauges = screen.selected_gauges(int(case["scalar_hex"], 16),
                                        old, orbit, codes, digits)
        counts = tuple(gauges.count(g) for g in range(3))
        before, after = tree(counts, old_plans), absolute_tree(counts, new_plans)
        assert after.work <= before.work and after.depth() <= before.depth()
        assert row["additions"] == max(0, len(gauges) - 1)
        assert row["rotations"] == 0
        assert after.work == (10 * len(gauges) - 14 if len(gauges) >= 2 else 0)
        totals["verified"] += 1
        totals["additions"] += row["additions"]
        totals["rotations"] += row["rotations"]
        totals["old_work"] += before.work
        totals["new_work"] += after.work
        totals["old_dag_depth"] += before.depth()
        totals["new_dag_depth"] += after.depth()
        totals["saved_calls"] += before.work - after.work
    assert totals["verified"] == len(cases)
    return {"schema": 1, "status": "absolute_gauge_native_points_and_model_pass",
            "cases": len(cases), **totals, "retained_bytes": EXPECTED_BYTES,
            "fixture_sha256": digest(fixture_path), "rows_sha256": digest(rows_path),
            "plan_sha256": digest(HERE / "plans.bin"),
            "checker_sha256": digest(Path(__file__))}


if __name__ == "__main__":
    fixture_path, rows_path = (Path(p) for p in sys.argv[1:3])
    result = check(fixture_path, rows_path)
    if "--write" in sys.argv:
        output = HERE / ("calibration-check.json" if "calibration" in rows_path.name
                         else "holdout-check.json")
        assert not output.exists()
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
