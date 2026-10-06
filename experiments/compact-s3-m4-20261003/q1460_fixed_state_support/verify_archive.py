#!/usr/bin/env python3
"""Independently replay selected Q1460 midpoint sets with Sage ONB roots."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, options  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

import screen  # noqa: E402

OUTPUT = HERE / "verification.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sage_replay(row: dict) -> dict:
    n, weight = row["degree_n"], row["weight"]
    onb = field.Onb(n)
    domains = []
    for fixed, ones in zip(row["leaf_fixed_mask_onb_hex"],
                           row["leaf_ones_onb_hex"]):
        values = options(PartialLeaf(int(fixed, 16), int(ones, 16)),
                         n, weight)
        if row["mode"] == "lift":
            values = tuple(x for x in values if
                           onb.trace(onb.add(onb.fromCoords(x),
                                             onb.inv(onb.fromCoords(x)))) == 0)
        domains.append(values)
    assert [len(values) for values in domains] == row["leaf_counts"]
    distinct = []
    root_values = []
    for side in (0, 2):
        mids = set()
        total = 0
        for a, b in itertools.product(domains[side], domains[side + 1]):
            roots = s3_roots(onb, onb.fromCoords(a), onb.fromCoords(b))
            total += len(roots)
            mids.update(onb.toCoords(x) for x in roots)
        distinct.append(len(mids))
        root_values.append(total)
    assert distinct == row["midpoint_cardinalities"]
    assert root_values == row["pair_root_values"]
    return {
        "cell": row["cell"], "state_index": row["state_index"],
        "mode": row["mode"], "pair_candidates": row["pair_candidates"],
        "midpoint_cardinalities": distinct,
        "pair_root_values": root_values,
    }


def make_verification() -> dict:
    protocol = json.loads(screen.PROTOCOL.read_text())
    screen.check_protocol(protocol)
    result = json.loads(screen.OUTPUT.read_text())
    assert result["proposal_id"] == "Q1460"
    assert result["protocol_sha256"] == sha(screen.PROTOCOL)
    assert result["binary_sha256"] == sha(screen.BINARY)
    assert result["complete_n131_log2_work"] is None
    assert result["challenge_run_admitted"] is False
    all_jobs = screen.jobs(json.loads((screen.Q1459 / "result.json").read_text()),
                           protocol)
    assert len(all_jobs) == len(result["rows"])
    for expected, row in zip(all_jobs, result["rows"]):
        assert row["cell"] == expected["cell"]
        assert row["state_index"] == expected["state_index"]
        assert row["mode"] == expected["mode"]
        assert row["raw_leaf_counts"] == expected["expected_raw_leaf_counts"]
        assert row["leaf_counts"] == expected["expected_leaf_counts"]
        assert row["pair_candidates"] == expected["expected_pair_candidates"]
        assert row["target_x_support_upper_bound"] == (
            2 * row["midpoint_cardinalities"][0] *
            row["midpoint_cardinalities"][1])
        assert row["target_x_support_upper_bound"] <= 2 ** 27
        assert row["raw_field_x_count"] == 2 ** row["degree_n"]
    controls = []
    for case, mode in (("n53_ordinary", "raw"),
                       ("n83_ordinary", "lift")):
        choices = [row for row in result["rows"]
                   if row["cell"] == case and row["mode"] == mode]
        assert choices
        selected = min(choices, key=lambda row: (
            sum(row["pair_candidates"]), row["state_index"]))
        controls.append(sage_replay(selected))
    return {
        "proposal_id": "Q1460", "status": "pass",
        "protocol_sha256": sha(screen.PROTOCOL),
        "result_sha256": sha(screen.OUTPUT),
        "checked_rows": len(result["rows"]),
        "independent_sage_replays": controls,
        "claim_scope": "fixed-state upper bound; no adaptive-search or successful-solve claim",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    verification = make_verification()
    if args.check:
        assert verification == json.loads(OUTPUT.read_text())
        print("Q1460 independent midpoint audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(verification, sort_keys=True,
                                     indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1460",
                          "independent_sage_replays": verification[
                              "independent_sage_replays"]}))


if __name__ == "__main__":
    main()
