#!/usr/bin/env python3
"""Compare a sound partial S3 span filter with exact sparse completions."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1428_bilinear_span.screen import relaxed_feasible, s3  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_sparse_partner(onb, m: int, a0_coords: int, b0_coords: int,
                         k: int, w: int, slack: int) -> dict:
    """Enumerate every allowed a completion; root the exact b equation."""
    n = onb.m
    fixed_mask = (1 << (n - k)) - 1
    free = range(n - k, n)
    root_calls = 0
    roots_seen = 0
    for added in range(slack + 1):
        for positions in itertools.combinations(free, added):
            a_coords = a0_coords | sum(1 << i for i in positions)
            assert a_coords and a_coords.bit_count() <= w
            a = onb.fromCoords(a_coords)
            root_calls += 1
            for b in s3_roots(onb, a, m):
                roots_seen += 1
                b_coords = onb.toCoords(b)
                if not b_coords or b_coords.bit_count() > w:
                    continue
                if b_coords & fixed_mask != b0_coords:
                    continue
                assert s3(onb, a, b, m) == 0
                return {"has_pair": True, "root_calls": root_calls,
                        "roots_seen": roots_seen,
                        "witness_a_coords": a_coords,
                        "witness_b_coords": b_coords}
    return {"has_pair": False, "root_calls": root_calls,
            "roots_seen": roots_seen,
            "witness_a_coords": None, "witness_b_coords": None}


def build() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1429"
    assert protocol["source_sha256"] == sha(Path(__file__))
    for name, digest in protocol["dependency_sha256"].items():
        assert sha(PARENT / name) == digest
    assert protocol["field_source_sha256"] == sha(
        ROOT / "ecc2k130/codegen/field.py")
    assert protocol["q1427_protocol_sha256"] == sha(
        PARENT / "q1427_interleaved_pair/protocol.json")
    assert protocol["q1428_protocol_sha256"] == sha(
        PARENT / "q1428_bilinear_span/protocol.json")
    assert protocol["q1425_pair_support_sha256"] == sha(
        PARENT / "q1425_reverse_pair/pair_support_screen.json")
    assert protocol["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    samples = []
    for item in protocol["degrees"]:
        n, w = item["degree_n"], item["weight_bound"]
        onb = field.Onb(n)
        basis = [onb.fromCoords(1 << i) for i in range(n)]
        for k in item["free_suffix_sizes"]:
            for slack in item["weight_slacks"]:
                assert 0 < slack < w and n - k >= w - slack
                fixed_one_count = w - slack
                domain_size = sum(math.comb(k, j)
                                  for j in range(slack + 1))
                assert domain_size <= protocol[
                    "maximum_exact_root_calls_per_sample"]
                rng = random.Random(protocol["seed"] + 100000 * n +
                                    100 * k + slack)
                for repetition in range(item["samples_per_cell"]):
                    m_coords = rng.randrange(1, 1 << n)
                    fixed = list(range(n - k))
                    a_coords = sum(1 << i for i in rng.sample(
                        fixed, fixed_one_count))
                    b_coords = sum(1 << i for i in rng.sample(
                        fixed, fixed_one_count))
                    m = onb.fromCoords(m_coords)
                    free = list(range(n - k, n))
                    relaxation = relaxed_feasible(
                        onb, basis, onb.fromCoords(a_coords),
                        onb.fromCoords(b_coords), m, free, free)
                    exact = exact_sparse_partner(
                        onb, m, a_coords, b_coords, k, w, slack)
                    assert relaxation["constant_in_span"] or not exact[
                        "has_pair"]
                    assert exact["has_pair"] or exact[
                        "root_calls"] == domain_size
                    samples.append({
                        "degree_n": n, "curve_id": item["curve_id"],
                        "free_suffix_size_each_leaf": k,
                        "remaining_weight_capacity_each_leaf": slack,
                        "fixed_one_count_each_leaf": fixed_one_count,
                        "repetition": repetition,
                        "m_coords": m_coords,
                        "a0_coords": a_coords,
                        "b0_coords": b_coords,
                        "exact_a_completion_domain_size": domain_size,
                        "linear_span_rank": relaxation["rank"],
                        "span_rejects": not relaxation["constant_in_span"],
                        "cross_columns_tested": relaxation[
                            "cross_columns_tested"],
                        **exact,
                    })
    grouped = []
    for item in protocol["degrees"]:
        n = item["degree_n"]
        for k in item["free_suffix_sizes"]:
            for slack in item["weight_slacks"]:
                cell = [row for row in samples if row["degree_n"] == n
                        and row["free_suffix_size_each_leaf"] == k
                        and row["remaining_weight_capacity_each_leaf"] ==
                        slack]
                assert len(cell) == item["samples_per_cell"]
                grouped.append({
                    "degree_n": n, "curve_id": item["curve_id"],
                    "free_suffix_size_each_leaf": k,
                    "remaining_weight_capacity_each_leaf": slack,
                    "samples": len(cell),
                    "minimum_rank": min(row["linear_span_rank"] for row in cell),
                    "maximum_rank": max(row["linear_span_rank"] for row in cell),
                    "span_rejections": sum(row["span_rejects"] for row in cell),
                    "exact_pairs_found": sum(row["has_pair"] for row in cell),
                    "exact_root_calls": sum(row["root_calls"] for row in cell),
                    "exact_root_calls_saved_if_filter_first": sum(
                        row["root_calls"] for row in cell
                        if row["span_rejects"]),
                    "cross_columns_tested": sum(
                        row["cross_columns_tested"] for row in cell),
                })
    return {
        "kind": "q1429_weight_unsaturated_s3_span_vs_exact_completion_screen",
        "proposal_id": "Q1429", "candidate_id": None,
        "isogeny": "none", "samples": samples, "cells": grouped,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "is_empirical_solver_measurement": False,
        "is_natural_relation_yield_measurement": False,
        "complete_solve_work_log2": None,
        "scope": (
            "Uniform nonzero intermediates and synthetic partial leaves "
            "with unfilled weight capacity. Exact completion checks the "
            "S3 equation and normal-basis weight/prefix constraints, but "
            "does not impose curve lifting, subgroup base membership, or "
            "a target link. Counts are field-root calls and bilinear "
            "columns, not equivalent work units or an ordinary solver "
            "measurement. No degree-131 complete work follows."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert OUTPUT.read_text() == content
    else:
        assert not OUTPUT.exists()
        OUTPUT.write_text(content)
    print(json.dumps({"status": "PASS", "samples": len(result["samples"]),
                      "span_rejections": sum(row["span_rejections"]
                                             for row in result["cells"]),
                      "exact_pairs_found": sum(row["exact_pairs_found"]
                                               for row in result["cells"])}))


if __name__ == "__main__":
    main()
