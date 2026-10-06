#!/usr/bin/env python3
"""Freeze a post-result audit of the Q1459 new N83 admission."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "overlap_protocol.json"
SELECTED = ((20, "lift"), (22, "raw"), (22, "lift"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol() -> dict:
    result = json.loads((HERE / "result.json").read_text())
    assert result["proposal_id"] == "Q1460"
    assert result["cases"]["n83_ordinary"]["raw_states"] == 1
    assert result["cases"]["n83_ordinary"]["lift_states"] == 2
    for state, mode in SELECTED:
        assert any(row["cell"] == "n83_ordinary" and
                   row["state_index"] == state and row["mode"] == mode
                   for row in result["rows"])
    sources = [HERE / "audit_overlap.py", HERE / "freeze_overlap_protocol.py",
               PARENT / "q1455_joint_tail/joint_tail.py",
               PARENT / "s3_root_oracle.py", PARENT / "chain_s3.py"]
    inputs = [HERE / "protocol.json", HERE / "result.json",
              HERE / "verification.json", HERE / "sage_runtime_info.json",
              PARENT / "q1459_leaf_lift_screen/result.json",
              PARENT / "q1420_root_theory/n83_field.txt"]
    return {
        "kind": "q1460_post_result_n83_midpoint_overlap_protocol",
        "proposal_id": "Q1460", "candidate_id": None,
        "isogeny": "none", "post_result_follow_up": True,
        "selection_reason": (
            "the Q1460 result shows equal midpoint cardinalities for "
            "the newly admitted N83 lift state and the previously "
            "admitted N83 raw state; compare exact sets, not counts"),
        "case": "n83_ordinary",
        "selected_state_modes": [list(pair) for pair in SELECTED],
        "midpoint_digest_encoding": (
            "sorted unique ONB coordinate integers, each encoded as "
            "11-byte big-endian unsigned binary, then SHA-256"),
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = make_protocol()
    if args.check:
        assert protocol == json.loads(OUTPUT.read_text())
        print("Q1460 post-result overlap protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
        print("Q1460 post-result overlap protocol frozen")


if __name__ == "__main__":
    main()
