#!/usr/bin/env python3
"""Freeze and measure a larger same-point N83 native quotient-pair screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
BUILD = Path("/private/tmp/q1445build")
BINARY = BUILD / "native_q1400_pair_comparator"
BASE = BUILD / "n83_q1325_pair_base.bin"
FREEZE = HERE / "freeze.json"
RESULTS = HERE / "measurements.json"
SOURCES = [
    "experiments/compact-s3-m4-20261003/native_q1400_pair_comparator.cpp",
    "experiments/koblitz-pair-claw-20260929/native_n83_bloom_core.hpp",
    "experiments/koblitz-pair-claw-20260929/native_n83_pairs.cpp",
    "ecc2k130/runner/generated/eccF83.h",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed_inputs() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    q1400 = json.loads((PARENT / "q1400_pair_protocol.json").read_text())
    inputs = json.loads((PARENT / "native_inputs/n83_q1400_pair_manifest.json").read_text())
    assert protocol["proposal_id"] == "Q1445"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["curve_id"] == q1400["curve_id"] == inputs["curve_id"]
    assert protocol["workload_id"] == q1400["workload_id"] == inputs["workload_id"]
    assert protocol["isogeny"] == q1400["isogeny"] == "none"
    assert protocol["factor_base_actual_B"] == q1400["factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == q1400["factor_base_folded_columns_K"]
    assert protocol["factor_base_enumerated_set_sha256"] == q1400[
        "factor_base_enumerated_set_sha256"]
    assert sha(BASE) == inputs["base_binary_sha256"]
    assert sha(ROOT / "experiments/compact-s3-m4-20261003/bases/n83_weight5_full_point_orbits.bin") == protocol[
        "factor_base_enumerated_set_sha256"]
    for name in SOURCES:
        assert sha(BUILD / name) == sha(ROOT / name) if (ROOT / name).exists() else True
    assert sha(BUILD / SOURCES[0]) == q1400["point_decomposition"]["native_source_sha256"]
    for name, digest in q1400["point_decomposition"]["native_dependency_sha256"].items():
        assert sha(BUILD / name) == digest
    return {
        "protocol_sha256": sha(HERE / "protocol.json"),
        "q1400_protocol_sha256": sha(PARENT / "q1400_pair_protocol.json"),
        "input_manifest_sha256": sha(PARENT / "native_inputs/n83_q1400_pair_manifest.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "base_sha256": sha(BASE),
        "base_bytes": BASE.stat().st_size,
        "binary_sha256": sha(BINARY),
        "source_sha256": {name: sha(BUILD / name) for name in SOURCES},
        "public_target_onb_hex": inputs["ordinary_public_target_onb_hex"],
    }


def command(table: int, protocol: dict, frozen: dict) -> list[str]:
    p = protocol["point_decomposition"]
    return [str(BINARY), str(BASE), *frozen["public_target_onb_hex"],
            str(table), str(p["query_representatives"]),
            str(p["table_batch"]), str(p["table_step"]),
            str(p["table_offset"]), str(p["query_step"]),
            str(p["query_offset"]), str(p["bloom_bits_per_key"]),
            str(p["bloom_hashes"]), str(p["table_start"]),
            str(p["query_start"]), str(p["query_workers"]),
            str(p["representative_batch"])]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        assert not FREEZE.exists()
        FREEZE.write_text(json.dumps(fixed_inputs(), indent=2, sort_keys=True) + "\n")
        print(f"FROZEN {FREEZE}")
        return
    assert args.run
    assert not RESULTS.exists()
    frozen = json.loads(FREEZE.read_text())
    assert frozen == fixed_inputs()
    protocol = json.loads((HERE / "protocol.json").read_text())
    p = protocol["point_decomposition"]
    rows = []
    for table in p["table_descriptors"]:
        argv = command(table, protocol, frozen)
        start = time.perf_counter_ns()
        try:
            result = subprocess.run(argv, capture_output=True, text=True,
                                    timeout=protocol["limits"]["per_run_wall_seconds"],
                                    check=False)
            stdout, stderr, code, timed_out = (result.stdout, result.stderr,
                                               result.returncode, False)
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode(errors="replace")
            stderr = (error.stderr or b"").decode(errors="replace")
            code, timed_out = None, True
        elapsed_ns = time.perf_counter_ns() - start
        out = HERE / f"table_{table}.stdout.json"
        err = HERE / f"table_{table}.stderr.txt"
        out.write_text(stdout)
        err.write_text(stderr)
        native = json.loads(stdout) if code == 0 else None
        if native is not None:
            assert native["actual_B"] == protocol["factor_base_actual_B"]
            assert native["table_descriptors"] == table
            assert native["query_representatives"] == p["query_representatives"]
            assert native["lifted_query_pairs"] == p["query_representatives"] * 2 * protocol["field_degree"]
        status = "timeout" if timed_out else "native_error" if code else (
            "rss_cap_exceeded" if native["peak_rss_bytes"] >
            protocol["limits"]["peak_rss_mib"] * 1048576 else
            "exact_hit_pending_independent_replay" if native["exact_hit_keys"] else
            "no_exact_hit_at_cap")
        rows.append({
            "table_descriptors": table,
            "status": status,
            "returncode": code,
            "process_wall_ns": elapsed_ns,
            "stdout_sha256": sha(out),
            "stderr_sha256": sha(err),
            "argv": argv,
            "native": native,
            "charged_table_pair_sums": table if native else None,
            "charged_query_representative_pair_sums": p["query_representatives"] if native else None,
            "charged_target_signed_x_complements": 2 * protocol["field_degree"] * p["query_representatives"] if native else None,
            "charged_exact_replay_table_pair_sums": table if native and native["bloom_positive_queries"] else 0 if native else None,
        })
        print(json.dumps({"table": table, "status": status,
                          "hits": native["exact_hit_keys"] if native else None,
                          "wall_seconds": elapsed_ns / 1e9}), flush=True)
    RESULTS.write_text(json.dumps({
        "kind": "q1445_n83_matched_pair_budget_screen",
        "proposal_id": "Q1445",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
        "freeze_sha256": sha(FREEZE),
        "runner_sha256": sha(Path(__file__)),
        "rows": rows,
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
