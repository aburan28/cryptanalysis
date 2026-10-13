#!/usr/bin/env python3
"""Check native points and operation counts against a frozen fixture and plan."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-tree-20261013"
sys.path.insert(0, str(PRIOR))
import replay  # noqa: E402
from optimize import finish, load_module  # noqa: E402


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def check(fixture_path: Path, rows_path: Path) -> dict:
    base = replay.verify(fixture_path, rows_path)
    fixture = json.loads(fixture_path.read_text())
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    screen = load_module("workdepth_checker_screen", PRIOR / "screen.py")
    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("workdepth_checker_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("workdepth_checker_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    work = depth = rotations = 0
    for case, row in zip(fixture["cases"], rows):
        gauges = screen.selected_gauges(int(case["scalar_hex"], 16),
                                        old, orbit, codes, digits)
        counts = tuple(gauges.count(g) for g in range(3))
        plan = finish(counts)
        assert row["additions"] == max(0, len(gauges) - 1)
        assert row["rotations"] == plan.rotations
        work += plan.work
        depth += plan.depth
        rotations += plan.rotations
    assert rotations == base["rotations"]
    return {"schema": 1, "status": "native_point_and_plan_counts_pass",
            **base, "modeled_work": work, "modeled_depth": depth,
            "plan_sha256": digest(HERE / "plans.bin"),
            "optimizer_sha256": digest(HERE / "optimize.py"),
            "checker_sha256": digest(Path(__file__))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("rows", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = check(args.fixture, args.rows)
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.write:
        assert not args.receipt.exists()
        args.receipt.write_text(data)
    else:
        assert args.receipt.read_text() == data
    print(json.dumps({key: result[key] for key in
                      ("cases", "additions", "rotations", "modeled_work",
                       "modeled_depth")}, sort_keys=True))
