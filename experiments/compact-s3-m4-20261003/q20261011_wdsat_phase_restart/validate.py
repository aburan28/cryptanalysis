#!/usr/bin/env python3
"""Independently replay the frozen target, formula, build, and phase receipts."""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q20261011_wdsat_shared_prefix"))

from phase_schedule import INDICES, phases  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from prepare import evaluate, transform  # noqa: E402
from run_probe import curves, field  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()
    return raw_sha(data)


def verify_cell(kind: str, freeze: dict, target: dict) -> tuple[bytes, bytes]:
    cell = freeze["cells"][kind]
    source_path = Path(cell["source_archive_path"])
    derived_path = Path(cell["derived_archive_path"])
    assert sha(source_path) == cell["source_archive_sha256"]
    assert sha(derived_path) == cell["derived_archive_sha256"]
    source = gzip.decompress(source_path.read_bytes())
    derived = gzip.decompress(derived_path.read_bytes())
    assert raw_sha(source) == cell["source_raw_sha256"]
    assert raw_sha(derived) == cell["derived_raw_sha256"]
    assert int(source.splitlines()[0].split()[2]) == cell["original_variables"]
    assert int(derived.splitlines()[0].split()[2]) == cell["derived_variables"]
    assert cell["factor_base_actual_B"] == target["factor_base_actual_B"]
    assert cell["factor_base_folded_columns_K"] == target["factor_base_folded_columns_K"]
    assert cell["factor_base_enumerated_set_sha256"] == target[
        "factor_base_enumerated_set_sha256"]
    return source, derived


