#!/usr/bin/env python3
"""Audit the frozen W15 support, constructed control, and public query."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("/private/tmp/n131_w15_coupled_sixpair_public_20261010")
BASELINE = HERE.parent / "n131_w14_compact_columns_20261010/public_query/result.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def formula(path, result):
    digest = hashlib.sha256()
    size = cnf = xor = 0
    with gzip.open(path, "rb") as stream:
        header = next(stream)
        digest.update(header)
        size += len(header)
        assert header == (f"p cnf {result['variables']} "
                          f"{result['clauses'] + result['xor_rows']}\n").encode()
        for line in stream:
            digest.update(line)
            size += len(line)
            if line.startswith(b"x"):
                xor += 1
            else:
                cnf += 1
    assert digest.hexdigest() == result["sha256"]
    assert size == result["bytes"]
    assert cnf == result["clauses"] and xor == result["xor_rows"]
    return {"sha256": digest.hexdigest(), "bytes": size,
            "cnf_clauses": cnf, "xor_rows": xor}


def main():
    support_protocol = load(HERE / "support_protocol.json")
    support = load(HERE / "parent_receipt.json")
    source_audit = load(HERE / "sage_support_audit.json")
    group_audit = load(HERE / "sage_group_audit.json")
    protocol = load(HERE / "protocol.json")
    control = load(HERE / "control_result.json")
    control_group = load(HERE / "control_group_lift.json")
    count = load(HERE / "seed_sum_count.json")
    query_protocol = load(HERE / "query_protocol.json")
    result = load(OUTPUT / "result.json")
    baseline = load(BASELINE)
    assert support_protocol["status"] == "FROZEN_BEFORE_W15_SIX_PAIR_SUPPORT_ENUMERATION"
    assert support["status"] == "COMPLETE"
    assert source_audit["status"] == "PASS_FULL_MASKS_ORBITS_AND_SIX_WINDOW_BASE"
    assert group_audit["status"] == "PASS_EXACT_PROJECTED_GROUP_BASE"
    assert protocol["status"] == "FROZEN_BEFORE_W15_N131_CONTROL_AND_PUBLIC_QUERY"
    assert control["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert control_group["status"] == "PASS_W15_CONSTRUCTED_GROUP_LIFT"
    assert count["status"] == "PASS_EXACT_W15_SIX_PAIR_TUPLE_COUNT"
    assert query_protocol["status"] == "FROZEN_BEFORE_W15_N131_UNPINNED_PUBLIC_QUERY_ON_TEMP_VOLUME"
    assert query_protocol["source_sha256"]["runner"] == sha(HERE / "query_temp.py")
    assert query_protocol["source_sha256"]["experiment"] == sha(HERE / "experiment.py")
    assert query_protocol["source_sha256"]["circuit"] == sha(HERE / "w15_circuit.py")
    assert query_protocol["source_sha256"]["group_lift"] == sha(HERE / "w15_lift.py")
    assert query_protocol["source_sha256"]["support"] == sha(HERE / "support_w15.tsv")
    assert result["sha256"]["query_protocol"] == sha(HERE / "query_protocol.json")
    assert result["sha256"]["w15_protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(HERE / "control_result.json")
    assert result["sha256"]["control_group_lift"] == sha(HERE / "control_group_lift.json")
    assert result["target_q"] == query_protocol["target_q"] == baseline["target_q"]
    assert result["curve_id"] == protocol["curve_id"] == baseline["curve_id"]
    assert protocol["actual_projected_factor_base_B"] == group_audit[
        "actual_subgroup_factor_base_points_B"] == 197292
    assert protocol["folded_columns_K"] == source_audit["folded_columns_K"] == 16381
    assert result["phase_seconds"]["construction_plus_search"] < query_protocol[
        "construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < query_protocol["rss_cap_bytes"]
    assert result["formula"]["column_clauses"] == protocol["expected_compact_column_clauses"]
    assert result["sha256"]["formula_gzip"] == sha(OUTPUT / "system.xcnf.gz")
    assert result["sha256"]["stdout"] == sha(OUTPUT / "solver.stdout.txt")
    assert result["sha256"]["stderr"] == sha(OUTPUT / "solver.stderr.txt")
    profile = formula(OUTPUT / "system.xcnf.gz", result["formula"])
    lines = (OUTPUT / "solver.stdout.txt").read_text(errors="replace").splitlines()
    restarts = [line for line in lines if line.startswith("c rst ")]
    assert restarts
    assert result["status"] in ("CENSORED_TIME", "GROUP_RELATION_PENDING_INDEPENDENT_SAGE",
                                "SAT_NO_GROUP_LIFT", "UNSAT_FORMULA", "OOM")
    if result["status"] == "CENSORED_TIME":
        assert result["solver_status_lines"] in ([], ["s INDETERMINATE"])
        assert result["model_lines"] == 0
        assert result["verified_relations"] == result["useful_rank"] == 0
    if result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE":
        assert result["solver_status_lines"] == ["s SATISFIABLE"]
        assert result["producer_xcnf_check"] is not None
        assert load(OUTPUT / "group_lift.json")["status"] == "GROUP_LIFT_FOUND"
    receipt = {
        "status": "PASS_W15_N131_TERMINAL_AUDIT",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_q": result["target_q"],
        "public_status": result["status"],
        "formula": profile,
        "actual_factor_base_B": protocol["actual_projected_factor_base_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "group_wide_tuple_mean_before_cross_pair_column_filter": count[
            "group_wide_mean_before_cross_pair_column_filter"],
        "last_logged_conflicts": restarts[-1].split()[6],
        "construction_plus_search_seconds": result["phase_seconds"]["construction_plus_search"],
        "sampled_peak_rss_bytes": result["sampled_peak_combined_rss_bytes"],
        "raw_artifact_dir": str(OUTPUT),
        "source_sha256": {name: sha(path) for name, path in {
            "script": Path(__file__),
            "support_protocol": HERE / "support_protocol.json",
            "support_parent": HERE / "parent_receipt.json",
            "source_audit": HERE / "sage_support_audit.json",
            "group_audit": HERE / "sage_group_audit.json",
            "protocol": HERE / "protocol.json",
            "control": HERE / "control_result.json",
            "control_group_lift": HERE / "control_group_lift.json",
            "seed_sum_count": HERE / "seed_sum_count.json",
            "query_protocol": HERE / "query_protocol.json",
            "public_result": OUTPUT / "result.json",
            "public_formula_gzip": OUTPUT / "system.xcnf.gz",
            "solver_stdout": OUTPUT / "solver.stdout.txt",
            "solver_stderr": OUTPUT / "solver.stderr.txt",
        }.items()},
    }
    with (HERE / "terminal_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "public_status": receipt["public_status"],
                      "construction_plus_search_seconds": receipt[
                          "construction_plus_search_seconds"]}))


if __name__ == "__main__":
    main()
