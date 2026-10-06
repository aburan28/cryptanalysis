#!/usr/bin/env python3
"""Freeze a disjoint ARM M32/R30 holdout run with a canonical IC1 identity."""

import hashlib
import json
import math
from pathlib import Path

from freeze_n83_holdout_wave import freeze as q1090_freeze

HERE = Path(__file__).resolve().parent
PRIOR = HERE / "candidates" / (
    "IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h49b47d79e9e3.json")
TARGET = HERE / "n83_holdout_target_20261001.json"
WRAPPER = HERE / "run_n83_holdout_arm_q1093.py"
VERIFIER = HERE / "verify_n83_holdout_q1093_receipt_sage.py"
PLAN = HERE / "n83_q1093_local_arm_m32_r30_plan.json"
RESERVE = HERE / "n83_holdout_revised_30day_resource_ceiling.json"
Q1092 = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
M = 1 << 32
R = 1 << 30
QUERY_START = 208 * (1 << 29)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def freeze():
    prior = json.loads(PRIOR.read_text())
    assert prior["candidate_record_sha256"] == hashlib.sha256(canonical(
        {k: v for k, v in prior.items() if k not in
         ("candidate_id", "candidate_record_sha256")})).hexdigest()
    assert prior["isogeny"] == "none"
    assert prior["factor_base"]["actual_usable_points_B_before_folding"] == 8000204
    assert prior["factor_base"]["signed_frobenius_columns"] == 48194
    assert QUERY_START == 208 * (1 << 29)
    prior_coverage = json.loads(Q1092.read_text())
    assert prior_coverage["query_end_exclusive"] == QUERY_START
    assert QUERY_START + R <= math.comb(48194, 2) * 166
    target = json.loads(TARGET.read_text())
    assert target["fixture_scalar_retained"] is False
    assert target["workload"]["target_count"] == 1
    assert target["curve_id"] == prior["curve"]["curve_id"]
    assert target["factor_base_enumerated_set_sha256"] == prior[
        "factor_base"]["enumerated_set_sha256"]
    reserve = json.loads(RESERVE.read_text())
    assert reserve["local_reserve_seconds"] == 30 * 86400
    assert reserve["q1090_q1091_q1092_plus_local_cycle_capacity_log2"] < 61

    candidate = {k: v for k, v in prior.items() if k not in
                 ("candidate_id", "candidate_record_sha256")}
    candidate["point_decomposition"]["query_representatives_per_job"] = R
    candidate["implementation"]["cpu_backend"] = "arm_pmull"
    candidate["implementation"]["wrapper_source_sha256"] = sha(WRAPPER)
    candidate["implementation"]["independent_verifier_source_sha256"] = sha(
        VERIFIER)
    candidate["relation_collection"]["implementation_sha256"] = sha(WRAPPER)
    candidate["target_descent"]["implementation_sha256"] = sha(WRAPPER)
    digest = hashlib.sha256(canonical(candidate)).hexdigest()
    cid = f"IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h{digest[:12]}"
    candidate["candidate_id"] = cid
    candidate["candidate_record_sha256"] = digest
    candidate_path = HERE / "candidates" / (cid + ".json")

    plan = q1090_freeze()
    assert plan["curve_id"] == target["curve_id"]
    assert plan["factor_base_enumerated_set_sha256"] == candidate[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["query_end_exclusive"] == 16 * (1 << 29)
    field_calls = 26 * M + 13 * R + 13 * R * 83 + 90 * (
        2 * math.ceil(M / 1024) + 2 * math.ceil(R / 8))
    plan.update({
        "kind": "n83_q1093_fresh_holdout_source_bound_local_arm_m32_r30",
        "proposal_id": "Q1093",
        "candidate_id": cid,
        "candidate_manifest": str(candidate_path.relative_to(HERE)),
        "candidate_manifest_sha256": hashlib.sha256(
            (json.dumps(candidate, indent=2) + "\n").encode()).hexdigest(),
        "run_id": cid + "W" + target["workload_id"] + "R1",
        "query_starts": [QUERY_START],
        "query_representatives": R,
        "query_end_exclusive": QUERY_START + R,
        "cpu_backend": "arm_pmull",
        "workers": 4,
        "minimum_mem_available_bytes": 16 * (1 << 30),
        "minimum_spill_free_bytes": 16 * (1 << 30),
        "minimum_root_free_bytes": 128 * (1 << 20),
        "timeout_seconds_per_job": 12 * 3600,
        "modeled_native_field_calls_per_job": str(field_calls),
        "modeled_native_field_calls_log2": math.log2(field_calls),
        "runner_source_sha256": sha(WRAPPER),
        "source_sha256": sha(Path(__file__)),
        "revised_30day_resource_ceiling_sha256": sha(RESERVE),
        "local_reserve_end_utc": reserve["local_reserve_end_utc"],
        "q1090_q1091_q1092_query_end_exclusive": QUERY_START,
        "q1092_coverage_design_sha256": sha(Q1092),
        "preferred_spill_root": "/private/tmp",
        "limits": [
            "This is one additional candidate on the same frozen previously unseen target; it does not reuse Q1090-Q1092 query representatives.",
            "The local M32/R30 run is gated by free memory, spill space, source hashes, and the 30-day resource interval.",
            "The regular-path field-call model excludes Bloom, keying, memory, disk, failed work, and replay.",
            "No relation yield or complete discrete logarithm is claimed by this plan.",
        ],
    })
    plan.pop("modeled_native_field_calls_sixteen_jobs_log2")
    return candidate_path, candidate, plan


def main():
    candidate_path, candidate, plan = freeze()
    content = json.dumps(candidate, indent=2) + "\n"
    if candidate_path.exists():
        assert candidate_path.read_text() == content
    else:
        candidate_path.write_text(content)
    plan_content = json.dumps(plan, indent=2) + "\n"
    if PLAN.exists():
        assert PLAN.read_text() == plan_content
    else:
        PLAN.write_text(plan_content)
    print(json.dumps({"candidate_id": candidate["candidate_id"],
                      "run_id": plan["run_id"], "plan": str(PLAN),
                      "field_calls_log2": plan["modeled_native_field_calls_log2"]}))


if __name__ == "__main__":
    main()
