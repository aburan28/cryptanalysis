#!/usr/bin/env sage -python
"""Measured N131 S3 inverse join over the complete fixed-seed W15 domains."""

import hashlib
import json
import time
import traceback
from pathlib import Path

import psutil
from sage.all import GF, PolynomialRing

from sage_audit import encode, right_roots

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    with path.open("x") as out:
        json.dump(data, out, sort_keys=True, indent=2)
        out.write("\n")


def sources():
    return {"query": HERE / "sage_query.py",
            "freezer": HERE / "freeze_sage_query.py",
            "sage_kernel": HERE / "sage_audit.py",
            "source_protocol": HERE / "protocol.json",
            "source_result": HERE / "result.json",
            "independent_audit": HERE / "sage_audit.json",
            "pair_roots": BASE / "pair_roots.json",
            "sage_runtime": HERE / "sage_runtime_info.json"}


def main():
    protocol = json.loads((HERE / "sage_query_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_W15_S3_SAGE_QUERY"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert not (HERE / "sage_query_result.json").exists()
    source = json.loads((HERE / "result.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    assert source["status"] == "COMPLETE"
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_W15_S3_JOIN_AUDIT"
    assert audit["sha256"]["producer_result"] == sha(HERE / "result.json")
    setup_started = time.monotonic_ns()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "z", modulus=t**131+t**13+t**2+t+1)
    roots = json.loads((BASE / "pair_roots.json").read_text())
    left = {value for row in roots["pair_rows"][0]["pairs"] for value in row[2:]}
    right = {value for row in roots["pair_rows"][1]["pairs"] for value in row[2:]}
    assert [len(left), len(right)] == [8176, 8340]
    right_field = {field.from_integer(value) for value in right}
    left_field = [field.from_integer(value) for value in sorted(left)]
    setup_ns = time.monotonic_ns()-setup_started
    process = psutil.Process()
    peak = process.memory_info().rss
    cases = []
    for source_case in source["cases"]:
        q = field.from_integer(source_case["target_reciprocal"])
        started = time.monotonic_ns()
        hits = set()
        checked = 0
        status = "COMPLETE"
        for c in left_field:
            if checked % 128 == 0:
                peak = max(peak, process.memory_info().rss)
                if peak >= protocol["rss_cap_bytes"]:
                    status = "OOM"
                    break
                if time.monotonic_ns()-started >= protocol["per_query_cap_seconds"]*10**9:
                    status = "CENSORED_TIME"
                    break
            checked += 1
            for d in right_roots(c, q, field):
                if d in right_field:
                    hits.add((encode(c), encode(d)))
        query_ns = time.monotonic_ns()-started
        replay_start = time.monotonic_ns()
        expected = {(row["left_output"], row["right_output"])
                    for row in source_case["algebraic_hits"]}
        if status == "COMPLETE":
            assert checked == len(left) and hits == expected
        replay_ns = time.monotonic_ns()-replay_start
        cases.append({"name": source_case["name"], "status": status,
                      "target_reciprocal": source_case["target_reciprocal"],
                      "left_outputs_checked": checked,
                      "left_outputs_total": len(left),
                      "algebraic_hit_coordinate_pairs": sorted(hits),
                      "query_ns": query_ns,
                      "post_query_replay_ns": replay_ns,
                      "peak_process_rss_bytes": peak})
        print(json.dumps({"name": source_case["name"], "status": status,
                          "query_seconds": query_ns/1e9, "hits": len(hits)}), flush=True)
    status = ("OOM" if any(case["status"] == "OOM" for case in cases)
              else "COMPLETE" if all(case["status"] == "COMPLETE" for case in cases)
              else "CENSORED_TIME")
    receipt = {"status": status, "candidate_id": None,
               "curve_id": protocol["curve_id"], "target_count": 1,
               "domain_sizes": [len(left), len(right)],
               "reusable_setup_ns": setup_ns,
               "cases": cases, "peak_process_rss_bytes": peak,
               "sha256": {"protocol": sha(HERE / "sage_query_protocol.json"),
                          "source_result": sha(HERE / "result.json"),
                          "independent_audit": sha(HERE / "sage_audit.json"),
                          "query_source": sha(Path(__file__))}}
    save(HERE / "sage_query_result.json", receipt)
    print(json.dumps({"status": status, "setup_seconds": setup_ns/1e9,
                      "peak_rss_bytes": peak}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        save(HERE / "sage_query_failure.json",
             {"status": "PRODUCER_FAILURE", "traceback": traceback.format_exc()})
        raise
