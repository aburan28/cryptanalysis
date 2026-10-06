#!/usr/bin/env python3
"""Recount Q1459 leaf domains with the independent Q1422 native lift gate."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1422 = PARENT / "q1422_leaf_lift_gate"
Q1456 = PARENT / "q1456_joint_domain_profile"
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"
OUTPUT = HERE / "verification.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def domain(mask: int, ones: int, n: int, weight: int) -> tuple[int, ...]:
    assert 0 <= mask < (1 << n) and ones & ~mask == 0
    free = [i for i in range(n) if not (mask >> i & 1)]
    slack = weight - ones.bit_count()
    assert slack >= 0
    values = [ones | sum(1 << i for i in chosen)
              for size in range(min(slack, len(free)) + 1)
              for chosen in itertools.combinations(free, size)]
    return tuple(value for value in values if value)


def native_lift_map(n: int, values: set[int]) -> dict[int, bool]:
    validation = json.loads((Q1422 /
        f"n{n}_lift_validation.json").read_text())
    cli = Q1422 / "lift_gate_cli"
    assert validation["status"] == "PASS"
    assert validation["degree_n"] == n
    assert validation["lift_gate_cli_binary_sha256"] == sha(cli)
    assert validation["lift_gate_header_sha256"] == sha(Q1422 /
                                                      "lift_gate.hpp")
    field_file = PARENT / f"q1420_root_theory/n{n}_field.txt"
    assert validation["field_bridge_sha256"] == sha(field_file)
    ordered = sorted(values)
    completed = subprocess.run(
        [str(cli), str(field_file)],
        input="".join(f"{value:x}\n" for value in ordered),
        capture_output=True, text=True, check=True)
    lines = completed.stdout.splitlines()
    assert len(lines) == len(ordered)
    result = {}
    for value, line in zip(ordered, lines):
        encoded, bit = line.split()
        assert int(encoded, 16) == value
        assert bit in ("0", "1")
        result[value] = bit == "1"
    return result


def verify_degree(n: int, names: list[str], result_rows: dict,
                  protocol: dict) -> dict:
    domains: dict[tuple[int, int], tuple[int, ...]] = {}
    relevant = []
    for name in names:
        cell = protocol["cells"][name]
        parent_path = Q1456 / "runs" / name / "receipt.json"
        parent = json.loads(parent_path.read_text())
        snapshots = parent["solver_report"]["domain_snapshots"]
        row = result_rows[name]
        assert row["parent_receipt_sha256"] == sha(parent_path)
        assert row["total_unique_partial_states"] == len(snapshots)
        assert len(row["states"]) == len(snapshots)
        assert row["curve_id"] == cell["curve_id"]
        assert row["workload_id"] == cell["workload_id"]
        for index, (snapshot, state) in enumerate(zip(snapshots,
                                                       row["states"])):
            assert state["state_index"] == index
            for key in ("leaf_fixed_mask_onb_hex", "leaf_ones_onb_hex",
                        "target_preimage_index"):
                assert state[key] == snapshot[key]
            leaves = [(int(mask, 16), int(ones, 16))
                      for mask, ones in zip(
                          snapshot["leaf_fixed_mask_onb_hex"],
                          snapshot["leaf_ones_onb_hex"])]
            assert len(leaves) == 4
            raw = []
            for mask, ones in leaves:
                free = n - mask.bit_count()
                slack = cell["normal_basis_weight_bound"] - ones.bit_count()
                count = sum(math.comb(free, j)
                            for j in range(min(slack, free) + 1)) - int(
                                ones == 0)
                raw.append(count)
            assert raw == state["raw_leaf_option_counts"]
            pairs = [raw[0] * raw[1], raw[2] * raw[3]]
            assert pairs == state["raw_pair_candidate_counts"] == snapshot[
                "pair_candidate_counts"]
            admitted = max(pairs) <= protocol["pair_candidate_cap"]
            assert state["raw_cap_admitted"] == admitted
            if max(raw) <= protocol["leaf_option_cap"]:
                assert not state["screen_skipped_over_leaf_cap"]
                for mask, ones in leaves:
                    if (mask, ones) not in domains:
                        domains[mask, ones] = domain(
                            mask, ones, n, cell[
                                "normal_basis_weight_bound"])
                relevant.append((name, index, leaves, state))
            else:
                assert state["screen_skipped_over_leaf_cap"]
                assert state["liftable_leaf_option_counts"] is None
                assert state["liftable_pair_candidate_counts"] is None
                assert state["lift_filtered_cap_admitted"] is None
    all_values = {value for values in domains.values() for value in values}
    lift = native_lift_map(n, all_values)
    checked_states = 0
    for name, index, leaves, state in relevant:
        counts = [sum(lift[value] for value in domains[leaf])
                  for leaf in leaves]
        pairs = [counts[0] * counts[1], counts[2] * counts[3]]
        assert counts == state["liftable_leaf_option_counts"], (name, index)
        assert pairs == state["liftable_pair_candidate_counts"]
        assert state["lift_filtered_cap_admitted"] == (
            max(pairs) <= protocol["pair_candidate_cap"])
        checked_states += 1
    assert checked_states == sum(result_rows[name]["screened_partial_states"]
                                 for name in names)
    return {
        "degree_n": n,
        "unique_nonzero_x_native_checked": len(all_values),
        "distinct_leaf_domains_native_checked": len(domains),
        "partial_states_independently_checked": checked_states,
        "native_cli_sha256": sha(Q1422 / "lift_gate_cli"),
        "native_lift_validation_sha256": sha(Q1422 /
                                             f"n{n}_lift_validation.json"),
    }


def make_verification() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    result = json.loads(RESULT.read_text())
    assert protocol["proposal_id"] == result["proposal_id"] == "Q1459"
    assert result["status"] == "pass"
    assert result["protocol_sha256"] == sha(PROTOCOL)
    assert result["source_sha256"] == sha(HERE / "screen_lift.py")
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    rows = {row["case"]: row for row in result["rows"]}
    assert list(rows) == protocol["run_order"]
    degrees = [verify_degree(n, [name for name in protocol["run_order"]
                                 if protocol["cells"][name]["degree_n"] == n],
                             rows, protocol)
               for n in (53, 83)]
    assert [row["new_admissions_due_to_lift_filter"] for row in result[
        "rows"]] == [0, 0, 1]
    return {
        "kind": "q1459_native_independent_lift_count_audit",
        "proposal_id": "Q1459", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "degrees": degrees,
        "raw_admissions": [row["raw_pair_cap_admissions"] for row in
                           result["rows"]],
        "lift_filtered_admissions": [row[
            "lift_filtered_pair_cap_admissions"] for row in result["rows"]],
        "new_admissions": [row["new_admissions_due_to_lift_filter"]
                           for row in result["rows"]],
        "protocol_sha256": sha(PROTOCOL),
        "result_sha256": sha(RESULT),
        "source_sha256": sha(Path(__file__)),
        "successful_decomposition_cost": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_verification()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1459 independent native curve-lift audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1459",
                          "new_admissions": result["new_admissions"],
                          "native_x_checked": [row[
                              "unique_nonzero_x_native_checked"] for row
                              in result["degrees"]]}))


if __name__ == "__main__":
    main()
