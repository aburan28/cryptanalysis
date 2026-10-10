#!/usr/bin/env python3
"""Audit the W16 byte-compatible prefix cache and charged formula phases."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w16_fivepair_sat_gate_20261010"
WIDTH = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    cache = json.loads((HERE / "cache_result.json").read_text())
    result = json.loads((HERE / "compare_result.json").read_text())
    original = json.loads((OLD / "fivepair_control_result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_BYTE_IDENTICAL_W16_PREFIX_CACHE"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in {
        "runner": HERE / "run.py", "core": HERE / "core.py",
        "original_runner": OLD / "fivepair_run.py",
        "original_method": OLD / "fivepair_circuit.py",
        "original_control": OLD / "fivepair_control_result.json",
        "original_input": OLD / "fivepair_input.json",
        "width_support": WIDTH / "support_w16.tsv",
        "width_audit": WIDTH / "audit_result.json",
        "runtime": HERE / "sage_runtime_info.json"}.items()}
    assert cache["status"] == "PASS_W16_EXACT_SOURCE_PREFIX_CACHE"
    assert cache["source_sha256"] == protocol["source_sha256"]
    assert cache["protocol_sha256"] == sha(HERE / "protocol.json")
    assert cache["source_prefix_sha256"] == sha(HERE / "source_prefix.pickle.gz")
    assert cache["source_prefix_bytes"] == (HERE / "source_prefix.pickle.gz").stat().st_size
    assert cache["variables"] == 164
    assert cache["cnf_clauses"] == 327407
    assert cache["native_xor_rows"] == 0
    assert cache["build_and_archive_ns"] <= protocol["source_precompute_cap_seconds"]*10**9
    assert cache["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
    assert result["status"] == "PASS_BYTE_IDENTICAL_W16_FORMULA_FROM_PREFIX_CACHE"
    assert result["source_sha256"] == {
        "protocol": sha(HERE / "protocol.json"),
        "cache_result": sha(HERE / "cache_result.json"),
        "original_control": sha(OLD / "fivepair_control_result.json")}
    assert original["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    digest = hashlib.sha256()
    with gzip.open(OLD / "fivepair_control.xcnf.gz", "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    assert result["formula"] == {key: original["formula"][key] for key in result["formula"]}
    assert result["formula"]["sha256"] == digest.hexdigest()
    phases = result["phase_ns"]
    phase_sum = sum(phases[name] for name in
        ("target_preimages", "target_suffix", "formula_write", "formula_hash_check"))
    overhead = phases["target_formula_total"] - phase_sum
    assert 0 <= overhead < 1_000_000
    assert phases["target_formula_total"] <= protocol["target_formula_cap_seconds"]*10**9
    assert result["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
    assert result["target_q"] == protocol["target_q"]
    assert result["fixed_first_pair_columns"] == protocol["fixed_first_pair_columns"]
    audit = {"status": "PASS_N131_W16_BYTE_IDENTICAL_PREFIX_CACHE_AUDIT",
             "candidate_id": None,
             "formula_sha256": digest.hexdigest(),
             "target_formula_ns": phases["target_formula_total"],
             "unclassified_overhead_ns": overhead,
             "source_prefix_clauses": cache["cnf_clauses"],
             "source_sha256": {name: sha(path) for name, path in {
                 "audit": HERE / "verify.py", "protocol": HERE / "protocol.json",
                 "cache_result": HERE / "cache_result.json",
                 "compare_result": HERE / "compare_result.json",
                 "original_control": OLD / "fivepair_control_result.json"}.items()}}
    (HERE / "audit.json").write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": audit["status"],
                      "target_formula_ns": phases["target_formula_total"]}))


if __name__ == "__main__":
    main()
