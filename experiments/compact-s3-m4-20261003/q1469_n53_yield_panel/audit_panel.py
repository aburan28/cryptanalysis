#!/usr/bin/env python3
"""Replay Q1469 relations, measure rank, and charge every ordinary query."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1468 = PARENT / "q1468_n53_pair_oracle"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from orbit_key import OrbitKey  # noqa: E402
from q1469_n53_yield_panel.make_panel import render  # noqa: E402
from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "panel_audit.json"
PRIMITIVES = ("mul", "sqr", "inv")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_base(onb) -> tuple[list[tuple[int, int]], list[int]]:
    lines = (Q1468 / "inputs/base_points.txt").read_text().splitlines()
    assert lines[0] == "Q1468BASE1 53 2756 26"
    points, columns = [], []
    for line in lines[1:]:
        column, x, y = line.split()
        columns.append(int(column))
        points.append((onb.fromCoords(int(x, 16)),
                       onb.fromCoords(int(y, 16))))
    assert len(points) == len(columns) == 2756
    assert all(columns.count(column) == 106 for column in range(26))
    return points, columns


def rank_insert(row: list[int], basis: dict[int, list[int]], modulus: int) -> int:
    work = row[:]
    for pivot in sorted(basis):
        if work[pivot]:
            factor = work[pivot]
            work = [(a - factor * b) % modulus
                    for a, b in zip(work, basis[pivot])]
    for pivot, value in enumerate(work):
        if value:
            inverse = pow(value, -1, modulus)
            new_row = [(entry * inverse) % modulus for entry in work]
            for old_row in basis.values():
                factor = old_row[pivot]
                if factor:
                    old_row[:] = [(a - factor * b) % modulus
                                  for a, b in zip(old_row, new_row)]
            basis[pivot] = new_row
            return 1
    return 0


def wilson(successes: int, count: int) -> dict:
    assert count > 0
    z = 1.959963984540054
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    half = (z / denominator *
            math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)))
    return {"point": format(p, ".9f"),
            "lower_95": format(max(0, center - half), ".9f"),
            "upper_95": format(min(1, center + half), ".9f"),
            "method": "Wilson score interval, treating seeded targets as independent uniform draws"}


def bootstrap_ratio(rows: list[dict], numerator: str, successes: int) -> dict | None:
    if successes == 0:
        return None
    rng = random.Random(14690054)
    values = []
    for _ in range(2000):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        denominator = sum(row["status"] == "found" for row in sample)
        if denominator:
            values.append(sum(row[numerator] for row in sample) /
                          denominator)
    values.sort()
    assert values
    return {
        "point": format(sum(row[numerator] for row in rows) / successes,
                        ".6f"),
        "lower_95": format(values[int(0.025 * len(values))], ".6f"),
        "upper_95": format(values[min(len(values) - 1,
                                      int(0.975 * len(values)))], ".6f"),
        "method": "2000 seeded target-level bootstrap replicates; zero-hit replicates omitted",
        "replicates_with_hits": len(values),
    }


def describe() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    panel = json.loads((HERE / "panel.json").read_text())
    assert panel == render()
    assert protocol["proposal_id"] == panel["proposal_id"] == "Q1469"
    assert protocol["candidate_id"] is panel["candidate_id"] is None
    assert protocol["isogeny"] == panel["isogeny"] == "none"
    assert protocol["target_count"] == len(panel["targets"]) == 128
    assert sha(HERE / "panel.json") == protocol["panel_sha256"]
    assert sha(Q1468 / "native_oracle") == protocol["binary_sha256"]
    assert sha(Q1468 / "inputs/base_points.txt") == protocol["base_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    points, columns = load_base(onb)
    modulus = panel["subgroup_order"]
    assert curves.isPrimeBig(modulus)
    generator = tuple(panel["generator"])
    assert curve.mul(generator, modulus) is None
    q1468_protocol = json.loads((Q1468 / "protocol.json").read_text())
    excluded = {tuple(row["public_target"])
                for row in q1468_protocol["workloads"].values()}
    assert len(excluded) == 2
    seen = set(excluded)
    rng = random.Random(panel["seed"])
    fixture_scalars = []
    for target_row in panel["targets"]:
        while True:
            scalar = rng.randrange(1, modulus)
            point = curve.mul(generator, scalar)
            if point not in seen:
                break
        assert point == tuple(target_row["public_target"])
        assert point not in seen
        seen.add(point)
        fixture_scalars.append(scalar)
    assert len(fixture_scalars) == len(panel["targets"])
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, modulus)
    assert pow(eigenvalue, 53, modulus) == 1
    inverse_eigenvalue = pow(eigenvalue, -1, modulus)
    canonical_keys = {}
    canonical_points = {}
    for point, column in zip(points, columns):
        key, _, _ = orbit.canonical(point)
        if column in canonical_keys:
            assert canonical_keys[column] == key
        else:
            canonical_keys[column] = key
            canonical_points[column] = orbit.point_from_key(key)
    assert len(canonical_keys) == 26
    basis: dict[int, list[int]] = {}
    rows = []
    counts = {status: 0 for status in ("found", "absent", "censored", "error")}
    totals = {phase: {name: 0 for name in PRIMITIVES}
              for phase in ("table", "query")}
    table_wall_ns = query_wall_ns = process_wall_ns = 0
    peak_rss_global = 0
    table_calls_reference = None
    for target_row in panel["targets"]:
        index = target_row["index"]
        output = HERE / "runs" / f"{index:03d}"
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1469"
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"]["experiments/compact-s3-m4-20261003/"
                             "q1469_n53_yield_panel/run_panel.py"]
        assert receipt["binary_sha256"] == protocol["binary_sha256"]
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["panel_workload_id"] == protocol["panel_workload_id"]
        assert receipt["panel_index"] == index
        assert receipt["workload_id"] == target_row["workload_id"]
        assert receipt["curve_id"] == protocol["curve_id"]
        assert receipt["public_target"] == target_row["public_target"]
        assert receipt["factor_base_actual_B"] == 2756
        assert receipt["folded_columns_K"] == 26
        assert receipt["factor_base_enumerated_set_sha256"] == protocol[
            "factor_base_enumerated_set_sha256"]
        assert receipt["target_file_sha256"] == sha(output / "target.txt")
        target_lines = (output / "target.txt").read_text().splitlines()
        assert target_lines[0] == "Q1468TARGET1 53"
        assert len(target_lines) == 2
        target_x, target_y = target_lines[1].split()
        assert [onb.fromCoords(int(target_x, 16)),
                onb.fromCoords(int(target_y, 16))] == target_row[
                    "public_target"]
        assert receipt["native_stdout_sha256"] == sha(output / "stdout.txt")
        assert receipt["native_stderr_sha256"] == sha(output / "stderr.txt")
        assert receipt["native_exit_code"] == 0
        assert receipt["native_report_error"] is None
        assert receipt["independent_check_error"] is None
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        report = json.loads((output / "stdout.txt").read_text())
        assert report == receipt["native_report"]
        assert report["mode"] == "query"
        assert report["complete_pair_table"] is True
        assert report["pair_table_entries"] == 3651700
        assert report["duplicate_pair_sums"] == 0
        if table_calls_reference is None:
            table_calls_reference = report["table_field_calls"]
        else:
            assert report["table_field_calls"] == table_calls_reference
        status = report["status"]
        assert status == receipt["status"]
        counts[status] += 1
        coefficient_row = None
        if status == "absent":
            assert report["query_pair_sums_examined"] == 3651700
            assert report["complement_hits"] == report["rejected_shared_columns"]
            assert receipt["independent_check"] is None
            assert report["witness_indices"] is None
        elif status == "found":
            indices = report["witness_indices"]
            assert len(indices) == 4
            assert len({columns[i] for i in indices}) == 4
            total = None
            coefficient_row = [0] * 26
            for point_index in indices:
                point = points[point_index]
                total = curve.add(total, point)
                column = columns[point_index]
                key, frobenius_exponent, sign = orbit.canonical(point)
                assert key == canonical_keys[column]
                coefficient = (sign * pow(inverse_eigenvalue,
                                          frobenius_exponent, modulus)) % modulus
                assert curve.mul(canonical_points[column], coefficient) == point
                coefficient_row[column] = (coefficient_row[column] +
                                           coefficient) % modulus
            assert total == tuple(target_row["public_target"])
            assert receipt["independent_check"] == {
                "status": "verified_four_point_relation",
                "point_indices": indices,
                "folded_columns": [columns[i] for i in indices],
                "public_target": target_row["public_target"],
            }
            novel = rank_insert(coefficient_row, basis, modulus)
        else:
            raise AssertionError("censored/error cell prevents complete rate")
        if status != "found":
            novel = 0
        for phase in totals:
            calls = report[f"{phase}_field_calls"]
            for primitive in PRIMITIVES:
                totals[phase][primitive] += calls[primitive]
        table_wall_ns += report["table_wall_ns"]
        query_wall_ns += report["query_wall_ns"]
        assert receipt["process_wall_ns_exploratory"] >= (
            report["table_wall_ns"] + report["query_wall_ns"])
        process_wall_ns += receipt["process_wall_ns_exploratory"]
        peak_rss_global = max(peak_rss_global,
                              receipt["peak_child_rss_global_raw"])
        rows.append({
            "index": index, "workload_id": receipt["workload_id"],
            "known_target_generation_scalar_fixture":
                fixture_scalars[index],
            "status": status,
            "verified_relation": status == "found",
            "coefficient_row_mod_r": coefficient_row,
            "novel_rank_gain": novel,
            "rank_after_query": len(basis),
            "query_pair_sums_examined": report[
                "query_pair_sums_examined"],
            "table_wall_ns_exploratory": report["table_wall_ns"],
            "query_wall_ns_exploratory": report["query_wall_ns"],
            "query_field_calls": report["query_field_calls"],
            "receipt_sha256": sha(receipt_path),
        })
    assert sum(counts.values()) == 128
    assert counts["censored"] == counts["error"] == 0
    found = counts["found"]
    final_rank = len(basis)
    assert final_rank == sum(row["novel_rank_gain"] for row in rows)
    for pivot, row in basis.items():
        assert row[pivot] == 1
        assert all(other == pivot or row[other] == 0 for other in basis)
    sage_rows = [row["coefficient_row_mod_r"] for row in rows
                 if row["coefficient_row_mod_r"] is not None]
    assert int(matrix(GF(modulus), sage_rows).rank()) == final_rank
    compact = [{"status": row["status"],
                "query_wall_ns": row["query_wall_ns_exploratory"],
                **{f"query_{primitive}": row["query_field_calls"][primitive]
                   for primitive in PRIMITIVES}}
               for row in rows]
    return {
        "kind": "q1469_n53_ordinary_relation_supply_audit",
        "status": "passed", "proposal_id": "Q1469",
        "candidate_id": None, "isogeny": "none",
        "panel_workload_id": protocol["panel_workload_id"],
        "target_count": 128,
        "status_counts": counts,
        "verified_relation_count": found,
        "natural_relation_yield": wilson(found, 128),
        "final_relation_matrix_rank": final_rank,
        "folded_columns_K": 26,
        "novel_rank_per_query_decimal": format(final_rank / 128, ".9f"),
        "novel_rank_per_verified_relation_decimal": (
            format(final_rank / found, ".9f") if found else None),
        "canonical_signed_frobenius_eigenvalue_mod_r": eigenvalue,
        "relation_matrix_modulus_r": modulus,
        "target_query_field_calls_total": totals["query"],
        "target_independent_table_field_calls_total": totals["table"],
        "target_query_wall_ns_total_exploratory": query_wall_ns,
        "target_independent_table_wall_ns_total_exploratory": table_wall_ns,
        "cold_process_wall_ns_total_exploratory": process_wall_ns,
        "peak_child_rss_global_raw": peak_rss_global,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "query_wall_ns_per_verified_relation_exploratory":
            bootstrap_ratio(compact, "query_wall_ns", found),
        "query_field_calls_per_verified_relation_bootstrap": {
            primitive: bootstrap_ratio(compact, f"query_{primitive}", found)
            for primitive in PRIMITIVES},
        "query_field_calls_per_verified_relation": (
            {key: format(value / found, ".6f")
             for key, value in totals["query"].items()} if found else None),
        "query_field_calls_per_novel_row": (
            {key: format(value / final_rank, ".6f")
             for key, value in totals["query"].items()}
            if final_rank else None),
        "rows": rows,
        "protocol_sha256": sha(PROTOCOL),
        "auditor_source_sha256": sha(Path(__file__)),
        "measurement_scope": (
            "secondary N53 ordinary relation supply and row rank on "
            "one exact density-matched base; seeded pseudorandom target "
            "law, fresh pair table per target, exploratory wall time"),
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
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) +
                          "\n")
    else:
        assert result == json.loads(RESULT.read_text())
    print(json.dumps({"status": result["status"],
                      "found": result["verified_relation_count"],
                      "rank": result["final_relation_matrix_rank"]}),
          flush=True)


if __name__ == "__main__":
    main()
