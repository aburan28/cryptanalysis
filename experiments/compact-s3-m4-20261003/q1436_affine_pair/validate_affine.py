#!/usr/bin/env python3
"""Independently compare affine-pair decisions with direct Sage S3 enumeration."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1435 = PARENT / "q1435_bounded_tail"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1428_bilinear_span.screen import s3  # noqa: E402
from q1432_coefficient_cache.validate_span import witness_case_data  # noqa: E402

RESULT = HERE / "affine_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def partial(value: int, n: int, free_ones: int, free_zeros: int,
            rng: random.Random) -> tuple[int, int]:
    ones = [j for j in range(n) if value >> j & 1]
    zeros = [j for j in range(n) if not value >> j & 1]
    free = rng.sample(ones, free_ones) + rng.sample(zeros, free_zeros)
    fixed = ((1 << n) - 1) ^ sum(1 << j for j in free)
    return fixed, value & fixed


def direct_roots(onb, case: dict, weight: int) -> list[tuple[int, int]]:
    n = onb.m

    def values(fixed: int, ones: int) -> list[int]:
        free = [j for j in range(n) if not fixed >> j & 1]
        slack = weight - ones.bit_count()
        return [ones | sum(1 << j for j in bits)
                for size in range(slack + 1)
                for bits in itertools.combinations(free, size)]

    aa = values(case["a_fixed"], case["a_ones"])
    bb = values(case["b_fixed"], case["b_ones"])
    m = onb.fromCoords(case["m"])
    b_fields = [(b, onb.fromCoords(b)) for b in bb]
    return [(a, b) for a in aa
            for b, b_field in b_fields
            if s3(onb, onb.fromCoords(a), b_field, m) == 0]


def check_degree(n: int) -> dict:
    weight, witness_mid, witness_a, witness_b, sources = witness_case_data(n)
    rng = random.Random(1436 + n)
    receipt_path = Q1435 / "runs" / f"n{n}_ordinary" / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["solver_status"] == "censored"
    cases = []
    for snap in receipt["solver_report"]["tail_zero_snapshots"]:
        cases.append({"kind": "archived_ordinary_zero",
                      "m": int(snap["mid_onb_hex"], 16),
                      "a_fixed": int(snap["a_fixed_mask_onb_hex"], 16),
                      "a_ones": int(snap["a_ones_onb_hex"], 16),
                      "b_fixed": int(snap["b_fixed_mask_onb_hex"], 16),
                      "b_ones": int(snap["b_ones_onb_hex"], 16)})
    assert len(cases) == 16
    for slack_a, slack_b, free_a, free_b in (
            (1, 1, 5, 7), (1, 3, 5, 8), (2, 2, 6, 7),
            (2, 3, 6, 8), (2, 4, 6, 8)):
        if slack_b > weight:
            continue
        af, ao = partial(witness_a, n, slack_a, free_a - slack_a, rng)
        bf, bo = partial(witness_b, n, slack_b, free_b - slack_b, rng)
        cases.append({"kind": "verified_witness", "m": witness_mid,
                      "a_fixed": af, "a_ones": ao,
                      "b_fixed": bf, "b_ones": bo})
    for slack_a, slack_b, free_a, free_b in (
            (1, 1, 7, 9), (1, 3, 7, 9),
            (2, 2, 8, 9), (2, 3, 8, 9)):
        af, ao = partial(witness_a, n, slack_a, free_a - slack_a, rng)
        bf, bo = partial(witness_b, n, slack_b, free_b - slack_b, rng)
        cases.append({"kind": "synthetic_wrong_mid",
                      "m": rng.randrange(1, 1 << n),
                      "a_fixed": af, "a_ones": ao,
                      "b_fixed": bf, "b_ones": bo})
    text = f"Q1436AFFINE1 {len(cases)}\n" + "".join(
        " ".join(format(case[key], "x") for key in
                 ("m", "a_fixed", "a_ones", "b_fixed", "b_ones")) + "\n"
        for case in cases)
    with tempfile.TemporaryDirectory(prefix="q1436-affine-") as directory:
        input_path = Path(directory) / "cases.txt"
        input_path.write_text(text)
        completed = subprocess.run(
            [str(HERE / "affine_probe"), str(Q1420 / f"n{n}_field.txt"),
             str(input_path)], capture_output=True, text=True, check=True)
    assert not completed.stderr
    observed = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(observed) == len(cases)
    onb = field.Onb(n)
    rows = []
    for index, (case, got) in enumerate(zip(cases, observed)):
        roots = direct_roots(onb, case, weight)
        assert got["index"] == index
        assert got["feasible"] or not roots
        if got["unique"]:
            assert roots == [(int(got["unique_a_onb_hex"], 16),
                              int(got["unique_b_onb_hex"], 16))]
        if got["rank_deficient_options"] == 0:
            assert got["feasible"] == bool(roots)
            assert got["exact_solutions"] == len(roots)
        assert got["field_inv_calls"] == 0
        if case["kind"] == "verified_witness":
            assert (witness_a, witness_b) in roots
            assert got["feasible"]
        rows.append({"kind": case["kind"], "index": index,
                     "exact_roots": len(roots),
                     "feasible": got["feasible"],
                     "rank_deficient_options": got[
                         "rank_deficient_options"],
                     "coefficient_columns": got["coefficient_columns"],
                     "xor_ops": got["xor_ops"],
                     "field_mul_calls": got["field_mul_calls"],
                     "field_sqr_calls": got["field_sqr_calls"]})
    return {"degree_n": n, "rows": rows,
            "archived_q1435_receipt_sha256": sha(receipt_path),
            "witness_sources": sources,
            "case_input_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "probe_stdout_sha256": hashlib.sha256(
                completed.stdout.encode()).hexdigest(),
            "zero_cases": sum(not row["exact_roots"] for row in rows),
            "witness_cases": sum(row["kind"] == "verified_witness"
                                 for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    degrees = [check_degree(n) for n in (53, 83)]
    result = {"kind": "q1436_affine_pair_vs_direct_sage_s3",
              "proposal_id": "Q1436", "candidate_id": None,
              "isogeny": "none", "degrees": degrees,
              "total_cases": sum(len(row["rows"]) for row in degrees),
              "total_zero_cases": sum(row["zero_cases"] for row in degrees),
              "total_witness_cases": sum(row["witness_cases"]
                                         for row in degrees),
              "native_probe_sha256": sha(HERE / "affine_probe"),
              "native_header_sha256": sha(HERE / "affine_pair.hpp"),
              "oracle_source_sha256": sha(PARENT /
                                          "q1428_bilinear_span/screen.py"),
              "source_sha256": sha(Path(__file__)),
              "scope": "Sound local feasibility and uniqueness check; "
                       "archived zero trails, synthetic states, and known "
                       "witnesses. No natural-query yield or N131 estimate."}
    assert result["total_zero_cases"] > 0
    assert result["total_witness_cases"] == 9
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert RESULT.read_text() == content
    else:
        assert not RESULT.exists()
        RESULT.write_text(content)
    print(json.dumps({"status": "PASS", "cases": result["total_cases"],
                      "zero": result["total_zero_cases"],
                      "witness": result["total_witness_cases"]}))


if __name__ == "__main__":
    main()
