#!/usr/bin/env python3
"""Independently replay Q1477's complete one-target online transcript."""

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

from q1477_n53_online_target.freeze_protocol import render  # noqa: E402
from q1477_n53_online_target.validate_inputs import validate  # noqa: E402
from run_probe import curves, field  # noqa: E402

RUN = HERE / "runs/primary"
OUT = HERE / "audit_result.json"
BASE = PARENT / "q1468_n53_pair_oracle/inputs/base_points.txt"
MASK64 = (1 << 64) - 1
PHASES = ("target_query_generation", "target_PDP",
          "target_relation_check", "target_descent",
          "target_recovery_check")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_splitmix(state: int) -> tuple[int, int]:
    state = (state + 0x9e3779b97f4a7c15) & MASK64
    value = state
    value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & MASK64
    return state, value ^ (value >> 31)


def audit() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol == render()
    assert json.loads((HERE / "input_validation.json").read_text()) == \
        validate()
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert receipt["proposal_id"] == "Q1477"
    assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
    assert receipt["runner_source_sha256"] == sha(HERE / "run_stage.py")
    assert receipt["native_stdout_sha256"] == sha(RUN / "stdout.ndjson")
    assert receipt["native_stderr_sha256"] == sha(RUN / "stderr.txt")
    assert receipt["stage_config_id"] == protocol["stage_config_id"]
    assert receipt["stage_run_id"] == protocol["stage_run_id"]
    rows = [json.loads(line) for line in
            (RUN / "stdout.ndjson").read_text().splitlines()]
    assert len(rows) == 2 and receipt["native_exit_code"] == 0
    setup, online = rows
    assert setup == receipt["setup_report"]
    assert setup["mode"] == "setup" and online["mode"] == "online"
    assert setup["pair_table_entries"] == 3651700
    assert setup["duplicate_pair_sums"] == 0
    assert setup["table_field_calls"] == {
        "mul": 18279700, "sqr": 3789500, "inv": 2650}
    assert online["proposal_id"] == "Q1477"
    assert online["status"] == receipt["status"] == "verified"
    fixture = json.loads((HERE / "audit_fixture.json").read_text())
    assert fixture["workload_id"] == protocol["workload_id"]
    r = fixture["workload_record"]["subgroup_order"]
    generator = tuple(fixture["workload_record"]["generator"])
    target = tuple(fixture["workload_record"]["public_target"])
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    assert curve.mul(generator, r) is None
    base_lines = BASE.read_text().splitlines()[1:]
    log_lines = (HERE / "base_logs.txt").read_text().splitlines()[1:]
    points, columns, logs = [], [], []
    for index, (base_line, log_line) in enumerate(zip(base_lines, log_lines)):
        column, x, y = base_line.split()
        log_index, log_column, value = map(int, log_line.split())
        assert log_index == index and log_column == int(column)
        points.append((onb.fromCoords(int(x, 16)),
                       onb.fromCoords(int(y, 16))))
        columns.append(int(column))
        logs.append(value)
    assert len(points) == len(logs) == 2756
    attempts = online["attempts"]
    assert len(attempts) == online["attempt_count"]
    assert 1 <= len(attempts) <= protocol["attempt_limit"]
    phase_wall = {name: 0 for name in PHASES}
    phase_field = {name: {"mul": 0, "sqr": 0, "inv": 0}
                   for name in PHASES}
    state = protocol["target_shift_seed"]
    found = absent = censored = 0
    found_witness = None
    found_shift = None
    for index, attempt in enumerate(attempts):
        assert attempt["index"] == index
        if index:
            state, random_word = next_splitmix(state)
            shift = 1 + random_word % (r - 1)
        else:
            shift = 0
        assert attempt["shift_scalar"] == shift
        queried = curve.add(target, curve.mul(generator, shift))
        assert queried is not None
        assert attempt["queried_x_onb_hex"] == \
            format(onb.toCoords(queried[0]), "x")
        assert attempt["queried_y_onb_hex"] == \
            format(onb.toCoords(queried[1]), "x")
        phase_data = attempt["phases"]
        assert set(phase_data) == set(PHASES)
        for name in PHASES:
            phase = phase_data[name]
            assert phase["wall_ns"] >= 0
            assert phase["point_additions"] >= 0
            assert phase["point_doublings"] >= 0
            phase_wall[name] += phase["wall_ns"]
            for primitive in ("mul", "sqr", "inv"):
                count = phase["field_calls"][primitive]
                assert count >= 0
                phase_field[name][primitive] += count
        status = attempt["status"]
        if status == "found":
            found += 1
            assert index == len(attempts) - 1 and found == 1
            witness = attempt["witness_indices"]
            assert len(witness) == 4
            assert all(0 <= value < 2756 for value in witness)
            assert len({columns[value] for value in witness}) == 4
            sum_point = None
            for value in witness:
                sum_point = curve.add(sum_point, points[value])
            assert sum_point == queried
            shifted_log = sum(logs[value] for value in witness) % r
            recovered = (shifted_log - shift) % r
            assert recovered == online["recovered_scalar"]
            assert recovered == fixture["fixture_scalar"]
            assert curve.mul(generator, recovered) == target
            found_witness = witness
            found_shift = shift
        elif status == "absent":
            absent += 1
            assert attempt["witness_indices"] is None
            assert attempt["pair_sums_examined"] == 3651700
            assert attempt["complement_hits"] == attempt[
                "rejected_shared_columns"]
        else:
            assert status == "censored"
            censored += 1
            assert attempt["witness_indices"] is None
        assert 0 < attempt["pair_sums_examined"] <= 3651700
    assert (found, absent, censored) == (online["found"],
                                       online["absent"], online["censored"])
    assert found == 1
    assert sum(phase_wall.values()) == online["online_wall_ns"]
    assert online["setup_wall_ns_outside_online"] > setup["table_wall_ns"]
    return {
        "kind": "q1477_n53_one_target_audit", "proposal_id": "Q1477",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "status": "passed", "stage_config_id": protocol["stage_config_id"],
        "stage_run_id": protocol["stage_run_id"],
        "workload_id": protocol["workload_id"],
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": 2756, "folded_columns_K": 26,
        "attempt_count": len(attempts),
        "attempt_status_counts": {"found": found, "absent": absent,
                                  "censored": censored},
        "found_witness_indices": found_witness,
        "found_shift_scalar": found_shift,
        "recovered_scalar": online["recovered_scalar"],
        "fixture_scalar_matched": True,
        "online_wall_ns_exploratory": online["online_wall_ns"],
        "phase_wall_ns_exploratory": phase_wall,
        "phase_field_calls": phase_field,
        "setup_table_wall_ns_exploratory": setup["table_wall_ns"],
        "setup_table_field_calls": setup["table_field_calls"],
        "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        "peak_child_rss_units": receipt["peak_child_rss_units"],
        "input_validation_sha256": sha(HERE / "input_validation.json"),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "receipt_sha256": sha(RUN / "receipt.json"),
        "auditor_source_sha256": sha(Path(__file__)),
        "controlled_wall_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = audit()
    if args.emit:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(OUT.read_text())
    print(json.dumps({"status": "pass", "attempt_count":
                      result["attempt_count"], "recovered_scalar":
                      result["recovered_scalar"]}), flush=True)


if __name__ == "__main__":
    main()
