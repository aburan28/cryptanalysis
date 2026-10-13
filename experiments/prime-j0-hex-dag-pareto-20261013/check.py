#!/usr/bin/env python3
"""Independently replay points, native plan counts, and formula DAG scores."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "prime-j0-hex-tree-20261013"))
sys.path.insert(0, str(EXP / "prime-j0-hex-workdepth-20261013"))
import replay  # noqa: E402
from dag_depth import tree, load_module  # noqa: E402


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def check(fixture_path: Path, rows_path: Path) -> dict:
    point_receipt = replay.verify(fixture_path, rows_path)
    fixture = json.loads(fixture_path.read_text())
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    screen = load_module("pareto_checker_screen", EXP / "prime-j0-hex-tree-20261013/screen.py")
    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("pareto_checker_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("pareto_checker_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    old_table = (EXP / "prime-j0-hex-workdepth-20261013/plans.bin").read_bytes()
    new_table = (HERE / "plans.bin").read_bytes()
    totals = {"old_work": 0, "new_work": 0, "old_dag_depth": 0,
              "new_dag_depth": 0, "improved_cases": 0, "rotations": 0}
    for case, row in zip(fixture["cases"], rows):
        gauges = screen.selected_gauges(int(case["scalar_hex"], 16),
                                        old, orbit, codes, digits)
        counts = tuple(gauges.count(g) for g in range(3))
        before, after = tree(counts, old_table), tree(counts, new_table)
        assert after.work == before.work
        assert after.depth() <= before.depth()
        assert row["additions"] == max(0, len(gauges) - 1)
        record_index = (sum(counts) * (sum(counts) + 1) * (sum(counts) + 2) // 6
                        + counts[0] * (sum(counts) + 1)
                        - counts[0] * (counts[0] - 1) // 2 + counts[1])
        assert row["rotations"] == new_table[48 * record_index + 46]
        totals["old_work"] += before.work
        totals["new_work"] += after.work
        totals["old_dag_depth"] += before.depth()
        totals["new_dag_depth"] += after.depth()
        totals["improved_cases"] += after.depth() < before.depth()
        totals["rotations"] += row["rotations"]
    assert totals["rotations"] == point_receipt["rotations"]
    return {"schema": 1, "status": "native_point_plan_and_dag_replay_pass",
            **point_receipt, **totals, "plan_sha256": digest(HERE / "plans.bin"),
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
