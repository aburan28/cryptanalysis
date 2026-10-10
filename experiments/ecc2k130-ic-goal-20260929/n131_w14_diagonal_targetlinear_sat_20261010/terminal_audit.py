#!/usr/bin/env python3
"""Audit the target-linear formula and bounded published-point search."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

import importlib.util
spec = importlib.util.spec_from_file_location("n131_w14_targetlinear_query_audit", HERE / "query.py")
query = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query)
run = query.run


def decompressed_sha(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def main():
    construction_protocol = json.loads((HERE / "protocol.json").read_text())
    profile = json.loads((HERE / "profile.json").read_text())
    protocol = json.loads((HERE / "query_protocol.json").read_text())
    folder = HERE / "public_query"
    result = json.loads((folder / "result.json").read_text())
    assert construction_protocol["source_sha256"] == {
        name: run.sha(path) for name, path in run.sources().items()}
    assert protocol["source_sha256"] == {
        name: run.sha(path) for name, path in query.sources().items()}
    assert profile["status"] == "PASS_FULL_TARGETLINEAR_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    assert construction_protocol["pair_identity_checks"] == 32
    assert profile["full_xcnf_assignment_check"] == {
        "cnf_clauses": profile["formula"]["clauses"],
        "xor_rows": profile["formula"]["xor_rows"]}
    assert profile["formula"]["uncompressed_sha256"] == decompressed_sha(HERE / "constructed.xcnf.gz")
    assert result["formula"]["sha256"] == decompressed_sha(folder / "system.xcnf.gz")
    assert result["target_q"] == protocol["target_q"]
    assert result["sha256"]["protocol"] == run.sha(HERE / "query_protocol.json")
    assert result["status"] == "CENSORED_TIME" and result["model_lines"] == 0
    assert result["stop_reason"] == "SOLVER_WALL_CAP"
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    assert result["sha256"]["stdout"] == run.sha(stdout)
    assert result["sha256"]["stderr"] == run.sha(stderr)
    assert stderr.stat().st_size == 0
    log = stdout.read_text()
    assert "c rst " in log and "s SATISFIABLE" not in log and "s UNSATISFIABLE" not in log
    search_interval = (result["phase_seconds"]["target_formula"] +
                       result["phase_seconds"]["solver"])
    archival_overhang = result["phase_seconds"]["query_wall"]-search_interval
    assert 0 < search_interval < protocol["query_wall_cap_seconds"]
    assert archival_overhang > 0
    receipt = {"status": "PASS_FORMULAS_AND_SEARCH_CAP_WITH_ARCHIVE_OVERHANG",
               "candidate_id": None, "curve_id": protocol["curve_id"],
               "published_target_q": result["target_q"],
               "constructed_formula_sha256": profile["formula"]["uncompressed_sha256"],
               "published_formula_sha256": result["formula"]["sha256"],
               "solver_active_search": True,
               "published_query_status": result["status"],
               "target_formula_plus_solver_seconds": search_interval,
               "archival_and_receipt_overhang_seconds": archival_overhang,
               "recorded_total_process_wall_seconds": result["phase_seconds"]["query_wall"],
               "source_sha256": {"script":run.sha(__file__),
                                 "construction_protocol":run.sha(HERE / "protocol.json"),
                                 "query_protocol":run.sha(HERE / "query_protocol.json"),
                                 "query_result":run.sha(folder / "result.json")}}
    run.save(HERE / "terminal_audit.json", receipt)
    print(json.dumps({"status":receipt["status"],
                      "search_interval_seconds":search_interval,
                      "archival_overhang_seconds":archival_overhang}))


if __name__ == "__main__":
    main()
