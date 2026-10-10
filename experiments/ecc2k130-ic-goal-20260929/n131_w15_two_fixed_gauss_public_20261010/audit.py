#!/usr/bin/env python3
"""Audit the frozen public-query record and exact XCNF bytes."""

import gzip
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "n131_w15_two_fixed_seeds_public_20261010"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def formula(path, expected, appended):
    digest = hashlib.sha256()
    size = clauses = xors = 0
    tail = []
    with gzip.open(path, "rb") as stream:
        header = stream.readline()
        assert header == f"p cnf {expected['variables']} {expected['clauses']+expected['xor_rows']}\n".encode()
        digest.update(header)
        size += len(header)
        for line in stream:
            digest.update(line)
            size += len(line)
            if line.startswith(b"x"):
                xors += 1
            else:
                clauses += 1
                tail.append(line.decode().strip())
                if len(tail) > len(appended):
                    tail.pop(0)
    assert digest.hexdigest() == expected["sha256"]
    assert size == expected["bytes"]
    assert clauses == expected["clauses"] and xors == expected["xor_rows"]
    assert tail == appended
    return {"sha256": digest.hexdigest(), "bytes": size,
            "variables": expected["variables"], "cnf_clauses": clauses,
            "native_xor_rows": xors,
            "verified_appended_trace_clauses": len(appended)}


def main():
    protocol = load(HERE / "protocol.json")
    work = Path(protocol["work_directory"])
    control = load(work / "control.json")
    result = load(work / "result.json")
    count = load(HERE / "support_count.json")
    count_audit = load(HERE / "support_audit.json")
    assert protocol["status"] == "FROZEN_TWO_FIXED_SEEDS_GAUSS_W15_PUBLIC_GATE"
    assert control["status"] == "PASS_TWO_FIXED_SEEDS_GAUSS_CONSTRUCTED_CONTROL"
    assert protocol["target_count"] == result["target_count"] == 1
    assert protocol["target_q"] == result["target_q"]
    assert protocol["source_count"] == count["distinct_column_signed_sixpair_tuples"]
    assert count_audit["distinct_column_signed_sixpair_tuples"] == protocol["source_count"]
    identity = load(HERE / "identity.json")
    assert identity["status"] == "PASS_EXHAUSTIVE_TWO_FIXED_SEED_LINEAR_PRODUCTS"
    assert identity["ordered_usable_mask_pairs_checked"] == [8176, 8340]
    assert protocol["source_sha256"]["identity"] == sha(HERE / "identity.json")
    assert protocol["source_sha256"]["support_audit"] == sha(HERE / "support_audit.json")
    assert protocol["source_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["source_sha256"]["circuit"] == sha(HERE / "circuit.py")
    assert protocol["source_sha256"]["lift"] == sha(HERE / "lift.py")
    assert protocol["source_sha256"]["support_count"] == sha(HERE / "support_count.json")
    assert control["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(work / "control.json")
    assert control["xcnf_check"] == {"cnf_clauses": control["formula"]["clauses"],
                                    "xor_rows": control["formula"]["xor_rows"]}
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["sha256"]["group_lift"] == sha(work / "control_group_lift.json")
    assert control["formula_gzip_sha256"] == sha(work / "control.xcnf.gz")
    assert result["formula_gzip_sha256"] == sha(work / "system.xcnf.gz")
    assert result["sha256"]["formula_gzip"] == sha(work / "system.xcnf.gz")
    for key, name in (("stdout", "solver.stdout.txt"),
                      ("stderr", "solver.stderr.txt")):
        assert result["sha256"][key] == sha(work / name)
    assert result["phase_seconds"]["construction_plus_search"] <= \
        protocol["construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"] or \
        result["status"] == "OOM"
    checked_control = formula(work / "control.xcnf.gz", control["formula"],
                              control["added_trace_clauses"])
    checked_public = formula(work / "system.xcnf.gz", result["formula"],
                             result["added_trace_clauses"])
    assert len(result["added_trace_clauses"]) == len(control["added_trace_clauses"]) == 22
    stdout = (work / "solver.stdout.txt").read_text(errors="replace")
    baseline_stdout = (BASELINE / "solver.stdout.txt").read_text(errors="replace")
    matrix_pattern = re.compile(r"Using (\d+) matrices recovered from")
    baseline_matrices = [int(n) for n in matrix_pattern.findall(baseline_stdout)]
    tuned_matrices = [int(n) for n in matrix_pattern.findall(stdout)]
    assert baseline_matrices
    assert "--maxmatrixcols=4096" in result["solver_command"]
    assert "--maxnummatrices=8" in result["solver_command"]
    statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
    models = sum(line.startswith("v ") for line in stdout.splitlines())
    assert statuses == result["solver_status_lines"] and models == result["model_lines"]
    if result["status"] == "CENSORED_TIME":
        assert statuses in ([], ["s INDETERMINATE"])
        assert models == 0
        assert any(line.startswith("c rst ") for line in stdout.splitlines())
    elif result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE":
        assert statuses == ["s SATISFIABLE"] and models > 0
        assert result["producer_xcnf_check"] == {
            "cnf_clauses": checked_public["cnf_clauses"],
            "xor_rows": checked_public["native_xor_rows"]}
        assert load(work / "group_lift.json")["status"] == "GROUP_LIFT_FOUND"
    elif result["status"] == "UNSAT_FORMULA":
        assert statuses == ["s UNSATISFIABLE"]
    elif result["status"] == "OOM":
        assert result["stop_reason"] == "RSS_CAP"
    else:
        raise AssertionError("uncertified terminal status")
    receipt = {"status": "PASS_TWO_FIXED_SEEDS_GAUSS_TERMINAL_AUDIT",
               "query_status": result["status"],
               "curve_id": protocol["curve_id"], "target_q": result["target_q"],
               "control_formula": checked_control,
               "public_formula": checked_public,
               "construction_plus_search_seconds": result["phase_seconds"]["construction_plus_search"],
               "sampled_peak_combined_rss_bytes": result["sampled_peak_combined_rss_bytes"],
               "initial_gauss_matrices": {"baseline": baseline_matrices[0],
                                          "expanded_policy": tuned_matrices[0]
                                          if tuned_matrices else None},
               "too_many_columns_log_lines": {
                   "baseline": baseline_stdout.count("Too many columns in matrix"),
                   "expanded_policy": stdout.count("Too many columns in matrix")},
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "control": sha(work / "control.json"),
                          "result": sha(work / "result.json"),
                          "control_formula": sha(work / "control.xcnf.gz"),
                          "public_formula": sha(work / "system.xcnf.gz"),
                          "stdout": sha(work / "solver.stdout.txt"),
                          "stderr": sha(work / "solver.stderr.txt")}}
    with (work / "terminal_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "query_status": receipt["query_status"],
                      "public_formula": checked_public}))


if __name__ == "__main__":
    main()
