#!/usr/bin/env python3
"""Replay Q1473 selector-work receipts and the exact N83 target."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PARENT / "q20261011_wdsat_shared_prefix"))
from phase_schedule import INDICES, phases  # noqa: E402
from prepare import evaluate  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_parent_validator():
    path = Q1472 / "validate.py"
    spec = importlib.util.spec_from_file_location("q1472_validator_for_q1473", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def receipt(kind: str, phase: int) -> tuple[dict, Path] | None:
    directory = HERE / "runs" / kind / f"phase{phase}"
    path = directory / "receipt.json"
    return (json.loads(path.read_text()), directory) if path.exists() else None


def verify_smoke(build: dict) -> None:
    smoke = json.loads((HERE / "smoke_receipt.json").read_text())
    source = (HERE / "smoke.xcnf").read_bytes()
    assert smoke["status"] == "PASS" and smoke["proposal_id"] == "Q1473"
    assert smoke["source_sha256"] == sha(HERE / "smoke.py")
    assert smoke["input_sha256"] == hashlib.sha256(source).hexdigest()
    assert smoke["binary_sha256"] == build["binary_sha256"]
    assert smoke["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert len(smoke["rows"]) == len(INDICES)
    binary = build["binary_path"]
    for phase, saved in enumerate(smoke["rows"]):
        assert saved["phase"] == phase
        assert saved["flip_ids"] == phases()[phase]["flip_ids"]
        env = os.environ.copy()
        env["Q1469_ORDER_MODE"] = "selector_pair_mids"
        env["Q1472_PHASE_INDEX"] = "0"
        env["Q1473_SELECTOR_PHASE"] = str(phase)
        replay = subprocess.run([binary, "-i", str(HERE / "smoke.xcnf")],
                                env=env, capture_output=True, timeout=60)
        assert replay.returncode == 0
        assert hashlib.sha256(replay.stdout).hexdigest() == saved["stdout_sha256"]
        assert hashlib.sha256(replay.stderr).hexdigest() == saved["stderr_sha256"]
        models = [line.strip() for line in replay.stdout.decode().splitlines()
                  if len(line.strip()) == 2141 and
                  set(line.strip()) <= {"0", "1"}]
        assert len(models) == 1
        model = {i + 1: bit == "1" for i, bit in enumerate(models[0])}
        assert evaluate(source, model) == saved["replay"]


def verify_row(kind: str, phase: int, row: dict, directory: Path,
               freeze: dict, protocol: dict, build: dict, target: dict,
               cells: dict[str, tuple[bytes, bytes]]) -> None:
    cell = freeze["cells"][kind]
    assert row["proposal_id"] == "Q1473" and row["candidate_id"] is None
    assert row["phase_index"] == phase and row["kind"] == kind
    assert row["phase_flip_ids"] == freeze["phase_schedule"][str(phase)]["flip_ids"]
    assert row["phase_seed"] is None
    assert row["curve_id"] == protocol["curve_id"] == cell["curve_id"]
    assert row["workload_id"] == cell["workload_id"]
    assert row["public_target"] == cell["public_target"]
    assert row["factor_base_actual_B"] == target["factor_base_actual_B"]
    assert row["factor_base_folded_columns_K"] == target[
        "factor_base_folded_columns_K"]
    assert row["protocol_sha256"] == sha(HERE / "protocol.json")
    assert row["freeze_sha256"] == sha(HERE / "freeze.json")
    assert row["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert row["target_sha256"] == sha(HERE / "target.json")
    assert row["runner_sha256"] == freeze["runner_source_sha256"]
    assert row["binary_sha256"] == build["binary_sha256"]
    assert row["archive_sha256"] == cell["derived_archive_sha256"]
    assert row["source_archive_sha256"] == cell["source_archive_sha256"]
    assert row["left_branch_attempt_limit"] == protocol["limits"][
        "left_branch_attempts_per_phase"]
    if row["status"] == "CENSORED_BEFORE_SEARCH":
        assert row["timed_out"] and not row["search_started"]
        assert row["after_xor_init"]
        assert not row["order_marker_seen"] and not row["phase_marker_seen"]
    else:
        assert row["order_marker_seen"] and row["phase_marker_seen"]
        assert row["search_started"] and row["after_xor_init"]
    stdout_path = directory / "solver.stdout.txt"
    stderr_path = directory / "solver.stderr.txt"
    assert sha(stdout_path) == row["stdout_sha256"]
    assert sha(stderr_path) == row["stderr_sha256"]
    stderr = stderr_path.read_text()
    if row["status"] == "CENSORED_BEFORE_SEARCH":
        assert stderr.splitlines().count("Q1472_PHASE 0 0") == 0
        assert stderr.splitlines().count(
            f"Q1473_SELECTOR_PHASE {phase} 2140 2141") == 0
    else:
        assert stderr.splitlines().count("Q1472_PHASE 0 0") == 1
        assert stderr.splitlines().count(
            f"Q1473_SELECTOR_PHASE {phase} 2140 2141") == 1
    checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                stderr, re.MULTILINE)]
    assert checkpoints == row["branch_checkpoints"]
    assert checkpoints == [1 << i for i in range(len(checkpoints))]
    work = [list(map(int, values)) for values in re.findall(
        r"^Q1473_WORK (\d+) (\d+) (\d+)$", stderr, re.MULTILINE)]
    assert work == row["work_checkpoints"]
    assert [x[0] for x in work] == checkpoints
    assert row["branch_lower_bound"] == (checkpoints[-1] if checkpoints else 0)
    assert row["cnf_set_true_calls_lower_bound"] == (work[-1][1] if work else 0)
    assert row["xor_set_true_calls_lower_bound"] == (work[-1][2] if work else 0)
    finals = [list(map(int, values)) for values in re.findall(
        r"^Q1473_WORK_FINAL (\d+) (\d+)$", stderr, re.MULTILINE)]
    assert len(finals) <= 1
    assert row["cnf_set_true_calls_final"] == (finals[0][0] if finals else None)
    assert row["xor_set_true_calls_final"] == (finals[0][1] if finals else None)
    if row["status"] == "CENSORED_BEFORE_SEARCH":
        assert not checkpoints and not work and not finals
    if row["status"] == "BRANCH_CAP_REACHED":
        assert row["return_code"] == 42
        assert row["branch_exact_at_cap"] == 1 << 20
        assert row["branch_lower_bound"] == 1 << 20
        assert len(finals) == 1
        assert finals[0] == work[-1][1:]
    if row["status"] in ("SAT_REPLAYED_XCNF", "VERIFIED_RELATION"):
        width = cell["derived_variables"]
        models = [line.strip() for line in stdout_path.read_text().splitlines()
                  if len(line.strip()) == width and set(line.strip()) <= {"0", "1"}]
        assert len(models) == 1
        model = {i + 1: bit == "1" for i, bit in enumerate(models[0])}
        original, derived = cells[kind]
        replay = {"derived": evaluate(derived, model),
                  "original": evaluate(original, {i: model[i] for i in range(
                      1, cell["original_variables"] + 1)})}
        assert row["xcnf_replay"] == replay
        assert len(finals) == 1
    if row["status"] == "VERIFIED_RELATION":
        assert kind == "ordinary"
        group = row["group_replay"]
        assert group["status"] == "verified_four_point_relation"
        assert group["distinct_columns"] == 4
        assert group["public_target"] == target["public_target"]
        assert len(group["raw_leaf_x"]) == len(group["signs"]) == 4
        from run_probe import curves, field  # noqa: E402
        onb = field.Onb(83)
        curve = curves.Curve(onb)
        total = None
        for x_coord, sign in zip(group["raw_leaf_x"], group["signs"]):
            assert sign in (-1, 1)
            point = curve.pointFromX(onb.fromCoords(x_coord))
            assert point is not None
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        assert total is not None and curve.mul(total, 4) == tuple(target[
            "public_target"])


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert protocol["proposal_id"] == freeze["proposal_id"] == "Q1473"
    assert protocol["candidate_id"] is freeze["candidate_id"] is None
    assert protocol["workload_id"] == target["workload_id"]
    assert protocol["isogeny"] == target["isogeny"] == "none"
    assert freeze["phase_schedule"] == {str(i): phases()[i] for i in INDICES}
    for name, path in (("protocol", "protocol.json"),
                       ("runtime_info", "sage_runtime_info.json"),
                       ("target", "target.json"),
                       ("phase_source", "phase_schedule.py"),
                       ("build_source", "build.py"),
                       ("runner_source", "run.py"),
                       ("drive_source", "drive.py"),
                       ("freeze_source", "freeze.py")):
        assert freeze[f"{name}_sha256"] == sha(HERE / path)
    assert freeze["q1472_freeze_sha256"] == sha(Q1472 / "freeze.json")
    assert freeze["q1472_build_source_sha256"] == sha(Q1472 / "build.py")
    assert freeze["q1472_build_receipt_sha256"] == sha(Q1472 / "build_receipt.json")
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["selector_patch"]["phase_masks"] == freeze["phase_schedule"]
    assert build["selector_patch"]["selector_ids"] == [2140, 2141]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    verify_smoke(build)
    parent_validator = load_parent_validator()
    cells = {kind: parent_validator.verify_cell(kind, freeze, target)
             for kind in ("control", "ordinary")}
    parent_validator.verify_target(target, *cells["ordinary"])
    statuses = {}
    for kind in ("control", "ordinary"):
        rows = []
        for phase in INDICES:
            entry = receipt(kind, phase)
            if entry is None:
                assert all(receipt(kind, later) is None for later in INDICES
                           if later > phase)
                break
            row, directory = entry
            verify_row(kind, phase, row, directory, freeze, protocol, build,
                       target, cells)
            rows.append(row)
        statuses[kind] = rows
    assert drive["proposal_id"] == "Q1473" and drive["target_count"] == 1
    assert drive["workload_id"] == target["workload_id"]
    assert drive["source_sha256"] == sha(HERE / "drive.py")
    assert len(drive["controls"]) == len(statuses["control"])
    assert len(drive["ordinary_attempts"]) == len(statuses["ordinary"])
    for kind, key in (("control", "controls"), ("ordinary", "ordinary_attempts")):
        for phase, row in enumerate(statuses[kind]):
            entry = drive[key][phase]
            assert entry["phase"] == phase and entry["status"] == row["status"]
            assert entry["receipt_sha256"] == sha(HERE / "runs" / kind /
                                                   f"phase{phase}" / "receipt.json")
    ordinary = statuses["ordinary"]
    assert drive["new_ordinary_branch_lower_bound"] == sum(
        x["branch_lower_bound"] for x in ordinary)
    assert drive["new_ordinary_solver_child_user_cpu_seconds_exploratory"] == sum(
        x["user_cpu_seconds"] for x in ordinary)
    assert drive["new_ordinary_wall_seconds_exploratory"] == sum(
        x["run_wall_seconds_exploratory"] for x in ordinary)
    parent_drive = Q1472 / "drive_receipt.json"
    assert drive["prior_q1472_drive_sha256"] == sha(parent_drive)
    parent = json.loads(parent_drive.read_text())
    assert drive["cumulative_same_target_wall_seconds_exploratory"] == (
        parent["total_target_dependent_wall_seconds_exploratory"] +
        drive["new_ordinary_wall_seconds_exploratory"])
    assert drive["unattempted_ordinary_phase_indices"] == [i for i in INDICES
                                                            if i >= len(ordinary)]
    if drive["stop_status"] == "SCREEN_COMPLETED_WITHOUT_RELATION":
        assert len(ordinary) == len(INDICES)
        assert all(x["status"] == "BRANCH_CAP_REACHED" for x in ordinary)
    elif drive["stop_status"] == "VERIFIED_RELATION":
        assert ordinary and ordinary[-1]["status"] == "VERIFIED_RELATION"
    elif drive["stop_status"] == "ORDINARY_CENSORED_OR_FAILED":
        assert ordinary and ordinary[-1]["status"] not in (
            "BRANCH_CAP_REACHED", "VERIFIED_RELATION")
    else:
        assert drive["stop_status"] == "CONTROL_GATE_FAILED"
        assert statuses["control"][-1]["status"] != "SAT_REPLAYED_XCNF"
    output = {"status": "PASS", "proposal_id": "Q1473",
              "workload_id": target["workload_id"],
              "control_statuses": [x["status"] for x in statuses["control"]],
              "ordinary_statuses": [x["status"] for x in ordinary],
              "source_sha256": sha(Path(__file__)),
              "q1472_validator_sha256": sha(Q1472 / "validate.py")}
    (HERE / "validation.json").write_text(json.dumps(output, indent=2,
                                                       sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
