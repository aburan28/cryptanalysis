#!/usr/bin/env python3
"""Independently replay the Q1476 target, XCNFs, and matched-prefix receipts."""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"
Q1473 = PARENT / "q20261011_selector_polarity"
Q1474 = PARENT / "q20261011_n83_propagation_probe"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q20261011_wdsat_shared_prefix"))
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from prepare import evaluate, transform  # noqa: E402
from run_probe import curves, field  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return raw_sha(raw)


def main() -> None:
    assert sys.argv[1:] in ([], ["--inputs-only"])
    inputs_only = sys.argv[1:] == ["--inputs-only"]
    protocol = json.loads((HERE / "protocol.json").read_text())
    input_freeze = json.loads((HERE / "input_freeze.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    drive = (json.loads((HERE / "drive_receipt.json").read_text())
             if not inputs_only else None)
    assert protocol["proposal_id"] == input_freeze["proposal_id"] == frozen[
        "proposal_id"] == target["proposal_id"] == "Q1476"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["workload_id"] is None
    assert target["workload_id"] == frozen["workload_id"]
    if drive is not None:
        assert drive["proposal_id"] == "Q1476"
        assert drive["workload_id"] == target["workload_id"]
    assert protocol["isogeny"] == target["isogeny"] == "none"
    assert input_freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert frozen["input_freeze_sha256"] == target[
        "input_freeze_sha256"] == sha(HERE / "input_freeze.json")
    assert frozen["target_sha256"] == sha(HERE / "target.json")
    assert frozen["runtime_info_sha256"] == input_freeze[
        "runtime_info_sha256"] == target["runtime_info_sha256"] == sha(
            HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(Q1472 / "prepare_target.py") == frozen[
        "q1472_generator_sha256"] == target["generator_source_sha256"]
    assert sha(HERE / "prepare_target.py") == target["source_sha256"]
    assert sha(Q1474 / "run.py") == frozen["q1474_runner_sha256"]
    assert sha(Q1473 / "smoke_receipt.json") == frozen["q1473_smoke_sha256"]
    smoke = json.loads((Q1473 / "smoke_receipt.json").read_text())
    assert smoke["status"] == "PASS" and len(smoke["rows"]) == 4
    assert sha(Path(frozen["binary_path"])) == frozen["binary_sha256"] == smoke[
        "binary_sha256"]
    base_path = PARENT / "bases/n83_weight5_full_orbits.json"
    assert sha(base_path) == input_freeze["base_sha256"] == target[
        "base_receipt_sha256"]
    base = json.loads(base_path.read_text())
    curve_record = base["curve"]
    assert curve_record["curve_id"] == protocol["curve_id"] == target["curve_id"]
    fb = base["factor_base"]
    assert fb["actual_usable_points_B_before_folding"] == target[
        "factor_base_actual_B"] == protocol["factor_base_actual_B"]
    assert fb["signed_frobenius_columns"] == target[
        "factor_base_folded_columns_K"] == protocol["factor_base_folded_columns_K"]
    assert fb["enumerated_set_sha256"] == target[
        "factor_base_enumerated_set_sha256"] == input_freeze[
            "base_enumerated_set_sha256"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(map(int, curve_record["generator"]))
    order = int(curve_record["subgroup_order"])
    scalar = random.Random(protocol["target_generation_seed"]).randrange(1, order)
    public = tuple(target["public_target"])
    prior = json.loads((Q1472 / "target.json").read_text())
    assert str(scalar) == target["fixture_scalar"]
    assert curve.mul(generator, scalar) == public and curve.onCurve(public)
    assert curve.mul(public, order) is None
    assert list(public) != prior["public_target"]
    assert target["workload_record"]["target_generation"]["seed"] == protocol[
        "target_generation_seed"]
    assert target["workload_record"]["public_target"] == list(public)
    assert canonical_hash(target["workload_record"])[:12] == target["workload_id"]
    points = [tuple(point) for point in target["raw_preimage_points"]]
    xs = target["raw_preimage_x_coordinates"]
    assert len(points) == len(set(points)) == len(xs) == len(set(xs)) == 4
    for point, x in zip(points, xs):
        assert curve.onCurve(point) and curve.mul(point, 4) == public
        assert onb.toCoords(point[0]) == x
    cell = frozen["ordinary_cell"]
    assert cell["curve_id"] == protocol["curve_id"]
    assert cell["workload_id"] == target["workload_id"]
    assert cell["public_target"] == target["public_target"]
    raw = {}
    for kind, name in (("source", "original.xcnf.gz"),
                       ("derived", "width4.xcnf.gz")):
        path = HERE / name
        assert sha(path) == cell[f"{kind}_archive_sha256"]
        raw[kind] = gzip.decompress(path.read_bytes())
        assert raw_sha(raw[kind]) == cell[f"{kind}_raw_sha256"]
    formula, _, _, _, selectors = build_balanced(83, 5, xs)
    assert selectors == [2140, 2141]
    with tempfile.TemporaryDirectory(dir="/Volumes/SSD990/llm/tmp") as tmp:
        reconstructed = Path(tmp) / "system.xcnf"
        formula.write(reconstructed)
        assert reconstructed.read_bytes() == raw["source"]
    transformed, _, stats = transform(raw["source"])
    assert transformed == raw["derived"]
    assert json.loads(json.dumps(stats)) == target["transform_stats"]
    assert int(raw["source"].splitlines()[0].split()[2]) == cell[
        "original_variables"] == target["original_variables"]
    assert int(raw["derived"].splitlines()[0].split()[2]) == cell[
        "derived_variables"] == target["derived_variables"]
    assert frozen["phase_schedule"]["0"]["flip_ids"] == []
    assert frozen["phase_schedule"]["1"]["flip_ids"] == [2140]
    if inputs_only:
        print("PASS Q1476 frozen holdout inputs", target["workload_id"])
        return
    rows = []
    for phase in protocol["phase_order"]:
        folder = HERE / "runs" / f"phase{phase}"
        if not folder.exists():
            break
        outer = json.loads((folder / "receipt.json").read_text())
        child_path = folder / "implementation_receipt.json"
        child = json.loads(child_path.read_text())
        assert outer["proposal_id"] == "Q1476" and child["proposal_id"] == "Q1474"
        assert outer["implementation_receipt_sha256"] == sha(child_path)
        assert outer["phase"] == child["phase"] == phase
        assert outer["flip_ids"] == child["flip_ids"] == frozen[
            "phase_schedule"][str(phase)]["flip_ids"]
        for key in ("status", "branch_lower_bound", "cnf_set_true_calls_at_checkpoint",
                    "xor_set_true_calls_at_checkpoint", "user_cpu_seconds",
                    "solver_wall_seconds_exploratory", "verified_natural_relations"):
            assert outer[key] == child[key]
        assert outer["curve_id"] == child["curve_id"] == protocol["curve_id"]
        assert outer["workload_id"] == child["workload_id"] == target["workload_id"]
        assert child["binary_sha256"] == frozen["binary_sha256"]
        assert child["freeze_sha256"] == outer["freeze_sha256"] == sha(
            HERE / "freeze.json")
        assert child["source_sha256"] == frozen["q1474_runner_sha256"]
        assert outer["wrapper_source_sha256"] == sha(HERE / "run.py")
        stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout_path) == child["stdout_sha256"]
        assert sha(stderr_path) == child["stderr_sha256"]
        log = stderr_path.read_text(errors="replace")
        checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$", log, re.M)]
        work = [list(map(int, x)) for x in re.findall(
            r"^Q1473_WORK (\d+) (\d+) (\d+)$", log, re.M)]
        assert [item[0] for item in work] == checkpoints
        assert checkpoints == [1 << i for i in range(len(checkpoints))]
        assert child["branch_checkpoints"] == checkpoints and child["work_checkpoints"] == work
        at_cap = next((item for item in work if item[0] == protocol[
            "checkpoint_left_branches"]), None)
        assert child["cnf_set_true_calls_at_checkpoint"] == (at_cap[1] if at_cap else None)
        assert child["xor_set_true_calls_at_checkpoint"] == (at_cap[2] if at_cap else None)
        assert child["search_started"] == ("Q1458_SEARCH_START" in log)
        if outer["status"] == "CHECKPOINT_TERMINATED":
            assert at_cap and child["search_started"] and child["marker_ok"]
        elif outer["status"] == "VERIFIED_RELATION":
            model_lines = [line.strip() for line in stdout_path.read_text().splitlines()
                           if len(line.strip()) == cell["derived_variables"] and
                           set(line.strip()) <= {"0", "1"}]
            assert len(model_lines) == 1
            model = {i + 1: bit == "1" for i, bit in enumerate(model_lines[0])}
            assert evaluate(raw["derived"], model) == child["model_replay"]["derived"]
            assert evaluate(raw["source"], {i: model[i] for i in range(
                1, cell["original_variables"] + 1)}) == child["model_replay"]["original"]
            assert child["group_replay"]["status"] == "verified_four_point_relation"
            assert child["verified_natural_relations"] == 1
        else:
            assert outer["status"] in ("CENSORED_BEFORE_SEARCH", "WALL_CAP_SEARCH_STARTED",
                                       "CPU_CAP_BEFORE_SEARCH", "CPU_CAP_SEARCH_STARTED",
                                       "PRODUCER_FAILURE", "MODEL_REPLAY_FAILED")
        rows.append(outer)
    assert rows and len(rows) == drive["new_ordinary_attempts"]
    assert drive["phase_statuses"] == [row["status"] for row in rows]
    assert drive["new_verified_relations"] == sum(row["verified_natural_relations"] for row in rows)
    assert abs(drive["solver_attempt_wall_seconds_exploratory"] - sum(
        row["solver_wall_seconds_exploratory"] for row in rows)) < 1e-8
    assert abs(drive["solver_child_user_cpu_seconds_exploratory"] - sum(
        row["user_cpu_seconds"] for row in rows)) < 1e-8
    assert abs(drive["target_dependent_wall_phase_sum_seconds_exploratory"] - (
        target["target_preimage_seconds_exploratory"] +
        target["formula_build_seconds_exploratory"] +
        sum(row["solver_wall_seconds_exploratory"] for row in rows))) < 1e-8
    assert drive["complete_n83_decomposition_work_log2"] is None
    assert drive["complete_n131_solve_work_log2"] is None
    print("PASS Q1476", target["workload_id"], [row["status"] for row in rows])


if __name__ == "__main__":
    main()
