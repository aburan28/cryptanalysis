#!/usr/bin/env python3
"""Compare three native schedules on the same independent scalar panel."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

from check import check
from optimize import panel

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-tree-20261013"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run() -> dict:
    fixture_path = HERE / "holdout.json"
    cases = json.loads(fixture_path.read_text())["cases"]
    streams = {name: rows(HERE / f"holdout-{name}.jsonl")
               for name in ("serial", "greedy", "native")}
    assert all(len(stream) == len(cases) == 512 for stream in streams.values())
    tree = check(fixture_path, HERE / "holdout-native.jsonl")
    model = panel(fixture_path)
    assert tree["modeled_work"] == model["optimized_work"]
    assert tree["modeled_depth"] == model["optimized_depth"]
    assert tree["rotations"] == model["optimized_rotations"]
    totals = {}
    for name, stream in streams.items():
        expected_bytes = 11_505_936 if name == "serial" else 11_552_448
        for index, (case, row) in enumerate(zip(cases, stream)):
            expected = ("identity" if case["expected_identity"] else
                        f"{case['expected_x_hex']}:{case['expected_y_hex']}")
            assert row["index"] == case["index"] == index
            assert row["verified"] is True and row["point"] == expected
            assert row["retained_bytes"] == expected_bytes
            assert row["additions"] == streams["native"][index]["additions"]
        totals[name] = {"verified": len(stream),
                        "additions": sum(row["additions"] for row in stream),
                        "rotations": sum(row["rotations"] for row in stream),
                        "retained_bytes": expected_bytes,
                        "rows_sha256": digest(HERE / f"holdout-{name}.jsonl")}
    assert {name: data["additions"] for name, data in totals.items()} == {
        name: 7680 for name in totals}
    assert totals["greedy"]["rotations"] == model["greedy_rotations"]
    assert totals["native"]["rotations"] == model["optimized_rotations"]
    assert totals["serial"]["rotations"] == model["optimized_rotations"]
    return {"schema": 1, "status": "fresh_three_way_point_and_model_pass",
            "fixture_sha256": digest(fixture_path),
            "frozen_evaluator_commit": json.loads(fixture_path.read_text())["frozen_evaluator_commit"],
            "streams": totals, "model": model,
            "serial_modeled_work": 10 * totals["serial"]["additions"] + totals["serial"]["rotations"],
            "checker_sha256": digest(Path(__file__)),
            "new_plan_sha256": digest(HERE / "plans.bin"),
            "new_binary_sha256": json.loads((HERE / "native-receipt.json").read_text())["binary_sha256"],
            "greedy_binary_sha256": json.loads((PRIOR / "native-receipt.json").read_text())["binary_sha256"],
            "serial_binary_sha256": json.loads((PRIOR / "serial-native-receipt.json").read_text())["binary_sha256"]}


if __name__ == "__main__":
    result = run()
    output = HERE / "comparison.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        assert not output.exists()
        output.write_text(data)
    else:
        assert output.read_text() == data
    print(json.dumps({"status": result["status"],
                      "model": result["model"],
                      "serial_modeled_work": result["serial_modeled_work"]},
                     sort_keys=True))
