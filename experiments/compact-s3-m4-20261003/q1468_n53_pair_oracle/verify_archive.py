#!/usr/bin/env python3
"""Audit complete Q1468 pair-table runs and replay the recovered relation."""

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

from q1468_n53_pair_oracle.make_inputs import render  # noqa: E402
from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "archive_verification.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_points() -> tuple[list[tuple[int, int]], list[int]]:
    lines = (HERE / "inputs/base_points.txt").read_text().splitlines()
    assert lines[0] == "Q1468BASE1 53 2756 26"
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    points, columns = [], []
    for line in lines[1:]:
        column, x, y = line.split()
        point = (onb.fromCoords(int(x, 16)),
                 onb.fromCoords(int(y, 16)))
        assert curve.onCurve(point)
        columns.append(int(column))
        points.append(point)
    assert len(points) == len(columns) == 2756
    assert sorted(set(columns)) == list(range(26))
    assert all(columns.count(column) == 106 for column in range(26))
    return points, columns


def target(name: str) -> tuple[int, int]:
    lines = (HERE / "inputs" / f"{name}_target.txt").read_text().splitlines()
    assert lines[0] == "Q1468TARGET1 53" and len(lines) == 2
    x, y = lines[1].split()
    onb = field.Onb(53)
    return onb.fromCoords(int(x, 16)), onb.fromCoords(int(y, 16))


def describe() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1468"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["complete_cross_column_pair_count"] == (
        26 * 25 // 2 * 106 * 106) == 3651700
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for leaf, digest in protocol["input_sha256"].items():
        assert sha(HERE / "inputs" / leaf) == digest
    assert all((HERE / "inputs" / leaf).read_bytes() == payload
               for leaf, payload in render().items())
    assert sha(HERE / "native_oracle") == protocol["binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    points, columns = load_points()
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    rows = []
    table_calls = None
    for name in protocol["run_order"]:
        output = HERE / "runs" / name
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1468"
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"]["experiments/compact-s3-m4-20261003/"
                             "q1468_n53_pair_oracle/run_stage.py"]
        assert receipt["binary_sha256"] == protocol["binary_sha256"]
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["native_exit_code"] == 0
        assert receipt["native_report_error"] is None
        assert receipt["independent_check_error"] is None
        assert receipt["native_stdout_sha256"] == sha(output / "stdout.txt")
        assert receipt["native_stderr_sha256"] == sha(output / "stderr.txt")
        report = json.loads((output / "stdout.txt").read_text())
        assert report == receipt["native_report"]
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        if name == "selftest":
            assert report["mode"] == "selftest"
            assert len(report["samples"]) == 64
            for row in report["samples"]:
                i, j = row["i"], row["j"]
                assert columns[i] != columns[j]
                found = (onb.fromCoords(int(row["x_onb"], 16)),
                         onb.fromCoords(int(row["y_onb"], 16)))
                assert curve.add(points[i], points[j]) == found
            assert receipt["status"] == "passed"
            assert receipt["independent_check"] == {
                "status": "passed", "independent_group_additions": 64}
            rows.append({"case": name, "status": "passed",
                         "independent_group_additions": 64,
                         "receipt_sha256": sha(receipt_path)})
            continue
        assert report["mode"] == "query"
        assert report["complete_pair_table"] is True
        assert report["pair_table_entries"] == 3651700
        assert report["duplicate_pair_sums"] == 0
        assert receipt["workload_id"] == protocol["workloads"][name][
            "workload_id"]
        assert receipt["public_target"] == protocol["workloads"][name][
            "public_target"]
        assert target(name) == tuple(receipt["public_target"])
        if table_calls is None:
            table_calls = report["table_field_calls"]
        else:
            assert table_calls == report["table_field_calls"]
        assert report["table_wall_ns"] > 0
        assert report["query_wall_ns"] > 0
        assert receipt["process_wall_ns_exploratory"] >= (
            report["table_wall_ns"] + report["query_wall_ns"])
        status = report["status"]
        if name == "n53_planted_unpinned":
            assert status == receipt["status"] == "found"
            indices = report["witness_indices"]
            assert len(indices) == 4
            assert len({columns[index] for index in indices}) == 4
            total = None
            for index in indices:
                total = curve.add(total, points[index])
            assert total == target(name)
            assert receipt["independent_check"] == {
                "status": "verified_four_point_relation",
                "point_indices": indices,
                "folded_columns": [columns[index] for index in indices],
                "public_target": list(target(name)),
            }
        else:
            assert name == "n53_ordinary"
            assert status == receipt["status"] == "absent"
            assert report["witness_indices"] is None
            assert report["query_pair_sums_examined"] == 3651700
            assert report["complement_hits"] == 0
            assert receipt["independent_check"] is None
        rows.append({
            "case": name, "status": status,
            "workload_id": receipt["workload_id"],
            "pair_table_entries": report["pair_table_entries"],
            "query_pair_sums_examined": report["query_pair_sums_examined"],
            "table_wall_ns_exploratory": report["table_wall_ns"],
            "query_wall_ns_exploratory": report["query_wall_ns"],
            "table_field_calls": report["table_field_calls"],
            "query_field_calls": report["query_field_calls"],
            "verified_relation_count": int(status == "found"),
            "receipt_sha256": sha(receipt_path),
        })
    return {
        "kind": "q1468_exact_n53_pair_oracle_archive_verification",
        "status": "passed", "proposal_id": "Q1468",
        "candidate_id": None, "isogeny": "none",
        "protocol_sha256": sha(PROTOCOL),
        "verifier_source_sha256": sha(Path(__file__)),
        "rows": rows,
        "claim_scope": (
            "one independently replayed four-distinct-column N53 relation "
            "and one native complete-enumeration absent result on the exact "
            "base, with 64 independent group-addition samples; no panel "
            "yield, N83 transfer, or complete N131 work estimate"),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = describe()
    if args.emit:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) +
                          "\n")
    else:
        assert result == json.loads(OUTPUT.read_text())
    print(json.dumps({"status": result["status"],
                      "cases": [row["status"] for row in result["rows"]]}),
          flush=True)


if __name__ == "__main__":
    main()
