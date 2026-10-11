#!/usr/bin/env python3
"""Independently audit Q1478's same-point rho collision certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1478_n53_rho_reference.control import build as control_build  # noqa: E402
from q1478_n53_rho_reference.freeze_protocol import render  # noqa: E402
from run_probe import curves, field  # noqa: E402

RUN = HERE / "runs/primary"
OUT = HERE / "audit_result.json"
MASK64 = (1 << 64) - 1
PHASES = ("target_validation", "target_walk_precompute",
          "target_walk_search", "target_recovery_check")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_splitmix(state: int) -> tuple[int, int]:
    state = (state + 0x9e3779b97f4a7c15) & MASK64
    value = state
    value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & MASK64
    return state, value ^ (value >> 31)


def replay_state(curve, generator, target, order: int,
                 record: dict) -> tuple[int, int] | None:
    a, b = record["a"], record["b"]
    assert 0 <= a < order and 0 <= b < order
    point = curve.add(curve.mul(generator, a), curve.mul(target, b))
    assert point is not None
    return point


def audit() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol == render()
    assert json.loads((HERE / "control_result.json").read_text()) == \
        control_build()
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert receipt["proposal_id"] == "Q1478"
    assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
    assert receipt["runner_source_sha256"] == sha(HERE / "run_stage.py")
    assert receipt["native_stdout_sha256"] == sha(RUN / "stdout.json")
    assert receipt["native_stderr_sha256"] == sha(RUN / "stderr.txt")
    assert receipt["rho_reference_id"] == protocol["rho_reference_id"]
    assert receipt["workload_id"] == protocol["workload_id"]
    assert receipt["native_exit_code"] == 0
    assert receipt["status"] == "verified"
    report = json.loads((RUN / "stdout.json").read_text())
    assert report["proposal_id"] == "Q1478"
    assert report["status"] == "verified"
    assert report["worker_count"] == 1
    assert report["partition_count"] == 16
    assert report["distinguished_bits"] == 10
    fixture = json.loads((PARENT / "q1477_n53_online_target/"
                          "audit_fixture.json").read_text())
    assert fixture["workload_id"] == protocol["workload_id"]
    order = fixture["workload_record"]["subgroup_order"]
    generator = tuple(fixture["workload_record"]["generator"])
    target = tuple(fixture["workload_record"]["public_target"])
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    cert = report["collision_certificate"]
    assert cert is not None
    old_point = replay_state(curve, generator, target, order, cert["old"])
    new_point = replay_state(curve, generator, target, order, cert["new"])
    assert old_point == new_point
    assert cert["old"]["x_onb_hex"] == \
        cert["new"]["x_onb_hex"] == format(onb.toCoords(old_point[0]), "x")
    assert cert["old"]["y_onb_hex"] == \
        cert["new"]["y_onb_hex"] == format(onb.toCoords(old_point[1]), "x")
    assert (onb.toCoords(old_point[0]) & 1023) == 0
    numerator = (cert["old"]["a"] - cert["new"]["a"]) % order
    denominator = (cert["new"]["b"] - cert["old"]["b"]) % order
    assert numerator == cert["numerator"]
    assert denominator == cert["denominator"] and denominator != 0
    recovered = numerator * pow(denominator, -1, order) % order
    assert recovered == report["recovered_scalar"]
    assert recovered == fixture["fixture_scalar"]
    assert curve.mul(generator, recovered) == target
    phase_wall = {name: report["phases"][name]["wall_ns"]
                  for name in PHASES}
    assert sum(phase_wall.values()) == report["online_wall_ns"]
    assert phase_wall["target_validation"] > 0
    assert report["setup_wall_ns_outside_online"] > 0
    walks = report["walks"]
    assert len(walks) == report["walk_count"]
    assert sum(row["steps"] for row in walks) == report["walk_steps"]
    assert walks[-1]["status"] == "collision"
    assert report["walk_steps"] <= 50000000
    assert report["duplicate_endpoints"] >= 1
    assert report["distinguished_points_stored"] <= len(walks)
    for row in walks:
        assert row["status"] in ("distinguished", "collision",
                                 "abandoned_or_capped")
        if row["status"] != "abandoned_or_capped":
            assert int(row["endpoint_x_onb_hex"], 16) & 1023 == 0
            assert row["steps"] > 0
    assert walks[-1]["endpoint_x_onb_hex"] == cert[
        "new"]["x_onb_hex"]
    assert walks[-1]["endpoint_y_onb_hex"] == cert[
        "new"]["y_onb_hex"]

    # Replay three early transitions through the independent Python field
    # and group law, including the frozen partition and PRNG policies.
    state = 14780053
    jumps = []
    for _ in range(16):
        state, word_a = next_splitmix(state)
        state, word_b = next_splitmix(state)
        a, b = 1 + word_a % (order - 1), 1 + word_b % (order - 1)
        jumps.append(curve.add(curve.mul(generator, a),
                               curve.mul(target, b)))
    checked_walks = 0
    for row in walks[:3]:
        state, word_a = next_splitmix(state)
        state, word_b = next_splitmix(state)
        a, b = 1 + word_a % (order - 1), 1 + word_b % (order - 1)
        assert a == row["start_a"] and b == row["start_b"]
        point = curve.add(curve.mul(generator, a), curve.mul(target, b))
        assert point is not None
        for step_index in range(row["steps"]):
            partition = (onb.toCoords(point[0]) & 15) if point else 0
            point = curve.add(point, jumps[partition])
            if step_index + 1 < row["steps"]:
                assert point is None or (onb.toCoords(point[0]) & 1023)
        if row["status"] in ("distinguished", "collision"):
            assert point is not None
            assert format(onb.toCoords(point[0]), "x") == row[
                "endpoint_x_onb_hex"]
            assert format(onb.toCoords(point[1]), "x") == row[
                "endpoint_y_onb_hex"]
        checked_walks += 1
    return {
        "kind": "q1478_same_point_rho_audit", "proposal_id": "Q1478",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "status": "passed", "curve_id": protocol["curve_id"],
        "rho_reference_id": protocol["rho_reference_id"],
        "workload_id": protocol["workload_id"],
        "recovered_scalar": recovered,
        "fixture_scalar_matched": True,
        "collision_certificate_replayed": True,
        "independent_walk_prefix_replays": checked_walks,
        "online_wall_ns_exploratory": report["online_wall_ns"],
        "phase_wall_ns_exploratory": phase_wall,
        "phase_field_calls": {name: report["phases"][name]["field_calls"]
                              for name in PHASES},
        "phase_point_additions": {name: report["phases"][name][
            "point_additions"] for name in PHASES},
        "phase_point_doublings": {name: report["phases"][name][
            "point_doublings"] for name in PHASES},
        "walk_steps": report["walk_steps"],
        "walk_count": report["walk_count"],
        "distinguished_points_stored": report[
            "distinguished_points_stored"],
        "duplicate_endpoints": report["duplicate_endpoints"],
        "degenerate_collisions": report["degenerate_collisions"],
        "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        "peak_child_rss_units": receipt["peak_child_rss_units"],
        "q1477_target_fixture_sha256": sha(PARENT /
            "q1477_n53_online_target/audit_fixture.json"),
        "control_result_sha256": sha(HERE / "control_result.json"),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "receipt_sha256": sha(RUN / "receipt.json"),
        "auditor_source_sha256": sha(Path(__file__)),
        "controlled_online_speedup": None,
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
    print(json.dumps({"status": "pass", "walk_steps":
                      result["walk_steps"], "recovered_scalar":
                      result["recovered_scalar"]}), flush=True)


if __name__ == "__main__":
    main()
