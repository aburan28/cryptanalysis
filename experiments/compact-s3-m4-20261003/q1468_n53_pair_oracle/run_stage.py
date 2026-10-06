#!/usr/bin/env python3
"""Run frozen Q1468 native pair-table oracle and independently replay hits."""

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
sys.path.insert(0, str(PARENT))

from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
BINARY = HERE / "native_oracle"
COMPILE_RECEIPT = HERE / "compile_receipt.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_base() -> tuple[list[tuple[int, int]], list[int]]:
    lines = (HERE / "inputs/base_points.txt").read_text().splitlines()
    assert lines[0] == "Q1468BASE1 53 2756 26"
    onb = field.Onb(53)
    points, columns = [], []
    for line in lines[1:]:
        column, x, y = line.split()
        columns.append(int(column))
        points.append((onb.fromCoords(int(x, 16)),
                       onb.fromCoords(int(y, 16))))
    assert len(points) == len(columns) == 2756
    assert {columns.count(index) for index in range(26)} == {106}
    return points, columns


def read_target(name: str) -> tuple[int, int]:
    lines = (HERE / "inputs" / f"{name}_target.txt").read_text().splitlines()
    assert lines[0] == "Q1468TARGET1 53" and len(lines) == 2
    x, y = lines[1].split()
    onb = field.Onb(53)
    return onb.fromCoords(int(x, 16)), onb.fromCoords(int(y, 16))


def check_selftest(report: dict) -> dict:
    assert report["mode"] == "selftest"
    assert len(report["samples"]) == 64
    points, columns = read_base()
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    for sample in report["samples"]:
        i, j = sample["i"], sample["j"]
        assert 0 <= i < j < 2756
        assert columns[i] != columns[j]
        observed = (onb.fromCoords(int(sample["x_onb"], 16)),
                    onb.fromCoords(int(sample["y_onb"], 16)))
        assert curve.add(points[i], points[j]) == observed
    return {"status": "passed", "independent_group_additions": 64}


def check_witness(name: str, report: dict) -> dict | None:
    if report["status"] != "found":
        assert report["witness_indices"] is None
        return None
    indices = report["witness_indices"]
    assert isinstance(indices, list) and len(indices) == 4
    assert all(isinstance(i, int) and 0 <= i < 2756 for i in indices)
    points, columns = read_base()
    assert len({columns[i] for i in indices}) == 4
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    target = read_target(name)
    total = None
    for index in indices:
        total = curve.add(total, points[index])
    assert total == target
    assert all(curve.onCurve(points[i]) for i in indices)
    assert curve.mul(target, 21044858204113) is None
    return {
        "status": "verified_four_point_relation",
        "point_indices": indices,
        "folded_columns": [columns[i] for i in indices],
        "public_target": [int(x) for x in target],
    }


def run(name: str) -> None:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1468"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert name in protocol["run_order"]
    output = HERE / "runs" / name
    assert not output.exists(), "refuse overwrite"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for leaf, digest in protocol["input_sha256"].items():
        assert sha(HERE / "inputs" / leaf) == digest, leaf
    assert sha(BINARY) == protocol["binary_sha256"]
    assert sha(COMPILE_RECEIPT) == protocol["compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    base = HERE / "inputs/base_points.txt"
    field_bridge = PARENT / "q1420_root_theory/n53_field.txt"
    if name == "selftest":
        command = [str(BINARY), str(field_bridge), str(base), "--selftest"]
    else:
        command = [str(BINARY), str(field_bridge), str(base),
                   str(HERE / "inputs" / f"{name}_target.txt"),
                   str(protocol["native_wall_cap_seconds_per_phase"])]
    output.mkdir(parents=True)
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
            assert report["mode"] == ("selftest" if name == "selftest"
                                       else "query")
        except Exception as error:
            report_error = repr(error)
    independent = independent_error = None
    if report is not None:
        try:
            if name == "selftest":
                independent = check_selftest(report)
            else:
                assert report["complete_pair_table"] is True
                assert report["pair_table_entries"] == 3651700
                assert report["status"] in ("found", "absent", "censored")
                if report["status"] == "absent":
                    assert report["query_pair_sums_examined"] == 3651700
                independent = check_witness(name, report)
        except Exception as error:
            independent_error = repr(error)
    meta = json.loads((HERE / "inputs/meta.json").read_text())
    cell = meta["targets"].get(name)
    receipt = {
        "proposal_id": "Q1468", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "case": name, "curve_id": meta["curve_id"], "degree_n": 53,
        "factor_base_actual_B": meta["factor_base_actual_B"],
        "folded_columns_K": meta["folded_columns_K"],
        "factor_base_enumerated_set_sha256": meta[
            "factor_base_enumerated_set_sha256"],
        "workload_id": cell["workload_id"] if cell else None,
        "input_role": cell["input_role"] if cell else "correctness_control",
        "public_target": cell["public_target"] if cell else None,
        "native_exit_code": exit_code,
        "native_report": report, "native_report_error": report_error,
        "independent_check": independent,
        "independent_check_error": independent_error,
        "status": (report or {}).get("status") if name != "selftest"
                  else (independent or {}).get("status"),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "process_wall_ns_exploratory": process_wall_ns,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
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
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case": name, "status": receipt["status"],
                      "independent_check": independent,
                      "process_wall_seconds": process_wall_ns / 1e9}),
          flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("selftest",) + (
        "n53_planted_unpinned", "n53_ordinary"), required=True)
    run(parser.parse_args().case)


if __name__ == "__main__":
    main()
