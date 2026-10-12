#!/usr/bin/env python3
"""Exact single-leaf lift-filtered admission screen on Q1456 states."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1456 = PARENT / "q1456_joint_domain_profile"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1455_joint_tail.joint_tail import (  # noqa: E402
    PartialLeaf, option_count, options)

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "result.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_protocol(protocol: dict) -> None:
    assert protocol["proposal_id"] == "Q1459"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["leaf_option_cap"] == protocol["pair_candidate_cap"] == 4096
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative


def screen(name: str, cell: dict, option_cap: int,
           pair_cap: int) -> dict:
    parent_path = Q1456 / "runs" / name / "receipt.json"
    receipt = json.loads(parent_path.read_text())
    report = receipt["solver_report"]
    assert receipt["case"] == name and receipt["workload_id"] == cell[
        "workload_id"]
    assert receipt["curve_id"] == cell["curve_id"]
    assert receipt["solver_status"] == "censored"
    assert report["unique_partial_states"] == len(report["domain_snapshots"])
    n, weight = cell["degree_n"], cell["normal_basis_weight_bound"]
    onb = field.Onb(n)
    cache: dict[PartialLeaf, int] = {}
    lift_tests = 0
    rows = []
    start = time.perf_counter_ns()
    for index, snapshot in enumerate(report["domain_snapshots"]):
        leaves = [PartialLeaf(int(mask, 16), int(ones, 16))
                  for mask, ones in zip(
                      snapshot["leaf_fixed_mask_onb_hex"],
                      snapshot["leaf_ones_onb_hex"])]
        assert len(leaves) == 4
        raw = [option_count(leaf, n, weight) for leaf in leaves]
        raw_pairs = [raw[0] * raw[1], raw[2] * raw[3]]
        assert raw_pairs == snapshot["pair_candidate_counts"]
        filtered: list[int] | None = None
        filtered_pairs: list[int] | None = None
        if max(raw) <= option_cap:
            filtered = []
            for leaf, raw_count in zip(leaves, raw):
                if leaf not in cache:
                    domain = options(leaf, n, weight)
                    assert len(domain) == raw_count
                    admissible = 0
                    for x_bits in domain:
                        x = onb.fromCoords(x_bits)
                        inverse = onb.inv(x)
                        if onb.trace(onb.add(x, inverse)) == 0:
                            admissible += 1
                    cache[leaf] = admissible
                    lift_tests += len(domain)
                filtered.append(cache[leaf])
            filtered_pairs = [filtered[0] * filtered[1],
                              filtered[2] * filtered[3]]
            assert all(a <= b for a, b in zip(filtered, raw))
        rows.append({
            "state_index": index,
            "target_preimage_index": snapshot["target_preimage_index"],
            "leaf_fixed_mask_onb_hex": snapshot[
                "leaf_fixed_mask_onb_hex"],
            "leaf_ones_onb_hex": snapshot["leaf_ones_onb_hex"],
            "raw_leaf_option_counts": raw,
            "raw_pair_candidate_counts": raw_pairs,
            "liftable_leaf_option_counts": filtered,
            "liftable_pair_candidate_counts": filtered_pairs,
            "raw_cap_admitted": max(raw_pairs) <= pair_cap,
            "lift_filtered_cap_admitted": (
                max(filtered_pairs) <= pair_cap if
                filtered_pairs is not None else None),
            "screen_skipped_over_leaf_cap": max(raw) > option_cap,
        })
    elapsed = time.perf_counter_ns() - start
    return {
        "case": name, "degree_n": n,
        "curve_id": cell["curve_id"],
        "workload_id": cell["workload_id"],
        "input_role": cell["input_role"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "total_unique_partial_states": len(rows),
        "screened_partial_states": sum(
            not row["screen_skipped_over_leaf_cap"] for row in rows),
        "raw_pair_cap_admissions": sum(row["raw_cap_admitted"] for row in rows),
        "lift_filtered_pair_cap_admissions": sum(
            row["lift_filtered_cap_admitted"] is True for row in rows),
        "new_admissions_due_to_lift_filter": sum(
            not row["raw_cap_admitted"] and
            row["lift_filtered_cap_admitted"] is True for row in rows),
        "empty_liftable_leaf_states": sum(
            row["liftable_leaf_option_counts"] is not None and
            0 in row["liftable_leaf_option_counts"] for row in rows),
        "distinct_leaf_domains_evaluated": len(cache),
        "leaf_lift_tests": lift_tests,
        "leaf_lift_field_inversions": lift_tests,
        "screen_wall_ns_exploratory": elapsed,
        "states": rows,
        "parent_receipt_sha256": sha(parent_path),
    }


def make_result() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    check_protocol(protocol)
    rows = [screen(name, protocol["cells"][name],
                   protocol["leaf_option_cap"],
                   protocol["pair_candidate_cap"])
            for name in protocol["run_order"]]
    return {
        "kind": "q1459_exact_lift_filtered_cap_admission_screen",
        "proposal_id": "Q1459", "candidate_id": None,
        "run_id": None, "isogeny": "none", "status": "pass",
        "point_decomposition_stage_code": "PDP4hybrid",
        "leaf_option_cap": protocol["leaf_option_cap"],
        "pair_candidate_cap": protocol["pair_candidate_cap"],
        "rows": rows,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "natural_relation_yield_estimate": None,
        "successful_decomposition_cost": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_result()
    if args.check:
        expected = json.loads(OUTPUT.read_text())
        for observed_row, expected_row in zip(result["rows"], expected["rows"]):
            observed_row["screen_wall_ns_exploratory"] = expected_row[
                "screen_wall_ns_exploratory"]
        assert result == expected
        print("Q1459 exact lift-filtered cap screen: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1459",
                          "raw_admissions": [row[
                              "raw_pair_cap_admissions"] for row in result[
                                  "rows"]],
                          "lift_admissions": [row[
                              "lift_filtered_pair_cap_admissions"] for row
                              in result["rows"]]}))


if __name__ == "__main__":
    main()