def verify_target(target: dict, source: bytes, derived: bytes) -> None:
    base_path = PARENT / "bases/n83_weight5_full_orbits.json"
    assert sha(base_path) == target["base_receipt_sha256"]
    base = json.loads(base_path.read_text())
    curve_record = base["curve"]
    assert curve_record["curve_id"] == target["curve_id"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(map(int, curve_record["generator"]))
    order = int(curve_record["subgroup_order"])
    scalar = random.Random(14720083).randrange(1, order)
    public = tuple(target["public_target"])
    assert str(scalar) == target["fixture_scalar"]
    assert curve.onCurve(generator) and curve.mul(generator, order) is None
    assert curve.mul(generator, scalar) == public
    assert curve.onCurve(public) and curve.mul(public, order) is None
    assert target["workload_record"]["public_target"] == list(public)
    assert canonical_hash(target["workload_record"])[:12] == target["workload_id"]
    points = [tuple(point) for point in target["raw_preimage_points"]]
    assert len(points) == len(set(points)) == 4
    assert len(set(target["raw_preimage_x_coordinates"])) == 4
    for point, x_coord in zip(points, target["raw_preimage_x_coordinates"]):
        assert curve.onCurve(point)
        assert curve.mul(point, 4) == public
        assert onb.toCoords(point[0]) == x_coord
    formula, _, _, _, _ = build_balanced(83, 5, target["raw_preimage_x_coordinates"])
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / "reconstructed.xcnf"
        formula.write(candidate)
        assert candidate.read_bytes() == source
    rebuilt, _, stats = transform(source)
    assert rebuilt == derived
    assert json.loads(json.dumps(stats)) == target["transform_stats"]


def verify_receipts(freeze: dict, protocol: dict, build: dict,
                    target: dict, cells: dict[str, tuple[bytes, bytes]]) -> dict:
    statuses = {}
    for kind in ("control", "ordinary"):
        rows = []
        for phase in INDICES:
            directory = HERE / "runs" / kind / f"phase{phase}"
            receipt_path = directory / "receipt.json"
            if not receipt_path.exists():
                assert not any((HERE / "runs" / kind / f"phase{later}" /
                                "receipt.json").exists() for later in INDICES if later > phase)
                break
            row = json.loads(receipt_path.read_text())
            assert row["proposal_id"] == "Q1472" and row["candidate_id"] is None
            assert row["phase_index"] == phase and row["kind"] == kind
            assert row["phase_seed"] == freeze["phase_schedule"][str(phase)]["seed"]
            assert row["phase_flip_count"] == len(
                freeze["phase_schedule"][str(phase)]["flip_ids"])
            for name, path in (("protocol", "protocol.json"),
                               ("freeze", "freeze.json"),
                               ("build_receipt", "build_receipt.json"),
                               ("target", "target.json")):
                assert row[f"{name}_sha256"] == sha(HERE / path)
            assert row["runner_sha256"] == freeze["runner_source_sha256"]
            assert row["binary_sha256"] == build["binary_sha256"]
            assert row["workload_id"] == freeze["cells"][kind]["workload_id"]
            assert row["public_target"] == freeze["cells"][kind]["public_target"]
            assert row["archive_sha256"] == freeze["cells"][kind][
                "derived_archive_sha256"]
            assert row["source_archive_sha256"] == freeze["cells"][kind][
                "source_archive_sha256"]
            assert row["left_branch_attempt_limit"] == protocol["limits"][
                "left_branch_attempts_per_phase"]
            assert row["order_marker_seen"] and row["phase_marker_seen"]
            assert row["search_started"] and row["after_xor_init"]
            assert sha(directory / "solver.stdout.txt") == row["stdout_sha256"]
            assert sha(directory / "solver.stderr.txt") == row["stderr_sha256"]
            checkpoints = row["branch_checkpoints"]
            assert checkpoints == [1 << i for i in range(len(checkpoints))]
            assert row["branch_lower_bound"] == (checkpoints[-1] if checkpoints else 0)
            if row["status"] == "BRANCH_CAP_REACHED":
                assert row["return_code"] == 42
                assert row["branch_exact_at_cap"] == 1 << 20
                assert row["branch_lower_bound"] == 1 << 20
                assert row["verified_natural_relations"] == 0
            if row["status"] in ("SAT_REPLAYED_XCNF", "VERIFIED_RELATION"):
                model_lines = [line.strip() for line in (directory /
                               "solver.stdout.txt").read_text().splitlines()
                               if len(line.strip()) == freeze["cells"][kind][
                                   "derived_variables"] and set(line.strip()) <= {"0", "1"}]
                assert len(model_lines) == 1
                model = {i + 1: bit == "1" for i, bit in enumerate(model_lines[0])}
                original, derived = cells[kind]
                replay = {"derived": evaluate(derived, model),
                          "original": evaluate(original, {i: model[i] for i in range(
                              1, freeze["cells"][kind]["original_variables"] + 1)})}
                assert row["xcnf_replay"] == replay
            if row["status"] == "VERIFIED_RELATION":
                assert kind == "ordinary"
                group = row["group_replay"]
                assert group["status"] == "verified_four_point_relation"
                assert group["distinct_columns"] == 4
                assert group["public_target"] == target["public_target"]
                assert len(group["raw_leaf_x"]) == len(group["signs"]) == 4
                onb = field.Onb(83)
                curve = curves.Curve(onb)
                total = None
                for x_coord, sign in zip(group["raw_leaf_x"], group["signs"]):
                    assert sign in (-1, 1)
                    point = curve.pointFromX(onb.fromCoords(x_coord))
                    assert point is not None
                    total = curve.add(total, point if sign == 1 else curve.neg(point))
                assert total is not None and curve.mul(total, 4) == tuple(
                    target["public_target"])
                assert row["verified_natural_relations"] == 1
            rows.append(row)
        statuses[kind] = rows
    ordinary = statuses["ordinary"]
    assert ordinary
    assert all(row["status"] != "VERIFIED_RELATION" for row in ordinary[:-1])
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert drive["target_count"] == 1
    assert drive["workload_id"] == target["workload_id"]
    assert len(drive["attempts"]) == len(ordinary)
    for row, attempt in zip(ordinary, drive["attempts"]):
        assert attempt["status"] == row["status"]
        assert attempt["branch_lower_bound"] == row["branch_lower_bound"]
        assert attempt["user_cpu_seconds"] == row["user_cpu_seconds"]
    assert drive["total_user_cpu_seconds_exploratory"] == sum(
        row["user_cpu_seconds"] for row in ordinary)
    assert drive["total_target_dependent_wall_seconds_exploratory"] == (
        target["target_preimage_seconds_exploratory"] +
        target["formula_build_seconds_exploratory"] +
        sum(row["run_wall_seconds_exploratory"] for row in ordinary))
    if drive["stop_status"] == "INFRASTRUCTURE_TERMINATED_AFTER_PHASE6":
        termination_path = HERE / "termination.json"
        termination = json.loads(termination_path.read_text())
        assert drive["termination_sha256"] == sha(termination_path)
        assert termination["status"] == drive["stop_status"]
        assert termination["source_sha256"] == sha(HERE / "finalize_partial.py")
        assert termination["last_completed_ordinary_receipt_sha256"] == sha(
            HERE / "runs/ordinary/phase6/receipt.json")
        assert len(ordinary) == 7 and ordinary[-1]["status"] == "WALL_CAP_SEARCH_STARTED"
        assert drive["completed_ordinary_phase_indices"] == list(range(7))
        assert drive["unattempted_ordinary_phase_indices"] == [7, 8]
        assert termination["unattempted_ordinary_phases"] == [7, 8]
        assert drive["source_sha256"] == sha(HERE / "finalize_partial.py")
        interrupted = HERE / "runs/control/phase7"
        assert not interrupted.exists() or (interrupted.is_dir() and
                                            not any(interrupted.iterdir()))
        assert len(statuses["control"]) == 7
    elif drive["stop_status"] == "VERIFIED_RELATION":
        assert ordinary[-1]["status"] == "VERIFIED_RELATION"
    else:
        assert drive["stop_status"] == "PHASE_SCHEDULE_EXHAUSTED"
        assert len(ordinary) == len(INDICES)
    return {kind: [row["status"] for row in rows] for kind, rows in statuses.items()}


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    assert protocol["proposal_id"] == freeze["proposal_id"] == target["proposal_id"] == "Q1472"
    assert protocol["candidate_id"] is target["candidate_id"] is None
    assert protocol["isogeny"] == target["isogeny"] == "none"
    assert protocol["workload_id"] == target["workload_id"]
    assert freeze["phase_schedule"] == {str(i): phases()[i] for i in INDICES}
    for name, path in (("protocol", "protocol.json"), ("target", "target.json"),
                       ("runtime_info", "sage_runtime_info.json"),
                       ("runner_source", "run.py"), ("phase_source", "phase_schedule.py"),
                       ("build_source", "build.py"),
                       ("prepare_target_source", "prepare_target.py"),
                       ("freeze_source", "freeze.py")):
        assert freeze[f"{name}_sha256"] == sha(HERE / path)
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    cells = {kind: verify_cell(kind, freeze, target) for kind in ("control", "ordinary")}
    verify_target(target, *cells["ordinary"])
    statuses = verify_receipts(freeze, protocol, build, target, cells)
    output = {"status": "PASS", "proposal_id": "Q1472",
              "workload_id": target["workload_id"], "statuses": statuses,
              "source_sha256": sha(Path(__file__))}
    (HERE / "validation.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
