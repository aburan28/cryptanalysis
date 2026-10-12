#!/usr/bin/env python3
"""Freeze and measure the high-density Bloom cell on Q1445's same point."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_pair_budget_screen"
sys.path.insert(0, str(PRIOR))
from run import BASE, BINARY, command, fixed_inputs  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_record() -> dict:
    prior = json.loads((PRIOR / "measurements.json").read_text())
    parent = json.loads((PRIOR / "protocol.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["curve_id"] == parent["curve_id"] == prior["curve_id"]
    assert protocol["workload_id"] == parent["workload_id"] == prior["workload_id"]
    assert protocol["factor_base_enumerated_set_sha256"] == parent[
        "factor_base_enumerated_set_sha256"]
    assert protocol["point_decomposition"]["table_descriptors"] == 8000000
    assert protocol["point_decomposition"]["query_representatives"] == parent[
        "point_decomposition"]["query_representatives"]
    assert sha(BINARY) == fixed_inputs()["binary_sha256"]
    assert sha(BASE) == fixed_inputs()["base_sha256"]
    return {
        "protocol_sha256": sha(HERE / "protocol.json"),
        "parent_protocol_sha256": sha(PRIOR / "protocol.json"),
        "parent_measurements_sha256": sha(PRIOR / "measurements.json"),
        "parent_freeze_sha256": sha(PRIOR / "freeze.json"),
        "binary_sha256": sha(BINARY),
        "base_sha256": sha(BASE),
        "public_target_onb_hex": fixed_inputs()["public_target_onb_hex"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    freeze_path = HERE / "freeze.json"
    result_path = HERE / "measurement.json"
    if args.freeze:
        assert not freeze_path.exists()
        freeze_path.write_text(json.dumps(frozen_record(), indent=2, sort_keys=True) + "\n")
        print(f"FROZEN {freeze_path}")
        return
    assert args.run and not result_path.exists()
    freeze = json.loads(freeze_path.read_text())
    assert freeze == frozen_record()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent = json.loads((PRIOR / "protocol.json").read_text())
    p = protocol["point_decomposition"]
    argv = command(p["table_descriptors"], parent, freeze)
    argv[11] = str(p["bloom_bits_per_key"])
    argv[12] = str(p["bloom_hashes"])
    start = time.perf_counter_ns()
    try:
        done = subprocess.run(argv, capture_output=True, text=True,
                              timeout=protocol["limits"]["external_wall_seconds"],
                              check=False)
        stdout, stderr, code, timeout = done.stdout, done.stderr, done.returncode, False
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        code, timeout = None, True
    elapsed = time.perf_counter_ns() - start
    out = HERE / "native.stdout.json"
    err = HERE / "native.stderr.txt"
    out.write_text(stdout)
    err.write_text(stderr)
    native = json.loads(stdout) if code == 0 else None
    status = "timeout" if timeout else "native_error" if code else (
        "rss_cap_exceeded" if native["peak_rss_bytes"] >
        protocol["limits"]["peak_rss_mib"] * 1048576 else
        "exact_hit_pending_independent_replay" if native["exact_hit_keys"] else
        "no_exact_hit_at_cap")
    record = {
        "proposal_id": "Q1446",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "isogeny": "none",
        "status": status,
        "argv": argv,
        "process_wall_ns": elapsed,
        "returncode": code,
        "freeze_sha256": sha(freeze_path),
        "runner_sha256": sha(Path(__file__)),
        "stdout_sha256": sha(out),
        "stderr_sha256": sha(err),
        "native": native,
        "charged_table_pair_sums": p["table_descriptors"] if native else None,
        "charged_query_representative_pair_sums": p["query_representatives"] if native else None,
        "charged_target_signed_x_complements": 2 * 83 * p["query_representatives"] if native else None,
        "charged_exact_replay_table_pair_sums": p["table_descriptors"] if native and native["bloom_positive_queries"] else 0 if native else None,
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    result_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "hits": native["exact_hit_keys"] if native else None,
                      "bloom_positives": native["bloom_positive_queries"] if native else None,
                      "wall_seconds": elapsed / 1e9}))


if __name__ == "__main__":
    main()
