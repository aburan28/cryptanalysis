#!/usr/bin/env python3
"""Compare Q1431's native span check with the independent Sage oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1427 = PARENT / "q1427_interleaved_pair"
Q1428 = PARENT / "q1428_bilinear_span"
Q1430 = PARENT / "q1430_partial_trail"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1428_bilinear_span.screen import relaxed_feasible  # noqa: E402

RESULT = HERE / "span_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_bits(path: Path) -> dict[int, bool]:
    model = {}
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            for token in line[2:].split():
                lit = int(token)
                if lit:
                    assert abs(lit) not in model
                    model[abs(lit)] = lit > 0
    assert model
    return model


def witness_case_data(n: int):
    key = f"n{n}_free_partner"
    protocol = json.loads((Q1427 / "protocol.json").read_text())
    workload = protocol["workloads"][key]
    parent_key = workload["parent_q1420_key"]
    words = (Q1420 / "runs" / parent_key / "variables.txt").read_text().split()
    assert words[0] == "Q1420MAP1" and int(words[1]) == n
    w = int(words[2])
    rows = [[int(words[3 + i * n + j]) for j in range(n)]
            for i in range(6)]
    model_path = Q1427 / "runs" / key / "solver.model.txt"
    model = model_bits(model_path)
    coordinates = [sum(1 << j for j, var in enumerate(row) if model[var])
                   for row in rows]
    receipt_path = Q1427 / "runs" / key / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["model_check"]["status"] == (
        "verified_four_point_relation")
    assert coordinates[:4] == receipt["model_check"]["raw_leaf_x"]
    assert coordinates[2].bit_count() == coordinates[3].bit_count() == w
    return w, coordinates[5], coordinates[2], coordinates[3], {
        "receipt_sha256": sha(receipt_path),
        "model_sha256": sha(model_path),
        "variable_map_sha256": sha(Q1420 / "runs" / parent_key /
                                   "variables.txt"),
    }


def make_cases(n: int):
    rng = random.Random(1431 + n)
    w, witness_mid, witness_a, witness_b, witness_sources = (
        witness_case_data(n))
    threshold = 14 if n == 53 else 20
    full = (1 << n) - 1
    ordinary_path = Q1430 / "runs" / f"n{n}_ordinary" / "receipt.json"
    ordinary = json.loads(ordinary_path.read_text())
    assert ordinary["solver_status"] == "censored"
    cases = []
    for snapshot in ordinary["solver_report"]["screen_snapshots"]:
        cases.append({
            "kind": "archived_ordinary_trail",
            "m": int(snapshot["mid_onb_hex"], 16),
            "a_fixed": int(snapshot["a_fixed_mask_onb_hex"], 16),
            "a_ones": int(snapshot["a_ones_onb_hex"], 16),
            "b_fixed": int(snapshot["b_fixed_mask_onb_hex"], 16),
            "b_ones": int(snapshot["b_ones_onb_hex"], 16),
        })
    assert len(cases) == 16
    for index in range(24):
        k_a = threshold - index % 5
        k_b = threshold - (index * 2) % 5
        slack_a = 1 + index % 2
        slack_b = 1 + (index // 2) % 2

        def partial(k, slack):
            free = set(rng.sample(range(n), k))
            fixed = full ^ sum(1 << j for j in free)
            ones = sum(1 << j for j in rng.sample(
                [j for j in range(n) if j not in free], w - slack))
            return fixed, ones

        a_fixed, a_ones = partial(k_a, slack_a)
        b_fixed, b_ones = partial(k_b, slack_b)
        cases.append({
            "kind": "synthetic_partial",
            "m": 0 if index == 0 else rng.randrange(1, 1 << n),
            "a_fixed": a_fixed, "a_ones": a_ones,
            "b_fixed": b_fixed, "b_ones": b_ones,
        })
    for index in range(16):
        slack_a = 1 + index % 2
        slack_b = 1 + (index // 2) % 2

        def witness_partial(value, slack):
            ones = [j for j in range(n) if value >> j & 1]
            zeros = [j for j in range(n) if not (value >> j & 1)]
            free = set(rng.sample(ones, slack) +
                       rng.sample(zeros, threshold - slack))
            fixed = full ^ sum(1 << j for j in free)
            return fixed, value & fixed

        a_fixed, a_ones = witness_partial(witness_a, slack_a)
        b_fixed, b_ones = witness_partial(witness_b, slack_b)
        cases.append({
            "kind": "verified_witness_completion",
            "m": witness_mid,
            "a_fixed": a_fixed, "a_ones": a_ones,
            "b_fixed": b_fixed, "b_ones": b_ones,
        })
    assert len(cases) == 56
    return cases, {
        "q1430_ordinary_receipt_sha256": sha(ordinary_path),
        "q1427_verified_witness": witness_sources,
    }


def check_degree(n: int):
    cases, sources = make_cases(n)
    case_text = "Q1431SPAN1 " + str(len(cases)) + "\n"
    for case in cases:
        case_text += " ".join(format(case[name], "x") for name in
                              ("m", "a_fixed", "a_ones", "b_fixed",
                               "b_ones")) + "\n"
    with tempfile.TemporaryDirectory(prefix="q1431-span-") as temporary:
        case_path = Path(temporary) / "cases.txt"
        case_path.write_text(case_text)
        completed = subprocess.run(
            [str(HERE / "span_probe"), str(Q1420 / f"n{n}_field.txt"),
             str(case_path)], check=True, capture_output=True, text=True)
    assert not completed.stderr
    native = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(native) == len(cases)
    onb = field.Onb(n)
    basis = [onb.fromCoords(1 << i) for i in range(n)]
    rows = []
    for index, (case, observed) in enumerate(zip(cases, native)):
        assert observed["index"] == index
        free_a = [j for j in range(n) if not case["a_fixed"] >> j & 1]
        free_b = [j for j in range(n) if not case["b_fixed"] >> j & 1]
        expected = relaxed_feasible(
            onb, basis, onb.fromCoords(case["a_ones"]),
            onb.fromCoords(case["b_ones"]), onb.fromCoords(case["m"]),
            free_a, free_b)
        assert observed["feasible"] == expected["constant_in_span"]
        assert observed["rank"] == expected["rank"]
        assert observed["bilinear_columns"] == expected[
            "cross_columns_tested"]
        assert observed["linear_columns"] == len(free_a) + len(free_b)
        assert observed["field_inv_calls"] == 0
        if case["kind"] == "verified_witness_completion":
            assert observed["feasible"]
        rows.append({
            "index": index, "kind": case["kind"],
            "m_onb_hex": format(case["m"], "x"),
            "a_fixed_mask_onb_hex": format(case["a_fixed"], "x"),
            "a_ones_onb_hex": format(case["a_ones"], "x"),
            "b_fixed_mask_onb_hex": format(case["b_fixed"], "x"),
            "b_ones_onb_hex": format(case["b_ones"], "x"),
            "rank": observed["rank"],
            "span_feasible": observed["feasible"],
            "linear_columns": observed["linear_columns"],
            "bilinear_columns": observed["bilinear_columns"],
            "field_mul_calls": observed["field_mul_calls"],
            "field_sqr_calls": observed["field_sqr_calls"],
        })
    return {
        "degree_n": n,
        "curve_id": json.loads((Q1430 / "protocol.json").read_text())[
            "workloads"][f"n{n}_ordinary"]["curve_id"],
        "cases": rows,
        "case_input_sha256": hashlib.sha256(case_text.encode()).hexdigest(),
        "probe_stdout_sha256": hashlib.sha256(
            completed.stdout.encode()).hexdigest(),
        "archived_trail_rejections": sum(
            not row["span_feasible"] for row in rows
            if row["kind"] == "archived_ordinary_trail"),
        "verified_witness_false_rejections": sum(
            not row["span_feasible"] for row in rows
            if row["kind"] == "verified_witness_completion"),
        **sources,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    degrees = [check_degree(n) for n in (53, 83)]
    result = {
        "kind": "q1431_native_vs_sage_span_validation",
        "proposal_id": "Q1431", "candidate_id": None,
        "isogeny": "none",
        "degrees": degrees,
        "total_cases": sum(len(row["cases"]) for row in degrees),
        "total_verified_witness_false_rejections": sum(
            row["verified_witness_false_rejections"] for row in degrees),
        "q1428_small_field_self_test_sha256": sha(
            Q1428 / "self_test.json"),
        "q1428_oracle_source_sha256": sha(Q1428 / "screen.py"),
        "q1430_protocol_sha256": sha(Q1430 / "protocol.json"),
        "native_probe_sha256": sha(HERE / "span_probe"),
        "native_header_sha256": sha(HERE / "span_filter.hpp"),
        "source_sha256": sha(Path(__file__)),
        "scope": (
            "The native span check matches the independent Sage rank and "
            "membership oracle on archived actual-trail states, synthetic "
            "states, and completions of independently verified four-point "
            "witnesses. This validates the native necessary condition, "
            "not a solver speedup or natural relation yield."),
    }
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert RESULT.read_text() == content
    else:
        assert not RESULT.exists()
        RESULT.write_text(content)
    print(json.dumps({
        "status": "PASS", "cases": result["total_cases"],
        "trail_rejections": sum(
            row["archived_trail_rejections"] for row in degrees),
        "witness_false_rejections": result[
            "total_verified_witness_false_rejections"]}))


if __name__ == "__main__":
    main()
