#!/usr/bin/env python3
"""Bind frozen sources, two producer failures, run results, and Sage replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_hash(expected, path):
    if expected != sha(path):
        raise AssertionError("digest mismatch: " + str(path))


def main():
    p = json.loads((HERE / "protocol.json").read_text())
    r = json.loads((HERE / "result.json").read_text())
    inputs = {"run": HERE / "run.py",
              "geometry": BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json",
              "w14_inputs": BASE / "n131_w14_polynomial_pair_inverse_20261010/inputs.json",
              "public_protocol": BASE / "n131_w14_samepair_target_gate_20261010/query_protocol.json"}
    for key, path in inputs.items():
        require_hash(p["sha256"][key], path)
    require_hash(p["failure_v1_sha256"], HERE / "failure_v1.json")
    old = json.loads((HERE / "protocol_v1.json").read_text())
    require_hash(old["sha256"]["run"], HERE / "run_v1.py")
    assert r["status"] == "COMPLETE_DIAGNOSTIC" and r["candidate_id"] is None
    require_hash(r["protocol_sha256"], HERE / "protocol.json")
    require_hash(r["source_sha256"], HERE / "run.py")
    assert r["n41"]["pair_output_x_counts"] == [978, 978]
    assert r["n41"]["cases"][0]["s3_value"] == 0
    assert all(x["s3_value"] != 0 for x in r["n41"]["cases"][1:])
    assert all(x["s3_value"] != 0 for x in r["n131"]["cases"])
    assert all(x["ranks"]["12"] == 41 for x in r["n41"]["cases"])
    assert all(x["ranks"]["34"] == 131 for x in r["n131"]["cases"])

    ap = json.loads((HERE / "audit_protocol_v2.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    audit_paths = {"auditor": HERE / "sage_audit_v2.py", "result": HERE / "result.json",
                   "geometry": inputs["geometry"], "w14_inputs": inputs["w14_inputs"],
                   "runtime": HERE / "sage_runtime_info.json"}
    for key, path in audit_paths.items():
        require_hash(ap["sha256"][key], path)
    require_hash(ap["prior_audit_failure_sha256"], HERE / "audit_failure_v1.json")
    assert audit["status"] == "PASS"
    assert audit["result_sha256"] == sha(HERE / "result.json")
    assert audit["source_sha256"] == sha(HERE / "sage_audit_v2.py")
    assert audit["checks"]["n41_group_witness"]
    assert audit["checks"]["n131_pair_controls"] == 2
    assert audit["checks"]["n41_independent_ranks"] == 12
    assert audit["checks"]["n131_independent_ranks"] == 12

    fp = json.loads((HERE / "followup_protocol.json").read_text())
    fr = json.loads((HERE / "followup_result.json").read_text())
    follow_paths = {"source": HERE / "followup.py", "run": HERE / "run.py",
                    "result": HERE / "result.json", "geometry": inputs["geometry"]}
    for key, path in follow_paths.items():
        require_hash(fp["sha256"][key], path)
    require_hash(fr["protocol_sha256"], HERE / "followup_protocol.json")
    require_hash(fr["source_sha256"], HERE / "followup.py")
    assert fr["base_result_sha256"] == sha(HERE / "result.json")
    assert [x["first_nonsingleton_low_bits"] for x in fr["n41_collision_census"]] == [22, 22]
    assert all(fr["prefix_screens"]["n41"][str(k)]["positive_control_pass"]
               for k in fp["n41_low_bits"])
    assert fr["prefix_screens"]["n41"]["12"]["nonpositive_cases_rejected"] == 0
    assert fr["prefix_screens"]["n131"]["34"]["nonpositive_cases_rejected"] == 0

    cp = json.loads((HERE / "collision_rank_protocol.json").read_text())
    cr = json.loads((HERE / "collision_rank_result.json").read_text())
    collision_paths = {"source": HERE / "collision_rank.py", "run": HERE / "run.py",
                       "geometry": inputs["geometry"], "base_result": HERE / "result.json",
                       "followup_result": HERE / "followup_result.json"}
    for key, path in collision_paths.items():
        require_hash(cp["sha256"][key], path)
    require_hash(cr["protocol_sha256"], HERE / "collision_rank_protocol.json")
    require_hash(cr["source_sha256"], HERE / "collision_rank.py")
    assert cr["status"] == "COMPLETE_EXHAUSTIVE_PREFIX_SCAN"
    assert cr["free_low_bits"] == 22 and cr["cross_term_rank"] == 40
    assert cr["both_domain_prefix_rectangles"] == 977 * 977
    assert all(x["one_side_plus_cross_rank_counts"] == {"41": 977} and
               not x["prefixes_below_full_rank"] for x in cr["domains"])

    sp = json.loads((HERE / "sage_collision_protocol.json").read_text())
    sa = json.loads((HERE / "sage_collision_audit.json").read_text())
    sage_collision_paths = {"source": HERE / "sage_collision_audit.py",
                            "collision_result": HERE / "collision_rank_result.json",
                            "geometry": inputs["geometry"],
                            "runtime": HERE / "sage_runtime_info.json"}
    for key, path in sage_collision_paths.items():
        require_hash(sp["sha256"][key], path)
    require_hash(sa["protocol_sha256"], HERE / "sage_collision_protocol.json")
    require_hash(sa["source_sha256"], HERE / "sage_collision_audit.py")
    assert sa["status"] == "PASS" and sa["cross_term_rank"] == 40
    assert [x["prefix_count"] for x in sa["domains"]] == [977, 977]
    assert [x["collision_prefix"] for x in sa["domains"]] == [
        x["first_collision_prefix"] for x in cr["domains"]]
    print("PASS_S3_PREFIX_RANK_BOUNDARY")


if __name__ == "__main__":
    main()
