#!/usr/bin/env python3
"""Read-only provenance audit of the bounded W24/m5 SAT attempt."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def load(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("verification output already exists")
    config = load(HERE / "CONFIG.json")
    seed = EXPERIMENTS / "ecc2k130-orbit-closed-w24-seed-20261006/runs/R1/result.json"
    normal = EXPERIMENTS / "ecc2k130-w24-normal-barrel-20261006/runs/R2/result.json"
    workload = EXPERIMENTS / "ecc2k130-263-equal-w24-workload-20261005/primary_workload.json"
    check(digest(seed) == config["parent_seed_result_sha256"], "seed parent changed")
    check(digest(normal) == config["parent_normal_result_sha256"], "normal parent changed")
    check(digest(workload) == config["ordinary_primary_workload_sha256"],
          "ordinary workload changed")
    check(digest(HERE / "arithmetic.py") == config["parent_sat_arithmetic_sha256"],
          "arithmetic copy changed")
    check(digest(HERE / "xor_circuit.py") == config["parent_sat_xor_circuit_sha256"],
          "XCNF circuit copy changed")

    failed = HERE / "runs/monitor-denied"
    invalid = load(failed / "attempt.json")
    check(invalid["status"] == "invalid_memory_monitor_sandbox_denial" and
          not invalid["admitted_bounded_planted_result"], "first attempt not excluded")
    check(digest(failed / "runtime-info.json") == invalid["sage_runtime_info_sha256"],
          "invalid attempt runtime changed")
    for basename in ("system.xcnf", "solver.stdout.txt"):
        compressed = failed / (basename + ".gz")
        compressed_key = ("system_xcnf_compressed_sha256" if basename == "system.xcnf"
                          else "solver_stdout_compressed_sha256")
        check(digest(compressed) == invalid[compressed_key],
              "invalid attempt compressed artifact changed")
        raw_hash = hashlib.sha256(gzip.decompress(compressed.read_bytes())).hexdigest()
        key = ("system_xcnf_uncompressed_sha256" if basename == "system.xcnf"
               else "solver_stdout_sha256")
        check(raw_hash == invalid[key], f"invalid attempt {basename} raw hash")

    strict_dir = HERE / "runs/planted-r2"
    strict_path = strict_dir / "receipt.json"
    strict = load(strict_path)
    archive = load(strict_dir / "archive.json")
    check(strict["config_sha256"] == digest(HERE / "CONFIG.json"),
          "strict protocol mismatch")
    for name, expected in strict["source_sha256"].items():
        check(digest(HERE / name) == expected, f"strict source changed: {name}")
    check(strict["status"] == "unresolved" and strict["solver_status"] == "INDETERMINATE"
          and strict["solver_exit_code"] == 15 and strict["model"] is None,
          "strict SAT outcome changed")
    check(strict["monitor_error"] is None and strict["solver_peak_rss_bytes"] > 0,
          "valid attempt lacks working RSS monitor")
    check(strict["ordinary_workload_id"] is None and
          strict["target_online_ms"] is None, "unrun target metric populated")
    check(digest(strict_dir / "runtime-info.json") == strict["sage_runtime_info_sha256"],
          "strict runtime changed")
    for basename, hashes in archive["files"].items():
        compressed = strict_dir / (basename + ".gz")
        check(digest(compressed) == hashes["gzip_sha256"],
              f"strict {basename} compressed hash")
        raw = gzip.decompress(compressed.read_bytes())
        check(len(raw) == hashes["raw_bytes"] and
              hashlib.sha256(raw).hexdigest() == hashes["raw_sha256"],
              f"strict {basename} expanded hash")
    check(archive["files"]["system.xcnf"]["raw_sha256"] == strict["xcnf_sha256"],
          "strict formula hash")
    check(archive["files"]["solver.stdout.txt"]["raw_sha256"] ==
          strict["solver_stdout_sha256"], "strict solver stream hash")
    sage = load(strict_dir / "sage_replay.json")
    check(sage["status"] == "PASS_PLANTED_GEOMETRY_NO_SOLVER_WITNESS" and
          sage["strict_result_sha256"] == digest(strict_path),
          "Sage geometry replay changed")
    check(sage["verifier_source_sha256"] == digest(HERE / "verify_sage.py"),
          "Sage verifier source changed")

    witness_dir = HERE / "runs/witness-r2"
    witness_path = witness_dir / "receipt.json"
    witness = load(witness_path)
    packed = witness_dir / "assignment.bin.gz"
    check(witness["strict_result_sha256"] == digest(strict_path) and
          witness["xcnf_sha256"] == strict["xcnf_sha256"],
          "witness not bound to strict formula")
    check(digest(packed) == witness["compressed_assignment_sha256"] and
          hashlib.sha256(gzip.decompress(packed.read_bytes())).hexdigest() ==
          witness["raw_assignment_sha256"], "witness assignment changed")
    for name, expected in witness["source_sha256"].items():
        check(digest(HERE / name) == expected, f"witness source changed: {name}")
    verification = load(witness_dir / "verification-archived.json")
    check(verification["status"] == "PASS_KNOWN_PLANTED_XCNF_ASSIGNMENT" and
          verification["violations"] == 0 and
          verification["xcnf_sha256"] == strict["xcnf_sha256"],
          "independent XCNF certificate changed")
    check(verification["verifier_source_sha256"] == digest(HERE / "verify_xcnf.py"),
          "XCNF verifier source changed")
    mutation = load(witness_dir / "mutation.json")
    check(mutation["status"] == "PASS_MUTATED_SELECTOR_REJECTED" and
          mutation["violations"] > 0 and mutation["verifier_exit_code"] != 0,
          "negative control failed")
    check(mutation["verifier_source_sha256"] == digest(HERE / "verify_xcnf.py"),
          "mutation verifier source changed")

    report = {
        "schema": "ecc2k130-orbit-w24-m5-sat-archive-verification-v1",
        "status": "PASS_ARCHIVED_BOUND_SEARCH_AND_WITNESS",
        "candidate_id": None,
        "config_sha256": digest(HERE / "CONFIG.json"),
        "invalid_attempt_sha256": digest(failed / "attempt.json"),
        "strict_result_sha256": digest(strict_path),
        "strict_xcnf_sha256": strict["xcnf_sha256"],
        "sage_replay_sha256": digest(strict_dir / "sage_replay.json"),
        "xcnf_verification_sha256": digest(witness_dir / "verification-archived.json"),
        "mutation_sha256": digest(witness_dir / "mutation.json"),
        "verifier_source_sha256": digest(Path(__file__)),
        "unknown_witness_recovered": False,
        "ordinary_target_attempted": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
