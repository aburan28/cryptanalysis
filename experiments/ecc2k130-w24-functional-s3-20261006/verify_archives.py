#!/usr/bin/env python3
"""Audit archived W24 functional-S3 profile, invalid attempt, and strict run."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def digest_gzip(path):
    h = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def read(path):
    return json.loads(path.read_text())


def reconstruct_initial_run_source():
    current = (HERE / "run.py").read_text()
    fixed = '''                    except (RuntimeError, subprocess.TimeoutExpired,
                            OSError) as monitor_error:
                        stop_reason = "memory_monitor_failure"
                        report["memory_monitor_error_type"] = type(monitor_error).__name__
                        report["memory_monitor_error"] = str(monitor_error)
                        process.kill()
                        break
'''
    original = '''                    except (RuntimeError, subprocess.TimeoutExpired):
                        stop_reason = "memory_monitor_failure"
                        process.kill()
                        break
'''
    assert current.count(fixed) == 1
    return current.replace(fixed, original).encode()


def main():
    config = read(HERE / "CONFIG.json")
    profile = read(RUNS / "profile" / "receipt.json")
    failure = read(RUNS / "monitor-denied" / "attempt.json")
    strict = read(RUNS / "planted" / "receipt.json")
    replay = read(RUNS / "planted" / "sage_replay.json")
    assert profile["status"] == "profile_only" and profile["model"] is None
    assert failure["status"] == "excluded_memory_monitor_permission_error"
    assert failure["valid_bounded_comparison"] is False
    assert failure["monitor_error_type"] == "PermissionError"
    assert failure["solver_status_in_raw_output"] == "INDETERMINATE"
    assert strict["status"] == "timeout" and strict["model"] is None
    assert strict["solver_status"] is None and strict["solver_exit_code"] == -9
    assert strict["solver_peak_rss_bytes"] < config["peak_rss_limit_bytes"]
    assert strict["solver_command"][1:5] == ["--maxtime=30",
                                                 "--maxconfl=100000",
                                                 "--threads=1", "--random=0"]
    assert replay["status"] == "NO_MODEL_REPLAYED"
    assert replay["receipt_sha256"] == digest(RUNS / "planted" / "receipt.json")
    assert replay["source_sha256"] == digest(HERE / "replay_sage.py")

    initial_run_hash = digest_bytes(reconstruct_initial_run_source())
    assert initial_run_hash == profile["source_sha256"]["run.py"]
    assert initial_run_hash == failure["source_sha256"]["run.py"]
    assert strict["source_sha256"]["run.py"] == digest(HERE / "run.py")
    for name in ("functional.py", "selftest.py", "replay_sage.py"):
        actual = digest(HERE / name)
        assert profile["source_sha256"][name] == actual
        assert failure["source_sha256"][name] == actual
        assert strict["source_sha256"][name] == actual
    for run, record in (("profile", profile), ("monitor-denied", failure),
                        ("planted", strict)):
        run_dir = RUNS / run
        assert record["config_sha256"] == digest(HERE / "CONFIG.json")
        assert record["sage_runtime_info_sha256"] == digest(
            run_dir / "runtime-info.json")
        formula_hash, formula_size = digest_gzip(run_dir / "system.xcnf.gz")
        assert formula_hash == record["xcnf_sha256"]
        assert formula_size == record["xcnf_bytes"]
        if run != "profile":
            for name in ("solver.stdout.txt", "solver.stderr.txt"):
                actual, _ = digest_gzip(run_dir / (name + ".gz"))
                stream_name = name.split(".")[1]
                assert actual == record[f"solver_{stream_name}_sha256"]
    assert len({profile["xcnf_sha256"], failure["xcnf_sha256"],
                strict["xcnf_sha256"]}) == 1
    assert strict["solver_binary_sha256"] == config["solver_binary_sha256"]
    witness_dir = RUNS / "witness"
    witness = read(witness_dir / "receipt.json")
    xcnf_check = read(witness_dir / "verification.json")
    group_check = read(witness_dir / "sage_group_replay.json")
    assert witness["xcnf_sha256"] == strict["xcnf_sha256"]
    assert witness["packed_assignment_sha256"] == digest(
        witness_dir / "assignment.bin.gz")
    assert witness["sage_runtime_info_sha256"] == digest(
        witness_dir / "runtime-info.json")
    for name, expected in witness["source_sha256"].items():
        assert digest(HERE / name) == expected
    assert xcnf_check["status"] == "PASS_XCNF_WITNESS"
    assert xcnf_check["violations"] == 0
    assert xcnf_check["witness_receipt_sha256"] == digest(
        witness_dir / "receipt.json")
    assert xcnf_check["verifier_sha256"] == digest(HERE / "verify_witness.py")
    assert group_check["status"] == "PASS_PLANTED_GROUP_WITNESS"
    assert group_check["witness_receipt_sha256"] == digest(
        witness_dir / "receipt.json")
    assert group_check["xcnf_verification_sha256"] == digest(
        witness_dir / "verification.json")
    assert group_check["source_sha256"] == digest(HERE / "witness_sage.py")
    published = read(HERE / "RESULT.json")
    assert published["status"] == "planted_satisfiable_but_bounded_solver_timeout"
    assert published["candidate_id"] is None
    assert published["ordinary_target_attempted"] is False
    assert published["profile"]["xcnf_sha256"] == strict["xcnf_sha256"]
    assert published["strict_planted_control"]["status"] == strict["status"]
    assert published["witness"]["violations"] == 0
    assert published["witness"]["xcnf_check_status"] == xcnf_check["status"]
    assert published["witness"]["sage_group_status"] == group_check["status"]
    assert published["verified_logarithm"] is None
    assert published["rho_ratio"] is None
    result = {"schema": "ecc2k130-w24-functional-s3-archive-audit-v2",
              "status": "PASS",
              "xcnf_sha256": strict["xcnf_sha256"],
              "profile_variables": profile["variables"],
              "strict_status": strict["status"],
              "strict_sage_status": replay["status"],
              "xcnf_witness_status": xcnf_check["status"],
              "group_witness_status": group_check["status"],
              "invalid_attempt_preserved": True,
              "initial_source_reconstructed": True,
              "candidate_id": None}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
