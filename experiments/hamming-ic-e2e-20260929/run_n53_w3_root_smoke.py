#!/usr/bin/env python3
"""Bounded one-target smoke for the exact W3-base four-summand root index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import time

from n53_group import TARGET

HERE = Path(__file__).resolve().parent
CRYPTO = Path("/Volumes/SSD990/crypto")
EXAMPLE = HERE / "koblitz_w3_root_index.rs"
COMPILED_EXAMPLE = CRYPTO / "examples/koblitz_w3_root_index.rs"
BINARY = CRYPTO / "target/release/examples/koblitz_w3_root_index"
REPS = HERE / "runs/n53_w3_base_export_v1/representatives.json"
GEOMETRY = HERE / "runs/n53_weight3_geometry_v1/receipt.json"
SOURCE_PATHS = (
    CRYPTO / "Cargo.lock",
    CRYPTO / "src/cryptanalysis/koblitz_fast_arith.rs",
    CRYPTO / "src/cryptanalysis/koblitz_index_calculus.rs",
    CRYPTO / "src/cryptanalysis/semaev_decomp.rs",
    CRYPTO / "src/binary_ecc.rs",
    CRYPTO / "src/lib.rs",
)
KNOWN_SCALAR_VALIDATION_ONLY = 596471236405


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wall-seconds", type=int, default=120)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.wall_seconds < 1 or args.workers < 1:
        raise ValueError("limits must be positive")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("smoke output is immutable")
    assert sha(EXAMPLE) == sha(COMPILED_EXAMPLE)
    geometry = json.loads(GEOMETRY.read_text())
    reps = json.loads(REPS.read_text())
    assert len(reps["representatives"]) == geometry["effective_signed_frobenius_columns"] == 221
    out.mkdir(parents=True)
    target_path = out / "target_point.json"
    target_path.write_text(json.dumps(list(TARGET), separators=(",", ":")) + "\n")
    result_path = out / "ic_result.jsonl"
    cmd = [str(BINARY), "53", "0", "221", "53012",
           str(target_path), str(result_path), str(args.workers), str(REPS)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter_ns()
    timed_out = False
    with (out / "solver.stdout.txt").open("wb") as stdout, \
         (out / "solver.stderr.txt").open("wb") as stderr:
        proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, cwd=CRYPTO)
        launch_end = time.perf_counter_ns()
        try:
            code = proc.wait(timeout=args.wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            code = proc.wait()
    ended = time.perf_counter_ns()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    lines = result_path.read_text().splitlines() if result_path.exists() else []
    result = json.loads(lines[0]) if len(lines) == 1 else None
    bindings_valid = result is not None and result.get("target") == list(TARGET) \
        and result.get("factor_base_points") == 23426 \
        and result.get("orbit_columns") == 221 \
        and result.get("factor_base_source") == "frozen_weight3_projected_representatives_json"
    if timed_out:
        status = "EXTERNAL_TIMEOUT"
    elif code != 0:
        status = "PROCESS_FAILURE"
    elif result is None:
        status = "NO_RESULT_RECORD"
    elif bindings_valid and result.get("group_verified") is True \
            and result.get("recovered_scalar") == KNOWN_SCALAR_VALIDATION_ONLY:
        status = "IN_PROCESS_SCALAR_REPLAY_PASS"
    else:
        status = "UNVERIFIED_OR_UNSOLVED"
    source_hashes = {str(path): sha(path) for path in SOURCE_PATHS if path.is_file()}
    report = {
        "kind": "n53_weight3_root_index_one_target_smoke",
        "status": status, "candidate_id": None, "run_id": None,
        "target": list(TARGET), "target_count": 1,
        "curve_id": geometry["curve_id"],
        "factor_base": {"actual_usable_points": geometry["actual_usable_projected_points"],
                        "effective_columns": geometry["effective_signed_frobenius_columns"],
                        "projected_set_sha256": geometry["projected_set_sha256"]},
        "command": cmd, "workers": args.workers,
        "external_wall_limit_seconds": args.wall_seconds,
        "memory_limit_bytes": None,
        "exit_code": code, "external_timeout": timed_out,
        "process_launch_ns": launch_end - started,
        "process_wall_ns": ended - launch_end,
        "peak_child_rss": after.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin" else "kilobytes",
        "child_user_cpu_s": after.ru_utime - before.ru_utime,
        "child_system_cpu_s": after.ru_stime - before.ru_stime,
        "output_records": len(lines),
        "output_bindings_valid": bindings_valid,
        "in_process_group_verified": None if result is None else result.get("group_verified"),
        "recovered_matches_fixture_scalar": None if result is None else
             result.get("recovered_scalar") == KNOWN_SCALAR_VALIDATION_ONLY,
        "result_sha256": sha(result_path) if result_path.exists() else None,
        "stdout_sha256": sha(out / "solver.stdout.txt"),
        "stderr_sha256": sha(out / "solver.stderr.txt"),
        "target_sha256": sha(target_path),
        "representatives_sha256": sha(REPS),
        "example_source_sha256": sha(EXAMPLE),
        "binary_sha256": sha(BINARY),
        "relevant_crypto_source_sha256": source_hashes,
        "runner_source_sha256": sha(Path(__file__)),
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version()},
        "claim_boundary": "One bounded root-index stage smoke. Any in-process success still needs independent Sage replay and paired one-target rho before an IC speedup claim."
    }
    (out / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "exit_code", "external_timeout", "process_wall_ns",
                       "peak_child_rss", "output_records", "in_process_group_verified")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
