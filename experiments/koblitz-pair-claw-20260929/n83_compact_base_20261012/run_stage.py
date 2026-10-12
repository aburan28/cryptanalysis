#!/usr/bin/env python3
"""Check compact-base native parity on the fresh N83 M20/R18 workload."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
ROOT = PAIR.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
sys.path[:0] = [str(CODEGEN), str(HERE)]

import field  # noqa: E402
from generate import generate  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--audit", action="store_true",
                        help="check every expanded point against field squaring and sign")
    args = parser.parse_args()
    assert args.attempt >= 1
    assert platform.machine().lower() in ("arm64", "aarch64")
    stem = "" if args.attempt == 1 else f"_attempt{args.attempt}"
    result_path = HERE / f"candidate_result{stem}.json"
    receipt_path = HERE / f"stage_receipt{stem}.json"
    assert not result_path.exists() and not receipt_path.exists()
    parent_path = PAIR / "n83_fresh_m32_k23859_20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    reference_path = PAIR / "n83_fresh_m32_k23859_20261012/smoke_attempt3_result.json"
    reference = json.loads(reference_path.read_text())
    key_path = PAIR / "n83_base_size_search_20261012/minimal_base_keys_and_logs.bin"
    assert sha(key_path) == parent["factor_base_file_sha256"]
    onb = field.Onb(83)
    target_xy = [format(onb.toCoords(x), "x")
                 for x in parent["target_public_point_onb_raw"]]
    receipt = {
        "kind": "n83_compact_orbit_base_m20_r18_stage",
        "status": "started",
        "workload_id": parent["workload_id"],
        "parent_protocol_sha256": sha(parent_path),
        "reference_result_sha256": sha(reference_path),
        "base_file_sha256": sha(key_path),
        "compact_source_sha256": sha(HERE / "compact_base.inc"),
        "generator_source_sha256": sha(HERE / "generate.py"),
        "driver_source_sha256": sha(Path(__file__)),
        "timing_tier": "exploratory_local_unisolated",
        "complete_point_audit": args.audit,
    }
    save(receipt_path, receipt)
    with tempfile.TemporaryDirectory(prefix="n83-compact-stage-") as temporary:
        work = Path(temporary)
        generated = work / "generated"
        receipt["generated_source_sha256"] = generate(generated)
        binary = work / "pairclaw_compact"
        command = ["c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
                   "-DECC2K83_FAST_KEYER=1", "-DECC2K83_ORBITS=23859",
                   *(["-DCOMPACT_BASE_AUDIT=1"] if args.audit else []),
                   str(generated / "alt_main.cpp"), "-o", str(binary)]
        compile_result = subprocess.run(command, capture_output=True, text=True,
                                        timeout=300)
        receipt["build_returncode"] = compile_result.returncode
        receipt["build_stderr"] = compile_result.stderr[-4000:]
        if compile_result.returncode != 0:
            receipt["status"] = "build_failure"
            save(receipt_path, receipt)
            return
        receipt["binary_sha256"] = sha(binary)
        workload = parent["workload"]
        native = [str(binary), str(key_path), *target_xy,
                  str(1 << 20), str(1 << 18), str(parent["table_batch"]),
                  str(workload["table_step"]), str(workload["table_offset"]),
                  str(workload["table_step"]), str(workload["query_offset"]),
                  str(workload["bits_per_key"]), str(workload["hashes"]),
                  "0", "0", str(workload["workers"]),
                  str(parent["representative_batch"])]
        receipt["native_arguments_after_base_path"] = native[2:]
        environment = os.environ.copy()
        environment["ECC2K83_CANDIDATE_TMPDIR"] = str(work)
        started = time.perf_counter()
        completed = subprocess.run(native, capture_output=True, text=True,
                                   env=environment, timeout=300)
        receipt["subprocess_wall_seconds"] = time.perf_counter() - started
        receipt["native_returncode"] = completed.returncode
        receipt["native_stderr"] = completed.stderr[-4000:]
        if completed.returncode != 0:
            receipt["status"] = "native_failure"
            receipt["native_stdout_tail"] = completed.stdout[-4000:]
            save(receipt_path, receipt)
            return
        candidate = json.loads(completed.stdout)
        save(result_path, candidate)
        receipt["candidate_result_sha256"] = sha(result_path)
        fields = ["actual_B", "table_descriptors", "query_representatives",
                  "lifted_query_pairs", "bloom_bytes", "bloom_positive_queries",
                  "duplicate_positive_keys", "exact_hit_keys", "exact_hit_queries",
                  "false_positive_queries", "complement_identity_queries", "hits"]
        receipt["parity_fields"] = fields
        receipt["parity_status"] = "PASS" if all(
            candidate[key] == reference[key] for key in fields) else "FAIL"
        receipt["status"] = "completed" if receipt["parity_status"] == "PASS" else (
            "result_mismatch")
    save(receipt_path, receipt)
    print(json.dumps({"status": receipt["status"],
                      "peak_rss_bytes": candidate["peak_rss_bytes"],
                      "reference_peak_rss_bytes": reference["peak_rss_bytes"]}))


if __name__ == "__main__":
    main()
