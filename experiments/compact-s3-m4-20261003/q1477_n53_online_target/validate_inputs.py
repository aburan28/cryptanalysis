#!/usr/bin/env python3
"""Independently replay every precomputed Q1477 base-point logarithm."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1477_n53_online_target.make_inputs import render  # noqa: E402
from run_probe import curves, field  # noqa: E402

OUT = HERE / "input_validation.json"
BASE = PARENT / "q1468_n53_pair_oracle/inputs/base_points.txt"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict:
    expected = render()
    assert all(path.read_bytes() == content for path, content in expected.items())
    fixture = json.loads((HERE / "audit_fixture.json").read_text())
    manifest = json.loads((HERE / "input_manifest.json").read_text())
    assert fixture["workload_id"] == manifest["workload_id"]
    assert manifest["target_file_sha256"] == sha(HERE / "target.txt")
    assert manifest["base_logs_sha256"] == sha(HERE / "base_logs.txt")
    assert manifest["q1468_base_points_sha256"] == sha(BASE)
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(fixture["workload_record"]["generator"])
    target = tuple(fixture["workload_record"]["public_target"])
    r = fixture["workload_record"]["subgroup_order"]
    assert curve.mul(generator, r) is None
    assert curve.mul(generator, fixture["fixture_scalar"]) == target
    assert curve.mul(target, r) is None
    base_lines = BASE.read_text().splitlines()
    log_lines = (HERE / "base_logs.txt").read_text().splitlines()
    assert base_lines[0] == "Q1468BASE1 53 2756 26"
    assert log_lines[0] == f"Q1477LOGS1 53 2756 26 {r}"
    assert len(base_lines) == len(log_lines) == 2757
    checked = 0
    for index, (base_line, log_line) in enumerate(zip(base_lines[1:],
                                                      log_lines[1:])):
        base_column, x, y = base_line.split()
        log_index, log_column, value = map(int, log_line.split())
        assert log_index == index and log_column == int(base_column)
        assert 0 <= value < r
        point = (onb.fromCoords(int(x, 16)),
                 onb.fromCoords(int(y, 16)))
        assert curve.onCurve(point)
        assert curve.mul(generator, value) == point, index
        checked += 1
    target_lines = (HERE / "target.txt").read_text().splitlines()
    assert target_lines[0] == f"Q1477TARGET1 53 {r}"
    for rendered, point in zip(target_lines[1:], (generator, target)):
        x, y = (int(component, 16) for component in rendered.split())
        assert (onb.fromCoords(x), onb.fromCoords(y)) == point
    return {
        "kind": "q1477_pre_run_input_validation", "proposal_id": "Q1477",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "status": "passed", "base_point_log_replays": checked,
        "target_fixture_scalar_replayed": True,
        "workload_id": fixture["workload_id"],
        "input_manifest_sha256": sha(HERE / "input_manifest.json"),
        "base_logs_sha256": sha(HERE / "base_logs.txt"),
        "target_file_sha256": sha(HERE / "target.txt"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "validator_source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = validate()
    if args.emit:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(OUT.read_text()) == result
    print(json.dumps({"status": "pass", "base_point_log_replays":
                      result["base_point_log_replays"]}), flush=True)


if __name__ == "__main__":
    main()
