#!/usr/bin/env python3
"""Measure exact midpoint-set sizes on Q1459's bounded archived states."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1459 = PARENT / "q1459_leaf_lift_screen"
PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "result.json"
BINARY = HERE / "midpoint_profile"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_protocol(protocol: dict) -> None:
    assert protocol["proposal_id"] == "Q1460"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["pair_candidate_cap"] == 4096
    assert protocol["generic_fixed_state_target_x_bound"] == 2 ** 27
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    build = json.loads((HERE / "compile_receipt.json").read_text())
    assert sha(BINARY) == build["binary_sha256"]


def jobs(prior: dict, protocol: dict) -> list[dict]:
    result = []
    prior_by_case = {row["case"]: row for row in prior["rows"]}
    assert set(prior_by_case) == set(protocol["run_order"])
    for name in protocol["run_order"]:
        cell = protocol["cells"][name]
        parent = prior_by_case[name]
        for key in ("curve_id", "workload_id", "factor_base_actual_B",
                    "folded_columns_K", "factor_base_enumerated_set_sha256"):
            assert cell[key] == parent[key], (name, key)
        for state in parent["states"]:
            for mode, admitted in (
                ("raw", state["raw_cap_admitted"]),
                ("lift", state["lift_filtered_cap_admitted"])):
                if admitted is True:
                    result.append({
                        "cell": name,
                        "degree_n": cell["degree_n"],
                        "weight": cell["normal_basis_weight_bound"],
                        "state_index": state["state_index"],
                        "target_preimage_index": state["target_preimage_index"],
                        "mode": mode,
                        "leaf_fixed_mask_onb_hex": state[
                            "leaf_fixed_mask_onb_hex"],
                        "leaf_ones_onb_hex": state[
                            "leaf_ones_onb_hex"],
                        "expected_raw_leaf_counts": state[
                            "raw_leaf_option_counts"],
                        "expected_leaf_counts": (state[
                            "raw_leaf_option_counts"] if mode == "raw" else
                            state["liftable_leaf_option_counts"]),
                        "expected_pair_candidates": (state[
                            "raw_pair_candidate_counts"] if mode == "raw"
                            else state["liftable_pair_candidate_counts"]),
                    })
    return result


def native_rows(selected: list[dict]) -> list[dict]:
    output = []
    for n in (53, 83):
        group = [row for row in selected if row["degree_n"] == n]
        weight = group[0]["weight"]
        assert group and all(row["weight"] == weight for row in group)
        field = PARENT / "q1420_root_theory" / f"n{n}_field.txt"
        lines = []
        for row in group:
            words = [row["cell"], str(row["state_index"]), row["mode"]]
            for fixed, ones in zip(row["leaf_fixed_mask_onb_hex"],
                                   row["leaf_ones_onb_hex"]):
                words.extend((fixed, ones))
            lines.append(" ".join(words))
        completed = subprocess.run(
            [str(BINARY), str(field), str(weight)],
            input="\n".join(lines) + "\n", capture_output=True, text=True,
            check=True)
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        assert len(rows) == len(group)
        for job, row in zip(group, rows):
            for key in ("cell", "state_index", "mode"):
                assert job[key] == row[key], (job, row, key)
            assert row["raw_leaf_counts"] == job["expected_raw_leaf_counts"]
            assert row["leaf_counts"] == job["expected_leaf_counts"]
            assert row["pair_candidates"] == job["expected_pair_candidates"]
            assert max(row["pair_candidates"]) <= 4096
            assert row["target_x_support_upper_bound"] == (
                2 * math.prod(row["midpoint_cardinalities"]))
            assert row["target_x_support_upper_bound"] <= 2 ** 27
            assert all(m <= 2 * p for m, p in zip(
                row["midpoint_cardinalities"], row["pair_candidates"]))
            row.update({key: job[key] for key in (
                "degree_n", "weight", "target_preimage_index",
                "leaf_fixed_mask_onb_hex", "leaf_ones_onb_hex")})
            row["raw_field_x_count"] = 2 ** n
            row["raw_field_coverage_ceiling_log2"] = format(
                math.log2(row["target_x_support_upper_bound"]) - n,
                ".3f") if row["target_x_support_upper_bound"] else None
            output.append(row)
    return output


def make_result() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    check_protocol(protocol)
    prior = json.loads((Q1459 / "result.json").read_text())
    assert sha(Q1459 / "result.json") == protocol[
        "parent_q1459_result_sha256"]
    selected = jobs(prior, protocol)
    rows = native_rows(selected)
    by_case = {}
    for name in protocol["run_order"]:
        cell = protocol["cells"][name]
        subset = [row for row in rows if row["cell"] == name]
        by_case[name] = {
            "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "input_role": cell["input_role"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "raw_states": sum(row["mode"] == "raw" for row in subset),
            "lift_states": sum(row["mode"] == "lift" for row in subset),
            "max_raw_state_target_x_support_upper_bound": max(
                (row["target_x_support_upper_bound"] for row in subset
                 if row["mode"] == "raw"), default=0),
            "max_lift_state_target_x_support_upper_bound": max(
                (row["target_x_support_upper_bound"] for row in subset
                 if row["mode"] == "lift"), default=0),
            "root_pair_inputs": sum(sum(row["pair_candidates"])
                                    for row in subset),
            "root_mul_calls": sum(row["root_mul_calls"] for row in subset),
            "root_sqr_calls": sum(row["root_sqr_calls"] for row in subset),
            "root_inv_calls": sum(row["root_inv_calls"] for row in subset),
            "lift_inv_calls": sum(row["lift_inv_calls"] for row in subset),
        }
    return {
        "kind": "q1460_fixed_state_target_x_support_screen",
        "proposal_id": "Q1460", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "protocol_sha256": sha(PROTOCOL),
        "binary_sha256": sha(BINARY),
        "parent_q1459_result_sha256": sha(Q1459 / "result.json"),
        "generic_fixed_state_target_x_bound": 2 ** 27,
        "interpretation_scope": "fixed state only; adaptive search may select states using the target",
        "cases": by_case,
        "rows": rows,
        "successful_decomposition_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_result()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1460 fixed-state support screen: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1460", "cases": result["cases"]}))


if __name__ == "__main__":
    main()
