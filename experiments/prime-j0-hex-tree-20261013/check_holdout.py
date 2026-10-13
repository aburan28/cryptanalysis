#!/usr/bin/env python3
"""Replay the fresh hex-tree panel against independent points and frozen cost model."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay  # noqa: E402
tree_spec = spec_from_file_location("hex_tree_screen", HERE / "screen.py")
assert tree_spec is not None and tree_spec.loader is not None
screen = module_from_spec(tree_spec)
sys.modules[tree_spec.name] = screen
tree_spec.loader.exec_module(screen)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    fixture_path = HERE / "holdout.json"
    serial_path = HERE / "holdout-serial.jsonl"
    tree_path = HERE / "holdout-native.jsonl"
    fixture = json.loads(fixture_path.read_text())
    serial = [json.loads(line) for line in serial_path.read_text().splitlines()]
    tree = [json.loads(line) for line in tree_path.read_text().splitlines()]
    assert len(serial) == len(tree) == len(fixture["cases"]) == 512
    tree_replay = replay.verify(fixture_path, tree_path)

    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("holdout_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("holdout_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    modeled = screen.panel([int(case["scalar_hex"], 16)
                            for case in fixture["cases"]], old, orbit, codes, digits)
    additions = serial_rotations = tree_rotations = 0
    for index, (case, a, b) in enumerate(zip(fixture["cases"], serial, tree)):
        expected = ("identity" if case["expected_identity"] else
                    f"{case['expected_x_hex']}:{case['expected_y_hex']}")
        assert a["index"] == b["index"] == case["index"] == index
        assert a["verified"] is True and b["verified"] is True
        assert a["point"] == b["point"] == expected
        assert a["retained_bytes"] == 11_505_936
        assert b["retained_bytes"] == 11_552_448
        gauges = screen.selected_gauges(int(case["scalar_hex"], 16),
                                        old, orbit, codes, digits)
        assert a["additions"] == b["additions"] == max(0, len(gauges) - 1)
        assert a["rotations"] == screen.serial_cost(gauges)[2]
        assert b["rotations"] == screen.tree_plan(tuple(sorted(gauges)))[2]
        additions += b["additions"]
        serial_rotations += a["rotations"]
        tree_rotations += b["rotations"]
    assert additions == modeled["additions"]
    assert serial_rotations == modeled["serial_rotations"]
    assert tree_rotations == modeled["tree_rotations"]
    assert tree_replay["rows_sha256"] == digest(tree_path)
    return {
        "schema": 1, "status": "fresh_holdout_correctness_pass",
        "frozen_evaluator_commit": fixture["frozen_evaluator_commit"],
        "fixture_sha256": digest(fixture_path),
        "serial_rows_sha256": digest(serial_path),
        "tree_rows_sha256": digest(tree_path),
        "serial_binary_sha256": json.loads(
            (HERE / "serial-native-receipt.json").read_text())["binary_sha256"],
        "tree_binary_sha256": json.loads((HERE / "native-receipt.json").read_text())["binary_sha256"],
        "model_source_sha256": digest(HERE / "screen.py"),
        "checker_source_sha256": digest(Path(__file__)),
        "independent_point_generator_sha256": digest(
            HERE.parent / "prime-j0-axis152-20261012/holdout2.py"),
        "cases": 512, "verified_serial": 512, "verified_tree": 512,
        "additions_each": additions, "serial_rotations": serial_rotations,
        "tree_rotations": tree_rotations, "model": modeled,
    }


if __name__ == "__main__":
    result = run()
    output = HERE / "holdout-receipt.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        if output.exists():
            raise SystemExit("holdout receipt exists; remove only after preserving its prior version")
        output.write_text(data)
    else:
        assert output.read_text() == data
    print(json.dumps({key: result[key] for key in
                      ("status", "cases", "additions_each", "serial_rotations",
                       "tree_rotations", "fixture_sha256")}, sort_keys=True))
