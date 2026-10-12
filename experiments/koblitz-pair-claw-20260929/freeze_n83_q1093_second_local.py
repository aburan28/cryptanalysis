#!/usr/bin/env python3
"""Freeze a second disjoint local rectangle of the exact Q1093 candidate."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIRST = HERE / "n83_q1093_local_arm_m32_r30_plan.json"
SECOND = HERE / "n83_q1093_second_local_arm_m32_r30_plan.json"
Q1092 = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
FIRST_STARTED = HERE / "runs/n83_q1093_local_arm_m32_r30.started.json"
LAUNCHER = HERE / "launch_n83_q1093_second_local_arm.py"
R = 1 << 30


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    first = json.loads(FIRST.read_text())
    prior = json.loads(Q1092.read_text())
    started = json.loads(FIRST_STARTED.read_text())
    assert first["proposal_id"] == "Q1093"
    assert first["status"] == "ready_for_dispatch"
    assert first["isogeny"] == "none"
    assert first["query_starts"] == [prior["query_end_exclusive"]]
    assert first["query_representatives"] == R
    assert first["query_end_exclusive"] == first["query_starts"][0] + R
    assert first["table_descriptors"] == 1 << 32
    assert first["cpu_backend"] == "arm_pmull"
    assert first["bits_per_key"] == 20 and first["hashes"] == 10
    assert started["proposal_id"] == "Q1093"
    assert started["candidate_id"] == first["candidate_id"]
    assert started["run_id"] == first["run_id"]
    assert started["query_start"] == first["query_starts"][0]
    assert started["query_representatives"] == R
    assert started["factor_base_enumerated_set_sha256"] == first[
        "factor_base_enumerated_set_sha256"]
    assert sha(HERE / first["candidate_manifest"]) == first[
        "candidate_manifest_sha256"]
    start = first["query_end_exclusive"]
    assert start + R <= math.comb(48194, 2) * 166
    second = dict(first)
    second.update({
        "kind": "n83_q1093_second_disjoint_local_arm_m32_r30",
        "query_starts": [start],
        "query_end_exclusive": start + R,
        "prior_Q1093_local_plan_sha256": sha(FIRST),
        "prior_Q1093_started_receipt_sha256": sha(FIRST_STARTED),
        "launcher_source_sha256": sha(LAUNCHER),
        "source_sha256": sha(Path(__file__)),
        "minimum_mem_available_bytes": 24 * (1 << 30),
        "minimum_spill_free_bytes": 16 * (1 << 30),
        "limits": [
            "The first Q1093 rectangle is source-bound and already running; this second rectangle follows it without overlap.",
            "This is the same exact curve, factor base, candidate, target, workload, and run ID, with a distinct query interval and receipt.",
            "Concurrent launch requires at least 24 GiB currently free memory and 16 GiB spill-volume free space; failure leaves a separate terminal record.",
            "The revised 30-day local reserve charges all 14 physical cores continuously, including both local rectangles.",
            "No natural yield, scalar, or complete-solve work is claimed by this plan.",
        ],
    })
    return second


def main():
    plan = freeze()
    content = json.dumps(plan, indent=2) + "\n"
    if SECOND.exists():
        assert SECOND.read_text() == content
    else:
        SECOND.write_text(content)
    print(json.dumps({"candidate_id": plan["candidate_id"],
                      "run_id": plan["run_id"],
                      "query_start": plan["query_starts"][0],
                      "query_end_exclusive": plan["query_end_exclusive"],
                      "plan": str(SECOND)}))


if __name__ == "__main__":
    main()
