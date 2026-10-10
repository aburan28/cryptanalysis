#!/usr/bin/env python3
"""Audit source-matched batch-inversion controls and N131 run receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def core(value):
    return {name: value[name] for name in
            ("status", "field_degree", "source_dimension", "seed_sum",
             "output_z", "total_product_states", "processed_product_states", "hits")}


def main():
    protocol = load(HERE / "protocol.json")
    result = load(HERE / "result.json")
    assert protocol["status"] == "FROZEN_BEFORE_MATCHED_N131_FOUR_ATOM_BATCH_INVERSION_PANEL"
    assert result["status"] == "PASS_MATCHED_N131_FOUR_ATOM_BATCH_INVERSION_PANEL"
    assert sha(HERE / "baseline.cpp") == sha(PRIOR / "native.cpp")
    assert sha(HERE / "resultant_terms.hpp") == sha(PRIOR / "resultant_terms.hpp")
    assert protocol["source_sha256"]["runner"] == sha(HERE / "bench.py")
    assert protocol["source_sha256"]["baseline_source"] == sha(HERE / "baseline.cpp")
    assert protocol["source_sha256"]["batch_source"] == sha(HERE / "batch.cpp")
    assert protocol["source_sha256"]["terms_header"] == sha(HERE / "resultant_terms.hpp")
    for name in ("baseline", "batch"):
        assert protocol["source_sha256"][f"{name}_binary"] == sha(HERE / name)
    assert protocol["source_sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    assert load(HERE / "sage_runtime_info.json")["status"] == "verified"
    prior_sage = load(PRIOR / "sage_audit.json")
    assert prior_sage["status"] == "PASS_INDEPENDENT_SAGE_FOUR_ATOM_NATIVE_ORACLE"
    assert result["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["source_sha256"]["prior_sage_audit"] == sha(PRIOR / "sage_audit.json")
    assert len(protocol["run_order"]) == len(result["run_order"]) == 8
    assert protocol["workers"] == 1 and protocol["rss_cap_bytes"] == 4 * 1024**3
    assert protocol["source_dimension"] == 14 and protocol["product_states"] == 8192
    n41 = {}
    for case in ("positive", "control"):
        for variant in ("baseline", "batch"):
            path = HERE / f"n41_{variant}_{case}.json"
            assert protocol["source_sha256"][f"n41_{variant}_{case}"] == sha(path)
            n41[(variant, case)] = load(path)
        assert core(n41[("baseline", case)]) == core(n41[("batch", case)])
        assert len(n41[("batch", case)]["hits"]) == (2 if case == "positive" else 0)
        assert n41[("batch", case)]["field_inverse_calls"] == 1
    query_rows = []
    for index, specification in enumerate(protocol["run_order"]):
        variant, case, repetition = (specification[key] for key in
                                     ("variant", "case", "repetition"))
        label = f"{variant}_{case}_r{repetition}"
        run_dir = HERE / "runs" / label
        receipt = load(run_dir / "receipt.json")
        producer = load(run_dir / "producer.json")
        prior_case = "positive" if case == "positive" else "trace_zero_control"
        input_path = PRIOR / f"native_n131_{prior_case}.txt"
        prior_result = load(PRIOR / f"native_run_n131_{prior_case}" / "result.json")
        assert core(producer) == core(prior_result)
        assert receipt["status"] == producer["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        assert receipt["variant"] == variant and receipt["case"] == case
        assert receipt["repetition"] == repetition and receipt["exit_code"] == 0
        assert receipt["stop_reason"] is None
        assert receipt["parent_wall_ns"] < protocol["parent_cap_seconds_per_run"] * 10**9
        assert receipt["sampled_peak_rss_bytes"] < protocol["rss_cap_bytes"]
        assert receipt["source_sha256"] == {
            "protocol": sha(HERE / "protocol.json"),
            "input": sha(input_path), "binary": sha(HERE / variant),
            "stdout": sha(run_dir / "stdout.txt"),
            "stderr": sha(run_dir / "stderr.txt"),
            "producer": sha(run_dir / "producer.json"),
        }
        assert producer["total_product_states"] == producer["processed_product_states"] == 8192
        if variant == "batch":
            assert producer["evaluated_product_states"] == 8192
            assert producer["nonconstant_resultants"] == 8192
            assert producer["field_inverse_calls"] == 1
            total_phases = sum(producer[key] for key in
                               ("phase_evaluate_ns", "phase_batch_inverse_ns", "phase_gcd_ns"))
            assert abs(total_phases - producer["query_ns"]) < 1000000
        assert result["run_order"][index] == {
            "label": label, "status": "COMPLETE_ALGEBRAIC_SCAN",
            "query_ns": producer["query_ns"], "hits": len(producer["hits"]),
            "wall_ns": receipt["parent_wall_ns"],
        }
        query_rows.append({"label": label, "query_ns": producer["query_ns"],
                           "parent_wall_ns": receipt["parent_wall_ns"],
                           "peak_rss_bytes": receipt["sampled_peak_rss_bytes"]})
    receipt = {
        "status": "PASS_INDEPENDENT_MATCHED_FOUR_ATOM_BATCH_AUDIT",
        "exact_n41_controls": 4,
        "exact_n131_runs": 8,
        "per_resultant_field_inversions": 8192,
        "batch_field_inversions": 1,
        "query_rows": query_rows,
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "result": sha(HERE / "result.json"),
                          "prior_sage_audit": sha(PRIOR / "sage_audit.json"),
                          "script": sha(__file__)},
    }
    with (HERE / "audit.json").open("x") as sink:
        json.dump(receipt, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps({"status": receipt["status"], "n131_runs": len(query_rows)}))


if __name__ == "__main__":
    main()
