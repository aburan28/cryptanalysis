#!/usr/bin/env python3
"""Compare native exact-tail counts with direct Sage S3 enumeration."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1432 = PARENT / "q1432_coefficient_cache"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1428_bilinear_span.screen import s3  # noqa: E402
from q1432_coefficient_cache.validate_span import (  # noqa: E402
    make_cases, witness_case_data)

RESULT = HERE / "tail_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_degree(n: int) -> dict:
    weight, mid, witness_a, witness_b, sources = witness_case_data(n)
    cases, case_sources = make_cases(n)
    cases = [case for case in cases if
             weight - case["a_ones"].bit_count() == 1 and
             weight - case["b_ones"].bit_count() == 1]
    full = (1 << n) - 1
    for a_bit in [j for j in range(n) if witness_a >> j & 1][:2]:
        for b_bit in [j for j in range(n) if witness_b >> j & 1][:2]:
            a_fixed = full ^ (1 << a_bit)
            b_fixed = full ^ (1 << b_bit)
            cases.append({"kind": "minimal_verified_witness",
                          "m": mid, "a_fixed": a_fixed,
                          "a_ones": witness_a & a_fixed,
                          "b_fixed": b_fixed,
                          "b_ones": witness_b & b_fixed})
    assert cases
    case_text = "Q1434TAIL1 " + str(len(cases)) + "\n"
    for case in cases:
        case_text += " ".join(format(case[name], "x") for name in
                              ("m", "a_fixed", "a_ones", "b_fixed",
                               "b_ones")) + "\n"
    with tempfile.TemporaryDirectory(prefix="q1434-tail-") as directory:
        path = Path(directory) / "cases.txt"
        path.write_text(case_text)
        completed = subprocess.run(
            [str(HERE / "tail_probe"), str(Q1420 / f"n{n}_field.txt"),
             str(path)], check=True, capture_output=True, text=True)
    assert not completed.stderr
    native = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(native) == len(cases)
    onb = field.Onb(n)
    rows = []
    for index, (case, observed) in enumerate(zip(cases, native)):
        free_a = [j for j in range(n) if not case["a_fixed"] >> j & 1]
        free_b = [j for j in range(n) if not case["b_fixed"] >> j & 1]
        a_values = [case["a_ones"]] + [case["a_ones"] | 1 << j
                                        for j in free_a]
        b_values = [case["b_ones"]] + [case["b_ones"] | 1 << j
                                        for j in free_b]
        a_field = [onb.fromCoords(value) for value in a_values]
        b_field = [onb.fromCoords(value) for value in b_values]
        m_field = onb.fromCoords(case["m"])
        roots = [(a_value, b_value)
                 for a_value, a_element in zip(a_values, a_field)
                 for b_value, b_element in zip(b_values, b_field)
                 if s3(onb, a_element, b_element, m_field) == 0]
        assert observed["index"] == index
        assert observed["candidates"] == len(a_values) * len(b_values)
        assert observed["solutions"] == len(roots)
        assert observed["field_inv_calls"] == 0
        if len(roots) == 1:
            assert int(observed["unique_a_onb_hex"], 16) == roots[0][0]
            assert int(observed["unique_b_onb_hex"], 16) == roots[0][1]
        else:
            assert observed["unique_a_onb_hex"] == "0" or roots
        if case["kind"] in ("verified_witness_completion",
                            "minimal_verified_witness"):
            assert (witness_a, witness_b) in roots
        rows.append({"index": index, "kind": case["kind"],
                     "candidates": observed["candidates"],
                     "solutions": observed["solutions"],
                     "field_mul_calls": observed["field_mul_calls"],
                     "field_sqr_calls": observed["field_sqr_calls"]})
    return {
        "degree_n": n, "cases": rows,
        "zero_solution_cases": sum(row["solutions"] == 0 for row in rows),
        "unique_solution_cases": sum(row["solutions"] == 1 for row in rows),
        "witness_false_rejections": sum(
            row["solutions"] == 0 for row in rows if row["kind"] in
            ("verified_witness_completion", "minimal_verified_witness")),
        "case_input_sha256": hashlib.sha256(case_text.encode()).hexdigest(),
        "probe_stdout_sha256": hashlib.sha256(
            completed.stdout.encode()).hexdigest(),
        "cache_payload_bytes_lower_bound": native[-1][
            "cache_payload_bytes_lower_bound"],
        "q1432_case_sources": case_sources,
        "verified_witness_sources": sources,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    degrees = [check_degree(n) for n in (53, 83)]
    result = {
        "kind": "q1434_native_exact_tail_vs_direct_sage_s3_validation",
        "proposal_id": "Q1434", "candidate_id": None,
        "isogeny": "none", "degrees": degrees,
        "total_cases": sum(len(row["cases"]) for row in degrees),
        "total_witness_false_rejections": sum(
            row["witness_false_rejections"] for row in degrees),
        "total_zero_solution_cases": sum(
            row["zero_solution_cases"] for row in degrees),
        "total_unique_solution_cases": sum(
            row["unique_solution_cases"] for row in degrees),
        "native_probe_sha256": sha(HERE / "tail_probe"),
        "native_header_sha256": sha(HERE / "exact_tail.hpp"),
        "cached_header_sha256": sha(Q1432 / "cached_span.hpp"),
        "oracle_source_sha256": sha(PARENT /
                                    "q1428_bilinear_span/screen.py"),
        "source_sha256": sha(Path(__file__)),
        "scope": (
            "Native cached-coefficient exact-tail counts and unique "
            "coordinates match direct Sage S3 enumeration on archived "
            "ordinary partial trails, synthetic states, and independently "
            "verified witness completions. This is a local clause-soundness "
            "control, not a natural relation yield or complete IC cost."),
    }
    assert result["total_witness_false_rejections"] == 0
    assert result["total_zero_solution_cases"] > 0
    assert result["total_unique_solution_cases"] > 0
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert RESULT.read_text() == content
    else:
        assert not RESULT.exists()
        RESULT.write_text(content)
    print(json.dumps({"status": "PASS", "cases": result["total_cases"],
                      "zero": result["total_zero_solution_cases"],
                      "unique": result["total_unique_solution_cases"]}))


if __name__ == "__main__":
    main()
