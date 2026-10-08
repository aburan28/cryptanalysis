#!/usr/bin/env python3
"""Run frozen N53 ordinary targets through the exact Q1468 oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1468 = PARENT / "q1468_n53_pair_oracle"
sys.path.insert(0, str(PARENT))

from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
BINARY = Q1468 / "native_oracle"
BASE = Q1468 / "inputs/base_points.txt"
FIELD = PARENT / "q1420_root_theory/n53_field.txt"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def point_base() -> tuple[list[tuple[int, int]], list[int]]:
    lines = BASE.read_text().splitlines()
    assert lines[0] == "Q1468BASE1 53 2756 26"
    onb = field.Onb(53)
    points, columns = [], []
    for line in lines[1:]:
        column, x, y = line.split()
        points.append((onb.fromCoords(int(x, 16)),
                       onb.fromCoords(int(y, 16))))
        columns.append(int(column))
    assert len(points) == len(columns) == 2756
    return points, columns


def target_bytes(onb, point: list[int]) -> bytes:
    x = int(onb.toCoords(point[0]))
    y = int(onb.toCoords(point[1]))
    return f"Q1468TARGET1 53\n{x:x} {y:x}\n".encode()


def witness_check(report: dict, target: tuple[int, int],
                  points: list[tuple[int, int]],
                  columns: list[int], curve) -> dict | None:
    if report["status"] != "found":
        assert report["witness_indices"] is None
        return None
    indices = report["witness_indices"]
    assert len(indices) == 4
    assert all(isinstance(index, int) and 0 <= index < len(points)
               for index in indices)
    assert len({columns[index] for index in indices}) == 4
    total = None
    for index in indices:
        total = curve.add(total, points[index])
    assert total == target
    return {
        "status": "verified_four_point_relation",
        "point_indices": indices,
        "folded_columns": [columns[index] for index in indices],
        "public_target": list(target),
    }


def run_one(protocol: dict, row: dict, onb, curve,
            points: list[tuple[int, int]], columns: list[int]) -> dict:
    index = row["index"]
    output = HERE / "runs" / f"{index:03d}"
    if output.exists():
        receipt = json.loads((output / "receipt.json").read_text())
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["workload_id"] == row["workload_id"]
        assert receipt["public_target"] == row["public_target"]
        assert receipt["target_file_sha256"] == sha(output / "target.txt")
        return receipt
    output.mkdir(parents=True)
    target_file = output / "target.txt"
    target_file.write_bytes(target_bytes(onb, row["public_target"]))
    command = [str(BINARY), str(FIELD), str(BASE), str(target_file),
               str(protocol["native_wall_cap_seconds_per_phase"])]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["external_safeguard_seconds"])
        stdout, stderr, exit_code = (completed.stdout, completed.stderr,
                                     completed.returncode)
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code = None
    process_wall_ns = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output / "stdout.txt"
    stderr_path = output / "stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    report = report_error = None
    if exit_code == 0:
        try:
            report = json.loads(stdout)
            assert report["mode"] == "query"
            assert report["status"] in ("found", "absent", "censored")
            assert report["complete_pair_table"] is True
            assert report["pair_table_entries"] == 3651700
            if report["status"] == "absent":
                assert report["query_pair_sums_examined"] == 3651700
        except Exception as error:
            report_error = repr(error)
            report = None
    independent = independent_error = None
    if report is not None:
        try:
            independent = witness_check(
                report, tuple(row["public_target"]), points, columns, curve)
        except Exception as error:
            independent_error = repr(error)
    receipt = {
        "proposal_id": "Q1469", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "panel_index": index,
        "panel_workload_id": protocol["panel_workload_id"],
        "workload_id": row["workload_id"],
        "curve_id": protocol["curve_id"], "degree_n": 53,
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "public_target": row["public_target"],
        "input_role": "ordinary_seeded_subgroup_target",
        "native_exit_code": exit_code,
        "native_report": report,
        "native_report_error": report_error,
        "independent_check": independent,
        "independent_check_error": independent_error,
        "status": (report or {}).get("status", "error"),
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "process_wall_ns_exploratory": process_wall_ns,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_global_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "target_file_sha256": sha(target_file),
        "native_stdout_sha256": sha(stdout_path),
        "native_stderr_sha256": sha(stderr_path),
        "binary_sha256": sha(BINARY),
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", type=int, default=128)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1469"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert 1 <= args.stop <= protocol["target_count"] == 128
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "panel.json") == protocol["panel_sha256"]
    assert sha(BASE) == protocol["base_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    assert sha(Q1468 / "protocol.json") == protocol[
        "q1468_protocol_sha256"]
    assert sha(Q1468 / "compile_receipt.json") == protocol[
        "q1468_compile_receipt_sha256"]
    assert sha(FIELD) == protocol["field_bridge_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    panel = json.loads((HERE / "panel.json").read_text())
    assert panel["panel_workload_id"] == protocol["panel_workload_id"]
    assert panel["target_count"] == protocol["target_count"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    points, columns = point_base()
    status_counts: dict[str, int] = {}
    panel_start = time.perf_counter()
    for row in panel["targets"][:args.stop]:
        if time.perf_counter() - panel_start >= protocol[
                "overall_wall_budget_seconds"]:
            print(json.dumps({"stopped": "overall_wall_budget",
                              "completed": row["index"],
                              "status_counts": status_counts}), flush=True)
            break
        receipt = run_one(protocol, row, onb, curve, points, columns)
        status = receipt["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        if (row["index"] + 1) % 8 == 0 or row["index"] + 1 == args.stop:
            print(json.dumps({"completed": row["index"] + 1,
                              "status_counts": status_counts}), flush=True)


if __name__ == "__main__":
    main()
