#!/usr/bin/env python3
"""Bind the frozen bit-field and Sage S3 join records to their exact inputs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    protocol = load(HERE / "protocol.json")
    result = load(HERE / "result.json")
    sage_audit = load(HERE / "sage_audit.json")
    sage_protocol = load(HERE / "sage_query_protocol.json")
    sage_result = load(HERE / "sage_query_result.json")
    public = load(BASE / "result.json")
    control = load(CONTROL)
    roots = load(BASE / "pair_roots.json")
    assert protocol["status"] == "FROZEN_W15_FIXEDSEED_S3_JOIN"
    assert sage_protocol["status"] == "FROZEN_W15_S3_SAGE_QUERY"
    assert result["status"] == sage_result["status"] == "COMPLETE"
    assert sage_audit["status"] == "PASS_INDEPENDENT_SAGE_W15_S3_JOIN_AUDIT"
    assert roots["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS"
    assert protocol["curve_id"] == result["curve_id"] == sage_result["curve_id"] == roots["curve_id"]
    assert protocol["public_target_q"] == public["target_q"] == result["published_target_q"]
    assert protocol["source_sha256"] == {
        "producer": sha(HERE / "run.py"),
        "freezer": sha(HERE / "freeze.py"),
        "pair_roots": sha(BASE / "pair_roots.json"),
        "pair_root_audit": sha(BASE / "prefix_audit.json"),
        "bit_field": sha(BASE / "audit_prefix.py"),
        "constructed_input": sha(CONTROL),
        "published_input": sha(BASE / "result.json"),
        "checked_sage_runtime": sha(HERE / "sage_runtime_info.json")}
    assert sage_protocol["source_sha256"] == {
        "query": sha(HERE / "sage_query.py"),
        "freezer": sha(HERE / "freeze_sage_query.py"),
        "sage_kernel": sha(HERE / "sage_audit.py"),
        "source_protocol": sha(HERE / "protocol.json"),
        "source_result": sha(HERE / "result.json"),
        "independent_audit": sha(HERE / "sage_audit.json"),
        "pair_roots": sha(BASE / "pair_roots.json"),
        "sage_runtime": sha(HERE / "sage_runtime_info.json")}
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["source"] == sha(HERE / "run.py")
    assert sage_audit["sha256"]["producer_result"] == sha(HERE / "result.json")
    assert sage_audit["sha256"]["auditor"] == sha(HERE / "sage_audit.py")
    assert sage_result["sha256"]["protocol"] == sha(HERE / "sage_query_protocol.json")
    assert sage_result["sha256"]["query_source"] == sha(HERE / "sage_query.py")
    assert [len({v for row in block["pairs"] for v in row[2:]})
            for block in roots["pair_rows"]] == [8176, 8340]
    assert result["domain_sizes"] == sage_result["domain_sizes"] == [8176, 8340]
    assert len(result["cases"]) == len(sage_result["cases"]) == len(sage_audit["cases"]) == 3
    names = ["constructed_four_atom", "published_point_lift_0", "published_point_lift_2"]
    assert [row["name"] for row in result["cases"]] == names
    assert [row["name"] for row in sage_result["cases"]] == names
    assert [row["name"] for row in sage_audit["cases"]] == names
    assert result["cases"][0]["target_reciprocal"] == control["middle_reciprocals"][6]
    assert sage_audit["positive_group_replay"] == "PASS"
    from run import inverse, half_trace
    for index, (first, second, audit) in enumerate(zip(result["cases"],
                                                         sage_result["cases"],
                                                         sage_audit["cases"])):
        assert first["status"] == second["status"] == "COMPLETE"
        assert first["target_reciprocal"] == second["target_reciprocal"]
        assert first["right_outputs_visited"] == 8340
        assert second["left_outputs_checked"] == 8176
        assert first["quadratic_outputs"] == 8340
        assert first["linear_outputs"] == first["no_rational_roots"] == 0
        matches = {(row["left_output"], row["right_output"])
                   for row in first["algebraic_hits"]}
        assert matches == set(map(tuple, second["algebraic_hit_coordinate_pairs"]))
        assert len(matches) == audit["algebraic_hit_pairs"] == (1 if index == 0 else 0)
        if index:
            raw_index = 0 if index == 1 else 2
            q = inverse(public["raw_target_preimages"][raw_index][0])
            assert q == first["target_reciprocal"] and half_trace(q) is not None
        assert first["query_seconds"] <= protocol["per_query_cap_seconds"]
        assert second["query_ns"] <= sage_protocol["per_query_cap_seconds"]*10**9
    assert result["sampled_peak_process_rss_bytes"] < protocol["rss_cap_bytes"]
    assert sage_result["peak_process_rss_bytes"] < sage_protocol["rss_cap_bytes"]
    receipt = {"status": "PASS_W15_FIXEDSEED_S3_TERMINAL_AUDIT",
               "curve_id": protocol["curve_id"], "case_names": names,
               "domain_sizes": [8176, 8340],
               "coordinate_hits": [1, 0, 0],
               "positive_group_replay": "PASS",
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "bit_field_result": sha(HERE / "result.json"),
                          "sage_audit": sha(HERE / "sage_audit.json"),
                          "sage_query_protocol": sha(HERE / "sage_query_protocol.json"),
                          "sage_query_result": sha(HERE / "sage_query_result.json")}}
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "coordinate_hits": receipt["coordinate_hits"]}))


if __name__ == "__main__":
    main()
